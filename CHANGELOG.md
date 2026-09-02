# Changelog

All notable changes are documented here. PhaseProbe follows semantic versioning.

## Unreleased

- `generate-test` now writes a path-portable claim/decision evidence record that binds the
  validated replay verdict to SHA-256 hashes of the copied fixture and generated pytest, the
  exact reproduction command, PhaseProbe attribution, and explicit scientific limitations.
- Identical generated evidence is idempotent; conflicting evidence is rejected without overwrite.
- Invariant-only fixtures now use the narrower `simulation-replay-regression` claim kind, and the
  unsigned evidence-integrity boundary is explicit.

## 0.2.1 — 2026-08-31

- Fixed Issue #4: all four SciPy quick-start configurations now ship inside the importable
  package in both wheel and source distribution and load through `importlib.resources` as the
  `scipy-lorenz`, `scipy-lorenz-negative`, `scipy-predator-prey`, and
  `scipy-predator-prey-coarse` built-in examples.
- Preserved the four exact former `examples/scipy/` config paths as narrow compatibility aliases
  when no file exists at the requested path. Existing user files take precedence; matching is
  case-sensitive and separator-portable, with no fuzzy or basename fallback.
- Added actionable, versioned diagnostics for missing or malformed built-in resources without
  changing arbitrary config-path or built-in-example behavior.
- Added Linux and Windows Python 3.12 release gates that build, inspect, install, and exercise the
  wheel and sdist outside the checkout with `PYTHONPATH` removed. The gate runs scan, replay,
  generated pytest, SciPy Lorenz, SciPy predator–prey, `pip check`, and a dependency-free base
  wheel check.
- Added a source-derived runtime-resource audit and the PEP 561 `py.typed` marker.
- Generated regression creation is now idempotent for identical evidence and rejects conflicting
  files instead of silently overwriting them.
- Added an analytic backward-time directional-event check while preserving all solver defaults
  and the existing tolerance-based adaptive replay contract.

## 0.2.0 — 2026-08-02

- Added the backward-compatible `TrajectoryAdapter` protocol and shared engine dispatch; all v0.1
  step adapters and examples continue unchanged.
- Added optional `phaseprobe[scipy]` support with a typed public `SolveIVPAdapter`, controlled
  evaluation grids, scalar/vector tolerances, methods, maximum step, named events, observables,
  classifiers, invariants, invalid-value checks, bounded retention, and solver/environment evidence.
- Added schema-v2 `exact` and `tolerance` replay while keeping schema-v1 exact fixtures readable.
  Tolerance fixtures preserve state, observable, classifier, invariant threshold, grid, endpoint,
  event, solver-success, version, and platform evidence without claiming byte-identical replay.
- Added genuine SciPy Lorenz finite-time divergence and predator–prey first-integral examples,
  negative controls, refinement evidence, HTML evidence, and generated pytest fixtures.
- Added explicit safe-shape Python module/factory loading, core-without-SciPy tests, optional import
  diagnostics, a Windows/Linux core/SciPy CI matrix, current SciPy audit, security/limitations docs,
  demo assets, and an unposted upstream visibility proposal.
- Base installation remains dependency-free. NumPy and SciPy are optional; no PyPI publication was
  performed.

## 0.1.0 — 2026-08-01

- Added `scan`, `perturb`, `check`, `replay`, `generate-test`, and `report` commands.
- Added typed adapters for logistic map, Lorenz, Lotka–Volterra predator–prey, and a mutually repressing genetic toggle.
- Added deterministic seeds, canonical configuration, fixed-step execution, invalid-integration diagnostics, capped trace retention, and exact trace hashes.
- Added transition brackets, bounded initial-state search, repeatability confirmation, replay fixtures with integrity hashes, and fixed-template pytest generation.
- Added terminal, versioned JSON, and self-contained offline HTML evidence.
- Added Windows/Linux CI, packaging and packed-install checks, documentation/hygiene gates, and repository-native demo assets.
