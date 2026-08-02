# Prepared SciPy integration visibility proposal

Status: prepared for human review; not posted or submitted anywhere.

## Problem addressed

Real ODE applications need regression checks that survive routine solver and platform variation
without reducing a trajectory to an exact byte hash or one arbitrary endpoint assertion.
PhaseProbe adds a bounded layer around a user-declared `solve_ivp` model: search a parameter or
initial-state dimension, preserve qualitative transition/invariant evidence, and materialize the
declared comparison as pytest.

SciPy integrates trajectories. PhaseProbe searches declared dimensions, preserves qualitative
boundaries, and creates regressions. It neither replaces an ODE solver nor changes SciPy.

## Python example

```python
from phaseprobe import run_perturbation
from phaseprobe.adapters.scipy import SolveIVPAdapter

adapter = SolveIVPAdapter(
    name="lorenz-scipy",
    identity="my-lorenz-v1",
    rhs=lorenz_rhs,
    state_names=("x", "y", "z"),
    initial_state=(1.0, 1.0, 1.0),
    t_span=(0.0, 25.0),
    t_eval=1001,
    method="DOP853",
    rtol=1e-9,
    atol=1e-12,
    max_step=0.05,
    classifier=classify_lorenz,
)

outcome = run_perturbation(adapter, config)
```

The user supplies the RHS and scientific callbacks. PhaseProbe stores an explicit model identity
plus solver configuration metadata; it does not hash or serialize callable source.

## CLI example

```bash
python -m pip install "phaseprobe[scipy]"
phaseprobe perturb --config examples/scipy/lorenz.json
phaseprobe check --config examples/scipy/predator-prey.json
phaseprobe replay .phaseprobe/runs/<run-id>/replay.json
phaseprobe generate-test .phaseprobe/runs/<run-id>/replay.json
```

The `adapter.module`/`adapter.factory` configuration explicitly executes trusted Python model code
only when a command runs. JSON validation alone does not import it.

## Numerical validation

- Lorenz: a small initial-condition search reports only repeatable finite-time divergence over a
  declared 25-unit window and distance threshold. A five-unit negative control finds no crossing.
- Predator–prey: tight DOP853 settings preserve the declared first integral within policy. A
  deliberately loose RK23 configuration violates the same scientific policy, providing
  refinement/convergence evidence rather than assuming solver success implies accuracy.
- Windows and Linux CI cover Python 3.10, 3.12, and 3.14 with separate core-only and SciPy-extra
  jobs.

## Replay semantics

Built-in fixed-step adapters use exact retained-trace hashes. Adaptive SciPy runs use declared
tolerances for states, observables, invariant outcomes and thresholds, retained times, endpoints,
and event times. The fixture itself remains integrity-hashed and records Python/NumPy/SciPy,
method, tolerances, grid, maximum step, initial state, parameters, events, termination, and
evaluation counts. A tolerance match is not called exact deterministic replay.

## Limitations

- Evidence is finite-window and model-policy-specific; no global proof, formal Lyapunov exponent,
  or exact bifurcation point is claimed.
- Event detection can miss multiple zero crossings inside one solver step.
- PhaseProbe's common serialized state is real-valued; complex systems must split components.
- User-selected Python adapter modules execute code and must be trusted.
- Cross-platform adaptive results can differ within declared tolerances.

## Duplication check

Searches reviewed
[SciPy #18039](https://github.com/scipy/scipy/issues/18039),
[#9686](https://github.com/scipy/scipy/issues/9686),
[#10319](https://github.com/scipy/scipy/issues/10319), and the Scientific Python
[`solve_ivp` callback discussion](https://discuss.scientific-python.org/t/design-of-callback-for-scipy-integrate-solve-ivp/1672).
They cover tolerance choice, solver work bounds, event return semantics, and callbacks. They do not
propose this external qualitative regression/replay layer.

## Public demo

Project quick start and terminal assets:
https://github.com/aliengineering-byte/phaseprobe#use-with-scipy

## Suggested discussion title

`PhaseProbe: tolerance-aware qualitative regression fixtures for SciPy solve_ivp models`

## Human-editable outreach message

> I built an optional, dependency-isolated PhaseProbe adapter for public `solve_ivp` models. It
> keeps SciPy responsible for integration and adds bounded qualitative searches, explicit
> tolerance replay, and generated pytest regressions. The examples include finite-time Lorenz
> divergence with a negative control and a Lotka–Volterra invariant refinement check. I reviewed
> related tolerance, event, work-bound, and callback discussions and do not propose a SciPy API
> change. Would this workflow be useful to users maintaining scientific simulation regressions?
