"""Feature 070 — RollMarkerStore (T020a).

Pins the claim-first two-phase protocol and the stale-claim re-take rule from
contracts/roll-marker-store.md.
"""
from datetime import timedelta

import pytest

from src.managers.roll_marker_store import RollMarkerStore
from src.models.config import AppConfiguration
from src.utils.time_utils import now_local


@pytest.fixture
def store(tmp_path):
    return RollMarkerStore(str(tmp_path / "memory_rolls"))


CHAT = "120363210094632983@g.us"
DATE = "2026-08-20"


class TestClaimCommitCycle:
    def test_fresh_claim_succeeds_then_is_not_yet_rolled(self, store):
        assert store.try_claim(CHAT, DATE, "daily-roll") is True
        assert store.is_rolled(CHAT, DATE) is False  # claimed != committed

    def test_double_claim_second_fails(self, store):
        assert store.try_claim(CHAT, DATE, "daily-roll") is True
        assert store.try_claim(CHAT, DATE, "daily-roll") is False

    def test_commit_makes_it_rolled(self, store):
        store.try_claim(CHAT, DATE, "daily-roll")
        store.commit(CHAT, DATE, message_count=7, memory_id="mem-1")
        assert store.is_rolled(CHAT, DATE) is True

    def test_empty_day_marker_is_rolled(self, store):
        store.try_claim(CHAT, DATE, "catch-up")
        store.commit(CHAT, DATE, message_count=0, memory_id=None)
        assert store.is_rolled(CHAT, DATE) is True

    def test_try_claim_never_overwrites_a_committed_row(self, store):
        store.try_claim(CHAT, DATE, "daily-roll")
        store.commit(CHAT, DATE, message_count=3, memory_id="mem-x")
        assert store.try_claim(CHAT, DATE, "migration") is False
        rows = store.list_markers(CHAT)
        assert len(rows) == 1 and rows[0]["summary_memory_id"] == "mem-x"

    def test_commit_without_claim_is_a_logged_noop(self, store):
        store.commit(CHAT, DATE, message_count=1, memory_id="m")  # no exception
        assert store.is_rolled(CHAT, DATE) is False


class TestStaleClaimRetake:
    def test_young_claim_not_retakeable(self, tmp_path):
        s = RollMarkerStore(str(tmp_path / "mr"), stale_claim_minutes=120)
        s.try_claim(CHAT, DATE, "daily-roll")
        assert s.try_claim(CHAT, DATE, "catch-up") is False

    def test_old_claim_is_retakeable(self, tmp_path):
        s = RollMarkerStore(str(tmp_path / "mr"), stale_claim_minutes=120)
        s.try_claim(CHAT, DATE, "daily-roll")
        # Backdate the claim well past the stale threshold.
        past = (now_local() - timedelta(minutes=200)).isoformat()
        s._conn.execute(
            "UPDATE roll_markers SET claimed_at=? WHERE chat=? AND date=?", (past, CHAT, DATE)
        )
        s._conn.commit()
        assert s.try_claim(CHAT, DATE, "catch-up") is True
        # It's a fresh claim now, still not committed.
        assert s.is_rolled(CHAT, DATE) is False


class TestConstruction:
    def test_ctor_takes_only_storage_dir_not_appconfiguration(self, tmp_path):
        cfg = AppConfiguration(
            green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        )
        with pytest.raises(TypeError):
            RollMarkerStore(cfg)  # type: ignore[arg-type]

    def test_db_file_created_under_storage_dir(self, tmp_path):
        d = tmp_path / "nested" / "memory_rolls"
        RollMarkerStore(str(d))
        assert (d / "roll_markers.db").exists()
