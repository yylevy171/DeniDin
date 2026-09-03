"""Feature 070 — archive_aged_and_backstopped_messages (T030a), US3.

Physically moves (rename, NEVER unlink) aged / backstopped messages into
{session_dir}/archived/. The balance invariant always holds; the newest message
is always retained; idempotent.
"""
import pytest

from src.managers.session_manager import SessionManager
from tests.helpers.message_integrity import assert_message_integrity
from tests.helpers.seed import seed_message

CHAT = "972522968679@c.us"


@pytest.fixture
def sm(tmp_path):
    return SessionManager(storage_dir=str(tmp_path / "sessions"))


def _sdir(sm):
    s = sm.get_session(CHAT)
    return sm.storage_dir / (s.storage_path or s.session_id)


def test_aged_message_moved_to_archived_integrity_holds(sm):
    seed_message(sm, CHAT, "user", "old", 40)
    seed_message(sm, CHAT, "user", "recent", 1)
    moved = sm.archive_aged_and_backstopped_messages(
        sm.get_session(CHAT), window_days=14, max_backstop_tokens=100000
    )
    assert moved == 1
    sdir = _sdir(sm)
    assert len(list((sdir / "archived").glob("*.json"))) == 1
    assert len(list((sdir / "messages").glob("*.json"))) == 1
    assert_message_integrity(sdir)


def test_backstop_archives_oldest_keeps_newest(sm):
    for i in range(20):
        seed_message(sm, CHAT, "user", f"msg {i} " * 30, days_ago=1)
    session = sm.get_session(CHAT)
    newest_id = session.message_ids[-1]
    moved = sm.archive_aged_and_backstopped_messages(
        session, window_days=14, max_backstop_tokens=150
    )
    assert moved > 0
    session = sm.get_session(CHAT)
    assert newest_id in session.message_ids
    assert newest_id not in session.archived_message_ids
    assert_message_integrity(_sdir(sm))


def test_tiny_backstop_terminates_and_keeps_newest(sm):
    seed_message(sm, CHAT, "user", "a " * 100, 1)
    seed_message(sm, CHAT, "user", "b " * 100, 1)
    session = sm.get_session(CHAT)
    newest_id = session.message_ids[-1]
    sm.archive_aged_and_backstopped_messages(session, window_days=14, max_backstop_tokens=1)
    assert sm.get_session(CHAT).message_ids == [newest_id]
    assert_message_integrity(_sdir(sm))


def test_idempotent_second_call_moves_nothing(sm):
    seed_message(sm, CHAT, "user", "old", 40)
    seed_message(sm, CHAT, "user", "recent", 1)
    sm.archive_aged_and_backstopped_messages(sm.get_session(CHAT), window_days=14)
    moved_again = sm.archive_aged_and_backstopped_messages(sm.get_session(CHAT), window_days=14)
    assert moved_again == 0
    assert_message_integrity(_sdir(sm))


def test_nothing_to_archive_returns_zero(sm):
    seed_message(sm, CHAT, "user", "recent", 0)
    assert sm.archive_aged_and_backstopped_messages(
        sm.get_session(CHAT), window_days=14, max_backstop_tokens=100000
    ) == 0
