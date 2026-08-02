"""Deterministic simulation, bounded search, refinement, and policy evaluation."""

from __future__ import annotations

import hashlib
import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from phaseprobe.adapters.loader import load_configured_adapter
from phaseprobe.config import ProbeConfig, canonical_json
from phaseprobe.errors import ConfigurationError, NumericalFailure
from phaseprobe.models import get_model
from phaseprobe.types import (
    InvariantResult,
    ModelAdapter,
    SimulationTrace,
    State,
    TracePoint,
    TrajectoryAdapter,
)

Adapter = ModelAdapter | TrajectoryAdapter


def _number(values: Mapping[str, object], name: str, default: float | None = None) -> float:
    value = values.get(name, default)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ConfigurationError(f"{name} must be finite")
    return result


def _integer(values: Mapping[str, object], name: str, default: int | None = None) -> int:
    value = values.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError(f"{name} must be an integer")
    return value


def _boolean(values: Mapping[str, object], name: str, default: bool) -> bool:
    value = values.get(name, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a boolean")
    return value


def _string(values: Mapping[str, object], name: str, default: str | None = None) -> str:
    value = values.get(name, default)
    if not isinstance(value, str):
        raise ConfigurationError(f"{name} must be a string")
    return value


def _numeric_mapping(values: Mapping[str, object], context: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for name, raw in values.items():
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise ConfigurationError(f"{context}.{name} must be a number")
        number = float(raw)
        if not math.isfinite(number):
            raise ConfigurationError(f"{context}.{name} must be finite")
        result[name] = number
    return result


@dataclass(frozen=True, slots=True)
class SimulationSettings:
    """Bounded execution settings shared by every adapter."""

    steps: int
    burn_in: int
    dt: float
    sample_every: int
    trace_cap: int
    hard_state_limit: float

    @classmethod
    def from_config(cls, values: Mapping[str, object]) -> SimulationSettings:
        settings = cls(
            steps=_integer(values, "steps"),
            burn_in=_integer(values, "burn_in", 0),
            dt=_number(values, "dt", 1.0),
            sample_every=_integer(values, "sample_every", 1),
            trace_cap=_integer(values, "trace_cap", 2048),
            hard_state_limit=_number(values, "hard_state_limit", 1e100),
        )
        if settings.steps <= 0 or settings.burn_in < 0:
            raise ConfigurationError("simulation steps must be positive and burn_in non-negative")
        if settings.dt <= 0.0 or settings.sample_every <= 0:
            raise ConfigurationError("simulation dt and sample_every must be positive")
        if settings.trace_cap < 16 or settings.trace_cap > 100_000:
            raise ConfigurationError("simulation trace_cap must be between 16 and 100000")
        if settings.hard_state_limit <= 0.0:
            raise ConfigurationError("simulation hard_state_limit must be positive")
        return settings

    def as_dict(self) -> dict[str, object]:
        return {
            "steps": self.steps,
            "burn_in": self.burn_in,
            "dt": self.dt,
            "sample_every": self.sample_every,
            "trace_cap": self.trace_cap,
            "hard_state_limit": self.hard_state_limit,
        }


@dataclass(frozen=True, slots=True)
class TrajectorySettings:
    """Engine-owned bounds for one trajectory-level adapter execution."""

    trace_cap: int
    hard_state_limit: float

    @classmethod
    def from_config(cls, values: Mapping[str, object]) -> TrajectorySettings:
        settings = cls(
            trace_cap=_integer(values, "trace_cap", 2048),
            hard_state_limit=_number(values, "hard_state_limit", 1e100),
        )
        if settings.trace_cap < 16 or settings.trace_cap > 100_000:
            raise ConfigurationError("simulation trace_cap must be between 16 and 100000")
        if settings.hard_state_limit <= 0.0:
            raise ConfigurationError("simulation hard_state_limit must be positive")
        return settings

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": "trajectory",
            "trace_cap": self.trace_cap,
            "hard_state_limit": self.hard_state_limit,
        }


def _invariant_dict(result: InvariantResult) -> dict[str, object]:
    return {
        "name": result.name,
        "passed": result.passed,
        "measured": result.measured,
        "tolerance": result.tolerance,
        "detail": result.detail,
    }


def _point_dict(point: TracePoint) -> dict[str, object]:
    return {
        "step": point.step,
        "time": point.time,
        "state": list(point.state),
        "observations": dict(point.observations),
    }


def trace_hash(trace: Sequence[TracePoint]) -> str:
    """Hash the retained canonical trace exactly for deterministic replay."""

    payload = [_point_dict(point) for point in trace]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """One bounded step-level or trajectory-level execution."""

    model: str
    model_identity: str
    seed: int
    parameters: Mapping[str, float]
    initial_state: State
    final_state: State
    settings: SimulationSettings | TrajectorySettings
    tolerances: Mapping[str, float]
    classification: str
    invariants: tuple[InvariantResult, ...]
    observations: Mapping[str, object]
    trace: tuple[TracePoint, ...]
    trace_sha256: str
    replay_mode: str
    execution_metadata: Mapping[str, object]

    @property
    def invariant_violations(self) -> int:
        return sum(not result.passed for result in self.invariants)

    def as_dict(self, *, include_trace: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "model_identity": self.model_identity,
            "seed": self.seed,
            "parameters": dict(self.parameters),
            "initial_state": list(self.initial_state),
            "final_state": list(self.final_state),
            "simulation": self.settings.as_dict(),
            "tolerances": dict(self.tolerances),
            "classification": self.classification,
            "invariants": [_invariant_dict(result) for result in self.invariants],
            "invariant_violations": self.invariant_violations,
            "observations": dict(self.observations),
            "trace_points_retained": len(self.trace),
            "trace_sha256": self.trace_sha256,
            "replay_mode": self.replay_mode,
            "execution_metadata": dict(self.execution_metadata),
        }
        if include_trace:
            payload["trace"] = [_point_dict(point) for point in self.trace]
        return payload


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    """Serializable result of a scan, perturbation search, or declared check."""

    command: str
    status: str
    config: ProbeConfig
    baseline: SimulationResult
    changed: SimulationResult | None
    finding: Mapping[str, object] | None
    history: tuple[Mapping[str, object], ...]
    reproducible: bool
    policy_failed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "2.0",
            "command": self.command,
            "status": self.status,
            "model": self.baseline.model,
            "source": self.config.source,
            "configuration": dict(self.config.data),
            "baseline": self.baseline.as_dict(),
            "changed": self.changed.as_dict() if self.changed is not None else None,
            "finding": dict(self.finding) if self.finding is not None else None,
            "history": [dict(item) for item in self.history],
            "reproducible": self.reproducible,
            "policy_failed": self.policy_failed,
        }


