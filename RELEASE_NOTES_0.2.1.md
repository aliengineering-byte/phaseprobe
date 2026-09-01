# PhaseProbe 0.2.1 release notes

Status: prepared locally on 2026-08-31; not published.

## Result

PhaseProbe 0.2.1 fixes GitHub Issue #4. The four SciPy quick-start configurations are runtime
resources inside the `phaseprobe` package, are present in both wheel and sdist, and load through
`importlib.resources` with installed-safe `--example scipy-*` names.

The exact former relative config paths also remain compatible. PhaseProbe first reads an existing
file; only when it is absent does one of the four case-sensitive `examples/scipy/` paths resolve to
its matching packaged built-in. Both slash styles are accepted. Arbitrary missing paths, basename
matches, and case variants remain errors. The reporter's original command therefore succeeds from
an unrelated working directory after installation:

```text
phaseprobe perturb --config examples/scipy/lorenz.json
```

The reporter-confirmed scan, replay, generated pytest, Lorenz, and predator–prey behavior remains
intact. This patch does not change solver methods, tolerances, thresholds, search bounds, replay
semantics, or scientific claims.

## Root cause

Version 0.2.0 documented `examples/scipy/*.json` paths that existed only in the source checkout.
Hatchling included the top-level `examples/` tree in the sdist as source material but built wheels
only from `src/phaseprobe`; consequently neither the published wheel nor a wheel built while
installing the sdist contained those configurations at runtime. Editable/source tests and CI ran
from the repository root, where the relative paths existed, masking the release defect.

## Changes

- Added narrow compatibility for the four former checkout-relative SciPy paths while preserving
  existing-file precedence and rejecting fuzzy matches.
- Added packaged SciPy Lorenz and predator–prey configurations plus positive/negative controls.
- Added missing/malformed built-in-resource diagnostics with package version and valid choices.
- Added source-derived wheel/sdist resource inventory checks and `py.typed`.
- Added clean wheel, clean sdist, and dependency-free base-wheel smoke verification outside the
  checkout with `PYTHONPATH` removed on Linux and Windows Python 3.12.
- The installed smoke runs scan, replay, generated pytest, Lorenz, predator–prey, and `pip check`.
- Generated regressions are idempotent for identical evidence and reject conflicting overwrites.
- Added an analytic backward-time directional event check for the SciPy adapter.

## Verification commands

```text
python -m ruff format --check .
python -m ruff check .
python -m mypy src tests
python -m pytest --cov=phaseprobe --cov-report=term-missing
python -m build
python -m twine check dist/*
python scripts/audit_package.py
python scripts/verify_artifacts.py --dist-dir dist --work-root <outside-checkout>
python scripts/check_links.py
python scripts/hygiene.py
```

## Artifact provenance

Local review builds produce `dist/phaseprobe-0.2.1-py3-none-any.whl` and
`dist/phaseprobe-0.2.1.tar.gz`. Their SHA-256 values identify only those exact local files; they are
not permanent release hashes. The trusted publishing workflow rebuilds artifacts from the final
tag, so published hashes must be recorded from that separately authorized run.

PhaseProbe 0.2.1 is not yet published. These notes do not assert that remote CI has passed. No
merge, PyPI upload, GitHub release, tag, or Issue #4 closure is part of this pull request.
