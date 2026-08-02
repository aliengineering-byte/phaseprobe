# Contributing

Contributions are welcome when they preserve PhaseProbe’s narrow testing job and scientific language.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\python -m pip install -e ".[dev]"
# Linux:   .venv/bin/python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m mypy src tests
python -m pytest --cov=phaseprobe
```

Install `.[dev,scipy]` to run the optional trajectory-adapter suite. Core-only jobs intentionally
install `.[dev]` and run tests marked `not scipy`; SciPy jobs run the full suite. The committed
`uv.lock` resolves the supported Python-dependent SciPy lines reproducibly.

Before a pull request, also run `python -m build`, `python -m twine check dist/*`,
`python scripts/audit_package.py`, install the base wheel and SciPy extra into separate clean
environments, execute both quick starts, run `python scripts/check_links.py`, and run
`python scripts/hygiene.py`.

## Scientific changes

New adapters or classifiers must include:

- equation or model definition and a primary technical citation;
- deterministic positive case and negative control;
- seed, solver/iteration settings, tolerances, burn-in, observation window, and invalid-state policy;
- an explanation of what the classifier establishes and what it does not;
- replay and generated-test coverage;
- solver-refinement or convergence evidence where numerical integration matters.

Trajectory adapters must serialize explicit configuration without callable source, select an
honest exact/tolerance replay mode, and test solver failure, invalid values, retention, and any
supported event behavior.

Do not call finite-time divergence a Lyapunov exponent, a numerical bracket an exact bifurcation point, or a bounded search result globally minimal.

## Pull requests

Keep changes focused, update documentation and `CHANGELOG.md`, and report exact validation commands. Never add copyrighted books, PDFs, extracted private text, credentials, personal email addresses, telemetry, runtime API/LLM/GPU/Docker requirements, or unsupported performance/adoption claims.

At least three starter tasks are available as structured good-first-issue templates: add a damped-pendulum adapter, add JSON Schema validation fixtures, and improve HTML-report accessibility.
