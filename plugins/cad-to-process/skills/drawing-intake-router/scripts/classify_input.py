#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from mdi_common import classify_source, evidence, finding, new_manifest, write_json


def pdf_hints(path: Path) -> dict[str, int | bool]:
    sample = path.read_bytes()[:8 * 1024 * 1024]
    text_ops = sample.count(b" BT") + sample.count(b"\nBT")
    font_refs = sample.count(b"/Font")
    image_refs = sample.count(b"/Subtype /Image")
    return {
        "text_operator_count": text_ops,
        "font_reference_count": font_refs,
        "image_reference_count": image_refs,
        "vector_text_hint": text_ops > 0 or font_refs > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"input does not exist: {args.input}")

    kind, route = classify_source(args.input)
    manifest = new_manifest(args.input, kind, "drawing-intake-router")
    manifest["document"]["route"] = route
    manifest["evidence"].append(
        evidence(
            "source-kind",
            state="observed",
            source_ref={"path": str(args.input.resolve())},
            value=kind,
        )
    )

    if kind == "pdf_requires_probe":
        hints = pdf_hints(args.input)
        manifest["document"]["pdf_probe"] = hints
        manifest["evidence"].append(
            evidence(
                "pdf-vector-hint",
                state="derived",
                source_ref={"path": str(args.input.resolve()), "method": "byte-probe"},
                confidence=0.55,
                value=hints,
            )
        )
        manifest["findings"].append(
            finding(
                "PDF_REQUIRES_OBJECT_PROBE",
                "PDF hints are not authoritative; use a vector object parser before choosing OCR.",
                severity="warning",
                state="derived",
            )
        )
        manifest["release"]["decision"] = "needs_review"
        manifest["release"]["blockers"].append("pdf_modality_unconfirmed")
    elif kind == "unsupported":
        manifest["findings"].append(
            finding(
                "UNSUPPORTED_INPUT",
                f"No safe parser route for {args.input.suffix or 'extensionless input'}.",
                severity="error",
            )
        )
        manifest["release"]["decision"] = "blocked"
        manifest["release"]["blockers"].append("unsupported_input")

    write_json(manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
