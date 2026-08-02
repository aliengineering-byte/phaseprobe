"""Typed public model-adapter and result interfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias, runtime_checkable

Scalar: TypeAlias = float | int | str
State: TypeAlias = tuple[float, ...]
Parameters: TypeAlias = Mapping[str, float]
ModelConfig: TypeAlias = Mapping[str, object]
Tolerances: TypeAlias = Mapping[str, float]
ReplayMode: TypeAlias = Literal["exact", "tolerance"]


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


@dataclass(frozen=True, slots=True)
class SimulationTrace:
    """One completed trajectory-level simulation before engine retention.

    ``metadata`` contains JSON-serializable execution evidence supplied by the adapter. It must
    describe solver termination and the numerical environment without embedding callable code.
    """

    points: tuple[TracePoint, ...]
    final_state: State
    success: bool
    status: int
    message: str
    metadata: Mapping[str, object]


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


@runtime_checkable
class TrajectoryAdapter(Protocol):
    """Optional protocol for solvers that naturally integrate a whole trajectory.

    The engine dispatches this protocol without manufacturing a fake fixed-step loop. Search,
    perturbation, policy, artifact, replay, and reporting code is shared with ``ModelAdapter``.
    """

    name: str
    identity: str
    dimensions: tuple[str, ...]

    @property
    def replay_mode(self) -> ReplayMode:
        """Declare whether numerical replay is exact or tolerance-based."""

    def initial_state(self, config: ModelConfig, seed: int) -> State:
        """Return the declared initial state for ``config`` and ``seed``."""

    def simulate(
        self,
        initial_state: State,
        parameters: Parameters,
        config: ModelConfig,
        seed: int,
    ) -> SimulationTrace:
        """Integrate once and return a finite, serializable trajectory."""

    def observe(self, trace: SimulationTrace) -> Mapping[str, Scalar]:
        """Return bounded summary observables for the completed trajectory."""

    def classify(self, trace: SimulationTrace, tolerances: Tolerances) -> str:
        """Return a qualitative class from retained trajectory evidence."""

    def invariants(
        self,
        trace: SimulationTrace,
        parameters: Parameters,
        tolerances: Tolerances,
    ) -> list[InvariantResult]:
        """Evaluate declared invariants or boundedness conditions."""

    def configuration(self) -> Mapping[str, object]:
        """Serialize adapter settings and explicit identity, never callable source."""
