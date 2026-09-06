"""Feature 070 US3 — archive-only maintenance end-to-end (T031a).

Real `AIHandler` (⇒ real `SessionManager` + `MemoryManager` + ChromaDB) on a tmp
data_root; OpenAI mocked at the network boundary only. Proves the archive step
physically **moves** (never deletes) aged / backstopped message files into
`{session_dir}/archived/`, the balance invariant still holds, the live rolling
window respects the token backstop, and — critically — the nightly roll for an
already-archived day **still summarises the archived messages** (it reads
`archived/` as well as `messages/`).
"""
import json
from datetime import timedelta
from pathlib import Path

import pytest

from src.handlers.ai_handler import AIHandler
from src.managers.message_integrity import assert_message_integrity
from src.services import daily_summary_roll_service as svc
from src.utils.time_utils import local_calendar_date, now_local
from tests.integration._rolling_helpers import fake_client, roll_context, rolling_config

CHAT = "972501112222@c.us"


def _seed(sm, content, days_ago):
    return sm.add_message_with_tokens(
        chat_id=CHAT, role="user", content=content, user_role="godfather",
        timestamp=now_local() - timedelta(days=days_ago),
    )


def _session_dir(sm, session):
    return Path(sm.storage_dir) / (session.storage_path or session.session_id)


@pytest.mark.integration
class TestArchiveOnlyIntegration:
    def test_aged_and_backstopped_messages_move_to_archived_and_balance_holds(self, tmp_path):
        capture = []
        h = AIHandler(fake_client(capture), rolling_config(tmp_path, CHAT, window_days=14))
        sm = h.session_manager

        old_id = _seed(sm, "הודעה ישנה מלפני 40 יום על הפקדה בבנק", 40)   # aged out
        _seed(sm, "word " * 400, 1)                                        # in-window, big
        _seed(sm, "word " * 400, 1)
        recent_id = _seed(sm, "הודעה אחרונה חשובה", 0)                     # newest — always kept

        session = sm.get_session(CHAT)
        moved = sm.archive_aged_and_backstopped_messages(
            session, now=now_local(), window_days=14, max_backstop_tokens=300,
        )
        assert moved >= 2  # the 40-day-old one + at least one backstopped

        sdir = _session_dir(sm, session)
        assert (sdir / "archived" / f"{old_id}.json").exists()
        assert not (sdir / "messages" / f"{old_id}.json").exists()
        assert (sdir / "messages" / f"{recent_id}.json").exists()  # newest still live
        assert_message_integrity(sdir)

        # idempotent — a second call moves nothing new
        again = sm.archive_aged_and_backstopped_messages(
            session, now=now_local(), window_days=14, max_backstop_tokens=300)
        assert again == 0
        assert_message_integrity(sdir)

    def test_live_rolling_window_respects_the_token_backstop(self, tmp_path):
        capture = []
        h = AIHandler(fake_client(capture), rolling_config(tmp_path, CHAT, window_days=14))
        for _ in range(12):
            _seed(h.session_manager, "פסקה ארוכה " * 60, 1)
        newest = _seed(h.session_manager, "ההודעה האחרונה", 0)

        window = h.session_manager.get_rolling_window(CHAT, window_days=14, max_tokens=1500)
        total = sum(h.session_manager.count_tokens(i["content"]) for i in window)
        # fits the budget bar the single newest message (always kept)
        assert total <= 1500 + h.session_manager.count_tokens("ההודעה האחרונה") + 5
        assert window and window[-1]["content"].endswith("ההודעה האחרונה")
        assert newest  # referenced

    def test_roll_still_summarises_a_day_whose_messages_were_archived(self, tmp_path):
        capture = []
        h = AIHandler(fake_client(capture), rolling_config(tmp_path, CHAT, window_days=14))
        sm = h.session_manager

        _seed(sm, "NEEDLE_ARCHIVED_CONTENT הפקדה של 12000 שקל", 30)  # aged → will be archived
        _seed(sm, "recent chatter", 1)

        session = sm.get_session(CHAT)
        sm.archive_aged_and_backstopped_messages(session, now=now_local(), window_days=14)
        assert len(sm.get_session(CHAT).archived_message_ids) == 1

        day = local_calendar_date(now_local()) - timedelta(days=30)
        svc._roll_one_chat_day(roll_context(h), CHAT, day, source="migration", log_prefix="")

        coll = h.memory_manager.get_or_create_collection(svc.collection_name_for_chat(CHAT))
        got = coll.get(where={"$and": [
            {"type": {"$eq": "daily_summary"}}, {"chat": {"$eq": CHAT}},
            {"date": {"$eq": day.isoformat()}},
        ]})
        assert len(got["ids"]) == 1
        # the fake summariser echoes its input transcript → the archived line is in it
        assert any("NEEDLE_ARCHIVED_CONTENT" in d for d in got["documents"])

    def test_no_message_file_is_ever_deleted_by_the_archive_or_roll_path(self, tmp_path):
        # static guard mirrored from test_retired_paths_removed.py, scoped to the
        # two modules this feature's archive/roll path lives in
        src = Path(__file__).resolve().parents[2] / "src"
        for rel in ("managers/session_manager.py", "services/daily_summary_roll_service.py"):
            text = (src / rel).read_text(encoding="utf-8")
            # strip comments/docstrings so a historical mention doesn't trip it
            body = "\n".join(
                ln.split("#")[0] for ln in text.splitlines()
            )
            for banned in (".unlink(", "os.remove(", "shutil.rmtree("):
                assert banned not in body, f"{banned} in {rel}"
