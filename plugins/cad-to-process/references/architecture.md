# CAD-to-Process architecture

The product-family boundary is:

`text-to-cad -> cad-to-process -> process-to-cam`

- `text-to-cad` produces a validated part definition and CAD geometry.
- `cad-to-process` produces reviewed, feasible, and ranked machining process
  routes from CAD, drawings, PMI, and manufacturing constraints.
- `process-to-cam` will translate a released route into toolpaths, simulation,
  post-processing, and machine-specific NC artifacts.

The product target is:

`CAD/drawing + manufacturing requirements -> part intent -> machining
features -> feasible process routes -> objective-aware recommendation`

The recommendation objective must be explicit, such as lowest cost, shortest
lead time, lowest risk, or a weighted value score. An optimizer may rank only
routes that have passed resource, setup, tolerance-chain, and process-feasibility
checks.

Version 0.1 implements six evidence-foundation responsibilities:

1. Route inputs without destroying richer source information.
2. Extract exact STEP/B-Rep and semantic PMI evidence.
3. Extract native DXF entities, dimensions, notes, leaders, and blocks.
4. Extract candidate evidence from raster drawings with eDOCr2.
5. Recognize auditable machining-feature candidates.
6. Fuse evidence, detect conflicts, and enforce release gates.

Keep the STEP, DXF, and OCR adapters in separate environments. Exchange only
versioned JSON manifests and immutable source-file references between them.
Treat vector PDF as a distinct future adapter; do not rasterize it by default.

The next governed skill layers are intentionally not claimed as implemented:

7. Generate process-route candidates from released part intent.
8. Check routes against machine, tooling, fixture, material, tolerance, and
   capacity constraints.
9. Estimate cost, cycle time, delivery risk, and uncertainty.
10. Rank feasible routes against a declared optimization objective while
    preserving alternatives and human release authority.
