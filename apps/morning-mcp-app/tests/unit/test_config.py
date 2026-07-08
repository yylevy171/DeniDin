"""Tests for denidin_mcp_morning.config — flat config.json loading + validation.

Real files, real jsonschema validation — no mocking (nothing external is called here).
Covers T003 from specs/in-definition/005-mcp-morning-green-receipt/tasks.md.
"""
import json
from pathlib import Path

import pytest

from denidin_mcp_morning.config import ConfigError, MorningMCPConfig, load_config

APP_ROOT = Path(__file__).resolve().parents[2]
TEST_CONFIG_PATH = APP_ROOT / "config" / "config.test.json"
EXAMPLE_CONFIG_PATH = APP_ROOT / "config" / "config.example.json"


def test_load_config_from_real_test_file():
    """config.test.json (the real, committed flat config) loads successfully."""
    config = load_config(TEST_CONFIG_PATH)

    assert isinstance(config, MorningMCPConfig)
    assert config.api_key_id
    assert config.api_key_secret
    assert config.api_url.startswith("https://")


def test_load_config_applies_defaults_when_optional_fields_missing():
    """config.test.json only has the 3 required keys; optional fields must default."""
    config = load_config(TEST_CONFIG_PATH)

    assert config.default_currency == "ILS"
    assert config.default_vat_rate == 0.17
    assert config.token_ttl_seconds == 3600
    assert config.refresh_before_seconds == 300
    assert config.rate_limit_per_second == 3
    assert config.enable_mcp_server is False


def test_load_config_from_example_file_with_full_flat_shape():
    """config.example.json (extended, flat) loads and reflects its explicit values."""
    config = load_config(EXAMPLE_CONFIG_PATH)

    assert config.mcp_transport == "streamable-http"
    assert config.mcp_port == 8000
    assert config.enable_mcp_server is False


def test_load_config_missing_file_raises_config_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    with pytest.raises(ConfigError):
        load_config(missing_path)


def test_load_config_missing_required_key_raises_config_error(tmp_path):
    bad_config = tmp_path / "config.json"
    bad_config.write_text(json.dumps({"api_key_id": "x", "api_key_secret": "y"}), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(bad_config)


def test_load_config_rejects_nested_morning_shape(tmp_path):
    """The old nested `{"morning": {...}}` shape must be rejected — flat only."""
    nested_config = tmp_path / "config.json"
    nested_config.write_text(
        json.dumps(
            {
                "morning": {
                    "api_key_id": "x",
                    "api_key_secret": "y",
                    "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(nested_config)


def test_load_config_never_reads_environment_variables(monkeypatch):
    """CONSTITUTION §I: config must come only from the file, never env vars."""
    monkeypatch.setenv("api_key_id", "SHOULD_NOT_BE_USED")
    monkeypatch.setenv("MORNING_API_KEY_ID", "SHOULD_NOT_BE_USED")

    config = load_config(TEST_CONFIG_PATH)

    assert config.api_key_id != "SHOULD_NOT_BE_USED"
