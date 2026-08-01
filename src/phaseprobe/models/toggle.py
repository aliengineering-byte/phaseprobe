"""Small mutually repressing genetic-toggle adapter."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from phaseprobe.models._common import initial_state, parameter, rk4_step
from phaseprobe.types import InvariantResult, Parameters, State, Tolerances, TracePoint


class GeneticToggleAdapter:
    """Dimensionless two-gene mutual-repression model."""

    name = "genetic-toggle"
    identity = "phaseprobe.builtin.genetic-toggle:v1"
    dimensions = ("u", "v")

    def initial_state(self, config: Mapping[str, object], seed: int) -> State:
        del seed
        return initial_state(config, self.dimensions, (3.0, 0.2))

    def step(self, state: State, parameters: Parameters, dt: float) -> State:
        alpha_u = parameter(parameters, "alpha_u", 3.0)
        alpha_v = parameter(parameters, "alpha_v", 3.0)
        hill_u = parameter(parameters, "hill_u", 2.0)
        hill_v = parameter(parameters, "hill_v", 2.0)

        def derivative(current: State) -> State:
            u, v = current
            return (
                alpha_u / (1.0 + v**hill_v) - u,
                alpha_v / (1.0 + u**hill_u) - v,
            )

        return rk4_step(state, dt, derivative)

    def observe(self, state: State) -> Mapping[str, float]:
        u, v = state
        return {"u": u, "v": v, "difference": u - v}

    def classify(self, trace: Sequence[TracePoint], tolerances: Tolerances) -> str:
        if not trace:
            return "unresolved"
        threshold = tolerances.get("dominance", 0.05)
        difference = trace[-1].state[0] - trace[-1].state[1]
        if difference > threshold:
            return "u-dominant"
        if difference < -threshold:
            return "v-dominant"
        return "balanced"

    def invariants(
        self,
        trace: Sequence[TracePoint],
        parameters: Parameters,
        tolerances: Tolerances,
    ) -> list[InvariantResult]:
        del parameters
        bound = tolerances.get("state_bound", 10.0)
        values = [value for point in trace for value in point.state]
        low = min(values, default=0.0)
        high = max(values, default=0.0)
        violation = max(-low, high - bound, 0.0)
        return [
            InvariantResult(
                name="nonnegative-declared-bound",
                passed=math.isfinite(violation) and violation == 0.0,
                measured=violation,
                tolerance=0.0,
                detail=f"Concentrations must remain in the declared interval [0, {bound:g}].",
            )
        ]
