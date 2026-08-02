"""Versioned exact/tolerance replay with integrity-protected evidence."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from phaseprobe import __version__
from phaseprobe.config import ProbeConfig, canonical_json, parse_config
from phaseprobe.engine import ProbeOutcome, SimulationResult, simulate
from phaseprobe.errors import ConfigurationError, IntegrityError
from phaseprobe.types import InvariantResult, TracePoint

REPLAY_SCHEMA_VERSION = "2.0"
SUPPORTED_REPLAY_SCHEMA_VERSIONS = frozenset({"1.0", REPLAY_SCHEMA_VERSION})


def _invariant_payload(result: InvariantResult) -> dict[str, object]:
    return {
        "name": result.name,
        "passed": result.passed,
        "measured": result.measured,
        "tolerance": result.tolerance,
        "detail": result.detail,
    }


def _point_payload(point: TracePoint) -> dict[str, object]:
    return {
        "step": point.step,
        "time": point.time,
        "state": list(point.state),
        "observations": dict(point.observations),
    }


def _execution_payload(result: SimulationResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "parameters": dict(result.parameters),
        "initial_state": list(result.initial_state),
        "final_state": list(result.final_state),
        "classification": result.classification,
        "observations": dict(result.observations),
        "invariants": [_invariant_payload(item) for item in result.invariants],
        "trace_sha256": result.trace_sha256,
        "invariant_violations": result.invariant_violations,
        "solver_success": bool(result.execution_metadata.get("solver_success", True)),
        "execution_metadata": dict(result.execution_metadata),
    }
    if result.replay_mode == "tolerance":
        payload["trace"] = [_point_payload(point) for point in result.trace]
    return payload


def _number(values: Mapping[str, object], name: str) -> float:
    raw = values.get(name)
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        raise ConfigurationError(f"replay.{name} must be numeric")
    result = float(raw)
    if not math.isfinite(result) or result < 0.0:
        raise ConfigurationError(f"replay.{name} must be finite and non-negative")
    return result


def _tolerance_policy(config: ProbeConfig) -> dict[str, object]:
    values = config.section("replay")
    if values.get("mode") != "tolerance":
        raise ConfigurationError(
            "trajectory adapters require replay.mode='tolerance'; exact adaptive replay is not claimed"
        )
    observable_raw = values.get("observable_atol")
    if not isinstance(observable_raw, dict):
        raise ConfigurationError("replay.observable_atol must be an object")
    observable_atol: dict[str, float] = {}
    for name, raw in observable_raw.items():
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise ConfigurationError(f"replay.observable_atol.{name} must be numeric")
        parsed = float(raw)
        if not math.isfinite(parsed) or parsed < 0.0:
            raise ConfigurationError(
                f"replay.observable_atol.{name} must be finite and non-negative"
            )
        observable_atol[name] = parsed
    max_unmatched = values.get("max_unmatched_points")
    if not isinstance(max_unmatched, int) or isinstance(max_unmatched, bool) or max_unmatched < 0:
        raise ConfigurationError("replay.max_unmatched_points must be a non-negative integer")
    expected_success = values.get("expected_solver_success")
    require_classifier = values.get("require_classifier")
    require_invariants = values.get("require_invariants")
    if not all(
        isinstance(item, bool)
        for item in (expected_success, require_classifier, require_invariants)
    ):
        raise ConfigurationError(
            "replay expected_solver_success, require_classifier, and require_invariants must be booleans"
        )
    return {
        "mode": "tolerance",
        "state_atol": _number(values, "state_atol"),
        "state_rtol": _number(values, "state_rtol"),
        "observable_atol": observable_atol,
        "invariant_measure_atol": _number(values, "invariant_measure_atol"),
        "endpoint_time_atol": _number(values, "endpoint_time_atol"),
        "event_time_atol": _number(values, "event_time_atol"),
        "retained_grid_time_atol": _number(values, "retained_grid_time_atol"),
        "max_unmatched_points": max_unmatched,
        "expected_solver_success": expected_success,
        "require_classifier": require_classifier,
        "require_invariants": require_invariants,
    }


def fixture_payload(outcome: ProbeOutcome) -> dict[str, object]:
    """Create an integrity-protected replay fixture from validated evidence."""

    modes = {outcome.baseline.replay_mode}
    if outcome.changed is not None:
        modes.add(outcome.changed.replay_mode)
    if len(modes) != 1:
        raise ConfigurationError("baseline and changed executions use different replay modes")
    mode = next(iter(modes))
    comparison = {"mode": "exact"} if mode == "exact" else _tolerance_policy(outcome.config)
    payload: dict[str, object] = {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "created_by": f"phaseprobe {__version__}",
        "model": outcome.baseline.model,
        "model_identity": outcome.baseline.model_identity,
        "seed": outcome.baseline.seed,
        "configuration": dict(outcome.config.data),
        "comparison": comparison,
        "baseline": _execution_payload(outcome.baseline),
        "changed": _execution_payload(outcome.changed) if outcome.changed is not None else None,
        "finding": dict(outcome.finding) if outcome.finding is not None else None,
        "reproducible": outcome.reproducible,
    }
    integrity = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    payload["integrity_sha256"] = integrity
    return payload


def _load_fixture(path: Path) -> dict[str, object]:
    try:
        parsed: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read replay fixture {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise IntegrityError(f"invalid replay JSON in {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise IntegrityError("replay fixture must be a JSON object")
    return cast(dict[str, object], parsed)


def validate_fixture(path: Path) -> dict[str, object]:
    """Validate a v1 exact or v2 exact/tolerance fixture before execution."""

    payload = _load_fixture(path)
    version = payload.get("schema_version")
    if version not in SUPPORTED_REPLAY_SCHEMA_VERSIONS:
        raise IntegrityError(
            f"unsupported replay schema {version!r}; supported versions are "
            f"{sorted(SUPPORTED_REPLAY_SCHEMA_VERSIONS)!r}"
        )
    expected = payload.get("integrity_sha256")
    if not isinstance(expected, str):
        raise IntegrityError("replay fixture has no integrity_sha256")
    unsigned = dict(payload)
    del unsigned["integrity_sha256"]
    actual = hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    if actual != expected:
        raise IntegrityError(
            f"replay fixture integrity mismatch: expected {expected}, got {actual}"
        )
    return payload


def _mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise IntegrityError(f"replay {context} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise IntegrityError(f"replay {context} must be an array")
    return cast(Sequence[object], value)


def _float_mapping(value: object, context: str) -> dict[str, float]:
    values = _mapping(value, context)
    result: dict[str, float] = {}
    for name, raw in values.items():
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise IntegrityError(f"replay {context}.{name} must be numeric")
        result[name] = float(raw)
    return result


def _state(value: object, context: str) -> tuple[float, ...]:
    raw_values = _sequence(value, context)
    state: list[float] = []
    for raw in raw_values:
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise IntegrityError(f"replay {context} contains a non-number")
        state.append(float(raw))
    return tuple(state)


def _policy_number(policy: Mapping[str, object], name: str) -> float:
    raw = policy.get(name)
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        raise IntegrityError(f"replay comparison.{name} must be numeric")
    result = float(raw)
    if not math.isfinite(result) or result < 0.0:
        raise IntegrityError(f"replay comparison.{name} must be finite and non-negative")
    return result


def _close(left: float, right: float, *, atol: float, rtol: float) -> bool:
    return math.isclose(left, right, abs_tol=atol, rel_tol=rtol)


def _observations_match(
    expected: object,
    actual: Mapping[str, object],
    policy: Mapping[str, object],
) -> bool:
    expected_values = _mapping(expected, "trace observations")
    tolerances = _mapping(policy.get("observable_atol"), "comparison.observable_atol")
    if set(expected_values) != set(actual):
        return False
    default_atol = _policy_number(policy, "state_atol")
    rtol = _policy_number(policy, "state_rtol")
    for name, expected_value in expected_values.items():
        actual_value = actual[name]
        if isinstance(expected_value, int | float) and not isinstance(expected_value, bool):
            if not isinstance(actual_value, int | float) or isinstance(actual_value, bool):
                return False
            configured = tolerances.get(name, default_atol)
            if not isinstance(configured, int | float) or isinstance(configured, bool):
                raise IntegrityError(f"replay observable tolerance for {name!r} is not numeric")
            if not _close(
                float(expected_value), float(actual_value), atol=float(configured), rtol=rtol
            ):
                return False
        elif expected_value != actual_value:
            return False
    return True


def _invariants_match(
    expected: object, actual: tuple[InvariantResult, ...], policy: Mapping[str, object]
) -> tuple[bool, bool]:
    expected_items = _sequence(expected, "invariants")
    if len(expected_items) != len(actual):
        return False, False
    outcome_match = True
    threshold_match = True
    atol = _policy_number(policy, "invariant_measure_atol")
    rtol = _policy_number(policy, "state_rtol")
    for raw, observed in zip(expected_items, actual, strict=True):
        item = _mapping(raw, "invariant")
        outcome_match = outcome_match and item.get("name") == observed.name
        outcome_match = outcome_match and item.get("passed") is observed.passed
        measured = item.get("measured")
        tolerance = item.get("tolerance")
        if not isinstance(measured, int | float) or isinstance(measured, bool):
            raise IntegrityError("replay invariant measured value must be numeric")
        if not isinstance(tolerance, int | float) or isinstance(tolerance, bool):
            raise IntegrityError("replay invariant tolerance must be numeric")
        outcome_match = outcome_match and _close(
            float(measured), observed.measured, atol=atol, rtol=rtol
        )
        threshold_match = threshold_match and float(tolerance) == observed.tolerance
    return outcome_match, threshold_match


def _event_match(
    expected_metadata: Mapping[str, object],
    actual_metadata: Mapping[str, object],
    policy: Mapping[str, object],
) -> bool:
    expected_events = _sequence(expected_metadata.get("events", []), "execution events")
    actual_events = _sequence(actual_metadata.get("events", []), "actual execution events")
    if len(expected_events) != len(actual_events):
        return False
    time_atol = _policy_number(policy, "event_time_atol")
    state_atol = _policy_number(policy, "state_atol")
    state_rtol = _policy_number(policy, "state_rtol")
    for expected_raw, actual_raw in zip(expected_events, actual_events, strict=True):
        expected = _mapping(expected_raw, "expected event")
        actual = _mapping(actual_raw, "actual event")
        if expected.get("name") != actual.get("name"):
            return False
        expected_times = _sequence(expected.get("times"), "expected event times")
        actual_times = _sequence(actual.get("times"), "actual event times")
        expected_states = _sequence(expected.get("states"), "expected event states")
        actual_states = _sequence(actual.get("states"), "actual event states")
        if len(expected_times) != len(actual_times) or len(expected_states) != len(actual_states):
            return False
        for expected_time, actual_time in zip(expected_times, actual_times, strict=True):
            if not isinstance(expected_time, int | float) or not isinstance(
                actual_time, int | float
            ):
                raise IntegrityError("replay event times must be numeric")
            if not _close(float(expected_time), float(actual_time), atol=time_atol, rtol=0.0):
                return False
        for expected_state, actual_state in zip(expected_states, actual_states, strict=True):
            left = _state(expected_state, "expected event state")
            right = _state(actual_state, "actual event state")
            if len(left) != len(right) or not all(
                _close(a, b, atol=state_atol, rtol=state_rtol)
                for a, b in zip(left, right, strict=True)
            ):
                return False
    return True


def _tolerance_comparison(
    label: str,
    expected: Mapping[str, object],
    run: SimulationResult,
    expected_identity: object,
    policy: Mapping[str, object],
) -> Mapping[str, object]:
    expected_trace = _sequence(expected.get("trace"), f"{label}.trace")
    actual_trace = run.trace
    max_unmatched = policy.get("max_unmatched_points")
    if not isinstance(max_unmatched, int) or isinstance(max_unmatched, bool):
        raise IntegrityError("replay comparison.max_unmatched_points must be an integer")
    count_difference = abs(len(expected_trace) - len(actual_trace))
    grid_match = count_difference <= max_unmatched
    state_match = True
    observations_match = True
    time_atol = _policy_number(policy, "retained_grid_time_atol")
    state_atol = _policy_number(policy, "state_atol")
    state_rtol = _policy_number(policy, "state_rtol")
    for raw, point in zip(expected_trace, actual_trace, strict=False):
        expected_point = _mapping(raw, f"{label}.trace point")
        expected_time = expected_point.get("time")
        if not isinstance(expected_time, int | float) or isinstance(expected_time, bool):
            raise IntegrityError(f"replay {label}.trace point time must be numeric")
        grid_match = grid_match and _close(
            float(expected_time), point.time, atol=time_atol, rtol=0.0
        )
        expected_state = _state(expected_point.get("state"), f"{label}.trace state")
        state_match = (
            state_match
            and len(expected_state) == len(point.state)
            and all(
                _close(a, b, atol=state_atol, rtol=state_rtol)
                for a, b in zip(expected_state, point.state, strict=False)
            )
        )
        observations_match = observations_match and _observations_match(
            expected_point.get("observations"), point.observations, policy
        )
    expected_final = _state(expected.get("final_state"), f"{label}.final_state")
    endpoint_state_match = len(expected_final) == len(run.final_state) and all(
        _close(a, b, atol=state_atol, rtol=state_rtol)
        for a, b in zip(expected_final, run.final_state, strict=False)
    )
    expected_metadata = _mapping(expected.get("execution_metadata"), "execution metadata")
    expected_endpoint = expected_metadata.get("termination_time")
    actual_endpoint = run.execution_metadata.get("termination_time")
    if not isinstance(expected_endpoint, int | float) or not isinstance(
        actual_endpoint, int | float
    ):
        raise IntegrityError("tolerance replay requires numeric termination_time evidence")
    endpoint_time_match = _close(
        float(expected_endpoint),
        float(actual_endpoint),
        atol=_policy_number(policy, "endpoint_time_atol"),
        rtol=0.0,
    )
    invariant_match, invariant_threshold_match = _invariants_match(
        expected.get("invariants"), run.invariants, policy
    )
    require_classifier = policy.get("require_classifier") is True
    require_invariants = policy.get("require_invariants") is True
    expected_success = policy.get("expected_solver_success")
    actual_success = bool(run.execution_metadata.get("solver_success", True))
    return {
        "series": label,
        "mode": "tolerance",
        "classification_match": (run.classification == expected.get("classification"))
        if require_classifier
        else True,
        "model_identity_match": run.model_identity == expected_identity,
        "solver_success_match": actual_success is expected_success,
        "retained_grid_match": grid_match,
        "state_tolerance_match": state_match,
        "observable_tolerance_match": observations_match,
        "endpoint_state_match": endpoint_state_match,
        "endpoint_time_match": endpoint_time_match,
        "event_tolerance_match": _event_match(expected_metadata, run.execution_metadata, policy),
        "invariant_result_match": invariant_match if require_invariants else True,
        "invariant_threshold_match": invariant_threshold_match if require_invariants else True,
        "artifact_trace_sha256_equal": run.trace_sha256 == expected.get("trace_sha256"),
        "expected_environment": expected_metadata,
        "actual_environment": dict(run.execution_metadata),
    }


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    """Replay verdict with exact or declared-tolerance comparisons."""

    ok: bool
    mode: str
    model: str
    baseline: SimulationResult
    changed: SimulationResult | None
    comparisons: tuple[Mapping[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "2.0",
            "status": "REPLAY VERIFIED" if self.ok else "REPLAY MISMATCH",
            "comparison_mode": self.mode,
            "model": self.model,
            "ok": self.ok,
            "comparisons": [dict(item) for item in self.comparisons],
            "baseline": self.baseline.as_dict(),
            "changed": self.changed.as_dict() if self.changed is not None else None,
        }


def verify_replay(path: Path) -> ReplayVerification:
    """Re-execute a v1/v2 fixture and apply its explicit comparison policy."""

    fixture = validate_fixture(path)
    configuration = fixture.get("configuration")
    if not isinstance(configuration, dict):
        raise IntegrityError("replay configuration must be an object")
    config = parse_config(canonical_json(configuration), f"replay fixture {path.name}")
    expected_model = fixture.get("model")
    if config.model != expected_model:
        raise IntegrityError("replay model does not match embedded configuration")
    expected_identity = fixture.get("model_identity")
    if fixture.get("schema_version") == "1.0":
        mode = "exact"
        policy: Mapping[str, object] = {"mode": mode}
    else:
        policy = _mapping(fixture.get("comparison"), "comparison")
        raw_mode = policy.get("mode")
        if raw_mode not in {"exact", "tolerance"}:
            raise IntegrityError("replay comparison.mode must be exact or tolerance")
        mode = cast(str, raw_mode)

    comparisons: list[Mapping[str, object]] = []

    def execute(label: str, raw: object) -> SimulationResult:
        expected = _mapping(raw, label)
        run = simulate(
            config,
            parameters_override=_float_mapping(expected.get("parameters"), f"{label}.parameters"),
            initial_override=_state(expected.get("initial_state"), f"{label}.initial_state"),
        )
        if mode == "exact":
            comparisons.append(
                {
                    "series": label,
                    "mode": "exact",
                    "classification_match": run.classification == expected.get("classification"),
                    "trace_hash_match": run.trace_sha256 == expected.get("trace_sha256"),
                    "model_identity_match": run.model_identity == expected_identity,
                    "expected_trace_sha256": expected.get("trace_sha256"),
                    "actual_trace_sha256": run.trace_sha256,
                }
            )
        else:
            comparisons.append(
                _tolerance_comparison(label, expected, run, expected_identity, policy)
            )
        return run

    baseline = execute("baseline", fixture.get("baseline"))
    changed_raw = fixture.get("changed")
    changed = execute("changed", changed_raw) if changed_raw is not None else None
    ok = all(
        all(value is True for key, value in item.items() if key.endswith("_match"))
        for item in comparisons
    )
    return ReplayVerification(
        ok=ok,
        mode=mode,
        model=config.model,
        baseline=baseline,
        changed=changed,
        comparisons=tuple(comparisons),
    )