def _validate_state(
    model: Adapter,
    state: State,
    settings: SimulationSettings | TrajectorySettings,
    step: int,
) -> None:
    if len(state) != len(model.dimensions):
        raise NumericalFailure(
            f"solver failure at step {step}: adapter returned {len(state)} dimensions; "
            f"expected {len(model.dimensions)}"
        )
    for dimension, value in zip(model.dimensions, state, strict=False):
        if not math.isfinite(value):
            raise NumericalFailure(
                f"invalid integration at step {step}: {dimension} is NaN or infinite"
            )
        if abs(value) > settings.hard_state_limit:
            raise NumericalFailure(
                f"invalid integration at step {step}: {dimension} exceeded hard_state_limit"
            )


def _resolve_adapter(config: ProbeConfig, adapter: Adapter | None) -> Adapter:
    if adapter is not None:
        if not isinstance(adapter, ModelAdapter | TrajectoryAdapter):
            raise ConfigurationError("adapter does not implement a PhaseProbe protocol")
        if adapter.name != config.model:
            raise ConfigurationError(
                f"adapter name {adapter.name!r} does not match model {config.model!r}"
            )
        return adapter
    try:
        return get_model(config.model)
    except ConfigurationError:
        if "adapter" not in config.data:
            raise
    return load_configured_adapter(config)


def _validate_trace_points(
    model: Adapter,
    trace: SimulationTrace,
    settings: TrajectorySettings,
) -> None:
    if not trace.points:
        raise NumericalFailure("trajectory adapter returned an empty trace")
    direction = 0
    previous_time: float | None = None
    for point in trace.points:
        if not math.isfinite(point.time):
            raise NumericalFailure("trajectory adapter returned a NaN or infinite time")
        _validate_state(model, point.state, settings, point.step)
        for name, value in point.observations.items():
            if not isinstance(name, str) or not name:
                raise NumericalFailure("trajectory observable names must be non-empty strings")
            if isinstance(value, int | float) and not isinstance(value, bool):
                if not math.isfinite(float(value)):
                    raise NumericalFailure(f"trajectory observable {name!r} is NaN or infinite")
            elif not isinstance(value, str):
                raise NumericalFailure(
                    f"trajectory observable {name!r} must be a finite number or string"
                )
        if previous_time is not None:
            delta = point.time - previous_time
            if delta == 0.0:
                raise NumericalFailure("trajectory retained duplicate time points")
            this_direction = 1 if delta > 0.0 else -1
            if direction == 0:
                direction = this_direction
            elif direction != this_direction:
                raise NumericalFailure("trajectory retained times are not monotonic")
        previous_time = point.time
    _validate_state(model, trace.final_state, settings, trace.points[-1].step)


