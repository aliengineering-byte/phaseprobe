# Roadmap

## Delivered in 0.2.0

- Explicit dotted-module/factory adapter loading with validation separated from code execution.
- Optional trajectory-level protocol and public `solve_ivp` adapter without a fake step loop.
- Exact and tolerance replay modes with v1 fixture compatibility and artifact integrity hashes.
- Genuine SciPy Lorenz and predator-prey positive/negative examples and generated regressions.
- Separate core-only and SciPy-extra Windows/Linux CI coverage.

## After 0.2.0

- Non-monotonic multi-dimension search: coarse exploration, stable bracket discovery, local refinement, repeatability, and delta debugging.
- Adapter-provided solver convergence studies and paired step-size evidence.
- Streaming trace summaries for expensive simulators without weakening the configured cap.
- JSON Schema publication and compatibility migration tooling.
- JUnit/SARIF policy output for CI annotation.
- Additional reference adapters only when they validate a missing capability such as stiff/event-heavy systems, with positive cases, negative controls, invalid-integration tests, and primary citations.

PyPI publication is intentionally absent and requires separate authorization.
