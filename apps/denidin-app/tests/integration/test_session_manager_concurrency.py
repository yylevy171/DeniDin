"""Feature 067 (REQ-RMH-029): concurrent callers cannot lose updates or tear session.json."""
import json
import threading

import pytest

from src.managers.session_manager import SessionManager
from src.models.user import Role
from tests.denidin_test_support import make_config, make_denidin

pytestmark = pytest.mark.integration

CHAT = "972522968679@c.us"


@pytest.fixture
def sm(tmp_path):
    cfg = make_config(memory={"session": {"storage_dir": str(tmp_path / "sessions")}})
    manager = SessionManager(make_denidin(cfg))
    yield manager
    manager.close()


def test_parallel_writers_lose_nothing_and_never_duplicate_order_num(sm):
    per_thread, workers = 15, 6
    errors = []

    def add(tid):
        try:
            for i in range(per_thread):
                sm.add_message_with_tokens(CHAT, "user", f"t{tid}-{i}", user_role=Role.GODFATHER)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def flip():
        try:
            for i in range(per_thread * 2):
                sm.set_approval_message_id(CHAT, f"A{i}")
                sm.set_active_capabilities(CHAT, ["x"] if i % 2 else [])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=add, args=(t,)) for t in range(workers)] + [threading.Thread(target=flip)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    session = sm.get_session(CHAT)
    assert len(session.message_ids) == per_thread * workers
    orders = [m["order_num"] for _mid, m in sm._iter_persisted_messages(session)]
    assert sorted(orders) == sorted(set(orders)) and len(orders) == per_thread * workers
    on_disk = json.loads((sm.storage_dir / (session.storage_path or session.session_id) / "session.json").read_text())
    assert len(on_disk["message_ids"]) == per_thread * workers
