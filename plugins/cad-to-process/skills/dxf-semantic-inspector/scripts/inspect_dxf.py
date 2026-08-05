#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from mdi_common import evidence, finding, new_manifest, write_json


def _xyz(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(value.x), float(value.y), float(value.z)]
    except Exception:
        try:
            values = list(value)
            return [float(item) for item in (*values, 0.0)[:3]]
        except Exception:
            return None


def _safe_dxf(entity: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(entity.dxf, name)
    except Exception:
        return default


def _dimension(entity: Any, layout: str) -> dict[str, Any]:
    try:
        measurement = entity.get_measurement()
        if hasattr(measurement, "x"):
            measurement = _xyz(measurement)
        elif isinstance(measurement, tuple):
            measurement = [float(value) for value in measurement]
        else:
            measurement = float(measurement)
    except Exception:
        measurement = None
    text = _safe_dxf(entity, "text", "")
    return {
        "id": f"dxf:{entity.dxf.handle}",
        "kind": "dimension",
        "state": "observed",
        "confidence": 1.0,
        "layout": layout,
        "handle": entity.dxf.handle,
        "layer": _safe_dxf(entity, "layer", "0"),
        "dimension_type": getattr(entity, "dimtype", None),
        "measurement": measurement,
        "explicit_text": text,
        "style": _safe_dxf(entity, "dimstyle"),
        "definition_point": _xyz(_safe_dxf(entity, "defpoint")),
        "definition_point_2": _xyz(_safe_dxf(entity, "defpoint2")),
        "definition_point_3": _xyz(_safe_dxf(entity, "defpoint3")),
        "requires_review": text not in {"", "<>", " "},
    }


def _text(entity: Any, layout: str) -> dict[str, Any]:
    kind = entity.dxftype().lower()
    if entity.dxftype() == "MTEXT":
        try:
            content = entity.plain_text()
        except Exception:
            content = _safe_dxf(entity, "text", "")
    else:
        content = _safe_dxf(entity, "text", "")
    return {
        "id": f"dxf:{entity.dxf.handle}",
        "kind": kind,
        "state": "observed",
        "confidence": 1.0,
        "layout": layout,
        "handle": entity.dxf.handle,
        "layer": _safe_dxf(entity, "layer", "0"),
        "text": content,
        "insert": _xyz(_safe_dxf(entity, "insert")),
        "rotation": _safe_dxf(entity, "rotation", 0.0),
    }


def _insert(entity: Any, layout: str) -> dict[str, Any]:
    attributes = []
    for attrib in getattr(entity, "attribs", []):
        attributes.append(
            {
                "handle": _safe_dxf(attrib, "handle"),
                "tag": _safe_dxf(attrib, "tag"),
                "text": _safe_dxf(attrib, "text"),
                "insert": _xyz(_safe_dxf(attrib, "insert")),
            }
        )
    return {
        "id": f"dxf:{entity.dxf.handle}",
        "kind": "insert",
        "state": "observed",
        "confidence": 1.0,
        "layout": layout,
        "handle": entity.dxf.handle,
        "layer": _safe_dxf(entity, "layer", "0"),
        "block_name": _safe_dxf(entity, "name"),
        "insert": _xyz(_safe_dxf(entity, "insert")),
        "rotation": _safe_dxf(entity, "rotation", 0.0),
        "scale": [
            float(_safe_dxf(entity, "xscale", 1.0)),
            float(_safe_dxf(entity, "yscale", 1.0)),
            float(_safe_dxf(entity, "zscale", 1.0)),
        ],
        "attributes": attributes,
    }


def _leader(entity: Any, layout: str) -> dict[str, Any]:
    vertices: list[list[float]] = []
    try:
        vertices = [_xyz(vertex) for vertex in entity.vertices]
        vertices = [vertex for vertex in vertices if vertex is not None]
    except Exception:
        pass
    return {
        "id": f"dxf:{entity.dxf.handle}",
        "kind": entity.dxftype().lower(),
        "state": "observed",
        "confidence": 1.0,
        "layout": layout,
        "handle": entity.dxf.handle,
        "layer": _safe_dxf(entity, "layer", "0"),
        "vertices": vertices,
        "style": _safe_dxf(entity, "dimstyle"),
    }


def inspect(path: Path) -> dict[str, Any]:
    try:
        import ezdxf
        from ezdxf import recover
        from ezdxf.lldxf.const import DXFStructureError
    except ImportError as exc:
        raise RuntimeError(
            "DXF runtime unavailable. Install requirements-dxf.txt in an isolated environment."
        ) from exc

    recovered = False
    auditor = None
    try:
        document = ezdxf.readfile(path)
        auditor = document.audit()
    except DXFStructureError:
        document, auditor = recover.readfile(path)
        recovered = True

    manifest = new_manifest(path, "dxf", "dxf-semantic-inspector")
    manifest["document"] = {
        "dxf_version": document.dxfversion,
        "encoding": getattr(document, "encoding", None),
        "units": int(getattr(document, "units", 0)),
        "recovered": recovered,
        "layers": [layer.dxf.name for layer in document.layers],
        "blocks": [block.name for block in document.blocks],
    }

    entity_counts: Counter[str] = Counter()
    annotations: list[dict[str, Any]] = []
    geometry_entities: list[dict[str, Any]] = []
    supported_annotations = {
        "DIMENSION",
        "TEXT",
        "MTEXT",
        "INSERT",
        "LEADER",
        "MLEADER",
        "TOLERANCE",
    }
    for layout in document.layouts:
        for entity in layout:
            kind = entity.dxftype()
            entity_counts[kind] += 1
            if kind == "DIMENSION":
                annotations.append(_dimension(entity, layout.name))
            elif kind in {"TEXT", "MTEXT", "TOLERANCE"}:
                annotations.append(_text(entity, layout.name))
            elif kind == "INSERT":
                annotations.append(_insert(entity, layout.name))
            elif kind in {"LEADER", "MLEADER"}:
                annotations.append(_leader(entity, layout.name))
            elif kind not in supported_annotations:
                geometry_entities.append(
                    {
                        "handle": _safe_dxf(entity, "handle"),
                        "type": kind,
                        "layout": layout.name,
                        "layer": _safe_dxf(entity, "layer", "0"),
                    }
                )

    manifest["annotations"] = annotations
    manifest["geometry"] = {
        "entity_type_counts": dict(sorted(entity_counts.items())),
        "entities": geometry_entities,
    }
    manifest["views"] = [
        {"id": f"dxf-layout:{layout.name}", "name": layout.name, "state": "observed"}
        for layout in document.layouts
    ]
    manifest["evidence"].append(
        evidence(
            "dxf-native-objects",
            state="observed",
            source_ref={"path": str(path.resolve()), "format": document.dxfversion},
            value={
                "annotation_count": len(annotations),
                "entity_type_counts": dict(entity_counts),
            },
        )
    )
    errors = list(getattr(auditor, "errors", [])) if auditor is not None else []
    fixes = list(getattr(auditor, "fixes", [])) if auditor is not None else []
    if recovered or errors or fixes:
        manifest["findings"].append(
            finding(
                "DXF_AUDIT_FINDINGS",
                f"recovered={recovered}, errors={len(errors)}, fixes={len(fixes)}",
                severity="warning",
            )
        )
        manifest["release"]["decision"] = "needs_review"
        manifest["release"]["blockers"].append("dxf_audit_findings")
    overridden = [
        item["id"]
        for item in annotations
        if item.get("kind") == "dimension" and item.get("requires_review")
    ]
    if overridden:
        manifest["findings"].append(
            finding(
                "DIMENSION_TEXT_OVERRIDE",
                "Explicit dimension text overrides require comparison with native geometry.",
                severity="warning",
                refs=overridden,
            )
        )
        manifest["release"]["decision"] = "needs_review"
        manifest["release"]["blockers"].append("dimension_text_override")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    if args.input.suffix.lower() != ".dxf":
        parser.error("input must be .dxf")
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
