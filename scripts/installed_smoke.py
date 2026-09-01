"""Exercise a PhaseProbe installation without importing from its source checkout."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import phaseprobe
from phaseprobe.config import EXAMPLES, canonical_json, load_config, load_example
from phaseprobe.errors import ConfigurationError


def run_cli(cwd: Path, *arguments: str, expected_returncode: int = 0) -> str:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "-m", "phaseprobe", *arguments],
        check=False,
        capture_output=True,
        cwd=cwd,
        env=environment,
        text=True,
        timeout=180,
    )
    if completed.returncode != expected_returncode:
        raise RuntimeError(
            f"phaseprobe {' '.join(arguments)} exited {completed.returncode}; "
            f"expected {expected_returncode}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def json_cli(cwd: Path, *arguments: str, expected_returncode: int = 0) -> dict[str, Any]:
    output = run_cli(cwd, *arguments, expected_returncode=expected_returncode)
    parsed = json.loads(output)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"expected JSON object from {' '.join(arguments)}")
    return parsed


def resolved_output_path(cwd: Path, value: object) -> Path:
    if not isinstance(value, str):
        raise RuntimeError(f"expected an artifact path, received {value!r}")
    path = Path(value)
    return (cwd / path).resolve() if not path.is_absolute() else path.resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    working_directory = Path.cwd().resolve()
    module_path = Path(phaseprobe.__file__).resolve()
    if module_path.is_relative_to(repo_root):
        raise RuntimeError(f"source checkout shadowed installed package: {module_path}")
    if working_directory.is_relative_to(repo_root):
        raise RuntimeError(
            f"smoke working directory is inside source checkout: {working_directory}"
        )
    if phaseprobe.__version__ != args.expected_version:
        raise RuntimeError(
            f"expected PhaseProbe {args.expected_version}, imported {phaseprobe.__version__}"
        )
    if os.environ.get("PYTHONPATH"):
        raise RuntimeError("PYTHONPATH must be unset for installed-package verification")

    loaded_examples: dict[str, str] = {}
    for name in EXAMPLES:
        config = load_example(name)
        loaded_examples[name] = str(config.data["schema_version"])

    help_output = run_cli(working_directory, "perturb", "--help")
    if "scipy-lorenz" not in help_output:
        raise RuntimeError("installed CLI help does not list the SciPy built-in examples")

    scipy_cli_results: dict[str, str] = {}
    scipy_commands = {
        "scipy-lorenz": ("perturb", 0, "FINITE-TIME TRAJECTORY DIVERGENCE FOUND"),
        "scipy-lorenz-negative": ("perturb", 0, "NO SENSITIVE PERTURBATION FOUND"),
        "scipy-predator-prey": ("check", 0, "CHECK POLICY PASSED"),
        "scipy-predator-prey-coarse": ("check", 1, "CHECK POLICY FAILED"),
    }
    for name, (command, returncode, expected_status) in scipy_commands.items():
        result = json_cli(
            working_directory,
            command,
            "--example",
            name,
            "--output-root",
            f"{name} runs",
            "--json",
            expected_returncode=returncode,
        )
        status = result.get("status")
        if status != expected_status:
            raise RuntimeError(f"{name} reported {status!r}; expected {expected_status!r}")
        scipy_cli_results[name] = str(status)

    legacy_output = run_cli(working_directory, "perturb", "--config", "examples/scipy/lorenz.json")
    if "FINITE-TIME TRAJECTORY DIVERGENCE FOUND" not in legacy_output:
        raise RuntimeError("former SciPy Lorenz config path did not resolve to its built-in")

    backslash_config = load_config(Path(r"examples\scipy\lorenz.json"))
    if backslash_config.data != load_example("scipy-lorenz").data:
        raise RuntimeError("backslash-separated former config path resolved incorrectly")
    for missing in (Path("elsewhere/lorenz.json"), Path("examples/scipy/LORENZ.json")):
        try:
            load_config(missing)
        except ConfigurationError as exc:
            if "cannot read configuration" not in str(exc):
                raise RuntimeError(f"unexpected missing-config diagnostic: {exc}") from exc
        else:
            raise RuntimeError(f"unrelated missing path was misclassified: {missing}")

    former_path = working_directory / "examples" / "scipy" / "lorenz.json"
    former_path.parent.mkdir(parents=True)
    custom = load_example("scipy-lorenz-negative")
    former_path.write_text(canonical_json(custom.data), encoding="utf-8")
    if load_config(Path("examples/scipy/lorenz.json")).data != custom.data:
        raise RuntimeError("an existing user config did not take precedence over compatibility")

    scan = json_cli(
        working_directory,
        "scan",
        "--example",
        "logistic-negative",
        "--output-root",
        "scan runs",
        "--json",
    )
    artifacts = scan.get("artifacts")
    if not isinstance(artifacts, dict):
        raise RuntimeError("scan did not report artifact paths")
    replay_fixture = resolved_output_path(working_directory, artifacts.get("replay"))
    replay = json_cli(working_directory, "replay", str(replay_fixture), "--json")

    generated = json_cli(
        working_directory,
        "generate-test",
        str(replay_fixture),
        "--output-directory",
        "generated tests",
        "--json",
    )
    test_path = resolved_output_path(working_directory, generated.get("test"))
    source = test_path.read_text(encoding="utf-8")
    for forbidden in (str(repo_root), str(working_directory)):
        if forbidden in source:
            raise RuntimeError(f"generated pytest contains machine-specific path {forbidden!r}")
    pytest_result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", test_path.name],
        check=False,
        capture_output=True,
        cwd=test_path.parent,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        text=True,
        timeout=180,
    )
    if pytest_result.returncode != 0:
        raise RuntimeError(
            f"generated pytest exited {pytest_result.returncode}\n"
            f"stdout:\n{pytest_result.stdout}\nstderr:\n{pytest_result.stderr}"
        )

    print(
        json.dumps(
            {
                "status": "PASS",
                "phaseprobe_file": str(module_path),
                "phaseprobe_version": phaseprobe.__version__,
                "python_version": sys.version.split()[0],
                "working_directory": str(working_directory),
                "loaded_examples": loaded_examples,
                "legacy_issue_4_command": "FINITE-TIME TRAJECTORY DIVERGENCE FOUND",
                "scipy_cli_results": scipy_cli_results,
                "scan": scan.get("status"),
                "replay": replay.get("status"),
                "generated_pytest": pytest_result.stdout.strip(),
                "lorenz": scipy_cli_results["scipy-lorenz"],
                "predator_prey": scipy_cli_results["scipy-predator-prey"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
