"""Core-only import, schema compatibility, and configured-loader safety tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from phaseprobe.adapters.loader import load_configured_adapter
from phaseprobe.config import parse_config
from phaseprobe.errors import ConfigurationError
from phaseprobe.models import get_model

ROOT = Path(__file__).resolve().parents[1]


def _isolated(command: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-S", "-c", command],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=20,
    )


def test_core_imports_without_site_packages_or_scipy() -> None:
    completed = _isolated("import phaseprobe; print(phaseprobe.__version__)")
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "0.2.0"


def test_scipy_adapter_import_has_actionable_optional_extra_error() -> None:
    completed = _isolated("from phaseprobe.adapters.scipy import SolveIVPAdapter")
    assert completed.returncode != 0
    assert "phaseprobe[scipy]" in completed.stderr
    assert "optional" in completed.stderr.lower()


@pytest.mark.parametrize(
    ("module", "factory"),
    [
        ("../untrusted", "build"),
        ("module.py", "build-model"),
        ("os;system", "build"),
        ("valid.module", "factory()"),
    ],
)
def test_malicious_or_path_like_adapter_references_are_rejected(module: str, factory: str) -> None:
    payload = {
        "schema_version": "2.0",
        "model": "external",
        "adapter": {
            "kind": "python",
            "module": module,
            "factory": factory,
        },
    }
    with pytest.raises(ConfigurationError, match="adapter"):
        parse_config(json.dumps(payload), "malicious test")


def test_v1_and_v2_configuration_schemas_remain_readable() -> None:
    for version in ("1.0", "2.0"):
        config = parse_config(
            json.dumps({"schema_version": version, "model": "logistic-map"}),
            f"schema {version}",
        )
        assert config.data["schema_version"] == version


def test_configured_loader_reports_import_and_factory_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_reference = parse_config(
        json.dumps({"schema_version": "2.0", "model": "external"}), "missing adapter"
    )
    with pytest.raises(ConfigurationError, match="adapter must be a JSON object"):
        load_configured_adapter(missing_reference)

    reference = parse_config(
        json.dumps(
            {
                "schema_version": "2.0",
                "model": "external",
                "adapter": {
                    "kind": "python",
                    "module": "trusted.adapters",
                    "factory": "build",
                },
            }
        ),
        "loader contract",
    )

    def fail_import(name: str) -> object:
        raise ImportError(f"no module named {name}")

    monkeypatch.setattr("phaseprobe.adapters.loader.importlib.import_module", fail_import)
    with pytest.raises(ConfigurationError, match="cannot import"):
        load_configured_adapter(reference)

    monkeypatch.setattr(
        "phaseprobe.adapters.loader.importlib.import_module",
        lambda name: SimpleNamespace(build=42),
    )
    with pytest.raises(ConfigurationError, match="not callable"):
        load_configured_adapter(reference)

    def rejected_factory(values: object) -> object:
        raise ConfigurationError("factory rejected its configuration")

    monkeypatch.setattr(
        "phaseprobe.adapters.loader.importlib.import_module",
        lambda name: SimpleNamespace(build=rejected_factory),
    )
    with pytest.raises(ConfigurationError, match="factory rejected"):
        load_configured_adapter(reference)

    def failed_factory(values: object) -> object:
        raise RuntimeError("factory bug")

    monkeypatch.setattr(
        "phaseprobe.adapters.loader.importlib.import_module",
        lambda name: SimpleNamespace(build=failed_factory),
    )
    with pytest.raises(ConfigurationError, match="factory bug"):
        load_configured_adapter(reference)

    monkeypatch.setattr(
        "phaseprobe.adapters.loader.importlib.import_module",
        lambda name: SimpleNamespace(build=lambda values: object()),
    )
    with pytest.raises(ConfigurationError, match="did not return"):
        load_configured_adapter(reference)

    model = get_model("logistic-map")
    monkeypatch.setattr(
        "phaseprobe.adapters.loader.importlib.import_module",
        lambda name: SimpleNamespace(build=lambda values: model),
    )
    with pytest.raises(ConfigurationError, match="does not match"):
        load_configured_adapter(reference)

    matching = parse_config(
        json.dumps(
            {
                "schema_version": "2.0",
                "model": "logistic-map",
                "adapter": {
                    "kind": "python",
                    "module": "trusted.adapters",
                    "factory": "build",
                },
            }
        ),
        "matching loader",
    )
    assert load_configured_adapter(matching) is model
