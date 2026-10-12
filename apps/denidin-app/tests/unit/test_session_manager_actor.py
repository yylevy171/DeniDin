"""Feature 067 (REQ-RMH-029): SessionManager is a serialized actor in front of SessionStore."""
import threading
import time

import pytest

from src.managers.session_manager import SessionManager, SessionManagerStopped, SessionManagerTimeout
from src.managers.session_store import SessionStore
from src.utils.bounded_queue import QueueLimitExceeded
from tests.denidin_test_support import make_config, make_denidin

CHAT = "972522968679@c.us"
PUBLIC = ["get_session", "set_active_capabilities", "set_active_flows", "set_approval_message_id", "add_message",
          "add_message_with_tokens", "get_conversation_history", "get_conversation_history_for_session",
          "load_message", "append_ledger_event_ids", "get_rolling_window", "update_message",
          "has_whatsapp_id_message", "get_messages_for_local_date", "known_chats",
          "archive_aged_and_backstopped_messages", "count_tokens", "calculate_session_tokens",
          "get_session_token_count"]


def _manager(tmp_path, **queues):
    cfg = make_config(memory={"session": {"storage_dir": str(tmp_path / "sessions")}}, message_queues=queues)
    return SessionManager(make_denidin(cfg))


@pytest.fixture
def sm(tmp_path):
    manager = _manager(tmp_path)
    yield manager
    manager.close()


def test_every_public_store_method_is_forwarded():
    public_store = {n for n in dir(SessionStore) if not n.startswith("_") and callable(getattr(SessionStore, n))}
    missing = public_store - set(dir(SessionManager))
    assert not missing, f"facade lacks {missing}"
    for name in PUBLIC:
        assert callable(getattr(SessionManager, name)), name


def test_operations_return_what_the_store_returns(sm):
    sm.add_message_with_tokens(CHAT, "user", "hello", user_role=__import__("src.models.user", fromlist=["Role"]).Role.GODFATHER)
    session = sm.get_session(CHAT)
    assert len(session.message_ids) == 1
    assert sm.known_chats() == [CHAT]
    assert sm.get_rolling_window(CHAT)[0]["content"] == "hello"
    assert sm.has_whatsapp_id_message(CHAT, "nope") is False


def test_all_operations_run_on_the_one_actor_thread(sm, monkeypatch):
    seen = set()
    real = sm._store.known_chats

    def spy():
        seen.add(threading.current_thread().name)
        return real()
    monkeypatch.setattr(sm._store, "known_chats", spy)
    threads = [threading.Thread(target=sm.known_chats) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen == {"session-manager-actor"}


def test_operations_never_overlap(sm, monkeypatch):
    active = {"now": 0, "max": 0}
    real = sm._store.known_chats

    def slow():
        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
        time.sleep(0.02)
        active["now"] -= 1
        return real()
    monkeypatch.setattr(sm._store, "known_chats", slow)
    threads = [threading.Thread(target=sm.known_chats) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert active["max"] == 1


def test_exception_in_actor_reaches_caller_and_actor_survives(sm):
    with pytest.raises(Exception):
        sm.add_message()  # missing arguments -> TypeError inside the actor
    assert sm.is_alive()
    assert sm.known_chats() == []


def test_slow_call_times_out_loudly(tmp_path, monkeypatch):
    manager = _manager(tmp_path, session_call_timeout_seconds=0.05)
    monkeypatch.setattr(manager._store, "known_chats", lambda: time.sleep(0.3))
    try:
        with pytest.raises(SessionManagerTimeout):
            manager.known_chats()
    finally:
        manager.close()


def test_full_queue_raises_limit_exceeded(tmp_path, monkeypatch):
    manager = _manager(tmp_path, session_max=1, session_call_timeout_seconds=2)
    gate = threading.Event()
    monkeypatch.setattr(manager._store, "known_chats", lambda: gate.wait(2))
    first = threading.Thread(target=manager.known_chats)
    first.start()
    time.sleep(0.1)  # the actor is now busy with the first call
    second = threading.Thread(target=lambda: manager.queue.put_or_raise(("known_chats", (), {}, None)))
    second.start()
    second.join()
    try:
        with pytest.raises(QueueLimitExceeded):
            manager.known_chats()
    finally:
        gate.set()
        first.join()
        manager.close()


def test_close_stops_the_thread_and_later_calls_fail(tmp_path):
    manager = _manager(tmp_path)
    manager.close()
    assert not manager.is_alive()
    with pytest.raises(SessionManagerStopped):
        manager.known_chats()


def test_restart_after_death_keeps_working(tmp_path):
    manager = _manager(tmp_path)
    manager.close()
    manager.start()
    try:
        assert manager.known_chats() == []
    finally:
        manager.close()


def test_reentrant_call_from_actor_does_not_deadlock(sm, monkeypatch):
    monkeypatch.setattr(sm._store, "known_chats", lambda: sm.get_session(CHAT) and ["x"])
    assert sm.known_chats() == ["x"]


def test_malformed_item_is_discarded_and_actor_survives(sm):
    sm.queue.put_or_raise(("known_chats", (), {}, None))
    assert sm.known_chats() == []
    assert sm.is_alive()
