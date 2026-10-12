"""Feature 101: the app calls Green API through the instance's own API host
(first four digits of the instance id), not the shared generic host.

On 2026-10-11 `api.green-api.com` (the library's hardcoded default) went down while the instance
hosts (e.g. `7107.api.greenapi.com`) kept answering `authorized` - prod could not start, because
nothing in the app ever overrode the library default.
"""
import json
from types import SimpleNamespace

import pytest

from src.models.config import AppConfiguration
from src.sources.green_api_source import GreenAPIMessageSource
from src.utils.green_api_bot import instance_api_host


class TestInstanceApiHost:
    @pytest.mark.parametrize("instance_id, expected", [
        ("710722700252", "https://7107.api.greenapi.com"),
        ("7105257767", "https://7105.api.greenapi.com"),
        ("1101000001", "https://1101.api.greenapi.com"),
    ])
    def test_prefix_is_the_first_four_digits(self, instance_id, expected):
        assert instance_api_host(instance_id) == expected

    @pytest.mark.parametrize("instance_id", [
        "YOUR_GREEN_API_INSTANCE_ID",  # config.example.json placeholder
        "test-instance",
        "",
        "123",  # fewer than four digits
        "71a7227",  # not all digits
    ])
    def test_non_instance_ids_fall_back_to_library_default(self, instance_id):
        """None makes the library use its own default host - never a malformed URL."""
        assert instance_api_host(instance_id) is None

    def test_numeric_id_given_as_an_int_is_accepted(self):
        assert instance_api_host(710722700252) == "https://7107.api.greenapi.com"


class _BotFactorySpy:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return SimpleNamespace()


def _config(instance_id, media_host=None, host_mode="instance"):
    return SimpleNamespace(
        green_api_instance_id=instance_id,
        green_api_token="tok",
        green_api_host_mode=host_mode,
        green_api_media_host=media_host,
    )


class TestSourcePassesHostsToTheBot:
    def test_connect_passes_the_instance_api_host(self):
        factory = _BotFactorySpy()
        GreenAPIMessageSource(_config("710722700252"), bot_factory=factory).connect()

        args, kwargs = factory.calls[0]
        assert args == ("710722700252", "tok")
        assert kwargs["host"] == "https://7107.api.greenapi.com"

    def test_media_host_defaults_to_the_library_default(self):
        factory = _BotFactorySpy()
        GreenAPIMessageSource(_config("710722700252"), bot_factory=factory).connect()

        assert factory.calls[0][1]["media"] is None

    def test_configured_media_host_is_passed_through(self):
        factory = _BotFactorySpy()
        GreenAPIMessageSource(
            _config("710722700252", media_host="https://media.greenapi.com"), bot_factory=factory
        ).connect()

        assert factory.calls[0][1]["media"] == "https://media.greenapi.com"

    def test_fixed_mode_leaves_the_library_default_host(self):
        """'fixed' (the default) = the shared generic host, even for a real instance id."""
        factory = _BotFactorySpy()
        GreenAPIMessageSource(_config("710722700252", host_mode="fixed"), bot_factory=factory).connect()

        assert factory.calls[0][1]["host"] is None

    def test_placeholder_instance_id_leaves_the_library_default_host(self):
        factory = _BotFactorySpy()
        GreenAPIMessageSource(_config("test-instance"), bot_factory=factory).connect()

        assert factory.calls[0][1]["host"] is None


class TestConfigField:
    _REQUIRED = {"green_api_instance_id": "710722700252", "green_api_token": "t", "ai_api_key": "k"}

    def test_media_host_defaults_to_none(self):
        assert AppConfiguration(**self._REQUIRED).green_api_media_host is None

    def test_host_mode_defaults_to_fixed(self):
        assert AppConfiguration(**self._REQUIRED).green_api_host_mode == "fixed"

    def test_host_mode_defaults_to_fixed_when_loaded_from_a_file(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(self._REQUIRED), encoding="utf-8")

        assert AppConfiguration.from_file(str(path)).green_api_host_mode == "fixed"

    def test_host_mode_instance_is_loaded_from_a_file(self, tmp_path):
        """Opting in to the instance host needs only a config edit + restart - no release."""
        path = tmp_path / "config.json"
        path.write_text(json.dumps({**self._REQUIRED, "green_api_host_mode": "instance"}), encoding="utf-8")

        config = AppConfiguration.from_file(str(path))
        config.validate()
        assert config.green_api_host_mode == "instance"

    @pytest.mark.parametrize("bad", ["Instance", "default", "", None, True])
    def test_invalid_host_mode_fails_validation(self, bad):
        config = AppConfiguration(**self._REQUIRED, green_api_host_mode=bad)

        with pytest.raises(ValueError, match="green_api_host_mode"):
            config.validate()

    def test_media_host_defaults_to_none_when_loaded_from_a_file(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(self._REQUIRED), encoding="utf-8")

        assert AppConfiguration.from_file(str(path)).green_api_media_host is None

    def test_media_host_is_loaded_from_a_file_when_set(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(
            json.dumps({**self._REQUIRED, "green_api_media_host": "https://media.greenapi.com"}),
            encoding="utf-8",
        )

        assert AppConfiguration.from_file(str(path)).green_api_media_host == "https://media.greenapi.com"
