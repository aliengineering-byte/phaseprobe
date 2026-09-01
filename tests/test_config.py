"""Configuration and registry unit tests."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

from phaseprobe.config import (
    EXAMPLES,
    SUPPORTED_CONFIG_SCHEMA_VERSIONS,
    canonical_json,
    load_config,
    load_example,
    parse_config,
)
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
    for name in EXAMPLES:
        config = load_example(name)
        assert config.data["schema_version"] in SUPPORTED_CONFIG_SCHEMA_VERSIONS
        json.loads(canonical_json(config.data))


def test_built_in_registry_matches_packaged_json_resources() -> None:
    package = resources.files("phaseprobe.data.examples")
    packaged = {item.name for item in package.iterdir() if item.name.endswith(".json")}
    assert {example.filename for example in EXAMPLES.values()} == packaged


@pytest.mark.parametrize(
    "name", [name for name, example in EXAMPLES.items() if example.legacy_config_path]
)
def test_packaged_scipy_examples_match_source_checkout_copies(name: str) -> None:
    legacy_path = EXAMPLES[name].legacy_config_path
    assert legacy_path is not None
    source = Path(__file__).resolve().parents[1] / legacy_path
    assert load_example(name).data == load_config(source).data


@pytest.mark.parametrize(
    "name", [name for name, example in EXAMPLES.items() if example.legacy_config_path]
)
def test_missing_former_scipy_path_loads_packaged_example(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_path = EXAMPLES[name].legacy_config_path
    assert legacy_path is not None
    monkeypatch.chdir(tmp_path)
    assert load_config(Path(legacy_path)).data == load_example(name).data
    assert load_config(Path(legacy_path.replace("/", "\\"))).data == load_example(name).data


def test_existing_former_scipy_path_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_path = EXAMPLES["scipy-lorenz"].legacy_config_path
    assert legacy_path is not None
    config_path = tmp_path / legacy_path
    config_path.parent.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "examples" / "configs" / "logistic-negative.json"
    config_path.write_bytes(source.read_bytes())
    monkeypatch.chdir(tmp_path)
    loaded = load_config(Path(legacy_path))
    assert loaded.model == "logistic-map"
    assert Path(loaded.source) == Path(legacy_path)


@pytest.mark.parametrize(
    "missing_path",
    ["elsewhere/lorenz.json", "examples/scipy/LORENZ.json", "lorenz.json"],
)
def test_missing_config_does_not_use_fuzzy_example_fallback(
    missing_path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigurationError, match="cannot read configuration"):
        load_config(Path(missing_path))


def test_unknown_example_is_actionable() -> None:
    with pytest.raises(ConfigurationError, match="unknown example") as error:
        load_example("missing")
    assert "phaseprobe <command> --help" in str(error.value)


def test_missing_built_in_resource_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("phaseprobe.config.resources.files", lambda package: tmp_path)
    with pytest.raises(ConfigurationError, match="packaged resource") as error:
        load_example("scipy-lorenz")
    message = str(error.value)
    assert "PhaseProbe" in message
    assert "scipy-lorenz.json" in message
    assert "Reinstall PhaseProbe" in message
    assert "phaseprobe <command> --help" in message


def test_malformed_built_in_resource_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "scipy-lorenz.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("phaseprobe.config.resources.files", lambda package: tmp_path)
    with pytest.raises(ConfigurationError, match="malformed") as error:
        load_example("scipy-lorenz")
    assert "unsupported configuration schema" in str(error.value)


def test_registry_models_implement_protocol() -> None:
    assert model_names() == ("genetic-toggle", "logistic-map", "lorenz", "predator-prey")
    for name in model_names():
        assert isinstance(get_model(name), ModelAdapter)


def test_unknown_model_is_actionable() -> None:
    with pytest.raises(ConfigurationError, match="unknown model"):
        get_model("missing")
