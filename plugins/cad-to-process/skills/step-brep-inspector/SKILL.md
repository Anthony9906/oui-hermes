---
name: step-brep-inspector
description: Inspect existing STEP/STP files with OCCT/OCP and emit auditable B-Rep, topology, assembly, surface, validity, and semantic PMI/GD&T evidence. Use for imported STEP models, AP242 files, face and edge facts, exact geometry references, PMI availability checks, feature-recognition preparation, or validating 3D evidence before DFM, quotation, process planning, or CAM.
---

# STEP B-Rep inspector

Treat STEP geometry as exact source evidence. Treat inferred manufacturing
features and reconstructed design history as separate downstream claims.

## Workflow

1. Confirm the STEP runtime:

   ```bash
   python ../../scripts/check_runtime.py
   ```

2. Run the inspector:

   ```bash
   python scripts/inspect_step.py part.step -o part.step-manifest.json
   ```

3. Verify transfer status, shape validity, occurrence count, solid count,
   surfaces, edges, and semantic PMI counts.
4. Preserve local selectors such as `#o1.f3` and `#o1.e8`.
5. Route the manifest to `$machining-feature-recognizer`.
6. If critical PMI exists only as graphical presentation or is not attached to
   a shape, block unattended release.

## Boundaries

- Do not claim recovery of native feature history from arbitrary STEP.
- Do not convert cylindrical faces directly into confirmed holes.
- Do not claim tolerance compliance from STEP topology alone.
- Do not heal or overwrite the source during inspection.
- Report missing Python bindings separately from missing data in the STEP file.

Read `references/step-evidence.md` for PMI and selector interpretation.
Read `../../references/evidence-model.md` before changing output semantics.
