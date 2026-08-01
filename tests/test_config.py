"""Configuration and registry unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phaseprobe.config import canonical_json, load_config, load_example, parse_config
from phaseprobe.errors import ConfigurationError
from phaseprobe.models import get_model, model_names
from phaseprobe.types import ModelAdapter


def test_canonical_json_is_stable() -> None:
    assert canonical_json({"b": 1, "a": [3, 2]}) == '{"a":[3,2],"b":1}'


def test_parse_rejects_wrong_schema() -> None:
    with pytest.raises(ConfigurationError, match="unsupported configuration schema"):
        parse_config('{"schema_version":"9","model":"lorenz"}', "test")


def test_parse_rejects_non_object() -> None:
    with pytest.raises(ConfigurationError, match="must be a JSON object"):
        parse_config("[]", "test")


def test_parse_rejects_bad_seed() -> None:
    with pytest.raises(ConfigurationError, match="seed"):
        parse_config('{"schema_version":"1.0","model":"lorenz","seed":-1}', "test")


def test_load_config_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="cannot read"):
        load_config(tmp_path / "missing.json")


def test_all_built_in_examples_are_versioned_json() -> None:
    for name in (
        "logistic",
        "logistic-negative",
        "lorenz",
        "lorenz-negative",
        "predator-prey",
        "predator-prey-negative",
        "toggle",
        "toggle-negative",
    ):
        config = load_example(name)
        assert config.data["schema_version"] == "1.0"
        json.loads(canonical_json(config.data))


def test_unknown_example_is_actionable() -> None:
    with pytest.raises(ConfigurationError, match="unknown example"):
        load_example("missing")


def test_registry_models_implement_protocol() -> None:
    assert model_names() == ("genetic-toggle", "logistic-map", "lorenz", "predator-prey")
    for name in model_names():
        assert isinstance(get_model(name), ModelAdapter)


def test_unknown_model_is_actionable() -> None:
    with pytest.raises(ConfigurationError, match="unknown model"):
        get_model("missing")
