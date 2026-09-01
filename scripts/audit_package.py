"""Audit built distribution metadata, optional extras, contents, and archive hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SOURCE_PACKAGE = ROOT / "src" / "phaseprobe"


def expected_runtime_files() -> set[str]:
    """Return every non-Python file that must survive both build targets."""

    return {
        path.relative_to(ROOT / "src").as_posix()
        for path in SOURCE_PACKAGE.rglob("*")
        if path.is_file() and path.suffix != ".py" and "__pycache__" not in path.parts
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(dist: Path = DIST) -> int:
    wheels = sorted(dist.glob("phaseprobe-*.whl"))
    sdists = sorted(dist.glob("phaseprobe-*.tar.gz"))
    issues: list[str] = []
    if len(wheels) != 1 or len(sdists) != 1:
        issues.append("dist must contain exactly one PhaseProbe wheel and one source archive")
    if issues:
        print(json.dumps({"status": "FAIL", "issues": issues}, indent=2))
        return 1
    wheel = wheels[0]
    sdist = sdists[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            issues.append("wheel must contain exactly one METADATA file")
            metadata = ""
        else:
            metadata = archive.read(metadata_names[0]).decode("utf-8")
        wheel_members = len(names)
    runtime_files = expected_runtime_files()
    missing_wheel_runtime = sorted(runtime_files.difference(names))
    if missing_wheel_runtime:
        issues.append(f"wheel is missing runtime files: {missing_wheel_runtime}")
    requirements = [
        line.removeprefix("Requires-Dist: ")
        for line in metadata.splitlines()
        if line.startswith("Requires-Dist: ")
    ]
    unconditional = [requirement for requirement in requirements if "extra ==" not in requirement]
    scipy_requirements = [
        requirement for requirement in requirements if "extra == 'scipy'" in requirement
    ]
    if unconditional:
        issues.append(f"base wheel has runtime dependencies: {unconditional}")
    if not any(requirement.startswith("numpy") for requirement in scipy_requirements):
        issues.append("scipy extra does not declare NumPy")
    if not any(requirement.startswith("scipy") for requirement in scipy_requirements):
        issues.append("scipy extra does not declare SciPy")
    with tarfile.open(sdist, "r:gz") as archive:
        source_names = archive.getnames()
    source_roots = {name.split("/", 1)[0] for name in source_names if "/" in name}
    if len(source_roots) != 1:
        issues.append(f"sdist must contain one top-level directory: {sorted(source_roots)}")
        missing_sdist_runtime = sorted(runtime_files)
    else:
        source_root = next(iter(source_roots))
        expected_sdist_runtime = {f"{source_root}/src/{name}" for name in runtime_files}
        missing_sdist_runtime = sorted(expected_sdist_runtime.difference(source_names))
    if missing_sdist_runtime:
        issues.append(f"sdist is missing package runtime files: {missing_sdist_runtime}")
    forbidden = [
        name
        for name in source_names
        if name.lower().endswith(".pdf")
        or any(part in name.split("/") for part in (".git", ".tools", ".venv", ".phaseprobe"))
    ]
    if forbidden:
        issues.append(f"source archive has forbidden paths: {forbidden}")
    result = {
        "schema_version": "1.0",
        "status": "PASS" if not issues else "FAIL",
        "base_runtime_dependencies": unconditional,
        "expected_runtime_files": sorted(runtime_files),
        "missing_wheel_runtime_files": missing_wheel_runtime,
        "missing_sdist_runtime_files": missing_sdist_runtime,
        "scipy_extra_requirements": scipy_requirements,
        "wheel": {
            "name": wheel.name,
            "bytes": wheel.stat().st_size,
            "sha256": sha256(wheel),
            "members": wheel_members,
        },
        "sdist": {
            "name": sdist.name,
            "bytes": sdist.stat().st_size,
            "sha256": sha256(sdist),
            "members": len(source_names),
        },
        "issues": issues,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, default=DIST)
    arguments = parser.parse_args()
    raise SystemExit(main(arguments.dist_dir.resolve()))
