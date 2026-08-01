"""PhaseProbe exception hierarchy and documented process exit codes."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Stable CLI exit-code contract."""

    OK = 0
    POLICY_FAILED = 1
    INVALID_INPUT = 2
    NUMERICAL_FAILURE = 3
    INTERNAL_ERROR = 4


class PhaseProbeError(Exception):
    """Base class for expected PhaseProbe failures."""


class ConfigurationError(PhaseProbeError):
    """Raised when a configuration or user input is invalid."""


class NumericalFailure(PhaseProbeError):
    """Raised when integration produces an invalid state or solver failure."""


class IntegrityError(PhaseProbeError):
    """Raised when a replay fixture fails integrity validation."""
