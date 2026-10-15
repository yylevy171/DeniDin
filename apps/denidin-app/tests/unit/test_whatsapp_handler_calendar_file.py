"""Feature 102 (T003A): WhatsAppHandler.send_calendar_file - a .ics sent through `sendFileByUpload`.

Same pattern as test_whatsapp_handler_document_send.py: only the Green API bot (a real external service)
is a stand-in; the retry policy is real tenacity code."""
from unittest.mock import MagicMock

import pytest
import requests

from src.handlers.whatsapp_handler import WhatsAppHandler
from tests.denidin_test_support import make_denidin

CHAT = "972500000000@c.us"


@pytest.fixture
def handler():
    return WhatsAppHandler(make_denidin())


@pytest.fixture
def bot(handler):
    handler.denidin.green_api_bot = MagicMock()
    return handler.denidin.green_api_bot


@pytest.fixture
def ics_path(tmp_path):
    path = tmp_path / "reminder_abcd1234.ics"
    path.write_bytes(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    return path


def _http_error(status):
    response = MagicMock()
    response.status_code = status
    return requests.HTTPError(response=response)


def test_sends_once_with_the_file_name_and_no_caption(handler, bot, ics_path):
    assert handler.send_calendar_file(CHAT, str(ics_path), "reminder_abcd1234.ics") is True
    bot.api.sending.sendFileByUpload.assert_called_once_with(
        CHAT, str(ics_path), fileName="reminder_abcd1234.ics", caption="")


def test_retries_once_on_5xx_then_succeeds(handler, bot, ics_path):
    bot.api.sending.sendFileByUpload.side_effect = [_http_error(500), None]
    assert handler.send_calendar_file(CHAT, str(ics_path), "x.ics") is True
    assert bot.api.sending.sendFileByUpload.call_count == 2


def test_never_retries_a_4xx(handler, bot, ics_path):
    bot.api.sending.sendFileByUpload.side_effect = _http_error(400)
    assert handler.send_calendar_file(CHAT, str(ics_path), "x.ics") is False
    assert bot.api.sending.sendFileByUpload.call_count == 1


def test_false_after_the_retry_is_exhausted(handler, bot, ics_path):
    bot.api.sending.sendFileByUpload.side_effect = _http_error(503)
    assert handler.send_calendar_file(CHAT, str(ics_path), "x.ics") is False
    assert bot.api.sending.sendFileByUpload.call_count == 2


def test_never_raises_on_a_connection_error(handler, bot, ics_path):
    bot.api.sending.sendFileByUpload.side_effect = requests.ConnectionError("boom")
    assert handler.send_calendar_file(CHAT, str(ics_path), "x.ics") is False


def test_false_when_no_bot_is_injected(handler, ics_path):
    handler.denidin.green_api_bot = None
    assert handler.send_calendar_file(CHAT, str(ics_path), "x.ics") is False


def test_leaves_the_file_alone(handler, bot, ics_path):
    handler.send_calendar_file(CHAT, str(ics_path), "x.ics")
    assert ics_path.exists()  # deleting it is the caller's job (DeniDin.send_calendar_file)


def test_outbound_file_is_wire_audited(handler, bot, ics_path, caplog):
    with caplog.at_level("INFO", logger="src.utils.wire_log"):
        handler.send_calendar_file(CHAT, str(ics_path), "reminder_abcd1234.ics")
    audit = [r.getMessage() for r in caplog.records if "WIRE-AUDIT" in r.getMessage()]
    assert any("boundary='whatsapp'" in line and "direction='out'" in line and "reminder_abcd1234.ics" in line
               for line in audit)
