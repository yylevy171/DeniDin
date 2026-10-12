"""Feature 098: denidin-app's own copy of the allocation threshold.

Used only to fill the runtime constitution's {{ALLOCATION_THRESHOLD_NIS}}
placeholder; morning-mcp-app enforces the rule from its own config.
Real AppConfiguration loading, nothing mocked.
"""
import json
from pathlib import Path

import pytest

from src.models.config import AppConfiguration

APP_ROOT = Path(__file__).resolve().parents[2]
_REQUIRED = {"green_api_instance_id": "x", "green_api_token": "x", "ai_api_key": "x"}


def _load(tmp_path, **extra):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**_REQUIRED, **extra}), encoding="utf-8")
    return AppConfiguration.from_file(str(path))


def test_defaults_to_5000_when_absent(tmp_path):
    assert _load(tmp_path).allocation_threshold_nis == 5000


def test_is_read_from_config(tmp_path):
    assert _load(tmp_path, allocation_threshold_nis=10000).allocation_threshold_nis == 10000


@pytest.mark.parametrize("bad_value", [0, -5000, "5000", True])
def test_validate_rejects_anything_but_a_positive_number(tmp_path, bad_value):
    config = _load(tmp_path, allocation_threshold_nis=bad_value)
    with pytest.raises(ValueError, match="allocation_threshold_nis"):
        config.validate()


def test_example_config_states_the_threshold_explicitly():
    raw = json.loads((APP_ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
    assert raw["allocation_threshold_nis"] == 5000
