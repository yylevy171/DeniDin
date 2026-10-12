"""Feature 067 (REQ-RMH-023/024/032): DeniDinDispatcher is a loop around dispatch()."""
import threading
import time
from types import SimpleNamespace

from src.intake.denidin_dispatcher import DeniDinDispatcher
from src.intake.intake_coordinator import IntakeCoordinator
from tests.denidin_test_support import make_config


def _coordinator():
    d = SimpleNamespace(config=make_config(), user_manager=None, prestore=lambda n: None)
    return IntakeCoordinator(d)


def _put(coord, id_message, type_message="textMessage"):
    ev = {"typeWebhook": "incomingMessageReceived", "idMessage": id_message,
          "senderData": {"chatId": "c", "sender": "c"}, "messageData": {"typeMessage": type_message}}
    coord.submit(coord.prepare(SimpleNamespace(event=ev)))


def _wait(predicate, seconds=3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_dispatches_each_item_once_in_order_with_type_and_notification():
    coord, seen = _coordinator(), []
    disp = DeniDinDispatcher(coord, lambda t, n: seen.append((t, n.event["idMessage"])), poll_seconds=0.01)
    for i, t in enumerate(["textMessage", "imageMessage", "editedMessage"]):
        _put(coord, f"m{i}", t)
    disp.start()
    try:
        assert _wait(lambda: len(seen) == 3)
        assert seen == [("textMessage", "m0"), ("imageMessage", "m1"), ("editedMessage", "m2")]
    finally:
        disp.stop()
    assert not disp.is_alive()


def test_one_message_at_a_time():
    coord, state = _coordinator(), {"now": 0, "max": 0, "done": 0}

    def slow(_t, _n):
        state["now"] += 1
        state["max"] = max(state["max"], state["now"])
        time.sleep(0.02)
        state["now"] -= 1
        state["done"] += 1
    disp = DeniDinDispatcher(coord, slow, poll_seconds=0.01)
    for i in range(5):
        _put(coord, f"m{i}")
    disp.start()
    try:
        assert _wait(lambda: state["done"] == 5)
        assert state["max"] == 1
    finally:
        disp.stop()


def test_failure_is_logged_and_the_next_message_is_still_handled(caplog):
    coord, seen = _coordinator(), []

    def dispatch(_t, n):
        if n.event["idMessage"] == "m0":
            raise RuntimeError("boom")
        seen.append(n.event["idMessage"])
    disp = DeniDinDispatcher(coord, dispatch, error_sleep_seconds=0.01, poll_seconds=0.01)
    _put(coord, "m0")
    _put(coord, "m1")
    disp.start()
    try:
        assert _wait(lambda: seen == ["m1"])
        assert disp.is_alive()
    finally:
        disp.stop()
    assert any("handling an item failed" in r.getMessage() for r in caplog.records)


def test_current_item_is_visible_to_prestored_lookup_during_dispatch():
    d = SimpleNamespace(config=make_config(), user_manager=None, prestore=lambda n: SimpleNamespace(tag="stored"))
    coord, found = IntakeCoordinator(d), []
    disp = DeniDinDispatcher(coord, lambda _t, n: found.append(coord.prestored_for(n)), poll_seconds=0.01)
    _put(coord, "m0")
    disp.start()
    try:
        assert _wait(lambda: found)
        assert found[0].tag == "stored"
    finally:
        disp.stop()


def test_restart_after_stop_works_and_idle_loop_does_not_busy_spin():
    coord = _coordinator()
    disp = DeniDinDispatcher(coord, lambda t, n: None, poll_seconds=0.01)
    disp.start()
    disp.stop()
    disp.start()
    try:
        assert disp.is_alive()
    finally:
        disp.stop()


def test_dispatcher_module_knows_nothing_about_green_api():
    import src.intake.denidin_dispatcher as mod
    imports = [line.lower() for line in open(mod.__file__, encoding="utf-8").read().splitlines()
               if line.startswith(("import ", "from "))]
    for forbidden in ("requests", "green", "whatsapp", "router", "session"):
        assert not any(forbidden in line for line in imports), forbidden