def _bounded_trace(trace: SimulationTrace, cap: int) -> SimulationTrace:
    if len(trace.points) <= cap:
        return trace
    last = len(trace.points) - 1
    indices = tuple(round(index * last / (cap - 1)) for index in range(cap))
    points = tuple(trace.points[index] for index in indices)
    metadata = dict(trace.metadata)
    metadata["retention"] = {
        "points_produced": len(trace.points),
        "points_retained": len(points),
        "strategy": "uniform-in-index-with-endpoints",
    }
    return SimulationTrace(
        points=points,
        final_state=trace.final_state,
        success=trace.success,
        status=trace.status,
        message=trace.message,
        metadata=metadata,
    )


def simulate(
    config: ProbeConfig,
    *,
    parameters_override: Mapping[str, float] | None = None,
    initial_override: State | None = None,
    adapter: Adapter | None = None,
) -> SimulationResult:
    """Execute one model with explicit seed, parameters, retention, and tolerances."""

    model = _resolve_adapter(config, adapter)
    parameters = _numeric_mapping(config.section("parameters"), "parameters")
    if parameters_override is not None:
        parameters.update(parameters_override)
    tolerances = _numeric_mapping(config.section("tolerances", required=False), "tolerances")
    model_config = config.section("model_config", required=False)
    state = (
        initial_override
        if initial_override is not None
        else model.initial_state(model_config, config.seed)
    )
    initial = tuple(state)
    if isinstance(model, TrajectoryAdapter):
        trajectory_settings = TrajectorySettings.from_config(config.section("simulation"))
        _validate_state(model, initial, trajectory_settings, 0)
        try:
            raw_trace = model.simulate(initial, parameters, model_config, config.seed)
        except NumericalFailure:
            raise
        except (ArithmeticError, RuntimeError, TypeError, ValueError) as exc:
            raise NumericalFailure(f"trajectory solver failure: {exc}") from exc
        _validate_trace_points(model, raw_trace, trajectory_settings)
        if not raw_trace.success:
            raise NumericalFailure(
                f"solver failure with status {raw_trace.status}: {raw_trace.message}"
            )
        bounded = _bounded_trace(raw_trace, trajectory_settings.trace_cap)
        classification = model.classify(bounded, tolerances)
        invariants = tuple(model.invariants(bounded, parameters, tolerances))
        observations = dict(model.observe(bounded))
        execution_metadata = dict(bounded.metadata)
        execution_metadata["adapter_configuration"] = dict(model.configuration())
        return SimulationResult(
            model=model.name,
            model_identity=model.identity,
            seed=config.seed,
            parameters=parameters,
            initial_state=initial,
            final_state=bounded.final_state,
            settings=trajectory_settings,
            tolerances=tolerances,
            classification=classification,
            invariants=invariants,
            observations=observations,
            trace=bounded.points,
            trace_sha256=trace_hash(bounded.points),
            replay_mode=model.replay_mode,
            execution_metadata=execution_metadata,
        )

    settings = SimulationSettings.from_config(config.section("simulation"))
    _validate_state(model, initial, settings, 0)
    retained: deque[TracePoint] = deque(maxlen=settings.trace_cap)
    total_steps = settings.burn_in + settings.steps
    for step in range(1, total_steps + 1):
        try:
            state = model.step(state, parameters, settings.dt)
        except (ArithmeticError, ValueError) as exc:
            raise NumericalFailure(f"solver failure at step {step}: {exc}") from exc
        _validate_state(model, state, settings, step)
        if step > settings.burn_in and (step - settings.burn_in) % settings.sample_every == 0:
            retained.append(
                TracePoint(
                    step=step,
                    time=step * settings.dt,
                    state=tuple(state),
                    observations=dict(model.observe(state)),
                )
            )
    trace = tuple(retained)
    if not trace:
        raise ConfigurationError("simulation retention settings produced an empty trace")
    classification = model.classify(trace, tolerances)
    invariants = tuple(model.invariants(trace, parameters, tolerances))
    return SimulationResult(
        model=model.name,
        model_identity=model.identity,
        seed=config.seed,
        parameters=parameters,
        initial_state=initial,
        final_state=tuple(state),
        settings=settings,
        tolerances=tolerances,
        classification=classification,
        invariants=invariants,
        observations=dict(trace[-1].observations),
        trace=trace,
        trace_sha256=trace_hash(trace),
        replay_mode="exact",
        execution_metadata={"execution_kind": "step", "solver_success": True},
    )


