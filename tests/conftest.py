"""Shared deterministic outcomes for the numerical test suite."""

from __future__ import annotations

import pytest

from phaseprobe.config import load_example
from phaseprobe.engine import ProbeOutcome, run_scan


@pytest.fixture(scope="session")
def logistic_outcome() -> ProbeOutcome:
    """Run the slower critical-transition example once per test session."""

    return run_scan(load_example("logistic"))
