"""Run the real SciPy quick start and render a short terminal demo plus static report."""

from __future__ import annotations

import shutil
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
EXAMPLES = ROOT / "examples" / "scipy"
WIDTH = 1200
HEIGHT = 720


def run(command: list[str], cwd: Path, *, expected: int = 0) -> tuple[str, float]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != expected:
        raise RuntimeError(completed.stdout + completed.stderr)
    return (completed.stdout + completed.stderr).strip(), elapsed


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("CascadiaMono.ttf", "consola.ttf", "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def frame(lines: list[str], active: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#09151b")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, WIDTH - 24, HEIGHT - 24), radius=18, fill="#10252d")
    for x, color in ((48, "#ef5b35"), (74, "#f2c14e"), (100, "#52b788")):
        draw.ellipse((x, 48, x + 16, 64), fill=color)
    draw.text((142, 44), "PhaseProbe + SciPy | tolerance replay", font=font(22), fill="#d9f2ec")
    y = 92
    terminal_font = font(19)
    for index, line in enumerate(lines[:25]):
        if index == active:
            draw.rounded_rectangle((42, y - 3, WIDTH - 42, y + 25), radius=5, fill="#173b46")
        draw.text(
            (52, y),
            line,
            font=terminal_font,
            fill="#efb366" if line.startswith("$") else "#d9f2ec",
        )
        y += 24
    draw.text(
        (52, HEIGHT - 58),
        "solve_ivp -> bounded evidence -> tolerance fixture -> generated pytest",
        font=font(18),
        fill="#62c6cf",
    )
    return image


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phaseprobe-scipy-demo-", dir=CACHE) as raw_temp:
        workspace = Path(raw_temp)
        output_root = workspace / "runs"
        lorenz_output, lorenz_time = run(
            [
                sys.executable,
                "-m",
                "phaseprobe",
                "perturb",
                "--example",
                "scipy-lorenz",
                "--output-root",
                str(output_root / "lorenz"),
            ],
            ROOT,
        )
        predator_output, predator_time = run(
            [
                sys.executable,
                "-m",
                "phaseprobe",
                "check",
                "--example",
                "scipy-predator-prey",
                "--output-root",
                str(output_root / "predator-prey"),
            ],
            ROOT,
        )
        predator_run = max((output_root / "predator-prey").iterdir())
        fixture = predator_run / "replay.json"
        replay_output, replay_time = run(
            [sys.executable, "-m", "phaseprobe", "replay", str(fixture)], ROOT
        )
        generated_directory = workspace / "generated"
        generate_output, generate_time = run(
            [
                sys.executable,
                "-m",
                "phaseprobe",
                "generate-test",
                str(fixture),
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
                "$ phaseprobe perturb --example scipy-lorenz\n" + lorenz_output,
                "$ phaseprobe check --example scipy-predator-prey\n" + predator_output,
                "$ phaseprobe replay .phaseprobe/runs/<run-id>/replay.json\n" + replay_output,
                "$ phaseprobe generate-test .phaseprobe/runs/<run-id>/replay.json\n"
                + generate_output,
                "$ python -m pytest -q tests/generated\n" + pytest_output,
            )
        )
        replacements = {
            str(ROOT): "<repository>",
            str(workspace): "<workspace>",
            str(predator_run): ".phaseprobe/runs/<run-id>",
            str(generated_directory): "tests/generated",
        }
        for original, replacement in replacements.items():
            transcript = transcript.replace(original, replacement)
        transcript = transcript.replace("\\", "/")
        timing = (
            f"\n\nMeasured demo run: lorenz={lorenz_time:.3f}s, "
            f"predator-prey={predator_time:.3f}s, replay={replay_time:.3f}s, "
            f"generate={generate_time:.3f}s, pytest={pytest_time:.3f}s."
        )
        (ASSETS / "scipy-demo-session.txt").write_text(transcript + timing + "\n", encoding="utf-8")
        shutil.copyfile(predator_run / "report.html", EXAMPLES / "report.html")

        selected = [
            "$ phaseprobe perturb --example scipy-lorenz",
            "FINITE-TIME TRAJECTORY DIVERGENCE FOUND",
            "Evidence: finite-time-divergence",
            "Repeatable: true",
            "Scope: declared finite search and 25-unit window",
            "",
            "$ phaseprobe check --example scipy-predator-prey",
            "CHECK POLICY PASSED",
            "Method: DOP853 | rtol=1e-10 | vector atol=1e-12",
            "First-integral drift: 3.997e-15 <= 1e-8",
            "",
            "$ phaseprobe replay .phaseprobe/runs/<run-id>/replay.json",
            "REPLAY VERIFIED",
            "Comparison mode: tolerance",
            "baseline: declared tolerances=True",
            "",
            "$ phaseprobe generate-test .phaseprobe/runs/<run-id>/replay.json",
            "PYTEST REGRESSION GENERATED",
            "$ python -m pytest -q tests/generated",
            ".                                                                    [100%]",
            "1 passed",
        ]
        images = [frame(selected[: limit + 1], limit) for limit in (1, 4, 9, 14, 20)]
        images[-1].save(ASSETS / "scipy-demo-static.png", optimize=True)
        images[0].save(
            ASSETS / "scipy-demo.gif",
            save_all=True,
            append_images=images[1:],
            duration=[900, 1100, 1300, 1300, 2200],
            loop=0,
            optimize=True,
        )
    print(
        textwrap.dedent(
            f"""\
            SciPy demo assets generated from real commands:
              {ASSETS / "scipy-demo.gif"}
              {ASSETS / "scipy-demo-static.png"}
              {ASSETS / "scipy-demo-session.txt"}
              {EXAMPLES / "report.html"}
            """
        ).strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
