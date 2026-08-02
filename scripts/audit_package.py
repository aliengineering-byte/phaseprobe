"""Audit built distribution metadata, optional extras, contents, and archive hashes."""

from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    wheels = sorted(DIST.glob("phaseprobe-*.whl"))
    sdists = sorted(DIST.glob("phaseprobe-*.tar.gz"))
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
    raise SystemExit(main())
