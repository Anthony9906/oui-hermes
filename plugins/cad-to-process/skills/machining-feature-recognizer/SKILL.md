---
name: machining-feature-recognizer
description: Recognize auditable machining-feature candidates from STEP/B-Rep evidence manifests using deterministic topology and geometry rules, with optional learned graph models reserved for ambiguous cases. Use for holes, coaxial cylindrical groups, pockets, slots, steps, bosses, setup-direction candidates, or feature evidence needed by DFM, quotation, process routing, and CAM planning.
---

# Machining feature recognizer

Generate candidates with explicit supporting face selectors. Prefer exact rules
and OCCT revalidation before learned classifications.

## Workflow

1. Start from a valid `$step-brep-inspector` manifest.
2. Run:

   ```bash
   python scripts/recognize_features.py part.step-manifest.json \
     -o part.features.json
   ```

3. Review every candidate's supporting faces, rule, confidence, and missing
   context.
4. Require stock, setup direction, openness, and signed concavity before
   promoting candidates such as pocket, boss, or hole.
5. Use GNN/AAG models only for ambiguous or intersecting features; store model
   results as separate `inferred` evidence.
6. Revalidate promoted feature geometry through OCCT before downstream use.

## Boundaries

- A cylindrical face is not automatically a hole.
- B-Rep alone may not distinguish pocket from boss without stock and direction.
- Do not merge intersecting feature candidates without preserving source faces.
- Do not send candidates directly to CAM.

Read `references/feature-policy.md` for promotion requirements.
Read `../../references/evidence-model.md` before changing output semantics.
