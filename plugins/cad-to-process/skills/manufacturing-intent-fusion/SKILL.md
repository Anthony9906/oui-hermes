---
name: manufacturing-intent-fusion
description: Fuse STEP/B-Rep, AP242 PMI, DXF, vector, OCR, and machining-feature evidence manifests into a traceable manufacturing-intent view with conflict detection and explicit human release gates. Use before DFM, quotation, process routing, inspection planning, CAM, NC generation, or any decision that depends on reconciling 2D requirements with 3D geometry.
---

# Manufacturing intent fusion

Merge evidence without collapsing provenance. Conflicts are first-class output,
not text to be explained away.

## Workflow

1. Validate every input manifest.
2. Run:

   ```bash
   python scripts/fuse_manifests.py step.json dxf.json ocr.json \
     -o manufacturing-intent.json
   ```

3. Review duplicate evidence IDs, requirement value conflicts, missing
   associations, inherited blockers, and critical inferred fields.
4. Preserve every source SHA-256 and local reference.
5. Mark `candidate_for_release` only when no release blocker remains.
6. Require an engineer to approve release before DFM/CAM/NC execution.

## Non-negotiables

- Never overwrite observed evidence with inferred evidence.
- Never average conflicting nominal values or tolerances.
- Never hide missing feature associations.
- Never auto-release an empty requirement set.
- Agent reasoning may recommend a resolution but cannot change the evidence
  state without a new source or human confirmation.

Read `references/release-gates.md` for blocking conditions.
Read `../../references/evidence-model.md` before changing output semantics.
