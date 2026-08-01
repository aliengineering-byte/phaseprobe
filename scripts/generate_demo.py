"""Run the real quick-start workflow and render repository-native terminal assets."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
CACHE = ROOT / ".cache"
WIDTH = 1200
HEIGHT = 700


def run(command: list[str], cwd: Path) -> tuple[str, float]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout + completed.stderr)
    return completed.stdout.strip(), elapsed


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("CascadiaMono.ttf", "consola.ttf", "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def frame(lines: list[str], active: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#0b171d")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, WIDTH - 24, HEIGHT - 24), radius=18, fill="#10252d")
    draw.ellipse((48, 48, 64, 64), fill="#ef5b35")
    draw.ellipse((74, 48, 90, 64), fill="#f2c14e")
    draw.ellipse((100, 48, 116, 64), fill="#52b788")
    draw.text(
        (142, 45), "PhaseProbe · deterministic simulation evidence", font=font(22), fill="#d9f2ec"
    )
    y = 92
    terminal_font = font(20)
    for index, line in enumerate(lines[:24]):
        color = "#efb366" if line.startswith("$") else "#d9f2ec"
        if index == active:
            draw.rounded_rectangle((42, y - 3, WIDTH - 42, y + 27), radius=5, fill="#173b46")
        draw.text((52, y), line, font=terminal_font, fill=color)
        y += 25
    draw.text(
        (52, HEIGHT - 58),
        "bounded search  →  replay fixture  →  generated pytest  →  pass",
        font=font(19),
        fill="#62c6cf",
    )
    return image


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phaseprobe-demo-", dir=CACHE) as raw_temp:
        workspace = Path(raw_temp)
        output_root = workspace / ".phaseprobe" / "runs"
        scan_output, scan_time = run(
            [
                sys.executable,
                "-m",
                "phaseprobe",
                "scan",
                "--example",
                "logistic",
                "--output-root",
                str(output_root),
            ],
            ROOT,
        )
        run_directory = max(output_root.iterdir(), key=lambda path: path.stat().st_mtime_ns)
        replay_output, replay_time = run(
            [sys.executable, "-m", "phaseprobe", "replay", str(run_directory / "replay.json")],
            ROOT,
        )
        generated_directory = workspace / "tests" / "generated"
        generate_output, generate_time = run(
            [
                sys.executable,
                "-m",
                "phaseprobe",
                "generate-test",
                str(run_directory / "replay.json"),
                "--output-directory",
                str(generated_directory),
            ],
            ROOT,
        )
        generated_test = next(generated_directory.glob("test_*_transition.py"))
        pytest_output, pytest_time = run(
            [sys.executable, "-m", "pytest", "-q", generated_test.name],
            generated_directory,
        )

        transcript = "\n\n".join(
            (
                "$ phaseprobe scan --example logistic\n" + scan_output,
                "$ phaseprobe replay .phaseprobe/runs/<run-id>/replay.json\n" + replay_output,
                "$ phaseprobe generate-test .phaseprobe/runs/<run-id>/replay.json\n"
                + generate_output,
                "$ python -m pytest -q tests/generated\n" + pytest_output,
            )
        )
        transcript = transcript.replace(str(run_directory), ".phaseprobe/runs/<run-id>")
        transcript = transcript.replace(str(generated_directory), "tests/generated")
        transcript = transcript.replace("\\", "/")
        timing = (
            f"\n\nMeasured generation run: scan={scan_time:.3f}s, replay={replay_time:.3f}s, "
            f"generate={generate_time:.3f}s, pytest={pytest_time:.3f}s."
        )
        (ASSETS / "demo-session.txt").write_text(transcript + timing + "\n", encoding="utf-8")

        selected = [
            "$ phaseprobe scan --example logistic",
            "QUALITATIVE TRANSITION FOUND",
            "Model: logistic-map",
            "Stable bracket: refined and repeated",
            "Baseline regime: period-2",
            "Changed regime: period-4",
            "Replay: .phaseprobe/runs/<run-id>/replay.json",
            "",
            "$ phaseprobe replay .phaseprobe/runs/<run-id>/replay.json",
            "REPLAY VERIFIED",
            "baseline: classification=True, trace-hash=True",
            "changed: classification=True, trace-hash=True",
            "",
            "$ phaseprobe generate-test .phaseprobe/runs/<run-id>/replay.json",
            "PYTEST REGRESSION GENERATED",
            "Test: tests/generated/test_logistic_map_transition.py",
            "",
            "$ python -m pytest -q tests/generated",
            ".                                                                    [100%]",
            "1 passed",
        ]
        images = [frame(selected[: limit + 1], limit) for limit in (1, 6, 11, 15, 19)]
        images[-1].save(ASSETS / "demo-static.png", optimize=True)
        images[0].save(
            ASSETS / "demo.gif",
            save_all=True,
            append_images=images[1:],
            duration=[900, 1200, 1200, 1200, 2200],
            loop=0,
            optimize=True,
        )
    print(
        textwrap.dedent(
            f"""\
            Demo assets generated from real commands:
              {ASSETS / "demo.gif"}
              {ASSETS / "demo-static.png"}
              {ASSETS / "demo-session.txt"}
            """
        ).strip()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
