"""Install wheel and sdist into fresh environments and run public smoke workflows."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import venv
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "installed_smoke.py"


def environment_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=cwd,
        env=environment,
        text=True,
        timeout=600,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command exited {completed.returncode}: {command!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def discover_one(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one {pattern} in {directory}, found {matches}")
    return matches[0].resolve()


def project_version() -> str:
    in_project = False
    for raw_line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "[project]":
            in_project = True
            continue
        if in_project and line.startswith("["):
            break
        key, separator, value = line.partition("=")
        if in_project and separator and key.strip() == "version":
            parsed = json.loads(value.strip())
            if isinstance(parsed, str):
                return parsed
            break
    raise RuntimeError("project.version must be a quoted string")


def verify_base_wheel(
    artifact: Path,
    work_root: Path,
    expected_version: str,
    base_environment: dict[str, str],
) -> dict[str, str]:
    environment_directory = work_root / "base wheel environment"
    smoke_directory = work_root / "base wheel unrelated working directory"
    smoke_directory.mkdir()
    venv.EnvBuilder(with_pip=True).create(environment_directory)
    python = environment_python(environment_directory)
    run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(artifact)],
        cwd=smoke_directory,
        environment=base_environment,
    )
    identity = run(
        [
            str(python),
            "-I",
            "-c",
            (
                "import importlib.util, json, phaseprobe; "
                "assert importlib.util.find_spec('numpy') is None; "
                "assert importlib.util.find_spec('scipy') is None; "
                f"assert phaseprobe.__version__ == {expected_version!r}; "
                "print(json.dumps({'phaseprobe_file': phaseprobe.__file__, "
                "'phaseprobe_version': phaseprobe.__version__}))"
            ),
        ],
        cwd=smoke_directory,
        environment=base_environment,
    )
    scan = run(
        [
            str(python),
            "-m",
            "phaseprobe",
            "scan",
            "--example",
            "logistic-negative",
            "--output-root",
            "base scan runs",
            "--json",
        ],
        cwd=smoke_directory,
        environment=base_environment,
    )
    pip_check = run(
        [str(python), "-m", "pip", "check"],
        cwd=smoke_directory,
        environment=base_environment,
    )
    return {
        "identity": identity.strip(),
        "scan": json.loads(scan)["status"],
        "pip_check": pip_check.strip(),
    }


def verify(
    kind: str,
    artifact: Path,
    work_root: Path,
    expected_version: str,
    base_environment: dict[str, str],
) -> dict[str, Any]:
    environment_directory = work_root / f"{kind} environment"
    smoke_directory = work_root / f"{kind} unrelated working directory"
    smoke_directory.mkdir()
    venv.EnvBuilder(with_pip=True).create(environment_directory)
    python = environment_python(environment_directory)
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            f"{artifact}[scipy]",
            "pytest==8.4.1",
        ],
        cwd=smoke_directory,
        environment=base_environment,
    )
    pip_check = run(
        [str(python), "-m", "pip", "check"],
        cwd=smoke_directory,
        environment=base_environment,
    ).strip()
    smoke_output = run(
        [
            str(python),
            str(SMOKE),
            "--repo-root",
            str(ROOT),
            "--expected-version",
            expected_version,
        ],
        cwd=smoke_directory,
        environment=base_environment,
    )
    smoke = json.loads(smoke_output)
    if not isinstance(smoke, dict):
        raise RuntimeError("installed smoke did not emit a JSON object")
    return {
        "artifact": str(artifact),
        "pip_check": pip_check,
        "smoke": smoke,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--expected-version")
    parser.add_argument("--artifact", choices=("both", "wheel", "sdist"), default="both")
    args = parser.parse_args()

    dist_directory = args.dist_dir.resolve()
    work_root = args.work_root.resolve()
    if work_root.exists():
        raise RuntimeError(f"work root already exists; refusing to overwrite it: {work_root}")
    work_root.mkdir(parents=True)
    temporary_directory = work_root / "temporary files"
    cache_directory = work_root / "pip cache"
    temporary_directory.mkdir()
    cache_directory.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_CACHE_DIR"] = str(cache_directory)
    environment["TEMP"] = str(temporary_directory)
    environment["TMP"] = str(temporary_directory)

    expected_version = args.expected_version or project_version()
    selected: list[tuple[str, Path]] = []
    wheel: Path | None = None
    if args.artifact in {"both", "wheel"}:
        wheel = discover_one(dist_directory, "phaseprobe-*.whl")
        selected.append(("wheel", wheel))
    if args.artifact in {"both", "sdist"}:
        selected.append(("sdist", discover_one(dist_directory, "phaseprobe-*.tar.gz")))
    results = {
        kind: verify(kind, artifact, work_root, expected_version, environment)
        for kind, artifact in selected
    }
    if wheel is not None:
        results["base-wheel"] = verify_base_wheel(wheel, work_root, expected_version, environment)
    print(json.dumps({"status": "PASS", "artifacts": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
