#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import math
from pathlib import Path
import sys
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from mdi_common import finding, load_json, validate_manifest, write_json


def _normalized_axis(axis: list[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(float(value) ** 2 for value in axis))
    if length <= 1e-12:
        return (0.0, 0.0, 0.0)
    values = [float(value) / length for value in axis]
    for value in values:
        if abs(value) > 1e-9:
            if value < 0:
                values = [-item for item in values]
            break
    return tuple(round(item, 5) for item in values)


def recognize(payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_manifest(payload)
    if errors:
        raise ValueError("; ".join(errors))

    groups: defaultdict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for occurrence in payload.get("geometry", {}).get("occurrences", []):
        for face in occurrence.get("faces", []):
            if face.get("surface_type") != "cylinder":
                continue
            params = face.get("params", {})
            axis = params.get("axis")
            origin = params.get("origin")
            radius = params.get("radius")
            if not isinstance(axis, list) or not isinstance(origin, list) or radius is None:
                continue
            normalized_axis = _normalized_axis(axis)
            origin_cross_axis = (
                origin[1] * normalized_axis[2] - origin[2] * normalized_axis[1],
                origin[2] * normalized_axis[0] - origin[0] * normalized_axis[2],
                origin[0] * normalized_axis[1] - origin[1] * normalized_axis[0],
            )
            key = (
                occurrence.get("selector"),
                round(float(radius), 5),
                normalized_axis,
                tuple(round(float(value), 4) for value in origin_cross_axis),
            )
            groups[key].append(face)

    candidates: list[dict[str, Any]] = []
    for index, (key, faces) in enumerate(sorted(groups.items(), key=str), start=1):
        occurrence, radius, axis, _line_moment = key
        candidates.append(
            {
                "id": f"feature:cylindrical-group:{index}",
                "kind": "coaxial_cylindrical_group",
                "state": "derived",
                "confidence": 0.8,
                "supporting_faces": [face["selector"] for face in faces],
                "occurrence": occurrence,
                "parameters": {
                    "radius": radius,
                    "axis": list(axis),
                    "face_count": len(faces),
                },
                "rule": "group analytic cylindrical faces by occurrence, radius, and axis line",
                "missing_context": [
                    "signed_concavity",
                    "stock_envelope",
                    "setup_direction",
                    "blind_or_through_condition",
                ],
                "promotion_blocked": True,
            }
        )

    payload["feature_candidates"] = candidates
    payload["findings"].append(
        finding(
            "FEATURES_ARE_CANDIDATES",
            "Cylindrical groups are not confirmed holes until stock, direction, and concavity are known.",
            severity="warning",
            state="derived",
            refs=[item["id"] for item in candidates],
        )
    )
    payload["release"]["decision"] = "needs_review"
    blockers = payload["release"].setdefault("blockers", [])
    if "feature_candidates_unpromoted" not in blockers:
        blockers.append("feature_candidates_unpromoted")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    try:
        payload = recognize(load_json(args.manifest))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_json(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
