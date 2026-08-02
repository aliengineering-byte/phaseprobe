# Changelog

All notable changes are documented here. PhaseProbe follows semantic versioning.

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
