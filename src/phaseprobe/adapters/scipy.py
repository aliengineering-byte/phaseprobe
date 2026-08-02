"""Trajectory-level adapter for the public :func:`scipy.integrate.solve_ivp` API."""

from __future__ import annotations

import hashlib
import math
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Literal, TypeAlias, cast

try:
    import numpy as np
    import numpy.typing as npt
    import scipy
    from scipy.integrate import solve_ivp
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in an isolated interpreter
    raise ImportError(
        "PhaseProbe SciPy support is optional; install it with "
        '`python -m pip install "phaseprobe[scipy]"`.'
    ) from exc

from phaseprobe.config import canonical_json
from phaseprobe.errors import ConfigurationError, NumericalFailure
from phaseprobe.types import (
    InvariantResult,
    ModelConfig,
    Parameters,
    Scalar,
    SimulationTrace,
    State,
    Tolerances,
    TracePoint,
)

FloatArray: TypeAlias = npt.NDArray[np.float64]
RHSCallback: TypeAlias = Callable[[float, FloatArray, Parameters], object]
EventCallback: TypeAlias = Callable[[float, FloatArray, Parameters], float]
ObservableCallback: TypeAlias = Callable[[float, State, Parameters], Mapping[str, Scalar]]
ClassifierCallback: TypeAlias = Callable[[SimulationTrace, Tolerances], str]
InvariantCallback: TypeAlias = Callable[
    [SimulationTrace, Parameters, Tolerances], list[InvariantResult]
]

SUPPORTED_METHODS = ("RK23", "RK45", "DOP853", "Radau", "BDF", "LSODA")
MAX_EVALUATION_POINTS = 100_000
MAX_EVENT_POINTS = 10_000


