# Limitations

- A reported bracket is finite-time, classifier-specific numerical evidence, not an exact bifurcation point.
- A smallest result is the smallest reproducible candidate found by the declared finite grid/refinement, not a proof of global minimality.
- The Lorenz metric is a finite-time divergence rate, not a Lyapunov exponent and not by itself proof of chaos.
- Fixed-step RK4 is transparent but not a substitute for adaptive solvers, stiffness detection, convergence studies, interval arithmetic, or rigorous numerics.
- Exact trace hashes can detect harmless floating-point differences across architectures or native math libraries. v0.1.0 has no configurable fuzzy replay mode.
- Only one scan parameter or one initial-state dimension is active per search. Non-monotonic multidimensional delta debugging is future work.
- Built-in models are small validation examples. Their success does not validate a downstream scientific model.
- Seeds are explicit, but an external adapter can still be nondeterministic through threads, native libraries, unordered data, clocks, file systems, or unrecorded external state.
- Trace retention is capped and may omit earlier behavior. Configuration must preserve a scientifically adequate observation window.
- Classification thresholds can create boundary ambiguity. The scan stops refinement when a midpoint matches neither stable endpoint class, but it cannot remove classifier bias.
- Replay fixtures can expose model configuration and state. Review them before committing if a downstream adapter contains sensitive data.
- Name research found no exact package collision on 2026-08-01, but it is not legal or trademark advice.
