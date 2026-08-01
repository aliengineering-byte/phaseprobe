## Outcome

Describe the user-visible testing outcome first.

## Scientific interpretation

- What does the evidence establish?
- What does it not establish?
- Which primary sources support model or algorithm claims?

## Validation

- [ ] `python -m ruff format --check .`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy src tests`
- [ ] `python -m pytest --cov=phaseprobe`
- [ ] Positive case and negative control
- [ ] Replay and generated pytest execution
- [ ] Package build and clean packed-install smoke
- [ ] `python scripts/check_links.py`
- [ ] `python scripts/hygiene.py`

List exact commands and measured results. Do not include private paths, credentials, PDFs, or fabricated evidence.