def _linspace(start: float, stop: float, points: int) -> list[float]:
    if points < 2:
        raise ConfigurationError("search points must be at least 2")
    return [start + (stop - start) * index / (points - 1) for index in range(points)]


def _logspace(start: float, stop: float, points: int) -> list[float]:
    if start <= 0.0 or stop <= 0.0:
        raise ConfigurationError("logarithmic search bounds must be positive")
    log_start = math.log(start)
    log_stop = math.log(stop)
    return [math.exp(value) for value in _linspace(log_start, log_stop, points)]


def run_scan(config: ProbeConfig, *, adapter: Adapter | None = None) -> ProbeOutcome:
    """Scan a one-dimensional parameter and refine the first adjacent class change."""

    scan = config.section("scan")
    parameter_name = _string(scan, "parameter")
    start = _number(scan, "start")
    stop = _number(scan, "stop")
    points = _integer(scan, "points")
    refinements = _integer(scan, "refine_iterations", 12)
    repeatability = _integer(scan, "repeatability", 2)
    if stop <= start or refinements < 0 or repeatability < 1:
        raise ConfigurationError("scan requires stop > start and non-negative refinement")

    history: list[Mapping[str, object]] = []
    runs: list[SimulationResult] = []
    values = _linspace(start, stop, points)
    for value in values:
        run = simulate(config, parameters_override={parameter_name: value}, adapter=adapter)
        runs.append(run)
        history.append({"phase": "coarse", "value": value, "classification": run.classification})

    transition_index: int | None = None
    for index in range(len(runs) - 1):
        if runs[index].classification != runs[index + 1].classification:
            transition_index = index
            break
    if transition_index is None:
        return ProbeOutcome(
            command="scan",
            status="NO QUALITATIVE TRANSITION FOUND",
            config=config,
            baseline=runs[0],
            changed=None,
            finding=None,
            history=tuple(history),
            reproducible=True,
        )

    coarse_left = values[transition_index]
    coarse_right = values[transition_index + 1]
    low = coarse_left
    high = coarse_right
    left_run = runs[transition_index]
    right_run = runs[transition_index + 1]
    left_class = left_run.classification
    right_class = right_run.classification
    unresolved_midpoint: float | None = None
    for _ in range(refinements):
        midpoint = (low + high) / 2.0
        midpoint_run = simulate(
            config, parameters_override={parameter_name: midpoint}, adapter=adapter
        )
        history.append(
            {
                "phase": "refine",
                "low": low,
                "high": high,
                "value": midpoint,
                "classification": midpoint_run.classification,
            }
        )
        if midpoint_run.classification == left_class:
            low = midpoint
            left_run = midpoint_run
        elif midpoint_run.classification == right_class:
            high = midpoint
            right_run = midpoint_run
        else:
            unresolved_midpoint = midpoint
            history.append(
                {
                    "phase": "refine-stopped",
                    "value": midpoint,
                    "classification": midpoint_run.classification,
                    "reason": "midpoint did not reproduce either stable endpoint class",
                }
            )
            break

    reproducible = True
    confirmations: list[dict[str, object]] = []
    for side, _expected in (("baseline", left_run), ("changed", right_run)):
        hashes: list[str] = []
        classes: list[str] = []
        for _ in range(repeatability):
            value = low if side == "baseline" else high
            confirmed = simulate(
                config, parameters_override={parameter_name: value}, adapter=adapter
            )
            hashes.append(confirmed.trace_sha256)
            classes.append(confirmed.classification)
        stable = len(set(hashes)) == 1 and len(set(classes)) == 1
        reproducible = reproducible and stable
        confirmations.append(
            {"side": side, "runs": repeatability, "stable": stable, "trace_sha256": hashes[0]}
        )
    finding: dict[str, object] = {
        "kind": "qualitative-regime-change",
        "parameter": parameter_name,
        "coarse_bracket": [coarse_left, coarse_right],
        "stable_bracket": [low, high],
        "bracket_width": high - low,
        "smallest_reproducible_change_found": high - low,
        "baseline_regime": left_run.classification,
        "changed_regime": right_run.classification,
        "classification_rule": config.string("classification_rule"),
        "refinement_rule": config.string("refinement_rule"),
        "repeatability": confirmations,
        "unresolved_midpoint": unresolved_midpoint,
        "minimality_statement": "Smallest reproducible separation found by the declared bounded scan and binary refinement; not a proof of a globally minimal perturbation or exact bifurcation point.",
    }
    return ProbeOutcome(
        command="scan",
        status="QUALITATIVE TRANSITION FOUND",
        config=config,
        baseline=left_run,
        changed=right_run,
        finding=finding,
        history=tuple(history),
        reproducible=reproducible,
    )


