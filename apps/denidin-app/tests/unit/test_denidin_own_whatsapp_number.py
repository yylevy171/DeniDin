"""
Unit tests for bugfix-024's `_fetch_own_whatsapp_number` (denidin.py) - the startup-time,
once-only fetch of DeniDin's own WhatsApp phone number via a real Green API call shape
(`green_api.account.getWaSettings()`), confirmed live (2026-08-05) to return
`{"phone": "<bare digits>", ...}`.

Updated for Feature 043 (the MessageSource refactor, research.md R3): `green_api` is now
an explicit, injected parameter (the real Green API client, e.g. a live bot's `.api`)
instead of reaching for a module-level `bot` global - there is no such global anymore,
since denidin.py no longer constructs a live Green API bot at import time. Same 4
scenarios as before (success / non-200 / missing phone / exception), just injected via a
fake `green_api` object instead of monkeypatching `denidin_module.bot.api`, plus a new
5th scenario for the graceful `green_api=None` degrade this signature change made
possible (a player/replay caller that never has a live Green API client at all).
"""
from unittest.mock import Mock

import denidin as denidin_module


def _mock_response(code, data=None):
    response = Mock()
    response.code = code
    response.data = data
    return response


def _fake_green_api(get_wa_settings):
    """A minimal stand-in for the real Green API client's surface this
    function touches (`green_api.account.getWaSettings()`)."""
    green_api = Mock()
    green_api.account.getWaSettings = get_wa_settings
    return green_api


class TestFetchOwnWhatsAppNumber:
    def test_successful_call_returns_phone_field(self):
        green_api = _fake_green_api(lambda: _mock_response(200, {
            'stateInstance': 'authorized',
            'deviceId': '972559723730:3@s.whatsapp.net',
            'chatId': '172336149954736@lid',
            'phone': '972559723730',
        }))

        result = denidin_module._fetch_own_whatsapp_number(green_api)

        assert result == '972559723730'

    def test_non_200_response_returns_empty_string(self):
        green_api = _fake_green_api(lambda: _mock_response(401, None))

        result = denidin_module._fetch_own_whatsapp_number(green_api)

        assert result == ''

    def test_missing_phone_field_returns_empty_string(self):
        green_api = _fake_green_api(lambda: _mock_response(200, {'stateInstance': 'authorized'}))

        result = denidin_module._fetch_own_whatsapp_number(green_api)

        assert result == ''

    def test_exception_during_call_returns_empty_string_not_raise(self):
        def _raise():
            raise ConnectionError("network unreachable")

        green_api = _fake_green_api(_raise)

        result = denidin_module._fetch_own_whatsapp_number(green_api)

        assert result == ''

    def test_none_green_api_returns_empty_string_not_raise(self):
        """New in Feature 043: a caller with no live Green API client at all
        (e.g. the player) passes green_api=None - must degrade the same way
        a failed real call does, never raise."""
        result = denidin_module._fetch_own_whatsapp_number(None)

        assert result == ''
