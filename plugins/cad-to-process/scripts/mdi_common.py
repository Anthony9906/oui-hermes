from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
EVIDENCE_STATES = {"observed", "derived", "inferred", "assumed", "unknown"}
RELEASE_DECISIONS = {
    "not_evaluated",
    "needs_review",
    "blocked",
    "candidate_for_release",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_id(path: Path) -> str:
    return f"{path.stem}-{sha256_file(path)[:12]}"


def new_manifest(path: Path, kind: str, parser: str) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id(resolved),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": str(resolved),
            "kind": kind,
            "sha256": sha256_file(resolved),
            "parser": parser,
            "parser_version": "0.1.0",
        },
        "document": {},
        "geometry": {},
        "views": [],
        "annotations": [],
        "associations": [],
        "feature_candidates": [],
        "requirements": [],
        "conflicts": [],
        "evidence": [],
        "findings": [],
        "release": {
            "decision": "not_evaluated",
            "blockers": [],
        },
    }


def finding(
    code: str,
    message: str,
    *,
    severity: str = "info",
    state: str = "observed",
    refs: list[str] | None = None,
) -> dict[str, Any]:
    if state not in EVIDENCE_STATES:
        raise ValueError(f"Unsupported evidence state: {state}")
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "state": state,
        "refs": refs or [],
    }


def evidence(
    evidence_id: str,
    *,
    state: str,
    source_ref: dict[str, Any],
    confidence: float = 1.0,
    value: Any = None,
) -> dict[str, Any]:
    if state not in EVIDENCE_STATES:
        raise ValueError(f"Unsupported evidence state: {state}")
    return {
        "id": evidence_id,
        "state": state,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "source_ref": source_ref,
        "value": value,
    }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def write_json(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")


def validate_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "schema_version",
        "artifact_id",
        "source",
        "document",
        "geometry",
        "views",
        "annotations",
        "associations",
        "feature_candidates",
        "requirements",
        "conflicts",
        "evidence",
        "findings",
        "release",
    ]
    for key in required:
        if key not in payload:
            errors.append(f"missing required key: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"unsupported schema_version: {payload.get('schema_version')!r}; "
            f"expected {SCHEMA_VERSION!r}"
        )
    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        for key in ("path", "kind", "sha256"):
            if not source.get(key):
                errors.append(f"source.{key} is required")
    for list_key in (
        "views",
        "annotations",
        "associations",
        "feature_candidates",
        "requirements",
        "conflicts",
        "evidence",
        "findings",
    ):
        if list_key in payload and not isinstance(payload[list_key], list):
            errors.append(f"{list_key} must be an array")
    for index, item in enumerate(payload.get("evidence", [])):
        if item.get("state") not in EVIDENCE_STATES:
            errors.append(f"evidence[{index}].state is invalid")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"evidence[{index}].confidence must be between 0 and 1")
    release = payload.get("release")
    if not isinstance(release, dict):
        errors.append("release must be an object")
    elif release.get("decision") not in RELEASE_DECISIONS:
        errors.append("release.decision is invalid")
    return errors


def dependency_status() -> dict[str, Any]:
    modules = {
        "step": ["OCP"],
        "dxf": ["ezdxf"],
        "ocr": ["cv2", "numpy", "pdf2image", "pytesseract", "tensorflow", "edocr2"],
    }
    result: dict[str, Any] = {}
    for group, names in modules.items():
        availability = {
            name: importlib.util.find_spec(name) is not None
            for name in names
        }
        result[group] = {
            "ready": all(availability.values()),
            "modules": availability,
        }
    return result


def classify_source(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    mapping = {
        ".step": ("step", "step-brep-inspector"),
        ".stp": ("step", "step-brep-inspector"),
        ".dxf": ("dxf", "dxf-semantic-inspector"),
        ".png": ("raster_drawing", "drawing-ocr-inspector"),
        ".jpg": ("raster_drawing", "drawing-ocr-inspector"),
        ".jpeg": ("raster_drawing", "drawing-ocr-inspector"),
        ".tif": ("raster_drawing", "drawing-ocr-inspector"),
        ".tiff": ("raster_drawing", "drawing-ocr-inspector"),
        ".bmp": ("raster_drawing", "drawing-ocr-inspector"),
        ".pdf": ("pdf_requires_probe", "drawing-intake-router"),
    }
    return mapping.get(suffix, ("unsupported", "drawing-intake-router"))
