"""Optional SciPy adapter, numerical controls, and tolerance-replay tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

import numpy as np
import numpy.typing as npt
import scipy

from phaseprobe import run_perturbation, run_simulation
from phaseprobe.adapters.scipy import EventSpec, SolveIVPAdapter
from phaseprobe.artifacts import write_artifacts
from phaseprobe.config import ProbeConfig, load_example, parse_config
from phaseprobe.engine import ProbeOutcome, run_check, run_perturb, simulate
from phaseprobe.errors import ConfigurationError, NumericalFailure
from phaseprobe.generate import generate_regression_test
from phaseprobe.replay import verify_replay
from phaseprobe.types import Parameters

pytestmark = pytest.mark.scipy
ROOT = Path(__file__).resolve().parents[1]
FloatArray = npt.NDArray[np.float64]


def exponential_rhs(time: float, state: FloatArray, parameters: Parameters) -> tuple[float, ...]:
    return (-parameters.get("rate", 1.0) * float(state[0]),)


def _adapter(
    *,
    atol: float | tuple[float, ...] = 1e-10,
    method: str = "DOP853",
    points: int = 21,
    events: tuple[EventSpec, ...] = (),
    vectorized: bool = False,
) -> SolveIVPAdapter:
    return SolveIVPAdapter(
        name="exponential-scipy",
        identity="test-exponential-v1",
        rhs=exponential_rhs,
        state_names=("value",),
        initial_state=(1.0,),
        t_span=(0.0, 2.0),
        t_eval=points,
        method=method,
        rtol=1e-9,
        atol=atol,
        max_step=0.1,
        events=events,
        vectorized=vectorized,
    )


def _engine_config() -> ProbeConfig:
    return parse_config(
        """{
          "schema_version":"2.0",
          "model":"exponential-scipy",
          "seed":7,
          "parameters":{"rate":1.0},
          "simulation":{"trace_cap":16,"hard_state_limit":100.0},
          "tolerances":{}
        }""",
        "test adapter",
    )


def test_adapter_construction_and_configuration_serialization() -> None:
    scalar = _adapter(atol=1e-10, method="RK45")
    vector = _adapter(atol=(1e-10,))
    assert scalar.configuration()["atol"] == 1e-10
    assert vector.configuration()["atol"] == [1e-10]
    assert scalar.configuration()["t_eval"] == {
        "kind": "linspace",
        "start": 0.0,
        "stop": 2.0,
        "points": 21,
    }
    assert scalar.identity.startswith("test-exponential-v1:sha256:")
    assert "rhs" not in scalar.configuration()


def test_t_eval_must_be_controlled_and_strictly_ordered() -> None:
    with pytest.raises(ConfigurationError, match="t_eval"):
        SolveIVPAdapter(
            name="bad-grid",
            identity="bad-grid-v1",
            rhs=exponential_rhs,
            state_names=("value",),
            initial_state=(1.0,),
            t_span=(0.0, 2.0),
            t_eval=(0.0, 1.0, 1.0, 2.0),
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"name": ""}, "name must be"),
        ({"state_names": ("value", "value"), "initial_state": (1.0, 2.0)}, "unique"),
        ({"initial_state": (1.0, 2.0)}, "length must match"),
        ({"t_span": (0.0, 0.0)}, "endpoints must differ"),
        ({"method": "not-a-method"}, "method must be"),
        ({"rtol": 0.0}, "rtol must be positive"),
        ({"atol": 0.0}, "atol must be positive"),
        ({"atol": (1e-9, 1e-9)}, "one positive value per state"),
        ({"max_step": 0.0}, "max_step must be positive"),
        ({"vectorized": 1}, "must be booleans"),
        ({"t_eval": True}, "integer point count"),
        ({"t_eval": 1}, "point count must be between"),
        ({"t_eval": (0.1, 2.0)}, "include both"),
    ],
)
def test_adapter_rejects_invalid_numerical_configuration(
    changes: dict[str, object], message: str
) -> None:
    arguments: dict[str, object] = {
        "name": "exponential-scipy",
        "identity": "validation-v1",
        "rhs": exponential_rhs,
        "state_names": ("value",),
        "initial_state": (1.0,),
        "t_span": (0.0, 2.0),
        "t_eval": 21,
    }
    arguments.update(changes)
    with pytest.raises(ConfigurationError, match=message):
        SolveIVPAdapter(**arguments)  # type: ignore[arg-type]


def test_event_policy_validation() -> None:
    def event(time: float, state: FloatArray, parameters: Parameters) -> float:
        return float(state[0])

    with pytest.raises(ConfigurationError, match="name"):
        EventSpec("", event)
    with pytest.raises(ConfigurationError, match="terminal"):
        EventSpec("bad-terminal", event, terminal=0)
    with pytest.raises(ConfigurationError, match="direction"):
        EventSpec("bad-direction", event, direction=float("nan"))
    duplicate = EventSpec("duplicate", event)
    with pytest.raises(ConfigurationError, match="event names must be unique"):
        _adapter(events=(duplicate, duplicate))


def test_from_config_accepts_serialized_options_and_rejects_bad_shapes() -> None:
    options: dict[str, object] = {
        "identity": "serialized-v1",
        "state_names": ["value"],
        "initial_state": [1.0],
        "t_span": [0.0, 2.0],
        "t_eval": {"kind": "linspace", "points": 5},
        "method": "RK45",
    }
    adapter = SolveIVPAdapter.from_config(
        name="serialized-scipy", rhs=exponential_rhs, values={"options": options}
    )
    assert adapter.configuration()["t_eval"] == {
        "kind": "linspace",
        "start": 0.0,
        "stop": 2.0,
        "points": 5,
    }

    invalid: list[tuple[object, str]] = [
        (None, "must be an object"),
        ({**options, "state_names": "value"}, "array of strings"),
        ({**options, "t_span": [0.0]}, "contain two values"),
        (
            {**options, "t_eval": {"kind": "explicit", "points": 5}},
            "kind must be 'linspace'",
        ),
        ({**options, "t_eval": {"kind": "linspace", "points": True}}, "must be an integer"),
        ({**options, "t_eval": "automatic"}, "array or linspace object"),
        ({**options, "vectorized": "yes"}, "must be booleans"),
    ]
    for raw_options, message in invalid:
        with pytest.raises(ConfigurationError, match=message):
            SolveIVPAdapter.from_config(
                name="serialized-scipy",
                rhs=exponential_rhs,
                values={"options": raw_options},
            )


def test_callback_and_solver_result_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _adapter()
    with pytest.raises(NumericalFailure, match="initial state"):
        adapter.simulate((1.0, 2.0), {}, {}, 0)

    def complex_rhs(time: float, state: FloatArray, parameters: Parameters) -> object:
        return np.array([1.0j])

    complex_adapter = SolveIVPAdapter(
        name="complex",
        identity="complex-v1",
        rhs=complex_rhs,
        state_names=("value",),
        initial_state=(1.0,),
        t_span=(0.0, 1.0),
    )
    with pytest.raises(NumericalFailure, match="real-valued states"):
        complex_adapter._checked_rhs({})(0.0, np.array([1.0]))

    def wrong_shape_rhs(time: float, state: FloatArray, parameters: Parameters) -> object:
        return np.array([1.0, 2.0])

    shape_adapter = SolveIVPAdapter(
        name="shape",
        identity="shape-v1",
        rhs=wrong_shape_rhs,
        state_names=("value",),
        initial_state=(1.0,),
        t_span=(0.0, 1.0),
    )
    with pytest.raises(NumericalFailure, match="RHS returned shape"):
        shape_adapter._checked_rhs({})(0.0, np.array([1.0]))

    def failed_solve(*args: object, **kwargs: object) -> object:
        raise ValueError("invalid public solver input")

    monkeypatch.setattr("phaseprobe.adapters.scipy.solve_ivp", failed_solve)
    with pytest.raises(NumericalFailure, match="failed before returning"):
        adapter.simulate((1.0,), {}, {}, 0)


@pytest.mark.parametrize(
    ("observable", "message"),
    [
        (lambda time, state, parameters: {"": 1.0}, "names must be non-empty"),
        (lambda time, state, parameters: {"value": float("nan")}, "NaN or infinite"),
        (lambda time, state, parameters: {"value": object()}, "finite number or string"),
    ],
)
def test_observable_and_classifier_contracts_are_validated(
    observable: object, message: str
) -> None:
    adapter = SolveIVPAdapter(
        name="callbacks",
        identity="callbacks-v1",
        rhs=exponential_rhs,
        state_names=("value",),
        initial_state=(1.0,),
        t_span=(0.0, 1.0),
        observable=observable,  # type: ignore[arg-type]
    )
    with pytest.raises(NumericalFailure, match=message):
        adapter._point(0, 0.0, np.array([1.0]), {})

    invalid_classifier = SolveIVPAdapter(
        name="classifier",
        identity="classifier-v1",
        rhs=exponential_rhs,
        state_names=("value",),
        initial_state=(1.0,),
        t_span=(0.0, 1.0),
        classifier=lambda trace, tolerances: "",
    )
    trace = _adapter().simulate((1.0,), {}, {}, 0)
    with pytest.raises(NumericalFailure, match="classifier"):
        invalid_classifier.classify(trace, {})


def test_solver_method_vectorization_and_tolerances_are_forwarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_solve_ivp(*args: object, **kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            t=np.array([0.0, 2.0]),
            y=np.array([[1.0, 0.1]]),
            t_events=None,
            y_events=None,
            success=True,
            status=0,
            message="finished",
            nfev=4,
            njev=0,
            nlu=0,
        )

    monkeypatch.setattr("phaseprobe.adapters.scipy.solve_ivp", fake_solve_ivp)
    adapter = _adapter(atol=(1e-11,), method="BDF", vectorized=True)
    trace = adapter.simulate((1.0,), {"rate": 1.0}, {}, 7)
    assert trace.success
    assert captured["method"] == "BDF"
    assert captured["vectorized"] is True
    captured_atol = captured["atol"]
    assert isinstance(captured_atol, np.ndarray)
    np.testing.assert_allclose(captured_atol, np.array([1e-11]))


def test_successful_solve_records_versions_status_and_function_evaluations() -> None:
    result = simulate(_engine_config(), adapter=_adapter())
    assert result.trace[-1].state[0] == pytest.approx(np.exp(-2.0), rel=1e-8)
    assert result.execution_metadata["scipy_version"] == scipy.__version__
    assert result.execution_metadata["solver_status"] == 0
    assert result.execution_metadata["solver_success"] is True
    nfev = result.execution_metadata["nfev"]
    assert isinstance(nfev, int) and nfev > 0
    assert result.replay_mode == "tolerance"


def test_public_python_api_accepts_a_supplied_trajectory_adapter() -> None:
    adapter = _adapter()
    result = run_simulation(
        adapter,
        {
            "parameters": {"rate": 1.0},
            "simulation": {"trace_cap": 21, "hard_state_limit": 100.0},
            "tolerances": {},
        },
    )
    assert result.model == "exponential-scipy"
    outcome = run_perturbation(
        adapter,
        {
            "parameters": {"rate": 1.0},
            "simulation": {"trace_cap": 21, "hard_state_limit": 100.0},
            "tolerances": {},
            "perturb": {
                "dimension": "value",
                "start": 1e-8,
                "stop": 1e-6,
                "points": 2,
                "predicate": "finite-time-divergence",
                "divergence_threshold": 1.0,
                "refine_iterations": 0,
                "repeatability": 1,
            },
            "classification_rule": "test bounded finite-time distance",
            "refinement_rule": "test declared grid",
        },
    )
    assert outcome.finding is None


def test_event_handling_retains_terminal_event_evidence() -> None:
    def half_value(time: float, state: FloatArray, parameters: Parameters) -> float:
        return float(state[0] - 0.5)

    adapter = _adapter(events=(EventSpec("half-value", half_value, terminal=True, direction=-1),))
    trace = adapter.simulate((1.0,), {"rate": 1.0}, {}, 7)
    assert trace.status == 1
    assert trace.success
    assert trace.metadata["termination_time"] == pytest.approx(np.log(2.0), rel=1e-8)
    events = trace.metadata["events"]
    assert isinstance(events, list)
    assert events[0]["name"] == "half-value"
    assert trace.final_state[0] == pytest.approx(0.5, rel=1e-8)


def test_invalid_initial_state_and_nan_rhs_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="finite"):
        SolveIVPAdapter(
            name="invalid",
            identity="invalid-v1",
            rhs=exponential_rhs,
            state_names=("value",),
            initial_state=(float("nan"),),
            t_span=(0.0, 1.0),
        )

    def nan_rhs(time: float, state: FloatArray, parameters: Parameters) -> tuple[float, ...]:
        return (float("nan"),)

    adapter = SolveIVPAdapter(
        name="nan-scipy",
        identity="nan-v1",
        rhs=nan_rhs,
        state_names=("value",),
        initial_state=(1.0,),
        t_span=(0.0, 1.0),
    )
    with pytest.raises(NumericalFailure, match="NaN or infinite"):
        adapter.simulate((1.0,), {}, {}, 0)


def test_unsuccessful_solver_termination_is_not_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_solve(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            t=np.array([0.0, 0.1]),
            y=np.array([[1.0, 0.9]]),
            t_events=None,
            y_events=None,
            success=False,
            status=-1,
            message="required step size is too small",
            nfev=20,
            njev=0,
            nlu=0,
        )

    monkeypatch.setattr("phaseprobe.adapters.scipy.solve_ivp", failed_solve)
    with pytest.raises(NumericalFailure, match="status -1"):
        simulate(_engine_config(), adapter=_adapter())


def test_engine_enforces_bounded_trace_retention() -> None:
    result = simulate(_engine_config(), adapter=_adapter(points=101))
    assert len(result.trace) == 16
    assert result.trace[0].time == 0.0
    assert result.trace[-1].time == 2.0
    assert result.execution_metadata["retention"] == {
        "points_produced": 101,
        "points_retained": 16,
        "strategy": "uniform-in-index-with-endpoints",
    }


@pytest.fixture(scope="session")
def lorenz_positive() -> ProbeOutcome:
    return run_perturb(load_example("scipy-lorenz"))


@pytest.fixture(scope="session")
def lorenz_negative() -> ProbeOutcome:
    return run_perturb(load_example("scipy-lorenz-negative"))


@pytest.fixture(scope="session")
def predator_prey_tight() -> ProbeOutcome:
    return run_check(load_example("scipy-predator-prey"))


@pytest.fixture(scope="session")
def predator_prey_coarse() -> ProbeOutcome:
    return run_check(load_example("scipy-predator-prey-coarse"))


def test_lorenz_positive_is_only_finite_time_divergence(lorenz_positive: ProbeOutcome) -> None:
    assert lorenz_positive.status == "FINITE-TIME TRAJECTORY DIVERGENCE FOUND"
    assert lorenz_positive.finding is not None
    assert lorenz_positive.finding["kind"] == "finite-time-divergence"
    assert lorenz_positive.reproducible


def test_lorenz_short_window_is_a_negative_control(lorenz_negative: ProbeOutcome) -> None:
    assert lorenz_negative.status == "NO SENSITIVE PERTURBATION FOUND"
    assert lorenz_negative.finding is None


def test_predator_prey_refinement_and_coarse_negative_control(
    predator_prey_tight: ProbeOutcome, predator_prey_coarse: ProbeOutcome
) -> None:
    tight = predator_prey_tight.baseline.invariants[0]
    coarse = predator_prey_coarse.baseline.invariants[0]
    assert predator_prey_tight.policy_failed is False
    assert tight.passed
    assert predator_prey_coarse.policy_failed is True
    assert not coarse.passed
    assert tight.measured < coarse.measured * 1e-6


def test_tolerance_replay_preserves_integrity_and_executes_generated_pytest(
    predator_prey_tight: ProbeOutcome, tmp_path: Path
) -> None:
    bundle = write_artifacts(predator_prey_tight, tmp_path / "runs")
    verification = verify_replay(bundle.replay_json)
    assert verification.ok
    assert verification.mode == "tolerance"
    assert verification.comparisons[0]["state_tolerance_match"] is True
    assert verification.comparisons[0]["artifact_trace_sha256_equal"] is True

    generated = generate_regression_test(bundle.replay_json, tmp_path / "generated")
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("COV_CORE") and name != "COVERAGE_PROCESS_START"
    }
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", generated.test_path.name],
        check=False,
        capture_output=True,
        cwd=generated.test_path.parent,
        env=environment,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "1 passed" in completed.stdout


def test_committed_v1_fixture_remains_exact_replay_compatible() -> None:
    fixture = ROOT / "tests" / "generated" / "fixtures" / "logistic_map-replay.json"
    verification = verify_replay(fixture)
    assert verification.ok
    assert verification.mode == "exact"
