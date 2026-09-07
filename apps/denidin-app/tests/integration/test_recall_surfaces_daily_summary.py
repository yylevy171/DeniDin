"""Feature 070 US2 — recall surfaces daily summaries in the model's context (T024a).

Real `AIHandler` + real `MemoryManager` + real ChromaDB on a tmp data_root,
OpenAI mocked at the network boundary only. Seeds 12 `daily_summary` records over
~3 weeks (plus a couple of legacy `session_summary` records) and asks a question
whose answer is only in one older summary → asserts that summary is in the
`RECALLED MEMORIES` block handed to the model. `daily_summary_top_k=10` keeps it
where the old default of 5 would have dropped it (contracts/ai-handler-recall.md).
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.handlers.ai_handler import AIHandler
from src.managers.memory_collections import collection_name_for_chat
from src.models.message import WhatsAppMessage
from src.utils.time_utils import local_calendar_date, now_local
from tests.integration._rolling_helpers import fake_client, rolling_config

CHAT = "972501230000@c.us"


def _msg(handler, text):
    m = WhatsAppMessage(message_id="q-1", chat_id=CHAT, sender_id=CHAT, sender_name="Avi",
                        text_content=text, timestamp=0, message_type="text")
    return handler.create_request(m, chat_id=CHAT, user_phone=CHAT)


@pytest.mark.integration
class TestRecallSurfacesDailySummary:
    def _seed_summaries(self, handler):
        mm = handler.memory_manager
        coll = collection_name_for_chat(CHAT)
        today = local_calendar_date(now_local())
        # 12 daily summaries; only the one 15 days ago mentions the accountant meeting.
        for d in range(1, 13):
            date_str = (today - timedelta(days=d)).isoformat()
            content = (f"סיכום יום {date_str}: עודכנו קבלות ותשלומים שוטפים, "
                       f"נשלחו חשבונית ללקוח.")
            if d == 12:  # the OLDEST of the twelve
                content = (f"סיכום יום {date_str}: נקבעה פגישה עם רואה חשבון "
                           f"ליום שלישי בנושא הדוח השנתי.")
            mm.remember(content, coll, metadata={
                "type": "daily_summary", "chat": CHAT, "date": date_str,
                "scope": "PRIVATE", "user_phone": CHAT, "message_count": 4, "source": "daily-roll",
            })
        # a couple of legacy session_summary records (should not break recall)
        for i in range(2):
            mm.remember(f"session summary legacy {i}: general chatter", coll, metadata={
                "type": "session_summary", "chat": CHAT, "scope": "PRIVATE", "user_phone": CHAT,
            })

    def test_old_daily_summary_reaches_the_model_via_recalled_memories(self, tmp_path):
        capture = []
        cfg = rolling_config(tmp_path, CHAT)
        cfg.memory["longterm"]["min_similarity"] = 0.0  # fake embeddings — rank, don't threshold
        handler = AIHandler(fake_client(capture), cfg)
        self._seed_summaries(handler)

        handler.get_response(_msg(handler, "מתי הפגישה עם רואה חשבון?"),
                             chat_id=CHAT, user_phone=CHAT, sender="Avi", recipient="DeniDin")

        assert capture, "the OpenAI boundary must have been called"
        instructions = capture[-1]["instructions"]
        assert "RECALLED MEMORIES" in instructions
        assert "פגישה עם רואה חשבון" in instructions, (
            "the oldest of 12 daily summaries (the accountant meeting) must still be "
            "recalled — daily_summary_top_k=10 keeps it where the old default of 5 would drop it"
        )

    def test_legacy_session_summaries_do_not_break_recall(self, tmp_path):
        capture = []
        cfg = rolling_config(tmp_path, CHAT)
        cfg.memory["longterm"]["min_similarity"] = 0.0
        handler = AIHandler(fake_client(capture), cfg)
        self._seed_summaries(handler)  # includes 2 legacy session_summary records
        # a plain turn still succeeds and still recalls daily summaries
        handler.get_response(_msg(handler, "עדכון כללי"),
                             chat_id=CHAT, user_phone=CHAT, sender="Avi", recipient="DeniDin")
        assert capture
        assert "RECALLED MEMORIES" in capture[-1]["instructions"]
