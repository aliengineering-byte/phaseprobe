"""Versioned replay fixtures, integrity validation, and deterministic re-execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from phaseprobe import __version__
from phaseprobe.config import canonical_json, parse_config
from phaseprobe.engine import ProbeOutcome, SimulationResult, simulate
from phaseprobe.errors import ConfigurationError, IntegrityError

REPLAY_SCHEMA_VERSION = "1.0"


def _execution_payload(result: SimulationResult) -> dict[str, object]:
    return {
        "parameters": dict(result.parameters),
        "initial_state": list(result.initial_state),
        "classification": result.classification,
        "trace_sha256": result.trace_sha256,
        "invariant_violations": result.invariant_violations,
    }


def fixture_payload(outcome: ProbeOutcome) -> dict[str, object]:
    """Create an integrity-protected replay fixture from validated evidence."""

    payload: dict[str, object] = {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "created_by": f"phaseprobe {__version__}",
        "model": outcome.baseline.model,
        "model_identity": outcome.baseline.model_identity,
        "seed": outcome.baseline.seed,
        "configuration": dict(outcome.config.data),
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
    """Validate replay schema and SHA-256 integrity before any execution."""

    payload = _load_fixture(path)
    if payload.get("schema_version") != REPLAY_SCHEMA_VERSION:
        raise IntegrityError(
            f"unsupported replay schema {payload.get('schema_version')!r}; "
            f"expected {REPLAY_SCHEMA_VERSION!r}"
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


def _float_mapping(value: object, context: str) -> dict[str, float]:
    values = _mapping(value, context)
    result: dict[str, float] = {}
    for name, raw in values.items():
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise IntegrityError(f"replay {context}.{name} must be numeric")
        result[name] = float(raw)
    return result


def _state(value: object, context: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise IntegrityError(f"replay {context} must be an array")
    state: list[float] = []
    for raw in value:
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            raise IntegrityError(f"replay {context} contains a non-number")
        state.append(float(raw))
    return tuple(state)


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    """Deterministic replay verdict with comparisons suitable for CI diagnostics."""

    ok: bool
    model: str
    baseline: SimulationResult
    changed: SimulationResult | None
    comparisons: tuple[Mapping[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "status": "REPLAY VERIFIED" if self.ok else "REPLAY MISMATCH",
            "model": self.model,
            "ok": self.ok,
            "comparisons": [dict(item) for item in self.comparisons],
            "baseline": self.baseline.as_dict(),
            "changed": self.changed.as_dict() if self.changed is not None else None,
        }


def verify_replay(path: Path) -> ReplayVerification:
    """Re-execute the recorded model/config/seed and compare exact trace evidence."""

    fixture = validate_fixture(path)
    configuration = fixture.get("configuration")
    if not isinstance(configuration, dict):
        raise IntegrityError("replay configuration must be an object")
    config = parse_config(canonical_json(configuration), f"replay fixture {path.name}")
    expected_model = fixture.get("model")
    if config.model != expected_model:
        raise IntegrityError("replay model does not match embedded configuration")
    expected_identity = fixture.get("model_identity")

    comparisons: list[Mapping[str, object]] = []

    def execute(label: str, raw: object) -> SimulationResult:
        expected = _mapping(raw, label)
        run = simulate(
            config,
            parameters_override=_float_mapping(expected.get("parameters"), f"{label}.parameters"),
            initial_override=_state(expected.get("initial_state"), f"{label}.initial_state"),
        )
        classification_match = run.classification == expected.get("classification")
        hash_match = run.trace_sha256 == expected.get("trace_sha256")
        identity_match = run.model_identity == expected_identity
        comparisons.append(
            {
                "series": label,
                "classification_match": classification_match,
                "trace_hash_match": hash_match,
                "model_identity_match": identity_match,
                "expected_trace_sha256": expected.get("trace_sha256"),
                "actual_trace_sha256": run.trace_sha256,
            }
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
        model=config.model,
        baseline=baseline,
        changed=changed,
        comparisons=tuple(comparisons),
    )
