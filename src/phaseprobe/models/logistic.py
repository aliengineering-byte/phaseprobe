"""Logistic-map adapter and finite-period classifier."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from phaseprobe.models._common import initial_state, parameter
from phaseprobe.types import InvariantResult, Parameters, State, Tolerances, TracePoint


class LogisticMapAdapter:
    """The discrete logistic map ``x[n+1] = r*x[n]*(1-x[n])``."""

    name = "logistic-map"
    identity = "phaseprobe.builtin.logistic-map:v1"
    dimensions = ("x",)

    def initial_state(self, config: Mapping[str, object], seed: int) -> State:
        del seed
        return initial_state(config, self.dimensions, (0.2,))

    def step(self, state: State, parameters: Parameters, dt: float) -> State:
        del dt
        r = parameter(parameters, "r", 3.44)
        x = state[0]
        return (r * x * (1.0 - x),)

    def observe(self, state: State) -> Mapping[str, float]:
        return {"x": state[0]}

    def classify(self, trace: Sequence[TracePoint], tolerances: Tolerances) -> str:
        values = [point.state[0] for point in trace]
        tolerance = tolerances.get("period", 1e-8)
        for period in (1, 2, 4, 8, 16):
            if len(values) < 4 * period:
                continue
            tail = values[-4 * period :]
            error = max(
                abs(tail[index] - tail[index - period]) for index in range(period, len(tail))
            )
            if error <= tolerance:
                return f"period-{period}"
        return "aperiodic-or-unresolved"

    def invariants(
        self,
        trace: Sequence[TracePoint],
        parameters: Parameters,
        tolerances: Tolerances,
    ) -> list[InvariantResult]:
        del parameters, tolerances
        values = [point.state[0] for point in trace]
        violation = max((max(-value, value - 1.0, 0.0) for value in values), default=0.0)
        return [
            InvariantResult(
                name="unit-interval-boundedness",
                passed=math.isfinite(violation) and violation == 0.0,
                measured=violation,
                tolerance=0.0,
                detail="For 0 <= r <= 4 and 0 <= x <= 1, retained states should remain in [0, 1].",
            )
        ]
