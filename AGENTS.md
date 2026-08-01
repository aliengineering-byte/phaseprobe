# PhaseProbe contributor instructions

- Work exclusively inside the PhaseProbe repository root; never inspect or modify neighboring projects or workspaces.
- Use the public author identity `Ali` only: no surname, personal email, workstation paths, credentials, or provider configuration in tracked files.
- Keep scientific language precise: distinguish finite-time trajectory divergence, sensitive dependence, numerical instability, invariant violation, qualitative regime change, bifurcation evidence, stochastic variation, invalid integration, and solver failure. Never claim exact or formal results beyond the implemented evidence.
- Support Windows and Linux on Python 3.10+ with no runtime LLM, API key, GPU, Docker, account, telemetry, or hosted service.
- Keep copyrighted books, PDFs, extracted text, research notes, caches, environments, tools, build output, and run output out of Git.
- Required validation: `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy src tests`, `python -m pytest`, `python -m build`, packed-install smoke test, quick start, examples, replay, generated-test execution, privacy/secret/large-file scans, and clean Git status.
- Do not fabricate tests, performance, scientific evidence, benchmark results, users, or adoption claims.
- Do not publish to PyPI without separate authorization.
- Release only after all local gates pass; then use the authenticated `aliengineering-byte` GitHub account, pass CI, tag an annotated `v0.1.0`, create the release, and verify a fresh unauthenticated clone.
