# SciPy `solve_ivp` audit

Reviewed 2026-08-02 against SciPy 1.18.0, the current stable release, using the
[official API reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html),
the tagged public
[`ivp.py`](https://github.com/scipy/scipy/blob/v1.18.0/scipy/integrate/_ivp/ivp.py) and
[`base.py`](https://github.com/scipy/scipy/blob/v1.18.0/scipy/integrate/_ivp/base.py) sources,
and the [1.18.0 release](https://github.com/scipy/scipy/releases/tag/v1.18.0).
PhaseProbe uses only the public `scipy.integrate.solve_ivp` function and public result fields.

## Public contract reviewed

The public signature is `solve_ivp(fun, t_span, y0, method='RK45', t_eval=None,
dense_output=False, events=None, vectorized=False, args=None, **options)`.

| area | reviewed behavior | PhaseProbe policy |
| --- | --- | --- |
| RHS | `fun(t, y)` returns the same shape as `y`; `args` can extend all user callables | Close over an immutable parameter mapping; reject shape mismatch, complex output, NaN, or infinity |
| `t_span` | Two float-convertible endpoints; forward and backward integration are supported | Require distinct finite endpoints and serialize both |
| `y0` | One-dimensional; tagged source rejects non-finite components | Require one finite real value per declared state name before calling SciPy |
| methods | `RK23`, `RK45`, `DOP853`, `Radau`, `BDF`, and `LSODA`, plus custom `OdeSolver` classes | Accept only the six public string names so configuration and replay remain portable and serializable |
| `t_eval` | Must be one-dimensional, strictly sorted in integration direction, and inside `t_span` | Always pass a controlled grid that includes both endpoints; allow explicit grids or bounded linspace specifications |
| `dense_output` | Returns an `OdeSolution` when enabled | Forward and record the option, but retain only the controlled finite grid and event states |
| events | Detect sign changes across solver steps; multiple crossings inside one step can be missed; `terminal` and `direction` affect handling | Wrap explicitly named event callables, retain bounded `t_events`/`y_events`, record terminal/direction, and never imply all roots were found |
| `vectorized` | May call `fun` with `(n, k)` state arrays; can accelerate finite-difference Jacobians for `Radau`/`BDF` but can slow small systems or other methods | Forward and record the declaration; the user callback remains responsible for the vectorized contract |
| `rtol`, `atol` | Local error target is `atol + rtol * abs(y)`; `atol` may be scalar or shape `(n,)`; defaults are `1e-3` and `1e-6` | Require positive finite values, validate vector length, serialize exact values, and make scientific examples choose explicit non-default values |
| `max_step` | Defaults to infinity and bounds the internal step when finite | Represent unbounded as JSON `null`; otherwise require a positive finite value and pass it explicitly |
| result | Public fields include `t`, `y`, `t_events`, `y_events`, `nfev`, `njev`, `nlu`, `status`, `message`, and `success` | Record every applicable field plus Python, NumPy, SciPy, machine, word-size, and byte-order evidence |
| status | `-1` is failed step, `0` reached `t_span` end, `1` terminated on event; success is `status >= 0` | Never classify an unsuccessful result; surface status and message as a numerical failure |

## Method and domain implications

SciPy recommends explicit `RK23`, `RK45`, and `DOP853` for non-stiff problems, with `DOP853`
for high precision. `Radau` and `BDF` target stiff problems; `LSODA` wraps ODEPACK and switches
between Adams and BDF formulas. Method selection is scientific configuration, not an
implementation detail, so PhaseProbe stores and replays it.

SciPy supports complex states only for some methods, and stiff complex problems require a
complex-differentiable RHS. PhaseProbe's common state protocol is deliberately a tuple of real
finite floats. `SolveIVPAdapter` therefore rejects complex state/output and tells users to split
real and imaginary components. This is narrower than SciPy, not a SciPy limitation.

SciPy validates finite `y0`, but intermediate non-finite RHS or result behavior can vary by
method and failure path. PhaseProbe independently validates RHS outputs, every retained time and
state, observables, events, and the final state. It treats solver exceptions, unsuccessful status,
and invalid values as different diagnostic evidence where possible.

## Adaptive replay and floating point

Adaptive step acceptance can change after small floating-point, compiler, architecture, NumPy,
or SciPy differences. A controlled `t_eval` makes comparison meaningful but does not make the
internal step sequence or interpolated values byte-identical. Therefore:

- built-in fixed-step adapters retain `exact` class/identity/trace-hash replay;
- SciPy trajectories use `tolerance` replay with declared state, observable, invariant, grid,
  endpoint, and event tolerances;
- every stored fixture and run artifact still has a SHA-256 integrity digest;
- environment evidence is preserved for interpretation but a version string is not substituted
  for numerical comparison.

This is tolerance-based numerical replay, never "exact deterministic replay."

## Supported versions

The optional extra is `numpy>=1.23.5,<2.5` and `scipy>=1.15,<1.19`. The lower bound preserves
PhaseProbe's Python 3.10 support through SciPy 1.15; the upper bound prevents silently claiming
support for an unreviewed future SciPy minor. The lock resolves and tests these representative
combinations:

| Python | representative SciPy | rationale |
| --- | --- | --- |
| 3.10 | 1.15.3 | Last supported minor line for Python 3.10 |
| 3.11 | 1.17.1 | Supported current bug-fix line for Python 3.11 |
| 3.12–3.14 | 1.18.0 | Audited current stable line |

SciPy 1.18.0 itself requires Python 3.12–3.14 and NumPy 2.0 or newer. Resolver metadata chooses
an older compatible SciPy within the declared PhaseProbe range on Python 3.10 and 3.11.

## Relevant upstream context

- [SciPy issue #18039](https://github.com/scipy/scipy/issues/18039) discusses default tolerance
  limitations, piecewise dynamics, `max_step`, and manual convergence checks.
- [SciPy issue #9686](https://github.com/scipy/scipy/issues/9686) discusses bounded internal work
  and minimum-step behavior.
- [SciPy issue #10319](https://github.com/scipy/scipy/issues/10319) records the distinction between
  a controlled `t_eval` grid and terminal event states returned through `y_events`.
- The Scientific Python discussion
  ["Design of callback for scipy.integrate.solve_ivp"](https://discuss.scientific-python.org/t/design-of-callback-for-scipy-integrate-solve-ivp/1672)
  concerns progress/control callbacks, not external qualitative regression evidence.

None duplicates PhaseProbe's external adapter, tolerance fixture, qualitative search, and pytest
materialization workflow, and this project requests no SciPy API change.
