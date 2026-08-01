"""Typed public model-adapter and result interfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeAlias, runtime_checkable

Scalar: TypeAlias = float | int | str
State: TypeAlias = tuple[float, ...]
Parameters: TypeAlias = Mapping[str, float]
ModelConfig: TypeAlias = Mapping[str, object]
Tolerances: TypeAlias = Mapping[str, float]


@dataclass(frozen=True, slots=True)
class TracePoint:
    """One retained point from a bounded simulation trace."""

    step: int
    time: float
    state: State
    observations: Mapping[str, Scalar]


@dataclass(frozen=True, slots=True)
class InvariantResult:
    """Result of evaluating a declared model invariant or boundedness rule."""

    name: str
    passed: bool
    measured: float
    tolerance: float
    detail: str


@runtime_checkable
class ModelAdapter(Protocol):
    """Small interface implemented by built-in and downstream simulation adapters.

    The explicit state tuple makes perturbation, serialization, and finite-value validation
    deterministic. Classifiers and invariants receive declared tolerances rather than hiding
    thresholds inside the engine.
    """

    name: str
    identity: str
    dimensions: tuple[str, ...]

    def initial_state(self, config: ModelConfig, seed: int) -> State:
        """Return a deterministic initial state for ``config`` and ``seed``."""

    def step(self, state: State, parameters: Parameters, dt: float) -> State:
        """Advance exactly one declared step."""

    def observe(self, state: State) -> Mapping[str, Scalar]:
        """Expose bounded scalar observables used in reports and classification."""

    def classify(self, trace: Sequence[TracePoint], tolerances: Tolerances) -> str:
        """Return a qualitative class using only retained trace evidence."""

    def invariants(
        self,
        trace: Sequence[TracePoint],
        parameters: Parameters,
        tolerances: Tolerances,
    ) -> list[InvariantResult]:
        """Evaluate declared invariants or boundedness conditions."""
