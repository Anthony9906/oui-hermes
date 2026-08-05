---
name: drawing-intake-router
description: Classify manufacturing drawing inputs and route STEP/STP, DXF, vector PDF, scanned PDF, and raster images to the correct evidence extractor. Use when a task starts with one or more unknown or mixed engineering files, when preserving the richest source modality matters, or when an evidence manifest must be initialized before geometry, OCR, feature, DFM, quotation, process-planning, or CAM work.
---

# Drawing intake router

Preserve the original source and route it before interpretation. Never rasterize
STEP, DXF, or vector PDF merely to simplify the workflow.

## Workflow

1. Run `scripts/classify_input.py` for every input.
2. Route STEP/STP to `$step-brep-inspector`.
3. Route DXF to `$dxf-semantic-inspector`.
4. Probe PDF before choosing vector parsing or `$drawing-ocr-inspector`.
5. Route raster images to `$drawing-ocr-inspector`.
6. Stop unsupported DWG and proprietary native CAD inputs with a conversion
   requirement; do not rename them to another format.
7. Preserve the generated manifest and source hash for downstream fusion.

```bash
python scripts/classify_input.py part.step -o part.intake.json
```

## Evidence rules

- Mark file type and hashes as `observed`.
- Mark heuristic PDF vector hints as `derived`, never as proof.
- Record unsupported formats as blockers.
- Do not infer missing units, revisions, tolerances, or manufacturing intent.

Read `references/routing.md` when handling mixed files or PDF.
Read `../../references/evidence-model.md` before changing manifest semantics.
