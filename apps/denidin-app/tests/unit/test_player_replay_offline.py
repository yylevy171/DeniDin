"""Offline end-to-end player replay (Feature 063, REQ-063-08).

Runs player.run_player.run_replay on a tiny real export zip through the real,
unmodified initialize_app/dispatch pipeline - only the external OpenAI client is
faked (it always answers with a send_to_user tool call). Proves the player still
works after the DeniDin-owns-every-manager refactor: the own-number override on
WhatsAppHandler, PlayerExportSource dispatch, and the reply landing in the session.
"""
import json
import zipfile
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import denidin
from player import run_player

CHAT_ID = "972500000001@c.us"
OWN_NUMBER = "972599999999"
REPLY = "קיבלתי, תודה"


def _send_to_user_response(*_args, **_kwargs):
    item = SimpleNamespace(
        type="function_call", name="send_to_user",
        arguments=json.dumps({"text": REPLY}), call_id="call1",
    )
    return SimpleNamespace(output=[item], output_text="", id="resp1", usage=None)


@pytest.fixture
def fake_openai(monkeypatch):
    client = MagicMock()
    client.responses.create.side_effect = _send_to_user_response
    monkeypatch.setattr(denidin, "OpenAI", lambda **_kwargs: client)
    return client


@pytest.fixture
def export_zip(tmp_path):
    chat_txt = tmp_path / "WhatsApp Chat with Ayelet.txt"
    chat_txt.write_text(f"9/2/25, 10:00 - Ayelet: שלום @{OWN_NUMBER} מה נשמע\n", encoding="utf-8")
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(chat_txt, chat_txt.name)
    return zip_path


def test_player_replays_through_the_real_pipeline(tmp_path, fake_openai, export_zip, monkeypatch):
    monkeypatch.setattr(denidin, "denidin_app", None)
    data_root = tmp_path / "player_data"

    outcomes = run_player.run_replay(
        export_zip=export_zip, chat_id=CHAT_ID,
        sender_map={"Ayelet": "972500000001@c.us"}, data_root=data_root,
        config_path="config/config.test.json",
        start=date(2025, 9, 1), end=date(2025, 9, 30), today=date(2025, 9, 30),
        whatsapp_own_number=OWN_NUMBER,
    )
    app = denidin.denidin_app
    try:
        assert [o["status"] for o in outcomes] == ["dispatched"]
        assert app.whatsapp_handler.own_whatsapp_number == OWN_NUMBER
        assert fake_openai.responses.create.called

        history = app.session_manager.get_conversation_history(CHAT_ID)
        contents = [m["content"] for m in history]
        assert any("@DeniDin" in c and f"@{OWN_NUMBER}" not in c for c in contents)
        assert REPLY in contents
        assert run_player._last_assistant_reply(denidin, CHAT_ID) == REPLY
    finally:
        for scheduler in (app.reminder_scheduler, app.daily_roll_scheduler):
            if scheduler is not None:
                scheduler.shutdown(wait=False)
