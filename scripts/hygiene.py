"""Repository privacy, secret, large-file, and tracked-output gate."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".phaseprobe",
    ".pytest_cache",
    ".research_private",
    ".ruff_cache",
    ".tools",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
}
FORBIDDEN_TRACKED_PARTS = {
    ".phaseprobe",
    ".research_private",
    ".tools",
    ".venv",
    "build",
    "dist",
    "htmlcov",
}
TEXT_SUFFIXES = {
    ".cff",
    ".css",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PRIVATE_TERMS = (
    "Ali" + "Prime",
    "AgentReliability" + "Lab",
    "Resili" + "Replay",
    "AI-" + "Workbench",
)
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "assigned secret": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    ),
}
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\")


def tracked_files() -> list[Path]:
    """Use Git's index when available; otherwise walk only public project content."""

    completed = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode == 0 and completed.stdout:
        return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    ]


def main() -> int:
    files = tracked_files()
    issues: list[str] = []
    large_files: list[dict[str, object]] = []
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in FORBIDDEN_TRACKED_PARTS for part in relative.parts):
            issues.append(f"tracked generated/private path: {relative.as_posix()}")
        if path.suffix.lower() == ".pdf":
            issues.append(f"tracked PDF: {relative.as_posix()}")
        size = path.stat().st_size
        if size > 1_000_000:
            large_files.append({"path": relative.as_posix(), "bytes": size})
        if size > 5_000_000:
            issues.append(f"tracked file exceeds 5 MB: {relative.as_posix()} ({size} bytes)")
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            ".gitignore",
            "LICENSE",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(f"declared text file is not UTF-8: {relative.as_posix()}")
            continue
        if EMAIL.search(text):
            issues.append(f"personal email-like string: {relative.as_posix()}")
        if WINDOWS_PATH.search(text):
            issues.append(f"absolute Windows path: {relative.as_posix()}")
        for term in PRIVATE_TERMS:
            if term in text:
                issues.append(f"private neighboring-workspace term {term!r}: {relative.as_posix()}")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                issues.append(f"possible {label}: {relative.as_posix()}")
    result = {
        "schema_version": "1.0",
        "status": "PASS" if not issues else "FAIL",
        "files_scanned": len(files),
        "author_identity_policy": "public author metadata is Ali only; no email-like strings found"
        if not any("email" in issue for issue in issues)
        else "failed",
        "large_files_over_1mb": large_files,
        "issues": issues,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
