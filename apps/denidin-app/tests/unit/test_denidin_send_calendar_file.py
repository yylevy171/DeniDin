"""Feature 102 (T004A): DeniDin.send_calendar_file - writes the .ics as a temp file under
{data_root}/tmp/reminder_ics/ (the way the fee-agreement docx is authored), sends it, always deletes it,
and stores a note of the sent file in the chat's conversation. Never raises.

Real DeniDin + real SessionManager + real WhatsAppHandler; only the Green API bot is a stand-in."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from src.handlers.whatsapp_handler import WhatsAppHandler
from tests.denidin_test_support import make_config, make_denidin, make_session_manager

CHAT = "972500000000@c.us"
ICS = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"


@pytest.fixture
def app(tmp_path):
    app = make_denidin(make_config(data_root=str(tmp_path / "data")),
                       session_manager=make_session_manager(storage_dir=str(tmp_path / "sessions")))
    app.whatsapp_handler = WhatsAppHandler(app)
    app.whatsapp_handler.own_whatsapp_number = "972559999999"
    app.green_api_bot = MagicMock()
    return app


def _tmp_dir(app):
    return Path(app.config.data_root) / "tmp" / "reminder_ics"


def _stored_texts(app):
    return [m["content"] for m in app.session_manager.get_rolling_window(CHAT)]


def test_sends_the_file_content_and_cleans_up(app):
    seen = {}

    def capture(chat_id, path, fileName, caption):
        seen.update(chat_id=chat_id, path=Path(path), name=fileName, content=Path(path).read_bytes())

    app.green_api_bot.api.sending.sendFileByUpload.side_effect = capture

    assert app.send_calendar_file(CHAT, "reminder_abcd1234.ics", ICS) is True

    assert seen["chat_id"] == CHAT and seen["name"] == "reminder_abcd1234.ics" and seen["content"] == ICS
    assert _tmp_dir(app) in seen["path"].parents  # authored under {data_root}/tmp/reminder_ics/
    assert not seen["path"].exists()  # deleted after the send
    assert list(_tmp_dir(app).glob("*")) == []


def test_a_note_of_the_sent_file_is_stored(app):
    app.send_calendar_file(CHAT, "reminder_abcd1234.ics", ICS)
    assert any("reminder_abcd1234.ics" in text for text in _stored_texts(app))


def test_failed_send_returns_false_stores_nothing_and_still_cleans_up(app):
    response = MagicMock()
    response.status_code = 400
    app.green_api_bot.api.sending.sendFileByUpload.side_effect = requests.HTTPError(response=response)

    assert app.send_calendar_file(CHAT, "reminder_abcd1234.ics", ICS) is False

    assert not any("reminder_abcd1234.ics" in text for text in _stored_texts(app))
    assert list(_tmp_dir(app).glob("*")) == []


def test_two_sends_in_a_row_do_not_collide(app):
    names = []
    app.green_api_bot.api.sending.sendFileByUpload.side_effect = (
        lambda chat_id, path, fileName, caption: names.append(path))
    app.send_calendar_file(CHAT, "same.ics", ICS)
    app.send_calendar_file(CHAT, "same.ics", ICS)
    assert len(set(names)) == 2  # a unique temp path per send


def test_no_whatsapp_handler_returns_false(app):
    app.whatsapp_handler = None
    assert app.send_calendar_file(CHAT, "x.ics", ICS) is False


def test_never_raises_when_the_temp_dir_cannot_be_written(app):
    data_root = Path(app.config.data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "tmp").write_text("a file where the directory should be")
    assert app.send_calendar_file(CHAT, "x.ics", ICS) is False
