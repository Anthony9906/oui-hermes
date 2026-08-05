---
name: dxf-semantic-inspector
description: Inspect existing DXF engineering drawings with ezdxf and extract layouts, layers, blocks, dimensions, text, tolerances, leaders, attributes, and geometry evidence while preserving native handles and coordinates. Use for vector manufacturing drawings, drawing-title data, dimension and note extraction, DXF quality checks, or preparing evidence for 2D-to-3D association and manufacturing-intent fusion.
---

# DXF semantic inspector

Read native DXF objects before rendering. Preserve entity handles, layouts,
blocks, coordinates, explicit text overrides, and auditor findings.

## Workflow

1. Confirm the DXF runtime with `python ../../scripts/check_runtime.py`.
2. Run:

   ```bash
   python scripts/inspect_dxf.py drawing.dxf -o drawing.dxf-manifest.json
   ```

3. Review dimensions whose displayed text overrides measured geometry.
4. Review exploded or proxy entities and unsupported MLEADER/vendor objects.
5. Preserve every native handle for downstream association.
6. Pass the manifest to `$manufacturing-intent-fusion`.

## Boundaries

- Do not treat rendered dimension primitives as semantic DIMENSION objects.
- Do not infer 3D depth from a single 2D view.
- Do not flatten blocks without preserving the block path and transform.
- Do not silently repair and overwrite the input.
- Treat audit recovery as a finding, not proof that no data was lost.

Read `references/dxf-evidence.md` for field interpretation.
Read `../../references/evidence-model.md` before changing output semantics.
