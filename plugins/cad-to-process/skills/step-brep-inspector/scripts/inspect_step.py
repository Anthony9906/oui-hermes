#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from mdi_common import evidence, finding, new_manifest, write_json


def _enum_name(value: Any, prefix: str) -> str:
    name = str(value).split(".")[-1]
    return name[len(prefix) :].lower() if name.startswith(prefix) else name.lower()


def _point(value: Any) -> list[float]:
    return [float(value.X()), float(value.Y()), float(value.Z())]


def _direction(value: Any) -> list[float]:
    return [float(value.X()), float(value.Y()), float(value.Z())]


def _label_entry(label: Any) -> str:
    for name in ("EntryDumpToString", "Tag"):
        method = getattr(label, name, None)
        if callable(method):
            try:
                return str(method())
            except Exception:
                pass
    return str(label)


def _surface_record(surface: Any) -> dict[str, Any]:
    surface_type = _enum_name(surface.GetType(), "GeomAbs_")
    params: dict[str, Any] = {}
    if surface_type == "plane":
        plane = surface.Plane()
        params = {
            "origin": _point(plane.Location()),
            "axis": _direction(plane.Axis().Direction()),
        }
    elif surface_type == "cylinder":
        cylinder = surface.Cylinder()
        params = {
            "origin": _point(cylinder.Location()),
            "axis": _direction(cylinder.Axis().Direction()),
            "radius": float(cylinder.Radius()),
        }
    elif surface_type == "cone":
        cone = surface.Cone()
        params = {
            "origin": _point(cone.Location()),
            "axis": _direction(cone.Axis().Direction()),
            "semi_angle_rad": float(cone.SemiAngle()),
        }
    elif surface_type == "sphere":
        sphere = surface.Sphere()
        params = {
            "center": _point(sphere.Location()),
            "radius": float(sphere.Radius()),
        }
    elif surface_type == "torus":
        torus = surface.Torus()
        params = {
            "center": _point(torus.Location()),
            "axis": _direction(torus.Axis().Direction()),
            "major_radius": float(torus.MajorRadius()),
            "minor_radius": float(torus.MinorRadius()),
        }
    elif surface_type in {"beziersurface", "bsplinesurface"}:
        params = {
            "u_periodic": bool(surface.IsUPeriodic()),
            "v_periodic": bool(surface.IsVPeriodic()),
        }
    return {"surface_type": surface_type, "params": params}


def _bbox(shape: Any, Bnd_Box: Any, BRepBndLib: Any) -> dict[str, list[float]]:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return {
        "min": [float(xmin), float(ymin), float(zmin)],
        "max": [float(xmax), float(ymax), float(zmax)],
        "size": [
            float(xmax - xmin),
            float(ymax - ymin),
            float(zmax - zmin),
        ],
    }


def _count_shapes(shape: Any, shape_type: Any, TopExp_Explorer: Any) -> int:
    count = 0
    explorer = TopExp_Explorer(shape, shape_type)
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _pmi_counts(doc: Any, XCAFDoc_DocumentTool: Any, TDF_LabelSequence: Any) -> tuple[dict[str, int], list[str]]:
    warnings: list[str] = []
    getter = getattr(XCAFDoc_DocumentTool, "DimTolTool_s", None)
    if not callable(getter):
        return {}, ["OCP binding does not expose XCAFDoc_DocumentTool.DimTolTool_s"]
    try:
        tool = getter(doc.Main())
    except Exception as exc:
        return {}, [f"Failed to initialize XCAF DimTolTool: {exc}"]

    result: dict[str, int] = {}
    for key, method_names in {
        "dimensions": ("GetDimensionLabels",),
        "geometric_tolerances": ("GetGeomToleranceLabels", "GetGeomToleranceLabels_s"),
        "datums": ("GetDatumLabels",),
    }.items():
        sequence = TDF_LabelSequence()
        called = False
        for method_name in method_names:
            method = getattr(tool, method_name, None)
            if callable(method):
                try:
                    method(sequence)
                    called = True
                    break
                except Exception as exc:
                    warnings.append(f"{method_name} failed: {exc}")
        if called:
            result[key] = int(sequence.Length())
        else:
            result[key] = 0
            warnings.append(f"No usable XCAF method for {key}")
    return result, warnings


