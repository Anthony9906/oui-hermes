---
name: drawing-ocr-inspector
description: Segment and extract candidate text, dimensions, GD&T frames, tables, and regions from scanned engineering drawings and rasterized PDF pages using eDOCr2-compatible tooling. Use for PNG, JPEG, TIFF, BMP, or confirmed scanned PDFs when native STEP, DXF, or vector-PDF evidence is unavailable; use it to create reviewable OCR evidence, not to authorize unattended manufacturing.
---

# Drawing OCR inspector

Use OCR only after confirming that richer vector evidence is unavailable.
Preserve page, bounding box, crop coordinates, parser version, and confidence.

## Workflow

1. Confirm the OCR runtime with `python ../../scripts/check_runtime.py`.
2. Install and review a pinned eDOCr2 revision and its model weights.
3. Run:

   ```bash
   python scripts/inspect_drawing.py scan.png -o scan.ocr-manifest.json
   ```

4. Review every critical dimension, tolerance, datum, material, and note.
5. Associate OCR regions with geometry only through
   `$manufacturing-intent-fusion`.
6. Keep release at `needs_review` until critical evidence is confirmed.

## Boundaries

- Never silently correct OCR text with a language model.
- Never convert OCR confidence into geometric correctness.
- Do not claim a GD&T frame is attached to a feature merely because it is near it.
- Keep eDOCr2 segmentation, Tesseract text, and any VLM correction as separate
  evidence records.
- Do not auto-release a raster-only drawing in this version.

Read `references/ocr-evidence.md` for region and confidence policy.
Read `../../references/evidence-model.md` before changing output semantics.
