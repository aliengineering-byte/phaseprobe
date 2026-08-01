# PhaseProbe v0.1.0 run log

Evidence is recorded only from executed commands. Private research paths, PDFs, extracted text, credentials, and machine-specific absolute paths are excluded from this public log.

## Scope and research — 2026-08-01

- Created only the PhaseProbe project root, then `.gitignore`, `AGENTS.md`, and this log; read all three back before research or implementation.
- Created the ignored private research ledger and source directories before retrieval. Four requested PDFs were retrieved privately, SHA-256 hashed, and excluded from Git. The unidentified PDF was identified from internal metadata rather than its URL. No PDF, extracted text, quotation, illustration, or chapter substitute is tracked.
- Verified prior art and public technical claims against primary papers or official project documentation. `PRIOR_ART.md` records direct links and a dated comparison.
- Exact-name registry checks on 2026-08-01 returned no `phaseprobe` GitHub repository and HTTP 404 from PyPI and npm project endpoints. The name decision is documented as a practical collision audit, not legal clearance.
- Installed uv 0.11.10 from its official release artifact under ignored `.tools/`; downloaded artifact SHA-256: `7A0C424C7BC55A74751F13592235953EBBE182FA00355F7AE3FB7AB734A51638`.
- Installed GitHub CLI 2.97.0 from its official release artifact under ignored `.tools/`; downloaded artifact SHA-256: `35D7FE05C4DD1411FFDA1E73DFC7C6F44B75C936CA51FA6595C657FDC0350CEC`.
- Installed CPython 3.12.13, environments, dependencies, and caches only within ignored project directories. `uv lock --check` and `uv sync --frozen --all-extras` passed.

## Architecture freeze

v0.1.0 uses a zero-runtime-dependency Python `src/` package with typed model adapters, canonical JSON configuration, explicit seeds, deterministic fixed-step execution, finite-state validation, capped traces, exact trace hashes, bounded one-dimensional scan/perturb search, repeatability confirmation, policy checks, integrity-protected replay fixtures, a fixed pytest generator, and terminal/JSON/offline-HTML reports.

The public commands are `scan`, `perturb`, `check`, `replay`, `generate-test`, and `report`. The stable exit contract is 0 completed, 1 policy/explicit fail-on-finding, 2 invalid input, 3 numerical failure, and 4 internal defect.

## Measured numerical evidence

Command suite: all eight built-in positive and negative-control commands, each with JSON output and its expected exit code.

| example | observed result | baseline | changed/control | exit |
| --- | --- | --- | --- | ---: |
| logistic | qualitative transition found | period-2 | period-4 | 0 |
| logistic-negative | no qualitative transition found | period-2 | n/a | 0 |
| lorenz | finite-time trajectory divergence found | two-lobe finite-time trajectory | same qualitative class; separation predicate triggered | 0 |
| lorenz-negative | no sensitive perturbation found | two-lobe finite-time trajectory | threshold not reached | 0 |
| predator-prey | check policy passed | bounded positive oscillation | no invariant violation | 0 |
| predator-prey-negative | check policy failed | bounded positive oscillation | coarse-step invariant drift | 1 |
| toggle | qualitative state switch found | u-dominant | v-dominant | 0 |
| toggle-negative | no sensitive perturbation found | u-dominant | u-dominant | 0 |

All eight commands completed in 12.238 seconds. The logistic classification bracket was `3.449477539 .. 3.449478027`, with a `4.882812501e-07` final endpoint separation. This is finite-time classifier evidence, not an exact bifurcation point. The Lorenz result is explicitly a finite-time divergence rate, not a Lyapunov exponent.

The predator–prey refined RK4 configuration passed its declared `1e-7` invariant-drift tolerance; the deliberately coarse negative control failed that same policy. Invalid-state tests covered hard-limit failure, and the engine checks NaN, infinity, arithmetic/domain failures, and state-dimension mismatch.

## Performance evidence

- Instrumented `phaseprobe scan --example logistic`: exit 0, 10.114 seconds wall time, 34.81 MiB peak process-tree working set, and 20.90 MiB peak process-tree private bytes. Monitoring followed the Windows virtual-environment launcher and its child processes.
- Repository-native demo generation: 14.957 seconds total. Its embedded real-command transcript measured scan 9.879 seconds, replay 1.328 seconds, generation 1.330 seconds, and generated pytest 1.631 seconds.
- Full example suite: 12.238 seconds.
- Final coverage suite: 38 tests in 64.86 seconds. The quick-start target of 30 seconds, full-example target of three minutes, and 512 MiB memory target were met on this measured environment.

