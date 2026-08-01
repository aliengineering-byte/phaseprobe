"""Offline terminal, JSON, and self-contained HTML evidence reports."""

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, dict) else {}


def _sequence(value: object) -> Sequence[object]:
    return cast(Sequence[object], value) if isinstance(value, list) else ()


def _format_float(value: object) -> str:
    return f"{value:.10g}" if isinstance(value, float) else str(value)


def _int_value(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def terminal_report(
    data: Mapping[str, object],
    *,
    replay: str | None = None,
    generated_test: str | None = None,
) -> str:
    """Lead with the result and present compact, scientifically qualified evidence."""

    status = str(data.get("status", "PHASEPROBE RESULT"))
    model = str(data.get("model", "unknown"))
    baseline = _mapping(data.get("baseline"))
    changed = _mapping(data.get("changed"))
    finding = _mapping(data.get("finding"))
    lines = [status, "", f"Model: {model}"]
    kind = finding.get("kind")
    if kind is not None:
        lines.append(f"Evidence: {kind}")
    parameter = finding.get("parameter") or finding.get("dimension")
    if parameter is not None:
        lines.append(f"Search dimension: {parameter}")
    bracket = _sequence(finding.get("stable_bracket"))
    if len(bracket) == 2:
        lines.append(f"Stable bracket: {_format_float(bracket[0])} .. {_format_float(bracket[1])}")
    smallest = finding.get("smallest_reproducible_change_found")
    if smallest is not None:
        lines.append(f"Smallest reproducible change found: {_format_float(smallest)}")
    lines.extend(
        [
            f"Baseline regime: {baseline.get('classification', 'n/a')}",
            f"Changed regime: {changed.get('classification', 'n/a') if changed else 'n/a'}",
        ]
    )
    violations = _int_value(baseline.get("invariant_violations", 0))
    if changed:
        violations += _int_value(changed.get("invariant_violations", 0))
    lines.append(f"Invariant violations: {violations}")
    lines.append(f"Repeatable: {str(bool(data.get('reproducible', False))).lower()}")
    if replay is not None:
        lines.append(f"Replay: {replay}")
    if generated_test is not None:
        lines.append(f"Generated test: {generated_test}")
    minimality = finding.get("minimality_statement")
    if minimality is not None:
        lines.extend(["", f"Scope: {minimality}"])
    return "\n".join(lines)


def json_report(data: Mapping[str, object]) -> str:
    """Render the complete versioned JSON evidence document."""

    return json.dumps(data, allow_nan=False, indent=2, sort_keys=True) + "\n"


def html_report(data: Mapping[str, object]) -> str:
    """Render a standalone offline report with no scripts, fonts, or CDN assets."""

    status = html.escape(str(data.get("status", "PhaseProbe result")))
    model = html.escape(str(data.get("model", "unknown")))
    baseline = _mapping(data.get("baseline"))
    changed = _mapping(data.get("changed"))
    finding = _mapping(data.get("finding"))
    history = _sequence(data.get("history"))
    config = _mapping(data.get("configuration"))

    history_rows: list[str] = []
    for item in history:
        row = _mapping(item)
        phase = html.escape(str(row.get("phase", "")))
        value = row.get("value", row.get("delta", ""))
        classification = html.escape(str(row.get("classification", "")))
        interval = ""
        if "low" in row and "high" in row:
            interval = f"{_format_float(row['low'])} .. {_format_float(row['high'])}"
        history_rows.append(
            "<tr>"
            f"<td>{phase}</td><td>{html.escape(_format_float(value))}</td>"
            f"<td>{classification}</td><td>{html.escape(interval)}</td>"
            "</tr>"
        )
    if not history_rows:
        history_rows.append('<tr><td colspan="4">No refinement history for this check.</td></tr>')

    finding_json = html.escape(json.dumps(finding, allow_nan=False, indent=2, sort_keys=True))
    config_json = html.escape(json.dumps(config, allow_nan=False, indent=2, sort_keys=True))
    limitations = (
        "This report contains bounded numerical evidence. It does not prove global minimality, "
        "an exact bifurcation point, chaos, a formal Lyapunov exponent, or scientific validity "
        "outside the declared model, integration settings, search space, and tolerances."
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PhaseProbe — {status}</title>
<style>
:root {{ color-scheme: light dark; --ink:#16202a; --paper:#f7f4ed; --accent:#ef5b35; --cool:#167d8d; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:16px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace; background:var(--paper); color:var(--ink); }}
main {{ max-width:1080px; margin:auto; padding:36px 24px 64px; }}
h1 {{ margin:.2rem 0; font-size:clamp(1.8rem,5vw,3.4rem); line-height:1.05; }}
.eyebrow {{ color:var(--cool); font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
.result {{ border-left:8px solid var(--accent); padding:18px 22px; background:#fff; box-shadow:0 10px 30px #16303b18; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; margin:22px 0; }}
.card {{ border:1px solid #16202a2c; border-radius:8px; padding:16px; background:#ffffffb8; }}
table {{ width:100%; border-collapse:collapse; margin:12px 0 24px; }}
th,td {{ padding:9px; border-bottom:1px solid #16202a2c; text-align:left; vertical-align:top; }}
pre {{ overflow:auto; padding:16px; border-radius:8px; background:#10232b; color:#eaf5f2; }}
.limit {{ border:1px solid #ef5b35; padding:14px; background:#fff4ef; }}
@media (prefers-color-scheme:dark) {{ body {{ --paper:#0f1b20; --ink:#eaf5f2; }} .result,.card {{ background:#16272e; }} .limit {{ background:#36221e; }} }}
</style>
</head>
<body><main>
<p class="eyebrow">PhaseProbe evidence report · schema {html.escape(str(data.get("schema_version", "unknown")))}</p>
<section class="result"><h1>{status}</h1><p>Model: <strong>{model}</strong></p></section>
<section class="grid">
<article class="card"><h2>Baseline</h2><p>{html.escape(str(baseline.get("classification", "n/a")))}</p><p>Trace SHA-256: <code>{html.escape(str(baseline.get("trace_sha256", "n/a")))}</code></p></article>
<article class="card"><h2>Changed</h2><p>{html.escape(str(changed.get("classification", "n/a")))}</p><p>Trace SHA-256: <code>{html.escape(str(changed.get("trace_sha256", "n/a")))}</code></p></article>
</section>
<h2>Finding</h2><pre>{finding_json}</pre>
<h2>Search and refinement history</h2>
<table><thead><tr><th>Phase</th><th>Value / delta</th><th>Classification</th><th>Bracket</th></tr></thead><tbody>{"".join(history_rows)}</tbody></table>
<h2>Configuration</h2><pre>{config_json}</pre>
<h2>Replay and generated test</h2><p>The run directory contains a versioned <code>replay.json</code> fixture. The <code>generate-test</code> command validates and copies that fixture into a fixed pytest template.</p>
<h2>Scientific limitations</h2><p class="limit">{html.escape(limitations)}</p>
</main></body></html>
"""


def regenerate_reports(run_directory: Path) -> tuple[Path, Path]:
    """Regenerate JSON and HTML evidence from a bounded run directory."""

    run_path = run_directory / "run.json"
    try:
        parsed = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load run evidence from {run_path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"run evidence in {run_path} is not a JSON object")
    data = cast(dict[str, object], parsed)
    json_path = run_directory / "report.json"
    html_path = run_directory / "report.html"
    json_path.write_text(json_report(data), encoding="utf-8")
    html_path.write_text(html_report(data), encoding="utf-8")
    return json_path, html_path
