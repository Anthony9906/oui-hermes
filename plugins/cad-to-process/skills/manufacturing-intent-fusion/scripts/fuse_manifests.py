#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from mdi_common import SCHEMA_VERSION, finding, load_json, validate_manifest, write_json


MERGED_ARRAYS = (
    "views",
    "annotations",
    "associations",
    "feature_candidates",
    "requirements",
    "conflicts",
    "evidence",
    "findings",
)


def _fingerprint(value: Any) -> str:
    import json

    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _value_signature(requirement: dict[str, Any]) -> tuple[Any, ...]:
    return (
        requirement.get("nominal"),
        requirement.get("lower"),
        requirement.get("upper"),
        requirement.get("tolerance"),
        requirement.get("unit"),
    )


def fuse(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    for index, payload in enumerate(payloads):
        errors = validate_manifest(payload)
        if errors:
            raise ValueError(f"manifest[{index}] invalid: {'; '.join(errors)}")

    source_hashes = [payload["source"]["sha256"] for payload in payloads]
    fused_sha = hashlib.sha256("|".join(source_hashes).encode("ascii")).hexdigest()
    fused: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": f"fused-{fused_sha[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": [payload["source"]["path"] for payload in payloads],
            "kind": "fused_manifest",
            "sha256": fused_sha,
            "parser": "manufacturing-intent-fusion",
            "parser_version": "0.1.0",
        },
        "document": {
            "source_documents": [
                {
                    "artifact_id": payload["artifact_id"],
                    "kind": payload["source"]["kind"],
                    "sha256": payload["source"]["sha256"],
                    "document": deepcopy(payload.get("document", {})),
                }
                for payload in payloads
            ]
        },
        "geometry": {
            "sources": [
                {
                    "artifact_id": payload["artifact_id"],
                    "geometry": deepcopy(payload.get("geometry", {})),
                }
                for payload in payloads
                if payload.get("geometry")
            ]
        },
        "views": [],
        "annotations": [],
        "associations": [],
        "feature_candidates": [],
        "requirements": [],
        "conflicts": [],
        "evidence": [],
        "findings": [],
        "release": {"decision": "not_evaluated", "blockers": []},
    }

    seen_ids: dict[tuple[str, str], str] = {}
    for payload in payloads:
        artifact = payload["artifact_id"]
        for array_name in MERGED_ARRAYS:
            for item in payload.get(array_name, []):
                copied = deepcopy(item)
                copied.setdefault("source_artifact_id", artifact)
                item_id = copied.get("id")
                if item_id:
                    key = (array_name, str(item_id))
                    fingerprint = _fingerprint(copied)
                    previous = seen_ids.get(key)
                    if previous is not None and previous != fingerprint:
                        fused["conflicts"].append(
                            {
                                "id": f"conflict:duplicate:{array_name}:{item_id}",
                                "kind": "duplicate_id_different_content",
                                "state": "derived",
                                "array": array_name,
                                "item_id": item_id,
                            }
                        )
                    seen_ids[key] = fingerprint
                fused[array_name].append(copied)

    requirements_by_characteristic: dict[str, list[dict[str, Any]]] = {}
    for requirement in fused["requirements"]:
        characteristic = requirement.get("characteristic_id")
        if characteristic:
            requirements_by_characteristic.setdefault(str(characteristic), []).append(
                requirement
            )
    for characteristic, requirements in requirements_by_characteristic.items():
        signatures = {_value_signature(item) for item in requirements}
        if len(signatures) > 1:
            fused["conflicts"].append(
                {
                    "id": f"conflict:requirement:{characteristic}",
                    "kind": "requirement_value_conflict",
                    "state": "derived",
                    "characteristic_id": characteristic,
                    "source_ids": [item.get("id") for item in requirements],
                    "values": [list(signature) for signature in sorted(signatures, key=str)],
                }
            )

    blockers = {
        blocker
        for payload in payloads
        for blocker in payload.get("release", {}).get("blockers", [])
    }
    if fused["conflicts"]:
        blockers.add("unresolved_conflicts")
    if not fused["requirements"]:
        blockers.add("no_requirements")
    for requirement in fused["requirements"]:
        if requirement.get("critical") and requirement.get("state") in {
            "inferred",
            "assumed",
            "unknown",
        }:
            blockers.add("critical_requirement_not_confirmed")
        if requirement.get("critical") and not requirement.get("geometry_refs"):
            blockers.add("critical_requirement_unassociated")
    if any(item.get("promotion_blocked") for item in fused["feature_candidates"]):
        blockers.add("feature_candidates_unpromoted")

    fused["release"]["blockers"] = sorted(blockers)
    fused["release"]["decision"] = (
        "candidate_for_release" if not blockers else "needs_review"
    )
    if blockers:
        fused["findings"].append(
            finding(
                "FUSION_RELEASE_BLOCKED",
                "Human review required: " + ", ".join(sorted(blockers)),
                severity="warning",
                state="derived",
            )
        )
    return fused


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    try:
        payload = fuse([load_json(path) for path in args.manifests])
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_json(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
