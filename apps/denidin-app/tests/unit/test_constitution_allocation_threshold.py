"""Feature 098: the runtime constitution's {{ALLOCATION_THRESHOLD_NIS}}
placeholder is filled from config.allocation_threshold_nis every time the
constitution is loaded. Real AIHandler, real files; the OpenAI client is a
real (never-called) SDK object.
"""
from pathlib import Path

import pytest
from openai import OpenAI

from src.handlers.ai_handler import (
    ALLOCATION_THRESHOLD_PLACEHOLDER,
    AIHandler,
    format_nis_amount,
)
from src.models.config import AppConfiguration

APP_ROOT = Path(__file__).resolve().parents[2]


def _handler(base_dir, threshold=5000):
    config = AppConfiguration(
        green_api_instance_id="test",
        green_api_token="test",
        ai_api_key="test-key",
        data_root="test_data",
        constitution_config={"file": "runtime_constitution.md", "base_dir": str(base_dir)},
        allocation_threshold_nis=threshold,
    )
    return AIHandler(OpenAI(api_key="test-key"), config)


@pytest.mark.parametrize(
    "value, expected",
    [(5000, "5,000"), (12500, "12,500"), (5000.5, "5,000.5"), (5000.0, "5,000"), (999, "999")],
)
def test_format_nis_amount(value, expected):
    assert format_nis_amount(value) == expected


@pytest.mark.parametrize("threshold, expected", [(5000, "5,000"), (12500, "12,500"), (5000.5, "5,000.5")])
def test_placeholder_is_filled_from_config(tmp_path, threshold, expected):
    (tmp_path / "runtime_constitution.md").write_text(
        f"Above {ALLOCATION_THRESHOLD_PLACEHOLDER} ₪ ask. Exactly {ALLOCATION_THRESHOLD_PLACEHOLDER} is fine.",
        encoding="utf-8",
    )

    loaded = _handler(tmp_path, threshold)._load_constitution()

    assert loaded == f"Above {expected} ₪ ask. Exactly {expected} is fine."


def test_placeholder_is_filled_on_every_load_not_only_the_first(tmp_path):
    """The mtime cache holds the raw text; substitution runs on each call."""
    (tmp_path / "runtime_constitution.md").write_text(
        f"limit {ALLOCATION_THRESHOLD_PLACEHOLDER}", encoding="utf-8"
    )
    handler = _handler(tmp_path)

    assert handler._load_constitution() == "limit 5,000"
    assert handler._load_constitution() == "limit 5,000"


def test_real_constitution_has_the_section_and_no_unfilled_placeholder():
    raw = (APP_ROOT / "config" / "runtime_constitution.md").read_text(encoding="utf-8")
    assert ALLOCATION_THRESHOLD_PLACEHOLDER in raw

    loaded = _handler(APP_ROOT / "config")._load_constitution()

    assert "Allocation Number (מספר הקצאה)" in loaded
    assert ALLOCATION_THRESHOLD_PLACEHOLDER not in loaded
    assert "5,000" in loaded
