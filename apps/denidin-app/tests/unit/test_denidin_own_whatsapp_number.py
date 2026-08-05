"""
Unit tests for bugfix-024's `_fetch_own_whatsapp_number` (denidin.py) - the startup-time,
once-only fetch of DeniDin's own WhatsApp phone number via a real Green API call shape
(`bot.api.account.getWaSettings()`), confirmed live (2026-08-05) to return
`{"phone": "<bare digits>", ...}`.

Mocks only `bot.api.account.getWaSettings` itself (the actual external-service call
boundary) - never denidin.py's own logic - matching this codebase's convention for
unit-testing a function whose only job is to call one external method and interpret
its result.
"""
from unittest.mock import Mock

import denidin as denidin_module


def _mock_response(code, data=None):
    response = Mock()
    response.code = code
    response.data = data
    return response


class TestFetchOwnWhatsAppNumber:
    def test_successful_call_returns_phone_field(self, monkeypatch):
        monkeypatch.setattr(
            denidin_module.bot.api.account, 'getWaSettings',
            lambda: _mock_response(200, {
                'stateInstance': 'authorized',
                'deviceId': '972559723730:3@s.whatsapp.net',
                'chatId': '172336149954736@lid',
                'phone': '972559723730',
            })
        )

        result = denidin_module._fetch_own_whatsapp_number()

        assert result == '972559723730'

    def test_non_200_response_returns_empty_string(self, monkeypatch):
        monkeypatch.setattr(
            denidin_module.bot.api.account, 'getWaSettings',
            lambda: _mock_response(401, None)
        )

        result = denidin_module._fetch_own_whatsapp_number()

        assert result == ''

    def test_missing_phone_field_returns_empty_string(self, monkeypatch):
        monkeypatch.setattr(
            denidin_module.bot.api.account, 'getWaSettings',
            lambda: _mock_response(200, {'stateInstance': 'authorized'})
        )

        result = denidin_module._fetch_own_whatsapp_number()

        assert result == ''

    def test_exception_during_call_returns_empty_string_not_raise(self, monkeypatch):
        def _raise():
            raise ConnectionError("network unreachable")

        monkeypatch.setattr(denidin_module.bot.api.account, 'getWaSettings', _raise)

        result = denidin_module._fetch_own_whatsapp_number()

        assert result == ''
