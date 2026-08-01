"""Deterministic local Markdown-link and external-link inventory check."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".cache", ".git", ".phaseprobe", ".research_private", ".tools", ".venv"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    issues: list[str] = []
    external: set[str] = set()
    markdown_files = [
        path
        for path in ROOT.rglob("*.md")
        if not any(part in EXCLUDED for part in path.relative_to(ROOT).parts)
    ]
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            target = raw.strip().strip("<>")
            parsed = urlparse(target)
            if parsed.scheme in {"http", "https"}:
                external.add(target)
                continue
            if parsed.scheme or target.startswith("#"):
                continue
            local_text = unquote(target.split("#", 1)[0])
            if not local_text:
                continue
            local_path = (path.parent / local_text).resolve()
            try:
                local_path.relative_to(ROOT)
            except ValueError:
                issues.append(f"{path.relative_to(ROOT)}: link escapes repository: {target}")
                continue
            if not local_path.exists():
                issues.append(f"{path.relative_to(ROOT)}: missing local target: {target}")
    result = {
        "schema_version": "1.0",
        "status": "PASS" if not issues else "FAIL",
        "markdown_files": len(markdown_files),
        "external_links_inventoried": len(external),
        "note": "External links are inventoried but not fetched in CI to avoid network-flaky gates.",
        "issues": issues,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