def inspect(path: Path) -> dict[str, Any]:
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.BRepGProp import BRepGProp
        from OCP.BinXCAFDrivers import BinXCAFDrivers
        from OCP.GProp import GProp_GProps
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.TDF import TDF_LabelSequence
        from OCP.TDocStd import TDocStd_Document
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS
        from OCP.XCAFApp import XCAFApp_Application
        from OCP.XCAFDoc import XCAFDoc_DocumentTool
    except ImportError as exc:
        raise RuntimeError(
            "STEP runtime unavailable. Install requirements-step.txt in an isolated environment."
        ) from exc

    manifest = new_manifest(path, "step", "step-brep-inspector")
    app = XCAFApp_Application.GetApplication_s()
    BinXCAFDrivers.DefineFormat_s(app)
    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    app.NewDocument(TCollection_ExtendedString("BinXCAF"), doc)

    reader = STEPCAFControl_Reader()
    for name in (
        "SetColorMode",
        "SetNameMode",
        "SetMatMode",
        "SetLayerMode",
        "SetSHUOMode",
        "SetGDTMode",
    ):
        method = getattr(reader, name, None)
        if callable(method):
            method(True)
    status = reader.ReadFile(str(path.resolve()))
    if int(status) != int(IFSelect_RetDone):
        raise RuntimeError(f"OCCT failed to read STEP file: status={status}")
    if not reader.Transfer(doc):
        raise RuntimeError("OCCT read the STEP file but failed to transfer it into XCAF")

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = TDF_LabelSequence()
    shape_tool.GetFreeShapes(labels)
    occurrences: list[dict[str, Any]] = []
    analytic_counts: defaultdict[str, int] = defaultdict(int)

    for occurrence_index in range(1, labels.Length() + 1):
        label = labels.Value(occurrence_index)
        shape = shape_tool.GetShape_s(label)
        occurrence_id = f"#o{occurrence_index}"
        faces: list[dict[str, Any]] = []
        edge_faces: defaultdict[int, list[int]] = defaultdict(list)
        face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
        face_index = 0
        while face_explorer.More():
            face_index += 1
            face = TopoDS.Face_s(face_explorer.Current())
            surface = BRepAdaptor_Surface(face)
            record = _surface_record(surface)
            record["selector"] = f"{occurrence_id}.f{face_index}"
            record["ordinal"] = face_index
            analytic_counts[record["surface_type"]] += 1
            face_edge_explorer = TopExp_Explorer(face, TopAbs_EDGE)
            while face_edge_explorer.More():
                edge_faces[hash(face_edge_explorer.Current())].append(face_index)
                face_edge_explorer.Next()
            faces.append(record)
            face_explorer.Next()

        edges: list[dict[str, Any]] = []
        edge_explorer = TopExp_Explorer(shape, TopAbs_EDGE)
        edge_index = 0
        while edge_explorer.More():
            edge_index += 1
            edge = edge_explorer.Current()
            edges.append(
                {
                    "selector": f"{occurrence_id}.e{edge_index}",
                    "ordinal": edge_index,
                    "adjacent_face_ordinals": sorted(
                        set(edge_faces.get(hash(edge), []))
                    ),
                }
            )
            edge_explorer.Next()

        props = GProp_GProps()
        try:
            BRepGProp.VolumeProperties_s(shape, props)
            volume = float(props.Mass())
        except Exception:
            volume = None
        occurrences.append(
            {
                "selector": occurrence_id,
                "xcaf_label": _label_entry(label),
                "valid_brep": bool(BRepCheck_Analyzer(shape).IsValid()),
                "bbox": _bbox(shape, Bnd_Box, BRepBndLib),
                "solid_count": _count_shapes(shape, TopAbs_SOLID, TopExp_Explorer),
                "face_count": face_index,
                "edge_count": edge_index,
                "volume": volume,
                "faces": faces,
                "edges": edges,
            }
        )

    pmi_counts, pmi_warnings = _pmi_counts(
        doc, XCAFDoc_DocumentTool, TDF_LabelSequence
    )
    manifest["geometry"] = {
        "occurrence_count": len(occurrences),
        "occurrences": occurrences,
        "surface_type_counts": dict(sorted(analytic_counts.items())),
    }
    manifest["document"]["semantic_pmi_counts"] = pmi_counts
    manifest["evidence"].append(
        evidence(
            "step-transfer",
            state="observed",
            source_ref={"path": str(path.resolve()), "format": "STEP/XCAF"},
            value={
                "occurrence_count": len(occurrences),
                "semantic_pmi_counts": pmi_counts,
            },
        )
    )
    for warning in pmi_warnings:
        manifest["findings"].append(
            finding(
                "PMI_BINDING_OR_EXTRACTION_LIMIT",
                warning,
                severity="warning",
            )
        )
    invalid = [
        item["selector"] for item in occurrences if not item["valid_brep"]
    ]
    if invalid:
        manifest["release"]["decision"] = "blocked"
        manifest["release"]["blockers"].append("invalid_brep")
        manifest["findings"].append(
            finding(
                "INVALID_BREP",
                f"Invalid B-Rep occurrences: {', '.join(invalid)}",
                severity="error",
                refs=invalid,
            )
        )
    elif not any(pmi_counts.values()):
        manifest["release"]["decision"] = "needs_review"
        manifest["release"]["blockers"].append("semantic_pmi_not_found")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    if args.input.suffix.lower() not in {".step", ".stp"}:
        parser.error("input must be .step or .stp")
    if not args.input.is_file():
        parser.error(f"input does not exist: {args.input}")
    try:
        payload = inspect(args.input)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_json(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
