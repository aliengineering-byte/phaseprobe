"""Lorenz-system adapter for finite-time trajectory-divergence evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from phaseprobe.models._common import initial_state, parameter, rk4_step
from phaseprobe.types import InvariantResult, Parameters, State, Tolerances, TracePoint


class LorenzAdapter:
    """Classical three-variable Lorenz equations integrated with fixed-step RK4."""

    name = "lorenz"
    identity = "phaseprobe.builtin.lorenz:v1"
    dimensions = ("x", "y", "z")

    def initial_state(self, config: Mapping[str, object], seed: int) -> State:
        del seed
        return initial_state(config, self.dimensions, (1.0, 1.0, 1.0))

    def step(self, state: State, parameters: Parameters, dt: float) -> State:
        sigma = parameter(parameters, "sigma", 10.0)
        rho = parameter(parameters, "rho", 28.0)
        beta = parameter(parameters, "beta", 8.0 / 3.0)

        def derivative(current: State) -> State:
            x, y, z = current
            return (sigma * (y - x), x * (rho - z) - y, x * y - beta * z)

        return rk4_step(state, dt, derivative)

    def observe(self, state: State) -> Mapping[str, float]:
        x, y, z = state
        return {"x": x, "y": y, "z": z, "radius": math.sqrt(x * x + y * y + z * z)}

    def classify(self, trace: Sequence[TracePoint], tolerances: Tolerances) -> str:
        del tolerances
        signs = {point.state[0] >= 0.0 for point in trace}
        if len(signs) > 1:
            return "two-lobe-finite-time-trajectory"
        if trace and trace[-1].state[0] >= 0.0:
            return "positive-lobe-finite-time-trajectory"
        return "negative-lobe-finite-time-trajectory"

    def invariants(
        self,
        trace: Sequence[TracePoint],
        parameters: Parameters,
        tolerances: Tolerances,
    ) -> list[InvariantResult]:
        del parameters
        bound = tolerances.get("state_bound", 100.0)
        measured = max((abs(value) for point in trace for value in point.state), default=0.0)
        return [
            InvariantResult(
                name="declared-finite-state-bound",
                passed=math.isfinite(measured) and measured <= bound,
                measured=measured,
                tolerance=bound,
                detail="A diagnostic finite-time bound, not a mathematical invariant of the Lorenz system.",
            )
        ]
