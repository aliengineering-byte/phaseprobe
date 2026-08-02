"""CLI integration and documented exit-code tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phaseprobe.artifacts import write_artifacts
from phaseprobe.cli import main
from phaseprobe.config import load_example
from phaseprobe.engine import run_check
from phaseprobe.errors import ExitCode


@pytest.fixture
def cli_artifact(tmp_path: Path) -> Path:
    outcome = run_check(load_example("predator-prey"))
    return write_artifacts(outcome, tmp_path / "artifact-runs").run_directory


def test_scan_success_is_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "scan",
            "--example",
            "logistic-negative",
            "--output-root",
            str(tmp_path / "runs"),
        ]
    )
    assert code == ExitCode.OK
    assert "NO QUALITATIVE TRANSITION FOUND" in capsys.readouterr().out


def test_check_policy_failure_is_one(tmp_path: Path) -> None:
    code = main(
        [
            "check",
            "--example",
            "predator-prey-negative",
            "--output-root",
            str(tmp_path / "runs"),
        ]
    )
    assert code == ExitCode.POLICY_FAILED


def test_invalid_configuration_is_two(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{}", encoding="utf-8")
    code = main(["scan", "--config", str(path), "--output-root", str(tmp_path / "runs")])
    assert code == ExitCode.INVALID_INPUT


def test_numerical_failure_is_three(tmp_path: Path) -> None:
    data = {
        "schema_version": "1.0",
        "model": "logistic-map",
        "seed": 1,
        "parameters": {"r": 1e50},
        "model_config": {"initial_state": {"x": 0.2}},
        "simulation": {
            "steps": 20,
            "burn_in": 0,
            "dt": 1,
            "sample_every": 1,
            "trace_cap": 20,
            "hard_state_limit": 10,
        },
        "tolerances": {"period": 1e-6},
        "scan": {"parameter": "r", "start": 1e50, "stop": 2e50, "points": 2},
        "classification_rule": "test",
        "refinement_rule": "test",
        "invalid_state_policy": "abort",
    }
    path = tmp_path / "numerical.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["scan", "--config", str(path), "--output-root", str(tmp_path / "runs")])
    assert code == ExitCode.NUMERICAL_FAILURE


def test_json_output_is_versioned(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "check",
            "--example",
            "predator-prey",
            "--output-root",
            str(tmp_path / "runs"),
            "--json",
        ]
    )
    assert code == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "2.0"
    assert payload["artifacts"]["replay"].endswith("replay.json")


def test_replay_generate_and_report_commands(
    cli_artifact: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    replay_code = main(["replay", str(cli_artifact / "replay.json")])
    assert replay_code == ExitCode.OK
    assert "REPLAY VERIFIED" in capsys.readouterr().out

    generated_directory = tmp_path / "generated-tests"
    generate_code = main(
        [
            "generate-test",
            str(cli_artifact / "replay.json"),
            "--output-directory",
            str(generated_directory),
            "--json",
        ]
    )
    assert generate_code == ExitCode.OK
    generated_payload = json.loads(capsys.readouterr().out)
    assert Path(generated_payload["test"]).exists()

    report_code = main(["report", str(cli_artifact), "--format", "all"])
    assert report_code == ExitCode.OK
    report_output = capsys.readouterr().out
    assert "CHECK POLICY PASSED" in report_output
    assert (cli_artifact / "report.json").exists()


def test_fail_on_finding_is_one(tmp_path: Path) -> None:
    code = main(
        [
            "perturb",
            "--example",
            "toggle",
            "--output-root",
            str(tmp_path / "runs"),
            "--fail-on-finding",
        ]
    )
    assert code == ExitCode.POLICY_FAILED


def test_tampered_replay_is_invalid_input(cli_artifact: Path) -> None:
    fixture = cli_artifact / "replay.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["seed"] = 999
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["replay", str(fixture)]) == ExitCode.INVALID_INPUT


def test_internal_defect_is_four(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_execute(_config: object) -> object:
        raise RuntimeError("synthetic containment test")

    monkeypatch.setattr("phaseprobe.cli.run_scan", broken_execute)
    code = main(
        [
            "scan",
            "--example",
            "logistic-negative",
            "--output-root",
            str(tmp_path / "runs"),
        ]
    )
    assert code == ExitCode.INTERNAL_ERROR
