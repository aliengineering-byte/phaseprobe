"""Explicit loading of user-selected Python adapter factories."""

from __future__ import annotations

import importlib

from phaseprobe.config import ProbeConfig
from phaseprobe.errors import ConfigurationError
from phaseprobe.types import ModelAdapter, TrajectoryAdapter


def load_configured_adapter(config: ProbeConfig) -> ModelAdapter | TrajectoryAdapter:
    """Import and call the explicitly configured adapter factory.

    Configuration parsing validates names but does not import anything. Calling this function
    executes the selected module and factory, so callers must trust that Python code.
    """

    reference = config.section("adapter")
    module_name = reference.get("module")
    factory_name = reference.get("factory")
    if not isinstance(module_name, str) or not isinstance(factory_name, str):
        raise ConfigurationError("adapter.module and adapter.factory must be strings")
    try:
        module = importlib.import_module(module_name)
    except (ImportError, ValueError) as exc:
        raise ConfigurationError(
            f"cannot import configured adapter module {module_name!r}: {exc}"
        ) from exc
    factory = getattr(module, factory_name, None)
    if not callable(factory):
        raise ConfigurationError(
            f"configured adapter factory {module_name}.{factory_name} is not callable"
        )
    try:
        candidate = factory(reference)
    except ConfigurationError:
        raise
    except Exception as exc:
        raise ConfigurationError(
            f"configured adapter factory {module_name}.{factory_name} failed: {exc}"
        ) from exc
    if not isinstance(candidate, ModelAdapter | TrajectoryAdapter):
        raise ConfigurationError(
            f"configured factory {module_name}.{factory_name} did not return a PhaseProbe adapter"
        )
    if candidate.name != config.model:
        raise ConfigurationError(
            f"configured adapter name {candidate.name!r} does not match model {config.model!r}"
        )
    return candidate
