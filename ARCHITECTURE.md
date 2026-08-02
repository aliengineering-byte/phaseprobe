# Architecture

PhaseProbe separates simulation semantics from search, evidence, and test materialization.

```text
JSON config / built-in example
            |
            v
       typed adapter ----> fixed step OR whole trajectory
            |                         |
            v                         v
 bounded engine ----> finite validation ----> capped trace + SHA-256 integrity
      |     |
      |     +---- scan / perturb / check policy
      v
 outcome ----> run artifacts ----> replay verification ----> fixed pytest template
      |
      +---- terminal / JSON / self-contained HTML
```

## Modules

- `config.py` emits schema `2.0`, keeps schema `1.0` readable, validates explicit Python adapter
  references without importing them, loads packaged examples, and emits canonical JSON.
- `types.py` defines the step-level `ModelAdapter`, trajectory-level `TrajectoryAdapter`, state
  shape, trace point/trace, replay mode, and invariant result.
- `models/` contains four independent reference adapters. They are examples, not engine special cases.
- `adapters/scipy.py` optionally imports NumPy/SciPy and wraps only public `solve_ivp` behavior.
- `adapters/loader.py` imports a user-selected dotted module and calls its named factory only at
  execution time.
- `engine.py` dispatches step versus trajectory execution and owns shared NaN/Inf/hard-limit
  checks, bounded retention, scanning, perturbation, bracket refinement, repeatability
  confirmation, and CI policy evaluation.
- `artifacts.py` creates one finite run directory and hashes each evidence file.
- `replay.py` reads v1 exact fixtures and emits v2 fixtures with explicit `exact` or `tolerance`
  comparison, always after SHA-256 integrity validation.
- `generate.py` uses a fixed code template and sanitized names. It never evaluates configuration text.
- `reporting.py` renders terminal, JSON, and offline HTML with explicit limitations.
- `cli.py` maps the six public commands to stable exit codes.

## Adapter design and dispatch

The engine deliberately does not require NumPy. A state is a tuple of finite floats; this keeps
serialization and perturbation explicit. Existing adapters implement `ModelAdapter.step`, and
their behavior is unchanged. Whole-trajectory solvers implement `TrajectoryAdapter.simulate` and
return `SimulationTrace`; the engine never manufactures a fake fixed-step loop around them.
Observations are scalar mappings and cannot carry arbitrary executable objects.

Resolution order is explicit: a Python API caller may supply an adapter instance; otherwise a
built-in model name resolves from the immutable registry; otherwise a schema-v2 `adapter` section
may name an absolute dotted module and factory. Loading that factory executes trusted user code.
Configuration validation alone checks syntax and does not import the module.

An adapter supplies scientific judgment: initial conditions, state advance, observables, qualitative classification, and invariants. The engine supplies operational judgment: search bounds, retention, failure containment, hashes, artifacts, and policy exits.

## Determinism and replay boundary

PhaseProbe controls seeds, canonical configuration serialization, fixed command order, search
grids, state perturbations, trace retention, and artifact hashing. An external adapter remains
responsible for solver settings, thread behavior, native library versions, and hardware-sensitive
arithmetic.

Step adapters default to exact classification/model-identity/trace-hash replay. Adaptive SciPy
adapters require tolerance replay: the fixture carries declared state/observable/invariant/grid/
endpoint/event tolerances and expected solver success. The original trace hash remains as artifact
integrity evidence but is not required to match numerically across environments.

## Artifact safety

Trace points are capped per series. Run IDs combine UTC time and an evidence digest. Replay fixtures carry a schema version and SHA-256 over every unsigned field. Generated tests copy a validated fixture into `tests/generated/fixtures/` and contain only a sanitized identifier plus a fixed relative path.

## Extension checklist

1. Give the adapter a stable explicit `identity` version and serialize configuration separately
   from callable code.
2. Make `initial_state` deterministic for the declared seed.
3. Return the same state dimension after every step.
4. Define classifier thresholds in configuration tolerances.
5. Distinguish mathematical invariants from diagnostic bounds in invariant details.
6. Select `exact` only where byte-identical retained values are justified; otherwise declare a
   complete tolerance policy.
7. Add positive, negative-control, invalid-state, repeatability, and replay tests.
8. Cite a primary technical source for the model and document solver limitations.
