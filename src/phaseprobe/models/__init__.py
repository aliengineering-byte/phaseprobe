"""Built-in deterministic model adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from phaseprobe.errors import ConfigurationError
from phaseprobe.models.logistic import LogisticMapAdapter
from phaseprobe.models.lorenz import LorenzAdapter
from phaseprobe.models.predator_prey import PredatorPreyAdapter
from phaseprobe.models.toggle import GeneticToggleAdapter
from phaseprobe.types import ModelAdapter

_MODELS: Mapping[str, ModelAdapter] = {
    "logistic-map": cast(ModelAdapter, LogisticMapAdapter()),
    "lorenz": cast(ModelAdapter, LorenzAdapter()),
    "predator-prey": cast(ModelAdapter, PredatorPreyAdapter()),
    "genetic-toggle": cast(ModelAdapter, GeneticToggleAdapter()),
}


def get_model(name: str) -> ModelAdapter:
    """Return a built-in model adapter by stable identity."""

    model = _MODELS.get(name)
    if model is None:
        choices = ", ".join(sorted(_MODELS))
        raise ConfigurationError(f"unknown model {name!r}; choose one of: {choices}")
    return model


def model_names() -> tuple[str, ...]:
    """Return stable built-in model names."""

    return tuple(sorted(_MODELS))
