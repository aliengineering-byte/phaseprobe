"""Bounded run-directory persistence and artifact manifests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from phaseprobe.config import canonical_json
from phaseprobe.engine import ProbeOutcome, SimulationResult
from phaseprobe.replay import fixture_payload
from phaseprobe.reporting import html_report, json_report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    """Paths written for one bounded PhaseProbe execution."""

    run_directory: Path
    run_json: Path
    findings_json: Path
    replay_json: Path
    trace_jsonl: Path
    report_html: Path
    manifest_json: Path


def _trace_lines(label: str, result: SimulationResult) -> list[str]:
    lines: list[str] = []
    for point in result.trace:
        payload = {
            "series": label,
            "step": point.step,
            "time": point.time,
            "state": list(point.state),
            "observations": dict(point.observations),
        }
        lines.append(canonical_json(payload))
    return lines


def write_artifacts(outcome: ProbeOutcome, output_root: Path) -> ArtifactBundle:
    """Write finite evidence files and a hash manifest under one run directory."""

    output_root.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(canonical_json(outcome.as_dict()).encode("utf-8")).hexdigest()[:8]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_directory = output_root / f"{timestamp}-{signature}"
    suffix = 1
    while run_directory.exists():
        run_directory = output_root / f"{timestamp}-{signature}-{suffix}"
        suffix += 1
    run_directory.mkdir()

    run_json = run_directory / "run.json"
    findings_json = run_directory / "findings.json"
    replay_json = run_directory / "replay.json"
    trace_jsonl = run_directory / "trace.jsonl"
    report_html = run_directory / "report.html"
    manifest_json = run_directory / "manifest.json"

    data = outcome.as_dict()
    run_json.write_text(json_report(data), encoding="utf-8")
    findings_json.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "status": outcome.status,
                "finding": dict(outcome.finding) if outcome.finding is not None else None,
                "reproducible": outcome.reproducible,
            },
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    replay_json.write_text(
        json.dumps(fixture_payload(outcome), allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    trace_lines = _trace_lines("baseline", outcome.baseline)
    if outcome.changed is not None:
        trace_lines.extend(_trace_lines("changed", outcome.changed))
    trace_jsonl.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")
    report_html.write_text(html_report(data), encoding="utf-8")

    files = [run_json, findings_json, replay_json, trace_jsonl, report_html]
    manifest = {
        "schema_version": "2.0",
        "run_id": run_directory.name,
        "bounded_trace": {
            "baseline_points": len(outcome.baseline.trace),
            "changed_points": len(outcome.changed.trace) if outcome.changed is not None else 0,
            "configured_cap_per_series": outcome.baseline.settings.trace_cap,
        },
        "files": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)} for path in files
        },
    }
    manifest_json.write_text(
        json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ArtifactBundle(
        run_directory=run_directory,
        run_json=run_json,
        findings_json=findings_json,
        replay_json=replay_json,
        trace_jsonl=trace_jsonl,
        report_html=report_html,
        manifest_json=manifest_json,
    )
