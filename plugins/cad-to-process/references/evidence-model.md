# Evidence model

Use one manifest for all modalities. Preserve the original file and never
silently promote model output into deterministic fact.

## Evidence states

- `observed`: read directly from the source format.
- `derived`: calculated deterministically from observed data.
- `inferred`: predicted by a model or heuristic.
- `assumed`: supplied to continue work despite missing evidence.
- `unknown`: explicitly unresolved.

## Stable source references

- STEP: XCAF label plus local face/edge selector such as `#o1.f3`.
- DXF: layout name, entity handle, block path, and coordinates.
- Raster: page, pixel bounding box, and saved crop.
- PDF vector: page, object identity, text span, and coordinates.

## Release rule

Never mark a manifest `candidate_for_release` when any critical requirement is
`inferred`, `assumed`, or `unknown`; when a critical association is missing; or
when unresolved conflicts remain. Agent reasoning may explain a conflict but
must not erase its evidence.
