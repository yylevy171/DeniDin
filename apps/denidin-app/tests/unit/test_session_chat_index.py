"""Feature 070 — durable chat->session index (T012a), bugfix-044.

chat_index.db keeps chat->session stable across a fresh SessionManager on the
same data_root; _reconcile_chat_index() picks up pre-existing UUID-dir sessions
(incl. under expired/); a chat mapping to >1 dir keeps max(message_counter),
warns, deletes nothing; the add_message_with_tokens(timestamp=) seam persists
the given timestamp and defaults to now.
"""
import json
import uuid
from datetime import timedelta

import pytest

from src.managers.session_manager import SessionManager
from src.utils.time_utils import now_local, local_calendar_date
from tests.helpers.seed import seed_message

CHAT = "972522968679@c.us"


@pytest.fixture
def sm(tmp_path):
    return SessionManager(storage_dir=str(tmp_path / "sessions"))


def test_chat_to_session_stable_across_restart(sm):
    seed_message(sm, CHAT, "user", "one", 1)
    sid = sm.get_session(CHAT).session_id
    fresh = SessionManager(storage_dir=str(sm.storage_dir))
    assert fresh.get_session(CHAT).session_id == sid
    seed_message(fresh, CHAT, "user", "two", 0)
    assert len(fresh.get_session(CHAT).message_ids) == 2


def test_index_db_persists_on_disk(sm):
    seed_message(sm, CHAT, "user", "x", 0)
    assert (sm.storage_dir / "chat_index.db").exists()


def test_reconcile_picks_up_a_preexisting_session_dir(sm, tmp_path):
    # Hand-write a session dir with no index row, then build a fresh manager.
    sid = str(uuid.uuid4())
    sdir = sm.storage_dir / sid
    (sdir / "messages").mkdir(parents=True)
    (sdir / "session.json").write_text(json.dumps({
        "session_id": sid, "whatsapp_chat": CHAT, "message_ids": [],
        "message_counter": 0, "created_at": now_local().isoformat(),
        "last_active": now_local().isoformat(), "total_tokens": 0,
    }))
    fresh = SessionManager(storage_dir=str(sm.storage_dir))
    assert fresh.get_session(CHAT).session_id == sid


def test_reconcile_picks_up_a_session_under_expired(sm):
    sid = str(uuid.uuid4())
    sdir = sm.storage_dir / "expired" / "2026-01-01" / sid
    (sdir / "messages").mkdir(parents=True)
    (sdir / "session.json").write_text(json.dumps({
        "session_id": sid, "whatsapp_chat": CHAT, "message_ids": [],
        "message_counter": 0, "created_at": now_local().isoformat(),
        "last_active": now_local().isoformat(), "total_tokens": 0,
        "storage_path": f"expired/2026-01-01/{sid}",
    }))
    fresh = SessionManager(storage_dir=str(sm.storage_dir))
    assert fresh.get_session(CHAT).session_id == sid


def test_duplicate_dirs_keep_max_counter_warn_delete_nothing(sm, caplog):
    lo, hi = str(uuid.uuid4()), str(uuid.uuid4())
    for sid, counter in [(lo, 2), (hi, 9)]:
        sdir = sm.storage_dir / sid
        (sdir / "messages").mkdir(parents=True)
        (sdir / "session.json").write_text(json.dumps({
            "session_id": sid, "whatsapp_chat": CHAT, "message_ids": [],
            "message_counter": counter, "created_at": now_local().isoformat(),
            "last_active": now_local().isoformat(), "total_tokens": 0,
        }))
    with caplog.at_level("WARNING"):
        fresh = SessionManager(storage_dir=str(sm.storage_dir))
    assert fresh.get_session(CHAT).session_id == hi  # max(message_counter)
    assert any(r.levelname == "WARNING" for r in caplog.records)
    assert (sm.storage_dir / lo).exists() and (sm.storage_dir / hi).exists()


class TestTimestampSeam:
    def test_seam_persists_the_given_timestamp(self, sm):
        target = now_local() - timedelta(days=6)
        mid = sm.add_message_with_tokens(
            chat_id=CHAT, role="user", content="past", user_role="godfather", timestamp=target,
        )
        session = sm.get_session(CHAT)
        mf = sm.storage_dir / (session.storage_path or session.session_id) / "messages" / f"{mid}.json"
        data = json.loads(mf.read_text())
        assert local_calendar_date(
            __import__("datetime").datetime.fromisoformat(data["timestamp"])
        ) == local_calendar_date(target)

    def test_default_none_uses_now(self, sm):
        mid = sm.add_message_with_tokens(
            chat_id=CHAT, role="user", content="now", user_role="godfather",
        )
        session = sm.get_session(CHAT)
        mf = sm.storage_dir / (session.storage_path or session.session_id) / "messages" / f"{mid}.json"
        data = json.loads(mf.read_text())
        assert local_calendar_date(
            __import__("datetime").datetime.fromisoformat(data["timestamp"])
        ) == local_calendar_date(now_local())
