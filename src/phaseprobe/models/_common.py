"""Shared validation and fixed-step integration helpers for built-in adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from phaseprobe.errors import ConfigurationError
from phaseprobe.types import State

Derivative = Callable[[State], State]


def float_value(values: Mapping[str, object], name: str, default: float | None = None) -> float:
    """Read a finite-number-shaped value; runtime finite checks happen in the engine."""

    value = values.get(name, default)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a number")
    return float(value)


def initial_state(
    config: Mapping[str, object], dimensions: Sequence[str], defaults: State
) -> State:
    """Read an optional named initial-state object."""

    raw = config.get("initial_state")
    if raw is None:
        return defaults
    if not isinstance(raw, dict):
        raise ConfigurationError("model.initial_state must be an object")
    values = raw
    return tuple(float_value(values, dimension) for dimension in dimensions)


def parameter(parameters: Mapping[str, float], name: str, default: float) -> float:
    """Read a model parameter with a documented default."""

    return float(parameters.get(name, default))


def rk4_step(state: State, dt: float, derivative: Derivative) -> State:
    """Advance an autonomous ODE with a deterministic classical RK4 step."""

    k1 = derivative(state)
    k2 = derivative(
        tuple(value + 0.5 * dt * slope for value, slope in zip(state, k1, strict=False))
    )
    k3 = derivative(
        tuple(value + 0.5 * dt * slope for value, slope in zip(state, k2, strict=False))
    )
    k4 = derivative(tuple(value + dt * slope for value, slope in zip(state, k3, strict=False)))
    return tuple(
        value + (dt / 6.0) * (a + 2.0 * b + 2.0 * c + d)
        for value, a, b, c, d in zip(state, k1, k2, k3, k4, strict=False)
    )
