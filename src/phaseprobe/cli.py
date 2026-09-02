"""PhaseProbe command-line interface and stable exit semantics."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from phaseprobe import __version__
from phaseprobe.artifacts import ArtifactBundle, write_artifacts
from phaseprobe.config import EXAMPLES, ProbeConfig, load_config, load_example
from phaseprobe.engine import ProbeOutcome, run_check, run_perturb, run_scan
from phaseprobe.errors import (
    ConfigurationError,
    ExitCode,
    IntegrityError,
    NumericalFailure,
    PhaseProbeError,
)
from phaseprobe.generate import generate_regression_test
from phaseprobe.replay import verify_replay
from phaseprobe.reporting import json_report, regenerate_reports, terminal_report


def _add_config_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="versioned JSON configuration")
    source.add_argument(
        "--example", choices=sorted(EXAMPLES), help="built-in deterministic example"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(".phaseprobe") / "runs",
        help="bounded run directory root (default: .phaseprobe/runs)",
    )
    parser.add_argument("--json", action="store_true", help="emit versioned JSON to stdout")


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser."""

    parser = argparse.ArgumentParser(
        prog="phaseprobe",
        description="Find bounded simulation transitions and turn them into regression tests.",
    )
    parser.add_argument("--version", action="version", version=f"phaseprobe {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="scan one parameter for adjacent qualitative changes")
    _add_config_source(scan)
    scan.add_argument(
        "--fail-on-finding",
        action="store_true",
        help="return exit 1 when a transition is found",
    )

    perturb = commands.add_parser(
        "perturb", help="search bounded initial-state perturbations with twin trajectories"
    )
    _add_config_source(perturb)
    perturb.add_argument(
        "--fail-on-finding",
        action="store_true",
        help="return exit 1 when a sensitive perturbation is found",
    )

    check = commands.add_parser("check", help="run a declared policy for CI enforcement")
    _add_config_source(check)

    replay = commands.add_parser("replay", help="re-execute an integrity-protected replay fixture")
    replay.add_argument("fixture", type=Path)
    replay.add_argument("--json", action="store_true")

    generate = commands.add_parser(
        "generate-test", help="generate fixed-template pytest from validated evidence"
    )
    generate.add_argument("fixture", type=Path)
    generate.add_argument("--output-directory", type=Path, default=Path("tests") / "generated")
    generate.add_argument("--json", action="store_true")

    report = commands.add_parser(
        "report", help="regenerate terminal, JSON, and offline HTML evidence"
    )
    report.add_argument("run_directory", type=Path)
    report.add_argument("--format", choices=("terminal", "json", "html", "all"), default="all")
    return parser


def _config_from_args(args: argparse.Namespace) -> ProbeConfig:
    config_path = getattr(args, "config", None)
    example = getattr(args, "example", None)
    if isinstance(config_path, Path):
        return load_config(config_path)
    if isinstance(example, str):
        return load_example(example)
    raise ConfigurationError("a configuration or built-in example is required")


def _with_artifacts(outcome: ProbeOutcome, bundle: ArtifactBundle) -> dict[str, object]:
    data = outcome.as_dict()
    data["artifacts"] = {
        "run_directory": str(bundle.run_directory),
        "replay": str(bundle.replay_json),
        "html_report": str(bundle.report_html),
        "manifest": str(bundle.manifest_json),
    }
    return data


def _run_evidence_command(
    args: argparse.Namespace, execute: Callable[[ProbeConfig], ProbeOutcome]
) -> int:
    config = _config_from_args(args)
    outcome = execute(config)
    output_root = args.output_root
    if not isinstance(output_root, Path):
        raise ConfigurationError("output root must be a path")
    bundle = write_artifacts(outcome, output_root)
    data = _with_artifacts(outcome, bundle)
    if bool(getattr(args, "json", False)):
        sys.stdout.write(json_report(data))
    else:
        print(terminal_report(data, replay=str(bundle.replay_json)))
        print(f"HTML report: {bundle.report_html}")
    if outcome.policy_failed:
        return int(ExitCode.POLICY_FAILED)
    if bool(getattr(args, "fail_on_finding", False)) and outcome.finding is not None:
        return int(ExitCode.POLICY_FAILED)
    return int(ExitCode.OK)


def _replay_command(args: argparse.Namespace) -> int:
    fixture = args.fixture
    if not isinstance(fixture, Path):
        raise ConfigurationError("fixture must be a path")
    verification = verify_replay(fixture)
    data = verification.as_dict()
    if bool(getattr(args, "json", False)):
        sys.stdout.write(json_report(data))
    else:
        print(str(data["status"]))
        print()
        print(f"Model: {verification.model}")
        print(f"Comparison mode: {verification.mode}")
        for comparison in verification.comparisons:
            if verification.mode == "exact":
                print(
                    f"{comparison['series']}: classification="
                    f"{comparison['classification_match']}, "
                    f"trace-hash={comparison['trace_hash_match']}, "
                    f"model-identity={comparison['model_identity_match']}"
                )
            else:
                matched = all(
                    value is True for key, value in comparison.items() if key.endswith("_match")
                )
                print(f"{comparison['series']}: declared tolerances={matched}")
    return int(ExitCode.OK if verification.ok else ExitCode.POLICY_FAILED)


def _generate_command(args: argparse.Namespace) -> int:
    fixture = args.fixture
    output_directory = args.output_directory
    if not isinstance(fixture, Path) or not isinstance(output_directory, Path):
        raise ConfigurationError("fixture and output directory must be paths")
    generated = generate_regression_test(fixture, output_directory)
    data: dict[str, object] = {
        "schema_version": "2.0",
        "status": "PYTEST REGRESSION GENERATED",
        "test": str(generated.test_path),
        "fixture": str(generated.fixture_path),
        "evidence": str(generated.evidence_path),
    }
    if bool(getattr(args, "json", False)):
        sys.stdout.write(json_report(data))
    else:
        print("PYTEST REGRESSION GENERATED")
        print()
        print(f"Test: {generated.test_path}")
        print(f"Replay fixture: {generated.fixture_path}")
        print(f"Execution evidence: {generated.evidence_path}")
    return int(ExitCode.OK)


def _report_command(args: argparse.Namespace) -> int:
    run_directory = args.run_directory
    report_format = args.format
    if not isinstance(run_directory, Path) or not isinstance(report_format, str):
        raise ConfigurationError("invalid report arguments")
    json_path, html_path = regenerate_reports(run_directory)
    parsed = json.loads((run_directory / "run.json").read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ConfigurationError("run.json must contain an object")
    data: dict[str, object] = parsed
    if report_format in {"terminal", "all"}:
        print(terminal_report(data, replay=str(run_directory / "replay.json")))
    if report_format in {"json", "all"}:
        if report_format == "json":
            sys.stdout.write(json_report(data))
        else:
            print(f"JSON report: {json_path}")
    if report_format in {"html", "all"}:
        print(f"HTML report: {html_path}")
    return int(ExitCode.OK)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and translate expected defects into the documented exit contract."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            return _run_evidence_command(args, run_scan)
        if args.command == "perturb":
            return _run_evidence_command(args, run_perturb)
        if args.command == "check":
            return _run_evidence_command(args, run_check)
        if args.command == "replay":
            return _replay_command(args)
        if args.command == "generate-test":
            return _generate_command(args)
        if args.command == "report":
            return _report_command(args)
        raise ConfigurationError(f"unknown command {args.command!r}")
    except NumericalFailure as exc:
        print(f"NUMERICAL FAILURE: {exc}", file=sys.stderr)
        return int(ExitCode.NUMERICAL_FAILURE)
    except (ConfigurationError, IntegrityError, ValueError, OSError) as exc:
        print(f"INVALID INPUT: {exc}", file=sys.stderr)
        return int(ExitCode.INVALID_INPUT)
    except PhaseProbeError as exc:
        print(f"PHASEPROBE ERROR: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)
    except Exception as exc:  # pragma: no cover - final CLI containment boundary
        print(f"INTERNAL PHASEPROBE DEFECT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return int(ExitCode.INTERNAL_ERROR)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
