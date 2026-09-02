"""Artifact, integrity, replay, report, and generated-test integration tests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from phaseprobe.artifacts import write_artifacts
from phaseprobe.config import load_example
from phaseprobe.engine import run_check
from phaseprobe.errors import IntegrityError
from phaseprobe.generate import generate_regression_test
from phaseprobe.replay import validate_fixture, verify_replay
from phaseprobe.reporting import regenerate_reports


@pytest.fixture
def artifact_run(tmp_path: Path) -> Path:
    outcome = run_check(load_example("predator-prey"))
    return write_artifacts(outcome, tmp_path / "runs").run_directory


def test_artifact_manifest_hashes_every_evidence_file(artifact_run: Path) -> None:
    manifest = json.loads((artifact_run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bounded_trace"]["baseline_points"] == 4000
    for name, evidence in manifest["files"].items():
        digest = hashlib.sha256((artifact_run / name).read_bytes()).hexdigest()
        assert digest == evidence["sha256"]


@pytest.mark.integration
def test_replay_reexecutes_exact_trace(artifact_run: Path) -> None:
    result = verify_replay(artifact_run / "replay.json")
    assert result.ok
    assert result.comparisons[0]["trace_hash_match"] is True


def test_replay_rejects_tampering(artifact_run: Path) -> None:
    fixture = artifact_run / "replay.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["seed"] = 999
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IntegrityError, match="integrity mismatch"):
        validate_fixture(fixture)


@pytest.mark.integration
def test_generated_pytest_genuinely_executes(artifact_run: Path, tmp_path: Path) -> None:
    generated = generate_regression_test(artifact_run / "replay.json", tmp_path / "generated")
    assert str(tmp_path) not in generated.test_path.read_text(encoding="utf-8")
    evidence = json.loads(generated.evidence_path.read_text(encoding="utf-8"))
    assert str(tmp_path) not in generated.evidence_path.read_text(encoding="utf-8")
    assert evidence["producer"] == {
        "capability": "validated-replay-to-pytest",
        "documentation": "https://github.com/aliengineering-byte/phaseprobe#five-minute-quick-start",
        "repository": "aliengineering-byte/phaseprobe",
        "version": "0.2.1",
    }
    assert evidence["claim"]["baseline_classification"] == "bounded-positive-oscillation"
    assert evidence["claim"]["changed_classification"] is None
    assert evidence["decision"]["status"] == "REPLAY_VERIFIED"
    assert evidence["artifacts"]["replay_fixture"]["path"] == ("fixtures/predator_prey-replay.json")
    assert evidence["artifacts"]["pytest_regression"]["path"] == (
        "test_predator_prey_transition.py"
    )
    for artifact in evidence["artifacts"].values():
        digest = hashlib.sha256((generated.test_path.parent / artifact["path"]).read_bytes())
        assert digest.hexdigest() == artifact["sha256"]
    assert evidence["reproduction"] == {
        "command": "python -m pytest -q test_predator_prey_transition.py",
        "working_directory": ".",
    }
    assert (
        generate_regression_test(artifact_run / "replay.json", tmp_path / "generated") == generated
    )
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


def test_generated_pytest_refuses_conflicting_overwrite(artifact_run: Path, tmp_path: Path) -> None:
    output_directory = tmp_path / "generated"
    generated = generate_regression_test(artifact_run / "replay.json", output_directory)
    generated.test_path.write_text("# user-owned test\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        generate_regression_test(artifact_run / "replay.json", output_directory)
    assert generated.test_path.read_text(encoding="utf-8") == "# user-owned test\n"


def test_generated_pytest_refuses_conflicting_evidence(artifact_run: Path, tmp_path: Path) -> None:
    output_directory = tmp_path / "generated"
    generated = generate_regression_test(artifact_run / "replay.json", output_directory)
    generated.evidence_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="generated pytest evidence"):
        generate_regression_test(artifact_run / "replay.json", output_directory)
    assert generated.evidence_path.read_text(encoding="utf-8") == "{}\n"


def test_html_report_is_self_contained_and_offline(artifact_run: Path) -> None:
    report = (artifact_run / "report.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in report
    assert "Scientific limitations" in report
    assert "cdn" not in report.lower()
    assert "<script" not in report.lower()


def test_report_command_source_regenerates_json_and_html(artifact_run: Path) -> None:
    json_path, html_path = regenerate_reports(artifact_run)
    assert json_path.exists()
    assert html_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == "2.0"