These are single-environment observations, not cross-machine benchmark claims.

## Validation gates

| gate | exact command or method | observed result |
| --- | --- | --- |
| format | `python -m ruff format --check .` | 28 files already formatted |
| lint | `python -m ruff check .` | passed |
| strict typing | `python -m mypy src tests` | passed; 25 source files |
| tests and branch coverage | `python -m pytest --cov=phaseprobe --cov-report=term-missing` | 38 passed in 64.86 seconds; 87.92% coverage; 85% gate met |
| generated test | `python -m pytest -q tests/generated` | 1 passed; committed fixture replays exact class and trace hashes |
| configuration lock | `uv lock --check` | passed |
| frozen development install | `uv sync --frozen --all-extras` | passed |
| version | `python -m phaseprobe --version` | `phaseprobe 0.1.0` |
| examples | eight positive/negative commands | expected statuses and exits; 12.238 seconds |
| quick start | instrumented positive logistic scan | 10.114 seconds; 34.81 MiB peak working set |
| replay | positive logistic fixture | both endpoints matched classification, model identity, and exact retained trace hashes |
| test generation | positive logistic fixture | fixed-template test and copied integrity fixture created; pytest passed |
| reports | terminal, JSON, HTML regeneration tests | passed; HTML contains no script or CDN reference |
| demo | `python scripts/generate_demo.py` | GIF, static PNG, sanitized real-command transcript created |
| documentation links | `python scripts/check_links.py` | 15 Markdown files, 22 external links inventoried, no missing local links |
| privacy/secret/large file | `python scripts/hygiene.py` | 77 public files scanned before Git, no issues, no file over 1 MB |
| package contents | wheel/SDist archive inspection | wheel 32 files, source archive 76 files, no PDF/private research/tool/environment path |
| runtime dependencies | wheel metadata plus clean uv environment | no runtime `Requires-Dist`; only PhaseProbe installed before test tooling |
| packed install | wheel into isolated project-local environment | version, positive scan, strict replay, test generation, and generated pytest passed |
| packed quick start | isolated wheel environment | 9.131 seconds |

## Package artifacts

- Wheel: `phaseprobe-0.1.0-py3-none-any.whl`, 42,313 bytes, final SHA-256 `207F303D70ABB5D9CCBC019BCF1AB9AF51D769838054283DF3A7C5D5D79CBA18`.
- Source distribution: `phaseprobe-0.1.0.tar.gz`, 352,805 bytes, final SHA-256 `4BC793351FBEAC740A4ECC15A681AFE567ACBE3E94D0DCD54262667BAECDA6A5`.

## Failures and repairs

1. The first editable build failed because package metadata referenced a README that had not yet been written. Added the README and reran successfully.
2. The first broad Ruff invocation traversed ignored project-local tool/cache files. Added explicit `.tools`, `.cache`, environment, private research, output, and build exclusions; all subsequent `ruff .` gates were bounded to public project content.
3. The first generated-test subprocess passed an absolute Windows test path; pytest misinterpreted it and inspected a protected compatibility directory. Ran the subprocess from the generated directory with a relative filename.
4. Initial measured coverage was 82.19%, below the declared 85% gate. Added command-level replay, test-generation, report, failure-code, and integrity tests; final coverage is 87.92%.
5. A nested generated-pytest process inherited coverage-control variables and produced incompatible combine data. Removed only those instrumentation variables from the nested test environment; functional behavior remained unchanged.
6. The first packed-smoke script used an unavailable old-PowerShell parameter. Replaced it with an explicit artifact count and compatible selection.
7. A uv-created smoke environment intentionally had no `pip` module, so `python -m pip freeze` was not a valid dependency query. Repeated the gate with `uv pip freeze --python`; wheel metadata independently confirmed zero runtime dependencies.
8. The first committed generated test failed Ruff import-block normalization. Updated the generator template, regenerated the test, and restarted the full final gate.

## Skipped or bounded checks

- External documentation links are inventoried in CI but not fetched there to avoid network-flaky builds; the prior-art/name audit used live official/primary sources during this release run.
- No formal trademark or legal clearance was performed.
- No PyPI or npm publication was attempted or authorized.
- GitHub/CI/release/fresh-public-clone evidence is appended only after those remote actions complete.
