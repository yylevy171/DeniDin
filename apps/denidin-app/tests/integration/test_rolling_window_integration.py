"""Feature 070 — rolling window through the real message path (T014a).

Real SessionManager + real Backbone on an isolated tmp data_root; OpenAI and the Green API
bot faked at the boundary only. Covers:
- the exact `input` items handed to the OpenAI boundary when a chat starts a new model chain
  == get_rolling_window() output + the new user turn (golden shape);
- restart continuity (bugfix-044 / AC-2 shape): a fresh Backbone on the same data_root
  continues the existing session (no "Created new session") and the model chain it left.
"""
from types import SimpleNamespace

import pytest

from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage
from tests.helpers.seed import seed_message
from tests.ai_handler_test_support import make_ai_handler
from tests.backbone_test_support import FakeBot

CHAT = "972501234567@c.us"


def _fake_client(capture):
    """The model answers each message with one send_to_user, then has nothing more to do."""
    def responses_create(**kwargs):
        capture.append(kwargs)
        n = len(capture)
        if n % 2 == 1:
            item = SimpleNamespace(type="function_call", name="send_to_user", arguments='{"text": "בסדר"}',
                                   call_id=f"c{n}")
            return SimpleNamespace(id=f"resp_{n}", output=[item], output_text="", model="gpt-5.6-luna", usage=None)
        return SimpleNamespace(id=f"resp_{n}", output=[], output_text="", model="gpt-5.6-luna", usage=None)

    def embeddings_create(model, input):
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * 8)])

    return SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        embeddings=SimpleNamespace(create=embeddings_create),
        with_options=lambda **_k: SimpleNamespace(
            responses=SimpleNamespace(create=responses_create)
        ),
    )


def _config(tmp_path):
    return AppConfiguration(
        green_api_instance_id="i", green_api_token="t", ai_api_key="k",
        ai_model="gpt-5.6-luna", ai_reply_max_tokens=500,
        godfather_phone=CHAT,
        feature_flags={"enable_memory_system": True, "enable_rbac": True},
        data_root=str(tmp_path),
        memory={
            "session": {
                "storage_dir": str(tmp_path / "sessions"),
                "window_days": 2,
                "max_tokens_by_role": {"client": 4000, "godfather": 100000},
            },
            "longterm": {"enabled": True, "storage_dir": str(tmp_path / "memory")},
            "roll": {"hour": 2, "catchup_lookback_days": 21, "stale_claim_minutes": 120},
        },
    )


def _turn(handler, text, message_id="m-new"):
    """One turn as the WhatsApp boundary drives it (2026-09-30, DeniDin stores every
    message): the user's message is stored on receipt, then the reply once "sent"."""
    app = handler.denidin
    m = WhatsAppMessage(
        message_id=message_id, chat_id=CHAT, sender_id=CHAT, sender_name="Avi",
        text_content=text, timestamp=0, message_type="text",
    )
    app.store_inbound(m)
    request = handler.create_request(m, chat_id=CHAT, user_phone=CHAT)
    return handler.handle_message(request, chat_id=CHAT, user_phone=CHAT, sender="Avi", recipient="DeniDin")


@pytest.mark.integration
class TestRollingWindowThroughTheBackbone:
    def test_input_items_are_the_rolling_window_plus_new_turn(self, tmp_path):
        capture = []
        handler = make_ai_handler(_fake_client(capture), _config(tmp_path))
        # 3 simulated days; window_days=2 so the oldest is out of window.
        seed_message(handler.session_manager, CHAT, "user", "יום ראשון", 2)
        seed_message(handler.session_manager, CHAT, "assistant", "קיבלתי", 2)
        seed_message(handler.session_manager, CHAT, "user", "יום שני", 1)

        # The window the model should be given = everything currently in the
        # last 2 calendar days, captured BEFORE the new message is stored - the
        # new message itself is stored on receipt but excluded from the window
        # (it's appended as the new user turn instead, never duplicated).
        expected_window = handler.session_manager.get_rolling_window(
            CHAT, window_days=2, max_tokens=100000
        )
        _turn(handler, "יום שלישי")

        assert capture, "OpenAI boundary must have been called"
        assert "previous_response_id" not in capture[0]  # a new chain: the window is the context
        sent = capture[0]["input"]
        # user items carry their send time (REQ-RMH-007): "[HH:MM:SS dd/mm] <text>"
        assert [i["role"] for i in sent[:-1]] == [i["role"] for i in expected_window]
        assert all(got["content"].endswith(want["content"]) for got, want in zip(sent[:-1], expected_window))
        assert sent[-1]["role"] == "user" and sent[-1]["content"].endswith("יום שלישי")
        # day-2 content is out of the 2-day window
        assert not any("יום ראשון" in i["content"] for i in sent)
        assert any("יום שני" in i["content"] for i in sent)

    def test_restart_continues_the_same_session(self, tmp_path, caplog):
        cap1 = []
        h1 = make_ai_handler(_fake_client(cap1), _config(tmp_path))
        _turn(h1, "ראשון", "m-1")
        sid = h1.session_manager.get_session(CHAT).session_id
        counter_after_1 = h1.session_manager.get_session(CHAT).message_counter

        # "Restart": brand-new Backbone on the SAME data_root.
        cap2 = []
        caplog.clear()
        with caplog.at_level("INFO"):
            h2 = make_ai_handler(_fake_client(cap2), _config(tmp_path))
            _turn(h2, "שני", "m-2")

        assert h2.session_manager.get_session(CHAT).session_id == sid
        assert h2.session_manager.get_session(CHAT).message_counter > counter_after_1
        assert not any(
            "Created new session" in r.message and CHAT in r.message
            for r in caplog.records
        )
        # the model chain the first process left continues on the new one (the pre-restart
        # turn is in the model's context through it)
        assert cap2[0]["previous_response_id"] == "resp_2"
