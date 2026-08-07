"""
Unit tests for PlayerConfig / load_player_config (Feature 043).

See specs/in-progress/043-production-data-setup-tooling/contracts/player-cli.md
for the file's documented shape.
"""
import json
from pathlib import Path

import pytest

from player.player_config import PlayerConfig, PlayerConfigError, load_player_config


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestLoadPlayerConfig:
    def test_loads_a_complete_config(self, tmp_path):
        path = _write(tmp_path, "player.json", {
            "export_zip": "tests/fixtures/whatsapp_exports/export.zip",
            "chat_id": "120363999999999999@g.us",
            "sender_map": {"אילה 🦋": "972501234567@c.us"},
            "data_root": "test_data",
            "denidin_config": "config/config.test.json",
        })

        result = load_player_config(path)

        assert result == PlayerConfig(
            export_zip=Path("tests/fixtures/whatsapp_exports/export.zip"),
            chat_id="120363999999999999@g.us",
            sender_map={"אילה 🦋": "972501234567@c.us"},
            data_root="test_data",
            denidin_config="config/config.test.json",
        )

    def test_sender_map_defaults_to_empty_dict_when_omitted(self, tmp_path):
        path = _write(tmp_path, "player.json", {
            "export_zip": "export.zip",
            "chat_id": "120363999999999999@g.us",
            "data_root": "test_data",
            "denidin_config": "config/config.test.json",
        })

        result = load_player_config(path)

        assert result.sender_map == {}

    @pytest.mark.parametrize("missing_field", ["export_zip", "chat_id", "data_root", "denidin_config"])
    def test_missing_required_field_raises(self, tmp_path, missing_field):
        data = {
            "export_zip": "export.zip",
            "chat_id": "120363999999999999@g.us",
            "data_root": "test_data",
            "denidin_config": "config/config.test.json",
        }
        del data[missing_field]
        path = _write(tmp_path, "player.json", data)

        with pytest.raises(PlayerConfigError, match=missing_field):
            load_player_config(path)

    def test_missing_file_raises_player_config_error(self, tmp_path):
        with pytest.raises(PlayerConfigError):
            load_player_config(tmp_path / "does-not-exist.json")

    def test_invalid_json_raises_player_config_error(self, tmp_path):
        path = tmp_path / "player.json"
        path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(PlayerConfigError):
            load_player_config(path)
