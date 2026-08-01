"""Numerical validation, positive cases, and negative controls."""

from __future__ import annotations

import math

import pytest

from phaseprobe.config import canonical_json, load_example, parse_config
from phaseprobe.engine import ProbeOutcome, run_check, run_perturb, run_scan, simulate
from phaseprobe.errors import ConfigurationError, NumericalFailure


@pytest.mark.numerical
def test_logistic_transition_is_refined_and_repeatable(logistic_outcome: ProbeOutcome) -> None:
    finding = logistic_outcome.finding
    assert finding is not None
    bracket = finding["stable_bracket"]
    assert isinstance(bracket, list)
    assert 3.449 < bracket[0] < bracket[1] < 3.45
    assert logistic_outcome.baseline.classification == "period-2"
    assert logistic_outcome.changed is not None
    assert logistic_outcome.changed.classification == "period-4"
    assert logistic_outcome.reproducible


@pytest.mark.numerical
def test_logistic_negative_control_has_no_transition() -> None:
    outcome = run_scan(load_example("logistic-negative"))
    assert outcome.finding is None
    assert outcome.status == "NO QUALITATIVE TRANSITION FOUND"


@pytest.mark.numerical
def test_lorenz_reports_finite_time_divergence_without_class_change() -> None:
    outcome = run_perturb(load_example("lorenz"))
    assert outcome.finding is not None
    assert outcome.finding["kind"] == "finite-time-divergence"
    metrics = outcome.finding["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["max_trajectory_distance"] >= 1.0
    assert isinstance(metrics["finite_time_divergence_rate"], float)
    assert outcome.changed is not None
    assert outcome.baseline.classification == outcome.changed.classification


@pytest.mark.numerical
def test_lorenz_short_window_negative_control() -> None:
    outcome = run_perturb(load_example("lorenz-negative"))
    assert outcome.finding is None
    assert outcome.status == "NO SENSITIVE PERTURBATION FOUND"


@pytest.mark.numerical
def test_predator_prey_refined_solver_preserves_declared_invariant() -> None:
    outcome = run_check(load_example("predator-prey"))
    assert not outcome.policy_failed
    assert outcome.baseline.classification == "bounded-positive-oscillation"
    assert outcome.baseline.invariant_violations == 0
    drift = outcome.baseline.invariants[0]
    assert drift.measured <= drift.tolerance


@pytest.mark.numerical
def test_predator_prey_coarse_solver_is_a_policy_failure() -> None:
    outcome = run_check(load_example("predator-prey-negative"))
    assert outcome.policy_failed
    assert outcome.finding is not None
    assert outcome.finding["kind"] == "invariant-violation"


@pytest.mark.numerical
def test_toggle_perturbation_switches_stable_state() -> None:
    outcome = run_perturb(load_example("toggle"))
    assert outcome.finding is not None
    assert outcome.baseline.classification == "u-dominant"
    assert outcome.changed is not None
    assert outcome.changed.classification == "v-dominant"
    assert outcome.reproducible


@pytest.mark.numerical
def test_toggle_negative_control_stays_in_baseline_basin() -> None:
    outcome = run_perturb(load_example("toggle-negative"))
    assert outcome.finding is None
    assert outcome.changed is not None
    assert outcome.changed.classification == "u-dominant"


def test_simulation_is_exactly_repeatable() -> None:
    config = load_example("predator-prey")
    first = simulate(config)
    second = simulate(config)
    assert first.trace_sha256 == second.trace_sha256
    assert first.final_state == second.final_state


def test_trace_retention_is_bounded() -> None:
    result = simulate(load_example("lorenz-negative"))
    assert len(result.trace) == result.settings.trace_cap == 500


def test_invalid_integration_is_diagnostic() -> None:
    base = load_example("logistic-negative")
    data = dict(base.data)
    data["parameters"] = {"r": 1e50}
    data["simulation"] = dict(base.section("simulation"), hard_state_limit=10.0)
    config = parse_config(canonical_json(data), "invalid-state-test")
    with pytest.raises(NumericalFailure, match="invalid integration"):
        simulate(config)


def test_invalid_search_bounds_are_rejected() -> None:
    base = load_example("logistic-negative")
    data = dict(base.data)
    data["scan"] = dict(base.section("scan"), stop=3.0)
    config = parse_config(canonical_json(data), "bad-scan")
    with pytest.raises(ConfigurationError, match="stop > start"):
        run_scan(config)


def test_every_retained_scalar_is_finite() -> None:
    result = simulate(load_example("toggle"))
    assert all(math.isfinite(value) for point in result.trace for value in point.state)
