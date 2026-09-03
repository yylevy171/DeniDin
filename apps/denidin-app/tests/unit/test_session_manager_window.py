"""Feature 070 — get_rolling_window (T010a).

contracts/session-manager-window.md: every message within the last `window_days`
Israel-local calendar days, verbatim, oldest-first, `[sender_name]` prefix for
group user turns, read-only token backstop (drop oldest, always keep newest).
"""
from datetime import datetime, timezone

import pytest

from src.managers.session_manager import SessionManager
from tests.helpers.seed import seed_message

ONE_ON_ONE = "972522968679@c.us"
GROUP = "120363210094632983@g.us"


@pytest.fixture
def sm(tmp_path):
    return SessionManager(storage_dir=str(tmp_path / "sessions"))


class TestWindowMembership:
    def test_only_last_14_calendar_days_returned_oldest_first(self, sm):
        for days_ago, text in [(20, "m20"), (15, "m15"), (13, "m13"), (2, "m2"), (0, "m0")]:
            seed_message(sm, ONE_ON_ONE, "user", text, days_ago)
        window = sm.get_rolling_window(ONE_ON_ONE, window_days=14)
        contents = [m["content"] for m in window]
        assert contents == ["m13", "m2", "m0"]  # 20/15 dropped, oldest-first

    def test_empty_chat_returns_empty_list(self, sm):
        assert sm.get_rolling_window("never-seen@c.us") == []

    def test_future_dated_message_is_kept_and_never_crashes(self, sm):
        seed_message(sm, ONE_ON_ONE, "user", "now", 0)
        seed_message(sm, ONE_ON_ONE, "user", "from the future", -3)  # 3 days ahead
        window = sm.get_rolling_window(ONE_ON_ONE, window_days=14)
        assert "from the future" in [m["content"] for m in window]

    def test_legacy_plus_00_00_timestamp_buckets_by_local_date(self, sm):
        # Write a message, then rewrite its on-disk timestamp to a legacy UTC value
        # that is 'today' in Israel local but 'yesterday' in UTC.
        mid = seed_message(sm, ONE_ON_ONE, "user", "legacy", 0)
        session = sm.get_session(ONE_ON_ONE)
        import json
        base = sm.storage_dir / (session.storage_path or session.session_id) / "messages" / f"{mid}.json"
        data = json.loads(base.read_text())
        data["timestamp"] = datetime(2000, 1, 1, 23, 30, tzinfo=timezone.utc).isoformat()
        base.write_text(json.dumps(data))
        # 2000-01-01 is way outside any window; assert it's excluded (bucketed, not crashed).
        assert sm.get_rolling_window(ONE_ON_ONE, window_days=14) == []


class TestGroupPrefix:
    def test_group_user_turn_prefixed_with_sender_name(self, sm):
        seed_message(sm, GROUP, "user", "שלום לכולם", 1, sender_name="Dana")
        window = sm.get_rolling_window(GROUP, window_days=14)
        assert window[0]["content"] == "[Dana] שלום לכולם"

    def test_one_on_one_user_turn_not_prefixed(self, sm):
        seed_message(sm, ONE_ON_ONE, "user", "היי", 1, sender_name="Dana")
        window = sm.get_rolling_window(ONE_ON_ONE, window_days=14)
        assert window[0]["content"] == "היי"


class TestTokenBackstop:
    def test_oldest_dropped_newest_always_kept(self, sm):
        for i in range(30):
            seed_message(sm, ONE_ON_ONE, "user", f"message number {i} " * 20, days_ago=1)
        full = sm.get_rolling_window(ONE_ON_ONE, window_days=14)
        capped = sm.get_rolling_window(ONE_ON_ONE, window_days=14, max_tokens=200)
        assert len(capped) < len(full)
        assert capped[-1] == full[-1]  # newest preserved
        # what remains is a contiguous newest-suffix of the full window
        assert capped == full[-len(capped):]

    def test_single_newest_returned_even_if_it_alone_exceeds_budget(self, sm):
        seed_message(sm, ONE_ON_ONE, "user", "old short", 1)
        seed_message(sm, ONE_ON_ONE, "user", "enormous " * 500, 1)
        capped = sm.get_rolling_window(ONE_ON_ONE, window_days=14, max_tokens=5)
        assert len(capped) == 1
        assert capped[0]["content"].startswith("enormous")

    def test_no_max_tokens_returns_whole_window(self, sm):
        for i in range(5):
            seed_message(sm, ONE_ON_ONE, "user", f"m{i}", 1)
        assert len(sm.get_rolling_window(ONE_ON_ONE, window_days=14)) == 5
