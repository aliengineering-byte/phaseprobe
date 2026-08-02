"""Practical Python API for supplied step-level or trajectory-level adapters."""

from __future__ import annotations

from collections.abc import Mapping

from phaseprobe.config import CONFIG_SCHEMA_VERSION, ProbeConfig, canonical_json, parse_config
from phaseprobe.engine import (
    Adapter,
    ProbeOutcome,
    SimulationResult,
    run_check,
    run_perturb,
    run_scan,
    simulate,
)


def _coerce_config(adapter: Adapter, config: ProbeConfig | Mapping[str, object]) -> ProbeConfig:
    if isinstance(config, ProbeConfig):
        return config
    data = dict(config)
    data.setdefault("schema_version", CONFIG_SCHEMA_VERSION)
    data.setdefault("model", adapter.name)
    data.setdefault("seed", 0)
    return parse_config(canonical_json(data), "Python API configuration")


def run_simulation(
    adapter: Adapter, config: ProbeConfig | Mapping[str, object]
) -> SimulationResult:
    """Run one supplied adapter without registering it globally."""

    return simulate(_coerce_config(adapter, config), adapter=adapter)


def run_parameter_scan(
    adapter: Adapter, config: ProbeConfig | Mapping[str, object]
) -> ProbeOutcome:
    """Run the shared bounded one-dimensional scan with a supplied adapter."""

    return run_scan(_coerce_config(adapter, config), adapter=adapter)


def run_perturbation(adapter: Adapter, config: ProbeConfig | Mapping[str, object]) -> ProbeOutcome:
    """Run the shared bounded initial-state perturbation search."""

    return run_perturb(_coerce_config(adapter, config), adapter=adapter)


def run_invariant_check(
    adapter: Adapter, config: ProbeConfig | Mapping[str, object]
) -> ProbeOutcome:
    """Run the shared declared CI policy and invariant evaluation."""

    return run_check(_coerce_config(adapter, config), adapter=adapter)


__all__ = [
    "run_invariant_check",
    "run_parameter_scan",
    "run_perturbation",
    "run_simulation",
]
