"""The active-reminder cap is configurable (reminders.max_active_reminders) and defaults to 100."""
import json

import pytest

from src.managers.reminder_manager import ReminderManager
from src.models.config import AppConfiguration
from tests.denidin_test_support import make_config, make_denidin


def _manager(tmp_path, **config_fields):
    return ReminderManager(make_denidin(make_config(data_root=str(tmp_path), **config_fields)))


def test_cap_defaults_to_100_when_no_reminders_block(tmp_path):
    assert _manager(tmp_path).max_active_reminders == 100


def test_cap_defaults_to_100_when_the_block_omits_the_key(tmp_path):
    assert _manager(tmp_path, reminders={"other": 1}).max_active_reminders == 100


def test_configured_cap_is_used(tmp_path):
    assert _manager(tmp_path, reminders={"max_active_reminders": 7}).max_active_reminders == 7


def _load(tmp_path, reminders):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "green_api_instance_id": "i", "green_api_token": "t", "ai_api_key": "k",
        "reminders": reminders,
    }), encoding="utf-8")
    return AppConfiguration.from_file(str(path))


def test_config_fills_100_when_the_block_omits_the_key(tmp_path):
    assert _load(tmp_path, {"x": 1}).reminders["max_active_reminders"] == 100


def test_config_rejects_a_non_positive_cap(tmp_path):
    with pytest.raises(ValueError):
        _load(tmp_path, {"max_active_reminders": 0}).validate()