def _distance(left: State, right: State) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=False)))


def _pair_metrics(
    baseline: SimulationResult, changed: SimulationResult, delta: float
) -> dict[str, object]:
    count = min(len(baseline.trace), len(changed.trace))
    if count == 0:
        raise NumericalFailure("cannot compare empty twin traces")
    left = baseline.trace[-count:]
    right = changed.trace[-count:]
    distances = [_distance(a.state, b.state) for a, b in zip(left, right, strict=False)]
    max_index = max(range(count), key=distances.__getitem__)
    max_distance = distances[max_index]
    elapsed = abs(right[max_index].time - right[0].time)
    if elapsed == 0.0:
        elapsed = 1.0
    initial_separation = abs(delta)
    rate: float | None = None
    if initial_separation > 0.0 and max_distance > 0.0:
        rate = math.log(max_distance / initial_separation) / elapsed
    return {
        "initial_separation": initial_separation,
        "max_trajectory_distance": max_distance,
        "terminal_trajectory_distance": distances[-1],
        "finite_time_divergence_rate": rate,
        "rate_observation_window": elapsed,
    }


def run_perturb(config: ProbeConfig, *, adapter: Adapter | None = None) -> ProbeOutcome:
    """Search bounded initial-state perturbations using a deterministic predicate."""

    search = config.section("perturb")
    model = _resolve_adapter(config, adapter)
    dimension = _string(search, "dimension")
    try:
        dimension_index = model.dimensions.index(dimension)
    except ValueError as exc:
        raise ConfigurationError(
            f"unknown perturbation dimension {dimension!r}; choose one of {model.dimensions}"
        ) from exc
    start = _number(search, "start")
    stop = _number(search, "stop")
    points = _integer(search, "points")
    scale = _string(search, "scale", "linear")
    predicate = _string(search, "predicate", "classification-change")
    target_classification_raw = search.get("target_classification")
    target_classification = (
        _string(search, "target_classification") if target_classification_raw is not None else None
    )
    threshold = _number(search, "divergence_threshold", 1.0)
    refinements = _integer(search, "refine_iterations", 10)
    repeatability = _integer(search, "repeatability", 2)
    if stop <= start or start < 0.0 or refinements < 0 or repeatability < 1:
        raise ConfigurationError("perturb requires stop > start >= 0 and valid refinement counts")
    if predicate not in {"classification-change", "finite-time-divergence"}:
        raise ConfigurationError(
            "perturb predicate must be classification-change or finite-time-divergence"
        )
    deltas = _logspace(start, stop, points) if scale == "log" else _linspace(start, stop, points)
    if scale not in {"linear", "log"}:
        raise ConfigurationError("perturb scale must be linear or log")

    baseline = simulate(config, adapter=model)
    initial = baseline.initial_state
    history: list[Mapping[str, object]] = []
    previous_delta = 0.0
    previous_triggered = False
    found_delta: float | None = None
    found_run: SimulationResult | None = None
    found_metrics: dict[str, object] | None = None

    def evaluate(delta: float, phase: str) -> tuple[bool, SimulationResult, dict[str, object]]:
        candidate_state = list(initial)
        candidate_state[dimension_index] += delta
        changed = simulate(config, initial_override=tuple(candidate_state), adapter=model)
        metrics = _pair_metrics(baseline, changed, delta)
        if predicate == "classification-change":
            triggered = (
                changed.classification == target_classification
                if target_classification is not None
                else changed.classification != baseline.classification
            )
        else:
            distance = metrics["max_trajectory_distance"]
            if not isinstance(distance, float):
                raise NumericalFailure("internal distance metric type failure")
            triggered = distance >= threshold
        history.append(
            {
                "phase": phase,
                "delta": delta,
                "classification": changed.classification,
                "triggered": triggered,
                **metrics,
            }
        )
        return triggered, changed, metrics

    for delta in deltas:
        triggered, changed, metrics = evaluate(delta, "coarse")
        if triggered:
            found_delta, found_run, found_metrics = delta, changed, metrics
            break
        previous_delta = delta
        previous_triggered = triggered

    if found_delta is None or found_run is None or found_metrics is None:
        last_delta = deltas[-1]
        _, last_run, _ = evaluate(last_delta, "negative-control-confirmation")
        return ProbeOutcome(
            command="perturb",
            status="NO SENSITIVE PERTURBATION FOUND",
            config=config,
            baseline=baseline,
            changed=last_run,
            finding=None,
            history=tuple(history),
            reproducible=True,
        )

    low = previous_delta
    high = found_delta
    if low > 0.0 and not previous_triggered:
        for _ in range(refinements):
            midpoint = (low + high) / 2.0
            triggered, changed, metrics = evaluate(midpoint, "refine")
            if triggered:
                high, found_run, found_metrics = midpoint, changed, metrics
            else:
                low = midpoint

    hashes: list[str] = []
    classes: list[str] = []
    triggered_confirmations: list[bool] = []
    for _ in range(repeatability):
        triggered, confirmed, _ = evaluate(high, "repeatability")
        hashes.append(confirmed.trace_sha256)
        classes.append(confirmed.classification)
        triggered_confirmations.append(triggered)
    reproducible = len(set(hashes)) == 1 and len(set(classes)) == 1 and all(triggered_confirmations)
    finding = {
        "kind": predicate,
        "dimension": dimension,
        "search_bounds": [start, stop],
        "stable_bracket": [low, high],
        "smallest_reproducible_change_found": high,
        "baseline_regime": baseline.classification,
        "changed_regime": found_run.classification,
        "target_classification": target_classification,
        "metrics": found_metrics,
        "classification_rule": config.string("classification_rule"),
        "refinement_rule": config.string("refinement_rule"),
        "repeatability": {
            "runs": repeatability,
            "stable": reproducible,
            "trace_sha256": hashes[0],
        },
        "minimality_statement": "Smallest reproducible perturbation found within the declared finite search; not a proof of global minimality.",
    }
    status = (
        "FINITE-TIME TRAJECTORY DIVERGENCE FOUND"
        if predicate == "finite-time-divergence"
        else "QUALITATIVE STATE SWITCH FOUND"
    )
    return ProbeOutcome(
        command="perturb",
        status=status,
        config=config,
        baseline=baseline,
        changed=found_run,
        finding=finding,
        history=tuple(history),
        reproducible=reproducible,
    )


