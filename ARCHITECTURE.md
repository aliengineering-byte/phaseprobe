# Architecture

PhaseProbe separates simulation semantics from search, evidence, and test materialization.

```text
JSON config / built-in example
            |
            v
       typed adapter ----> deterministic step + observe
            |                         |
            v                         v
 bounded engine ----> finite validation ----> capped trace + SHA-256
      |     |
      |     +---- scan / perturb / check policy
      v
 outcome ----> run artifacts ----> replay verification ----> fixed pytest template
      |
      +---- terminal / JSON / self-contained HTML
```

## Modules

- `config.py` validates schema `1.0`, loads packaged examples, and emits canonical JSON.
- `types.py` defines the public adapter protocol, state shape, trace point, and invariant result.
- `models/` contains four independent reference adapters. They are examples, not engine special cases.
- `engine.py` owns bounded execution, NaN/Inf/hard-limit checks, trace retention, scanning, perturbation, bracket refinement, repeatability confirmation, and CI policy evaluation.
- `artifacts.py` creates one finite run directory and hashes each evidence file.
- `replay.py` verifies fixture integrity before re-executing exact model/config/seed/state/parameter inputs and comparing classifications plus retained trace hashes.
- `generate.py` uses a fixed code template and sanitized names. It never evaluates configuration text.
- `reporting.py` renders terminal, JSON, and offline HTML with explicit limitations.
- `cli.py` maps the six public commands to stable exit codes.

## Adapter design

The engine deliberately does not require NumPy. A state is a tuple of finite floats; this keeps serialization and perturbation explicit. Downstream adapters may wrap larger simulators, but their `step` boundary must return a bounded tuple suitable for deterministic replay. Observations are scalar mappings and cannot carry arbitrary executable objects.

An adapter supplies scientific judgment: initial conditions, state advance, observables, qualitative classification, and invariants. The engine supplies operational judgment: search bounds, retention, failure containment, hashes, artifacts, and policy exits.

## Determinism boundary

PhaseProbe controls seeds, canonical configuration serialization, fixed command order, search grids, state perturbations, trace retention, and fixture hashing. An external adapter remains responsible for deterministic solver settings, thread behavior, native library versions, and hardware-sensitive arithmetic. Exact replay hashes intentionally expose drift; users may choose a classification-only policy in a future version, but v0.1.0 replay is strict.

## Artifact safety

Trace points are capped per series. Run IDs combine UTC time and an evidence digest. Replay fixtures carry a schema version and SHA-256 over every unsigned field. Generated tests copy a validated fixture into `tests/generated/fixtures/` and contain only a sanitized identifier plus a fixed relative path.

## Extension checklist

1. Give the adapter a stable `identity` version.
2. Make `initial_state` deterministic for the declared seed.
3. Return the same state dimension after every step.
4. Define classifier thresholds in configuration tolerances.
5. Distinguish mathematical invariants from diagnostic bounds in invariant details.
6. Add positive, negative-control, invalid-state, repeatability, and replay tests.
7. Cite a primary technical source for the model and document solver limitations.
