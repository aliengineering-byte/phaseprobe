"""Genuine SciPy-backed Lorenz and Lotka-Volterra reference adapters."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
import numpy.typing as npt

from phaseprobe.adapters.scipy import SolveIVPAdapter
from phaseprobe.types import (
    InvariantResult,
    Parameters,
    Scalar,
    SimulationTrace,
    State,
    Tolerances,
)

FloatArray = npt.NDArray[np.float64]


def lorenz_rhs(time: float, state: FloatArray, parameters: Parameters) -> tuple[float, ...]:
    """Classic Lorenz equations; time is accepted by the solve_ivp contract."""

    x, y, z = state
    sigma = parameters["sigma"]
    rho = parameters["rho"]
    beta = parameters["beta"]
    return (sigma * (y - x), x * (rho - z) - y, x * y - beta * z)


def lorenz_observable(time: float, state: State, parameters: Parameters) -> Mapping[str, Scalar]:
    x, y, z = state
    return {"x": x, "y": y, "z": z, "radius": math.sqrt(x * x + y * y + z * z)}


def lorenz_classifier(trace: SimulationTrace, tolerances: Tolerances) -> str:
    bound = tolerances.get("state_bound", 100.0)
    maximum = max(abs(value) for point in trace.points for value in point.state)
    return "bounded-finite-window" if maximum <= bound else "declared-bound-exceeded"


def lorenz_invariants(
    trace: SimulationTrace, parameters: Parameters, tolerances: Tolerances
) -> list[InvariantResult]:
    bound = tolerances.get("state_bound", 100.0)
    maximum = max(abs(value) for point in trace.points for value in point.state)
    return [
        InvariantResult(
            name="declared-state-bound",
            passed=maximum <= bound,
            measured=maximum,
            tolerance=bound,
            detail="Maximum absolute state over the declared finite observation window.",
        )
    ]


def lorenz_adapter(values: Mapping[str, object]) -> SolveIVPAdapter:
    """Factory named by the explicit CLI configuration."""

    return SolveIVPAdapter.from_config(
        name="lorenz-scipy",
        rhs=lorenz_rhs,
        values=values,
        observable=lorenz_observable,
        classifier=lorenz_classifier,
        invariant=lorenz_invariants,
    )


def predator_prey_rhs(time: float, state: FloatArray, parameters: Parameters) -> tuple[float, ...]:
    prey, predator = state
    alpha = parameters["alpha"]
    beta = parameters["beta"]
    delta = parameters["delta"]
    gamma = parameters["gamma"]
    return (
        alpha * prey - beta * prey * predator,
        delta * prey * predator - gamma * predator,
    )


def _first_integral(state: State, parameters: Parameters) -> float:
    prey, predator = state
    if prey <= 0.0 or predator <= 0.0:
        return math.inf
    return (
        parameters["delta"] * prey
        - parameters["gamma"] * math.log(prey)
        + parameters["beta"] * predator
        - parameters["alpha"] * math.log(predator)
    )


def predator_prey_observable(
    time: float, state: State, parameters: Parameters
) -> Mapping[str, Scalar]:
    return {
        "prey": state[0],
        "predator": state[1],
        "first_integral": _first_integral(state, parameters),
    }


def predator_prey_classifier(trace: SimulationTrace, tolerances: Tolerances) -> str:
    positive = all(point.state[0] > 0.0 and point.state[1] > 0.0 for point in trace.points)
    return "positive-oscillation" if positive else "non-positive-population"


def predator_prey_invariants(
    trace: SimulationTrace, parameters: Parameters, tolerances: Tolerances
) -> list[InvariantResult]:
    threshold = tolerances.get("invariant_drift", 1e-8)
    reference = _first_integral(trace.points[0].state, parameters)
    drift = max(abs(_first_integral(point.state, parameters) - reference) for point in trace.points)
    minimum_population = min(value for point in trace.points for value in point.state)
    return [
        InvariantResult(
            name="lotka-volterra-first-integral-drift",
            passed=math.isfinite(drift) and drift <= threshold,
            measured=drift,
            tolerance=threshold,
            detail="Maximum absolute drift of the declared Lotka-Volterra first integral.",
        ),
        InvariantResult(
            name="positive-populations",
            passed=minimum_population > 0.0,
            measured=minimum_population,
            tolerance=0.0,
            detail="Minimum retained population; the policy requires a value strictly above zero.",
        ),
    ]


def predator_prey_adapter(values: Mapping[str, object]) -> SolveIVPAdapter:
    """Factory named by the explicit CLI configuration."""

    return SolveIVPAdapter.from_config(
        name="predator-prey-scipy",
        rhs=predator_prey_rhs,
        values=values,
        observable=predator_prey_observable,
        classifier=predator_prey_classifier,
        invariant=predator_prey_invariants,
    )


__all__ = ["lorenz_adapter", "predator_prey_adapter"]