def run_check(config: ProbeConfig, *, adapter: Adapter | None = None) -> ProbeOutcome:
    """Execute a declared CI policy and mark only policy violations as failure."""

    check = config.section("check")
    analysis = _string(check, "analysis", "invariants")
    policy = config.section("policy")
    forbid_findings = _boolean(policy, "forbid_findings", False)
    require_finding = _boolean(policy, "require_finding", False)
    require_invariants = _boolean(policy, "require_invariants", True)

    if analysis == "scan":
        outcome = run_scan(config, adapter=adapter)
    elif analysis == "perturb":
        outcome = run_perturb(config, adapter=adapter)
    elif analysis == "invariants":
        baseline = simulate(config, adapter=adapter)
        violations = [_invariant_dict(item) for item in baseline.invariants if not item.passed]
        finding: Mapping[str, object] | None = None
        if violations:
            finding = {"kind": "invariant-violation", "violations": violations}
        outcome = ProbeOutcome(
            command="check",
            status="CHECK EVIDENCE COLLECTED",
            config=config,
            baseline=baseline,
            changed=None,
            finding=finding,
            history=(),
            reproducible=True,
        )
    else:
        raise ConfigurationError("check.analysis must be invariants, scan, or perturb")

    finding_present = outcome.finding is not None
    policy_failed = (forbid_findings and finding_present) or (
        require_finding and not finding_present
    )
    if require_invariants:
        policy_failed = policy_failed or outcome.baseline.invariant_violations > 0
        if outcome.changed is not None:
            policy_failed = policy_failed or outcome.changed.invariant_violations > 0
    return ProbeOutcome(
        command="check",
        status="CHECK POLICY FAILED" if policy_failed else "CHECK POLICY PASSED",
        config=config,
        baseline=outcome.baseline,
        changed=outcome.changed,
        finding=outcome.finding,
        history=outcome.history,
        reproducible=outcome.reproducible,
        policy_failed=policy_failed,
    )
