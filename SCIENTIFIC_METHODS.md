# Scientific methods

## SciPy trajectory evidence

SciPy integrates trajectories. PhaseProbe searches declared dimensions, preserves qualitative
boundaries, and creates regressions. `SolveIVPAdapter` passes a real-valued RHS, controlled
evaluation grid, method, `rtol`, scalar/vector `atol`, `max_step`, vectorization declaration, and
optional named events to the public `solve_ivp` API. It records termination status/message and
evaluation counts before PhaseProbe applies model-specific observables, classification, invariants,
search, policy, artifacts, and replay.

Adaptive error control is local and method-specific. A successful solver status is necessary but
not sufficient evidence that a scientific invariant or qualitative policy is resolved. The
predator–prey examples therefore compare a tightly resolved DOP853 run with a deliberately loose
RK23 control. The Lorenz examples use a controlled common `t_eval` grid for twin-distance evidence
and report only finite-time divergence within the declared window.

Tolerance replay compares retained times/states, named numeric observables, classifier outcome,
invariant results and stored thresholds, endpoint/event evidence, and expected solver success.
Environment and solver evidence are retained for interpretation. Artifact hashes still detect
fixture tampering, but an adaptive trace hash is not required to match across supported platforms.
The adapter validation suite checks an exponential system with an analytic terminal crossing in
both forward and backward integration directions; this validates event plumbing, not exhaustive
root detection between adaptive internal steps.
See [the complete SciPy audit](docs/SCIPY_SOLVE_IVP_AUDIT.md).

PhaseProbe 0.1.0 produces bounded computational evidence. It does not perform formal verification, model validation against observations, or computer-assisted proof.

## Execution record

Every result records the model identity, parameters, initial state, explicit seed, integration or iteration settings, tolerance map, burn-in, retained observation window, classification rule, refinement rule, invalid-state policy, capped trace, trace hash, and repeatability evidence. JSON objects are serialized with sorted keys and disallow NaN.

## Integration and iteration

The logistic map advances its exact recurrence once per declared step. The Lorenz, predator–prey, and genetic-toggle examples use classical fixed-step fourth-order Runge–Kutta (RK4). Fixed steps make the execution path transparent and dependency-free; they do not guarantee an accurate solution. The predator–prey positive/negative pair demonstrates why step refinement and an analytic invariant matter.

PhaseProbe stops a run as `invalid integration` when the adapter returns a wrong state dimension, NaN, infinity, a value beyond the declared hard state limit, or raises an arithmetic/domain failure. This is distinct from an invariant violation on an otherwise finite trajectory.

## Qualitative classification

Classification belongs to the adapter and is configured by explicit tolerances:

- Logistic: test retained tail recurrence for periods 1, 2, 4, 8, and 16 in that order. Failure to converge within the finite burn-in/window is `aperiodic-or-unresolved`, not a declaration of chaos.
- Lorenz: label finite-time lobe visitation only. The perturbation predicate is Euclidean twin-trajectory separation.
- Predator–prey: require retained positive populations; separately evaluate drift of the analytic Lotka–Volterra first integral.
- Genetic toggle: compare terminal `u-v` against a declared dominance tolerance.

Classifier output is model- and window-specific. A class change is a `qualitative regime change` under that rule, not automatically a physical phase transition.

## Parameter scanning

`scan` evaluates an inclusive deterministic one-dimensional grid and finds the first adjacent class change. It then probes midpoints while the midpoint reproduces one of the two stable endpoint classes. If a midpoint reproduces neither class, refinement stops instead of relabeling ambiguity. Final endpoints are rerun and their exact trace hashes compared.

The output is a numerical transition bracket. It is `bifurcation evidence` only when the classifier and model justify that interpretation, and it is never reported as an exact bifurcation point.

## Initial-state perturbation

`perturb` runs a baseline plus candidates ordered from smallest to largest over a linear or logarithmic declared range. A predicate may require a target class or a maximum twin-trajectory distance. When a non-trigger/trigger interval exists, deterministic binary refinement narrows it. The smallest triggering candidate is repeated exactly.

For Lorenz, PhaseProbe computes

```text
finite-time divergence rate = log(max separation / initial separation) / elapsed window
```

as a descriptive finite-window quantity. The method does not implement tangent-space evolution, renormalization, asymptotic limiting, or convergence validation required to claim a Lyapunov exponent.

## Counterexample minimization

For one monotonic declared predicate, bracketed binary refinement is used. PhaseProbe does not assume every simulation predicate is monotonic. v0.1.0 only automates one-dimensional scans and one active perturbation dimension; it therefore does not claim multidimensional delta debugging. The reported phrase is always “smallest reproducible change found within the declared search space.”

## Invariants

An invariant result includes its name, pass/fail value, measured value, tolerance, and detail. Some checks, such as the Lorenz finite-state bound, are explicitly diagnostic bounds rather than mathematical invariants. Passing an invariant does not validate the model or prove solver convergence.

## Primary sources for examples

- Robert M. May, “Simple mathematical models with very complicated dynamics,” *Nature* 261, 459–467 (1976), [doi:10.1038/261459a0](https://www.nature.com/articles/261459a0).
- Edward N. Lorenz, “Deterministic Nonperiodic Flow,” *Journal of the Atmospheric Sciences* 20, 130–141 (1963), [publisher record](https://journals.ametsoc.org/view/journals/atsc/20/2/1520-0469_1963_020_0130_dnf_2_0_co_2.xml).
- Alfred J. Lotka, “Analytical Note on Certain Rhythmic Relations in Organic Systems,” *PNAS* 6, 410–415 (1920), [doi:10.1073/pnas.6.7.410](https://doi.org/10.1073/pnas.6.7.410).
- Timothy S. Gardner, Charles R. Cantor, and James J. Collins, “Construction of a genetic toggle switch in *Escherichia coli*,” *Nature* 403, 339–342 (2000), [doi:10.1038/35002131](https://www.nature.com/articles/35002131).

Private books informed only bounded conceptual orientation. No public claim depends on them, and no PDF, extracted text, quotation, illustration, or chapter substitute is distributed.
