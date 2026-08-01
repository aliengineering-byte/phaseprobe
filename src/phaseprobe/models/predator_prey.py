"""Lotka-Volterra predator-prey adapter with a conserved-quantity diagnostic."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from phaseprobe.models._common import initial_state, parameter, rk4_step
from phaseprobe.types import InvariantResult, Parameters, State, Tolerances, TracePoint


class PredatorPreyAdapter:
    """Conservative two-species Lotka-Volterra equations."""

    name = "predator-prey"
    identity = "phaseprobe.builtin.predator-prey:v1"
    dimensions = ("prey", "predator")

    def initial_state(self, config: Mapping[str, object], seed: int) -> State:
        del seed
        return initial_state(config, self.dimensions, (10.0, 5.0))

    def step(self, state: State, parameters: Parameters, dt: float) -> State:
        alpha = parameter(parameters, "alpha", 1.1)
        beta = parameter(parameters, "beta", 0.4)
        delta = parameter(parameters, "delta", 0.1)
        gamma = parameter(parameters, "gamma", 0.4)

        def derivative(current: State) -> State:
            prey, predator = current
            return (
                alpha * prey - beta * prey * predator,
                delta * prey * predator - gamma * predator,
            )

        return rk4_step(state, dt, derivative)

    def observe(self, state: State) -> Mapping[str, float]:
        return {"prey": state[0], "predator": state[1]}

    def classify(self, trace: Sequence[TracePoint], tolerances: Tolerances) -> str:
        del tolerances
        if not trace:
            return "unresolved"
        minima = [min(point.state[index] for point in trace) for index in (0, 1)]
        return "bounded-positive-oscillation" if min(minima) > 0.0 else "invalid-population"

    def invariants(
        self,
        trace: Sequence[TracePoint],
        parameters: Parameters,
        tolerances: Tolerances,
    ) -> list[InvariantResult]:
        alpha = parameter(parameters, "alpha", 1.1)
        beta = parameter(parameters, "beta", 0.4)
        delta = parameter(parameters, "delta", 0.1)
        gamma = parameter(parameters, "gamma", 0.4)
        tolerance = tolerances.get("invariant_drift", 1e-5)

        def conserved(state: State) -> float:
            prey, predator = state
            if prey <= 0.0 or predator <= 0.0:
                return math.inf
            return (
                delta * prey - gamma * math.log(prey) + beta * predator - alpha * math.log(predator)
            )

        values = [conserved(point.state) for point in trace]
        drift = max((abs(value - values[0]) for value in values), default=0.0)
        min_population = min((value for point in trace for value in point.state), default=0.0)
        return [
            InvariantResult(
                name="lotka-volterra-conserved-quantity",
                passed=math.isfinite(drift) and drift <= tolerance,
                measured=drift,
                tolerance=tolerance,
                detail="Maximum retained drift from the initial value of the analytic first integral.",
            ),
            InvariantResult(
                name="positive-populations",
                passed=min_population > 0.0,
                measured=min_population,
                tolerance=0.0,
                detail="Both populations must remain strictly positive over the retained trajectory.",
            ),
        ]
