"""Feature 070 US2 — the nightly roll end-to-end over real components (T023a).

Real `AIHandler` (⇒ real `SessionManager`, `RollMarkerStore`, `MemoryManager`,
ChromaDB) on a tmp data_root; OpenAI mocked at the network boundary only. Adds
the coverage the unit file (`test_daily_roll_service.py`) does not:
`roll_markers.db` **row states** across a run, and the `collection.delete(where=…)`
idempotent overwrite when a marker is manually reset and the day re-rolled.
"""
from datetime import timedelta

import pytest

from src.handlers.ai_handler import AIHandler
from src.managers.memory_collections import collection_name_for_chat
from src.services import daily_summary_roll_service as svc
from src.utils.time_utils import local_calendar_date, now_local
from tests.integration._rolling_helpers import fake_client, roll_context, rolling_config

GROUP = "120363000000000001@g.us"
SOLO = "972509990000@c.us"


def _seed(sm, chat, content, days_ago, *, sender_name=None):
    return sm.add_message_with_tokens(
        chat_id=chat, role="user", content=content, user_role="godfather",
        sender_name=sender_name, timestamp=now_local() - timedelta(days=days_ago),
    )


def _marker_row(store, chat, date_str):
    cur = store._conn.execute(  # pylint: disable=protected-access
        "SELECT status, message_count, summary_memory_id, source FROM roll_markers "
        "WHERE chat=? AND date=?", (chat, date_str))
    return cur.fetchone()


@pytest.mark.integration
class TestDailyRollIntegration:
    def _handler(self, tmp_path, capture):
        return AIHandler(fake_client(capture), rolling_config(tmp_path, SOLO))

    def test_marker_rows_reach_committed_state_with_the_right_fields(self, tmp_path):
        capture = []
        h = self._handler(tmp_path, capture)
        _seed(h.session_manager, GROUP, "פגישה עם לקוח מחר", 1, sender_name="Dana")
        _seed(h.session_manager, SOLO, "today only", 0)  # nothing yesterday for SOLO

        svc._sweep_daily_roll(roll_context(h), now=now_local(), lookback_days=2)

        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        store = h.roll_marker_store

        grp = _marker_row(store, GROUP, y)
        assert grp["status"] == "committed"
        assert grp["message_count"] == 1
        assert grp["summary_memory_id"]  # a real ChromaDB id
        assert grp["source"] in ("daily-roll", "catch-up")

        solo = _marker_row(store, SOLO, y)
        assert solo["status"] == "committed"
        assert solo["message_count"] == 0          # empty day → marker only
        assert solo["summary_memory_id"] is None
        assert not capture or all("today only" not in str(c.get("input", "")) for c in capture)

    def test_manual_marker_reset_re_rolls_and_overwrites_the_summary(self, tmp_path):
        capture = []
        h = self._handler(tmp_path, capture)
        _seed(h.session_manager, SOLO, "הפקדה בבנק אלפא", 1)
        ctx = roll_context(h)

        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        coll = h.memory_manager.get_or_create_collection(collection_name_for_chat(SOLO))

        def summary_ids():
            return coll.get(where={"$and": [
                {"type": {"$eq": "daily_summary"}}, {"chat": {"$eq": SOLO}}, {"date": {"$eq": y}},
            ]})["ids"]

        first_ids = summary_ids()
        assert len(first_ids) == 1

        # Operator manually clears the marker; the next sweep must re-roll and the
        # collection.delete(where=…) must leave exactly ONE summary (not two).
        h.roll_marker_store._conn.execute(  # pylint: disable=protected-access
            "DELETE FROM roll_markers WHERE chat=? AND date=?", (SOLO, y))
        h.roll_marker_store._conn.commit()  # pylint: disable=protected-access

        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)

        after_ids = summary_ids()
        assert len(after_ids) == 1, "collection.delete(where=…) must overwrite, not duplicate"
        assert _marker_row(h.roll_marker_store, SOLO, y)["status"] == "committed"

    def test_startup_sweep_catches_up_missed_days_with_source_catch_up(self, tmp_path):
        capture = []
        h = self._handler(tmp_path, capture)
        for d in (1, 2, 3):
            _seed(h.session_manager, SOLO, f"יום {d}: עדכון", d)

        svc.run_startup_daily_roll_sweep(roll_context(h))

        today = local_calendar_date(now_local())
        for d in (1, 2, 3):
            row = _marker_row(h.roll_marker_store, SOLO, (today - timedelta(days=d)).isoformat())
            assert row["status"] == "committed"
            assert row["source"] == "catch-up"
