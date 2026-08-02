"""Versioned JSON configuration loading and deterministic serialization."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, cast

from phaseprobe.errors import ConfigurationError

CONFIG_SCHEMA_VERSION = "2.0"
SUPPORTED_CONFIG_SCHEMA_VERSIONS = frozenset({"1.0", CONFIG_SCHEMA_VERSION})
_DOTTED_MODULE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


def canonical_json(value: object) -> str:
    """Serialize configuration data deterministically for hashing and replay."""

    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _as_object(value: Any, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{context} must be a JSON object")
    return cast(dict[str, object], value)


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    """Validated top-level configuration with typed access helpers."""

    data: Mapping[str, object]
    source: str

    @property
    def model(self) -> str:
        value = self.data.get("model")
        if not isinstance(value, str) or not value:
            raise ConfigurationError("model must be a non-empty string")
        return value

    @property
    def seed(self) -> int:
        value = self.data.get("seed", 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ConfigurationError("seed must be a non-negative integer")
        return value

    def section(self, name: str, *, required: bool = True) -> Mapping[str, object]:
        value = self.data.get(name)
        if value is None and not required:
            return {}
        if not isinstance(value, dict):
            raise ConfigurationError(f"{name} must be a JSON object")
        return cast(Mapping[str, object], value)

    def string(self, name: str, default: str | None = None) -> str:
        value = self.data.get(name, default)
        if not isinstance(value, str):
            raise ConfigurationError(f"{name} must be a string")
        return value


def parse_config(text: str, source: str) -> ProbeConfig:
    """Parse and validate a versioned JSON configuration."""

    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"invalid JSON in {source}: {exc}") from exc
    data = _as_object(parsed, source)
    version = data.get("schema_version")
    if version not in SUPPORTED_CONFIG_SCHEMA_VERSIONS:
        raise ConfigurationError(
            f"unsupported configuration schema {version!r}; supported versions are "
            f"{sorted(SUPPORTED_CONFIG_SCHEMA_VERSIONS)!r}"
        )
    config = ProbeConfig(data=data, source=source)
    _ = config.model
    _ = config.seed
    adapter = data.get("adapter")
    if adapter is not None:
        values = _as_object(adapter, "adapter")
        kind = values.get("kind")
        module = values.get("module")
        factory = values.get("factory")
        if kind != "python":
            raise ConfigurationError("adapter.kind must be 'python'")
        if not isinstance(module, str) or _DOTTED_MODULE.fullmatch(module) is None:
            raise ConfigurationError("adapter.module must be an absolute dotted Python module name")
        if not isinstance(factory, str) or _IDENTIFIER.fullmatch(factory) is None:
            raise ConfigurationError("adapter.factory must be a Python identifier")
    return config


def load_config(path: Path) -> ProbeConfig:
    """Load a UTF-8 JSON configuration from a user-selected path."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read configuration {path}: {exc}") from exc
    return parse_config(text, str(path))


EXAMPLE_FILES: Mapping[str, str] = {
    "logistic": "logistic-scan.json",
    "logistic-negative": "logistic-negative.json",
    "lorenz": "lorenz-perturb.json",
    "lorenz-negative": "lorenz-negative.json",
    "predator-prey": "predator-prey-check.json",
    "predator-prey-negative": "predator-prey-negative.json",
    "toggle": "toggle-perturb.json",
    "toggle-negative": "toggle-negative.json",
}


def load_example(name: str) -> ProbeConfig:
    """Load one of the immutable examples embedded in the installed wheel."""

    filename = EXAMPLE_FILES.get(name)
    if filename is None:
        choices = ", ".join(sorted(EXAMPLE_FILES))
        raise ConfigurationError(f"unknown example {name!r}; choose one of: {choices}")
    package = resources.files("phaseprobe.data.examples")
    text = package.joinpath(filename).read_text(encoding="utf-8")
    return parse_config(text, f"built-in example {name}")