def _finite_number(value: object, context: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigurationError(f"{context} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ConfigurationError(f"{context} must be finite")
    return result


def _finite_sequence(value: object, context: str) -> tuple[float, ...]:
    if not isinstance(value, list | tuple):
        raise ConfigurationError(f"{context} must be an array of real numbers")
    return tuple(_finite_number(item, f"{context}[{index}]") for index, item in enumerate(value))


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{context} must be a non-empty string")
    return value


def _mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{context} must be an object")
    return cast(Mapping[str, object], value)


@dataclass(frozen=True, slots=True)
class EventSpec:
    """Named, explicitly configured solve_ivp event callback."""

    name: str
    function: EventCallback
    terminal: bool | int = False
    direction: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ConfigurationError("event name must be non-empty")
        terminal = self.terminal
        if not isinstance(terminal, bool) and (not isinstance(terminal, int) or terminal <= 0):
            raise ConfigurationError("event terminal must be a boolean or positive integer")
        if not math.isfinite(float(self.direction)):
            raise ConfigurationError("event direction must be finite")

    def as_dict(self) -> dict[str, object]:
        """Serialize event policy without serializing executable code."""

        return {
            "name": self.name,
            "terminal": self.terminal,
            "direction": float(self.direction),
        }


class _EventWrapper:
    def __init__(self, spec: EventSpec, parameters: Parameters) -> None:
        self._spec = spec
        self._parameters = parameters
        self.terminal = spec.terminal
        self.direction = float(spec.direction)

    def __call__(self, time: float, state: FloatArray) -> float:
        value = float(self._spec.function(time, state, self._parameters))
        if not math.isfinite(value):
            raise NumericalFailure(
                f"invalid event value from {self._spec.name!r}: expected a finite scalar"
            )
        return value


class SolveIVPAdapter:
    """Typed real-valued trajectory adapter backed by SciPy ``solve_ivp``.

    ``identity`` is an explicit user-controlled identifier. PhaseProbe combines it with a digest
    of serialized numerical configuration; callable source is never inspected or stored.
    """

    replay_mode: Literal["tolerance"] = "tolerance"

    def __init__(
        self,
        *,
        name: str,
        identity: str,
        rhs: RHSCallback,
        state_names: Sequence[str],
        initial_state: Sequence[float],
        t_span: tuple[float, float],
        t_eval: Sequence[float] | int = 501,
        method: str = "RK45",
        rtol: float = 1e-3,
        atol: float | Sequence[float] = 1e-6,
        max_step: float | None = None,
        events: Sequence[EventSpec] = (),
        observable: ObservableCallback | None = None,
        classifier: ClassifierCallback | None = None,
        invariant: InvariantCallback | None = None,
        vectorized: bool = False,
        dense_output: bool = False,
    ) -> None:
        self.name = _string(name, "name")
        self.explicit_identity = _string(identity, "identity")
        self.dimensions = tuple(_string(item, "state_names item") for item in state_names)
        if not self.dimensions or len(set(self.dimensions)) != len(self.dimensions):
            raise ConfigurationError("state_names must be non-empty and unique")
        self._initial_state = _finite_sequence(tuple(initial_state), "initial_state")
        if len(self._initial_state) != len(self.dimensions):
            raise ConfigurationError("initial_state length must match state_names")
        self._t_span = (
            _finite_number(t_span[0], "t_span[0]"),
            _finite_number(t_span[1], "t_span[1]"),
        )
        if self._t_span[0] == self._t_span[1]:
            raise ConfigurationError("t_span endpoints must differ")
        self._t_eval, self._grid_configuration = self._evaluation_grid(t_eval)
        if method not in SUPPORTED_METHODS:
            raise ConfigurationError(f"method must be one of {', '.join(SUPPORTED_METHODS)}")
        self.method = method
        self.rtol = _finite_number(rtol, "rtol")
        if self.rtol <= 0.0:
            raise ConfigurationError("rtol must be positive")
        if isinstance(atol, int | float) and not isinstance(atol, bool):
            scalar_atol = _finite_number(atol, "atol")
            if scalar_atol <= 0.0:
                raise ConfigurationError("atol must be positive")
            self.atol: float | tuple[float, ...] = scalar_atol
        else:
            vector_atol = _finite_sequence(atol, "atol")
            if len(vector_atol) != len(self.dimensions) or any(x <= 0.0 for x in vector_atol):
                raise ConfigurationError("vector atol must contain one positive value per state")
            self.atol = vector_atol
        if max_step is None:
            self.max_step = None
        else:
            parsed_max_step = _finite_number(max_step, "max_step")
            if parsed_max_step <= 0.0:
                raise ConfigurationError("max_step must be positive")
            self.max_step = parsed_max_step
        self.events = tuple(events)
        if len({event.name for event in self.events}) != len(self.events):
            raise ConfigurationError("event names must be unique")
        if not isinstance(vectorized, bool) or not isinstance(dense_output, bool):
            raise ConfigurationError("vectorized and dense_output must be booleans")
        self.vectorized = vectorized
        self.dense_output = dense_output
        self._rhs = rhs
        self._observable = observable or self._default_observable
        self._classifier = classifier or self._default_classifier
        self._invariant = invariant or self._default_invariants
        configuration = self.configuration()
        digest = hashlib.sha256(canonical_json(configuration).encode("utf-8")).hexdigest()
        self.identity = f"{self.explicit_identity}:sha256:{digest[:16]}"

    @classmethod
    def from_config(
        cls,
        *,
        name: str,
        rhs: RHSCallback,
        values: Mapping[str, object],
        observable: ObservableCallback | None = None,
        classifier: ClassifierCallback | None = None,
        invariant: InvariantCallback | None = None,
        events: Sequence[EventSpec] = (),
    ) -> SolveIVPAdapter:
        """Construct from a JSON-compatible ``adapter.options`` mapping."""

        options = _mapping(values.get("options"), "adapter.options")
        state_names_raw = options.get("state_names")
        if not isinstance(state_names_raw, list) or not all(
            isinstance(item, str) for item in state_names_raw
        ):
            raise ConfigurationError("adapter.options.state_names must be an array of strings")
        t_span_values = _finite_sequence(options.get("t_span"), "adapter.options.t_span")
        if len(t_span_values) != 2:
            raise ConfigurationError("adapter.options.t_span must contain two values")
        atol_raw = options.get("atol", 1e-6)
        if isinstance(atol_raw, list):
            atol: float | Sequence[float] = _finite_sequence(atol_raw, "adapter.options.atol")
        else:
            atol = _finite_number(atol_raw, "adapter.options.atol")
        t_eval_raw = options.get("t_eval", 501)
        if isinstance(t_eval_raw, dict):
            grid = _mapping(t_eval_raw, "adapter.options.t_eval")
            if grid.get("kind") != "linspace":
                raise ConfigurationError("adapter.options.t_eval.kind must be 'linspace'")
            points_raw = grid.get("points")
            if not isinstance(points_raw, int) or isinstance(points_raw, bool):
                raise ConfigurationError("adapter.options.t_eval.points must be an integer")
            t_eval: Sequence[float] | int = points_raw
        elif isinstance(t_eval_raw, list):
            t_eval = _finite_sequence(t_eval_raw, "adapter.options.t_eval")
        else:
            raise ConfigurationError("adapter.options.t_eval must be an array or linspace object")
        max_step_raw = options.get("max_step")
        max_step = (
            None
            if max_step_raw is None
            else _finite_number(max_step_raw, "adapter.options.max_step")
        )
        vectorized = options.get("vectorized", False)
        dense_output = options.get("dense_output", False)
        if not isinstance(vectorized, bool) or not isinstance(dense_output, bool):
            raise ConfigurationError("adapter.options.vectorized and dense_output must be booleans")
        return cls(
            name=name,
            identity=_string(options.get("identity"), "adapter.options.identity"),
            rhs=rhs,
            state_names=cast(list[str], state_names_raw),
            initial_state=_finite_sequence(
                options.get("initial_state"), "adapter.options.initial_state"
            ),
            t_span=(t_span_values[0], t_span_values[1]),
            t_eval=t_eval,
            method=_string(options.get("method", "RK45"), "adapter.options.method"),
            rtol=_finite_number(options.get("rtol", 1e-3), "adapter.options.rtol"),
            atol=atol,
            max_step=max_step,
            events=events,
            observable=observable,
            classifier=classifier,
            invariant=invariant,
            vectorized=vectorized,
            dense_output=dense_output,
        )

    def _evaluation_grid(
        self, requested: Sequence[float] | int
    ) -> tuple[tuple[float, ...], dict[str, object]]:
        start, stop = self._t_span
        if isinstance(requested, bool):
            raise ConfigurationError("t_eval must be an integer point count or numeric sequence")
        if isinstance(requested, int):
            if requested < 2 or requested > MAX_EVALUATION_POINTS:
                raise ConfigurationError(
                    f"t_eval point count must be between 2 and {MAX_EVALUATION_POINTS}"
                )
            values = tuple(
                start + (stop - start) * index / (requested - 1) for index in range(requested)
            )
            configuration: dict[str, object] = {
                "kind": "linspace",
                "start": start,
                "stop": stop,
                "points": requested,
            }
        else:
            values = _finite_sequence(tuple(requested), "t_eval")
            if len(values) < 2 or len(values) > MAX_EVALUATION_POINTS:
                raise ConfigurationError(
                    f"t_eval must contain between 2 and {MAX_EVALUATION_POINTS} values"
                )
            configuration = {"kind": "explicit", "values": list(values)}
        direction = 1.0 if stop > start else -1.0
        if values[0] != start or values[-1] != stop:
            raise ConfigurationError("t_eval must include both t_span endpoints")
        if any(direction * (right - left) <= 0.0 for left, right in pairwise(values)):
            raise ConfigurationError("t_eval must be strictly ordered in the t_span direction")
        return values, configuration

    def configuration(self) -> Mapping[str, object]:
        """Return stable JSON metadata; callables are represented only by declared labels."""

        return {
            "adapter": "scipy.solve_ivp",
            "identity": self.explicit_identity,
            "state_names": list(self.dimensions),
            "initial_state": list(self._initial_state),
            "t_span": list(self._t_span),
            "t_eval": self._grid_configuration,
            "method": self.method,
            "rtol": self.rtol,
            "atol": list(self.atol) if isinstance(self.atol, tuple) else self.atol,
            "max_step": self.max_step,
            "events": [event.as_dict() for event in self.events],
            "vectorized": self.vectorized,
            "dense_output": self.dense_output,
        }

    def initial_state(self, config: ModelConfig, seed: int) -> State:
        """Return the serialized initial state; config and seed remain replay evidence."""

        return self._initial_state

    def _default_observable(
        self, time: float, state: State, parameters: Parameters
    ) -> Mapping[str, Scalar]:
        return dict(zip(self.dimensions, state, strict=True))

    @staticmethod
    def _default_classifier(trace: SimulationTrace, tolerances: Tolerances) -> str:
        return "completed"

    @staticmethod
    def _default_invariants(
        trace: SimulationTrace, parameters: Parameters, tolerances: Tolerances
    ) -> list[InvariantResult]:
        return []

    def _checked_rhs(self, parameters: Parameters) -> Callable[[float, FloatArray], FloatArray]:
        def evaluate(time: float, state: FloatArray) -> FloatArray:
            raw: Any = self._rhs(time, state, parameters)
            if np.iscomplexobj(raw):
                raise NumericalFailure(
                    "SolveIVPAdapter supports real-valued states only; split complex states into "
                    "real and imaginary components"
                )
            result = np.asarray(raw, dtype=float)
            if result.shape != state.shape:
                raise NumericalFailure(f"RHS returned shape {result.shape}; expected {state.shape}")
            if not np.isfinite(result).all():
                raise NumericalFailure("RHS returned NaN or infinite derivative values")
            return cast(FloatArray, result)

        return evaluate

    def _point(self, index: int, time: float, state: object, parameters: Parameters) -> TracePoint:
        values_array = np.asarray(state)
        if np.iscomplexobj(values_array):
            raise NumericalFailure("solve_ivp returned a complex state to a real-valued adapter")
        values = tuple(float(value) for value in values_array)
        if len(values) != len(self.dimensions) or not all(math.isfinite(x) for x in values):
            raise NumericalFailure("solve_ivp returned an invalid state shape or NaN/Inf value")
        observations = dict(self._observable(time, values, parameters))
        for key, value in observations.items():
            if not isinstance(key, str) or not key:
                raise NumericalFailure("observable names must be non-empty strings")
            if isinstance(value, int | float) and not isinstance(value, bool):
                if not math.isfinite(float(value)):
                    raise NumericalFailure(f"observable {key!r} is NaN or infinite")
            elif not isinstance(value, str):
                raise NumericalFailure(f"observable {key!r} must be a finite number or string")
        return TracePoint(step=index, time=float(time), state=values, observations=observations)

    def simulate(
        self,
        initial_state: State,
        parameters: Parameters,
        config: ModelConfig,
        seed: int,
    ) -> SimulationTrace:
        """Run one public ``solve_ivp`` call and retain its declared evaluation grid."""

        if len(initial_state) != len(self.dimensions) or not all(
            math.isfinite(value) for value in initial_state
        ):
            raise NumericalFailure("initial state must match state_names and contain finite values")
        parameter_snapshot = dict(parameters)
        wrappers = tuple(_EventWrapper(event, parameter_snapshot) for event in self.events)
        try:
            solution: Any = solve_ivp(
                self._checked_rhs(parameter_snapshot),
                self._t_span,
                np.asarray(initial_state, dtype=float),
                method=self.method,
                t_eval=np.asarray(self._t_eval, dtype=float),
                dense_output=self.dense_output,
                events=wrappers or None,
                vectorized=self.vectorized,
                rtol=self.rtol,
                atol=np.asarray(self.atol, dtype=float)
                if isinstance(self.atol, tuple)
                else self.atol,
                max_step=np.inf if self.max_step is None else self.max_step,
            )
        except NumericalFailure:
            raise
        except (ArithmeticError, RuntimeError, TypeError, ValueError) as exc:
            raise NumericalFailure(f"solve_ivp failed before returning a result: {exc}") from exc

        times = np.asarray(solution.t)
        states = np.asarray(solution.y)
        if times.ndim != 1 or states.shape != (len(self.dimensions), len(times)):
            raise NumericalFailure("solve_ivp returned an invalid trajectory shape")
        if not np.isfinite(times).all() or not np.isfinite(states).all():
            raise NumericalFailure("solve_ivp returned NaN or infinite trajectory values")
        points = [
            self._point(index, float(time), states[:, index], parameter_snapshot)
            for index, time in enumerate(times)
        ]
        event_evidence: list[dict[str, object]] = []
        terminal_candidates: list[tuple[float, State]] = []
        t_events = solution.t_events or []
        y_events = solution.y_events or []
        for index, spec in enumerate(self.events):
            event_times = np.asarray(t_events[index])
            event_states = np.asarray(y_events[index])
            if len(event_times) > MAX_EVENT_POINTS:
                raise NumericalFailure(
                    f"event {spec.name!r} exceeded the bounded event retention limit"
                )
            serialized_states: list[list[float]] = []
            serialized_times: list[float] = []
            for event_time, event_state in zip(event_times, event_states, strict=True):
                point = self._point(len(points), float(event_time), event_state, parameter_snapshot)
                serialized_times.append(point.time)
                serialized_states.append(list(point.state))
                terminal_candidates.append((point.time, point.state))
            event_evidence.append(
                {
                    "name": spec.name,
                    "terminal": spec.terminal,
                    "direction": float(spec.direction),
                    "times": serialized_times,
                    "states": serialized_states,
                }
            )
        if not points:
            raise NumericalFailure("solve_ivp returned no retained evaluation points")
        final_state = points[-1].state
        termination_time = points[-1].time
        if int(solution.status) == 1 and terminal_candidates:
            direction = 1.0 if self._t_span[1] > self._t_span[0] else -1.0
            termination_time, final_state = max(
                terminal_candidates, key=lambda item: direction * item[0]
            )
            if not math.isclose(points[-1].time, termination_time, rel_tol=0.0, abs_tol=1e-15):
                points.append(
                    self._point(len(points), termination_time, final_state, parameter_snapshot)
                )
        metadata: dict[str, object] = {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "architecture_bits": 64 if sys.maxsize > 2**32 else 32,
                "byteorder": sys.byteorder,
            },
            "solver_method": self.method,
            "rtol": self.rtol,
            "atol": list(self.atol) if isinstance(self.atol, tuple) else self.atol,
            "evaluation_grid": self._grid_configuration,
            "maximum_step": self.max_step,
            "t_span": list(self._t_span),
            "initial_state": list(initial_state),
            "parameters": parameter_snapshot,
            "event_configuration": [event.as_dict() for event in self.events],
            "events": event_evidence,
            "solver_success": bool(solution.success),
            "solver_status": int(solution.status),
            "solver_message": str(solution.message),
            "termination_time": termination_time,
            "nfev": int(solution.nfev),
            "njev": int(solution.njev),
            "nlu": int(solution.nlu),
            "vectorized": self.vectorized,
            "dense_output": self.dense_output,
            "seed": seed,
        }
        return SimulationTrace(
            points=tuple(points),
            final_state=final_state,
            success=bool(solution.success),
            status=int(solution.status),
            message=str(solution.message),
            metadata=metadata,
        )

    def observe(self, trace: SimulationTrace) -> Mapping[str, Scalar]:
        """Return the final retained point's observables."""

        return dict(trace.points[-1].observations)

    def classify(self, trace: SimulationTrace, tolerances: Tolerances) -> str:
        """Delegate qualitative interpretation to the declared callback."""

        result = self._classifier(trace, tolerances)
        if not isinstance(result, str) or not result:
            raise NumericalFailure("classifier must return a non-empty string")
        return result

    def invariants(
        self,
        trace: SimulationTrace,
        parameters: Parameters,
        tolerances: Tolerances,
    ) -> list[InvariantResult]:
        """Delegate invariant evaluation to the declared callback."""

        return list(self._invariant(trace, parameters, tolerances))


__all__ = ["SUPPORTED_METHODS", "EventSpec", "SolveIVPAdapter"]
