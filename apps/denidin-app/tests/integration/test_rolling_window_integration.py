"""Feature 070 — rolling window through the real message path (T014a).

Real SessionManager + real AIHandler on an isolated tmp data_root; OpenAI mocked
at the network boundary only (responses + embeddings). Covers:
- the exact `input` items handed to the OpenAI boundary == get_rolling_window()
  output + the new user turn (golden shape);
- restart continuity (bugfix-044 / AC-2 shape): a fresh AIHandler on the same
  data_root continues the existing session, no "Created new session".
"""
from types import SimpleNamespace

import pytest

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage
from tests.helpers.seed import seed_message
from tests.ai_handler_test_support import make_ai_handler

CHAT = "972501234567@c.us"


def _fake_client(capture):
    def responses_create(**kwargs):
        capture.append(kwargs)
        return SimpleNamespace(
            id="resp_1", output=[], output_text="בסדר",
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=5, input_tokens=3, output_tokens=2),
        )

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
    response = handler.single_turn(request, chat_id=CHAT, user_phone=CHAT, sender="Avi", recipient="DeniDin")
    app.store_outbound(m, response.response_text)
    return response


@pytest.mark.integration
class TestRollingWindowThroughAIHandler:
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
        sent = capture[-1]["input"]
        assert sent[:-1] == expected_window
        assert sent[-1] == {"role": "user", "content": "יום שלישי"}
        # day-2 content is out of the 2-day window
        assert not any("יום ראשון" in i["content"] for i in sent)
        assert any("יום שני" in i["content"] for i in sent)

    def test_restart_continues_the_same_session(self, tmp_path, caplog):
        cap1 = []
        h1 = make_ai_handler(_fake_client(cap1), _config(tmp_path))
        _turn(h1, "ראשון", "m-1")
        sid = h1.session_manager.get_session(CHAT).session_id
        counter_after_1 = h1.session_manager.get_session(CHAT).message_counter

        # "Restart": brand-new AIHandler on the SAME data_root.
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
        # the pre-restart turn is in the model's context on the new process
        assert any("ראשון" in i["content"] for i in cap2[-1]["input"])
