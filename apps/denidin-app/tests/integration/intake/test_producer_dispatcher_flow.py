"""Feature 067 (REQ-RMH-003/005/021/023/033): real poller loop -> store -> acknowledge -> intake ->
dispatcher thread -> handler. Only the Green API HTTP layer is faked (CONSTITUTION §I/§V)."""
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.handlers.whatsapp_handler import WhatsAppHandler
from src.intake.denidin_dispatcher import DeniDinDispatcher
from src.intake.intake_coordinator import IntakeCoordinator
from src.managers.session_manager import SessionManager
from src.utils.green_api_bot import DeniDinGreenAPIBot
from tests.denidin_test_support import make_config, make_denidin, make_user_manager

pytestmark = pytest.mark.integration

CHAT = "972522968679@c.us"


def _body(n, type_message="textMessage", chat=CHAT, text=None):
    data = {"textMessage": {"textMessageData": {"textMessage": text or f"msg {n}"}},
            "imageMessage": {"fileMessageData": {"caption": f"cap {n}", "fileName": "a.jpg"}},
            "interactiveButtonsResponse": {}}[type_message]
    return {"typeWebhook": "incomingMessageReceived", "idMessage": f"ID{n}", "timestamp": 1760000000 + n,
            "senderData": {"chatId": chat, "sender": chat, "senderName": "Dana"},
            "messageData": {"typeMessage": type_message, **data}}


@pytest.fixture
def app(tmp_path):
    cfg = make_config(data_root=str(tmp_path), godfather_phone=CHAT,
                      memory={"session": {"storage_dir": str(tmp_path / "sessions")}})
    d = make_denidin(cfg)
    d.session_manager = SessionManager(d)
    d.user_manager = make_user_manager(godfather_phone=CHAT)
    d.whatsapp_handler = WhatsAppHandler(d)
    d.intake = IntakeCoordinator(d)
    yield d
    d.session_manager.close()


def _bot(app, bodies, *, non_incoming=()):
    bot = object.__new__(DeniDinGreenAPIBot)
    bot.api = Mock()
    bot.api.session.headers = {}
    bot.logger = Mock()
    bot.router = Mock()
    bot.router.message.state_manager = object()
    bot.raise_errors = False
    bot.on_notification_received = None
    bot.intake = app.intake
    responses = [Mock(data={"receiptId": i + 1, "body": b}) for i, b in enumerate(bodies)]
    bot.api.receiving.receiveNotification.side_effect = responses + [KeyboardInterrupt()]
    return bot


def _stored(app, chat=CHAT):
    return [m["content"] for _mid, m in app.session_manager._iter_persisted_messages(app.session_manager.get_session(chat))]


def _wait(pred, seconds=3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_burst_is_stored_individually_in_order_acknowledged_and_handled_in_order_without_loss(app):
    bodies = [_body(i) for i in range(10)]
    bot = _bot(app, bodies)
    handled = []
    disp = DeniDinDispatcher(app.intake, lambda t, n: handled.append((t, app.receive(n))), poll_seconds=0.01)
    disp.start()
    try:
        bot.run_forever()
        assert _wait(lambda: len(handled) == 10)
    finally:
        disp.stop()
    assert _stored(app) == [f"msg {i}" for i in range(10)]
    assert [m.text_content for _t, m in handled] == [f"msg {i}" for i in range(10)]
    assert [c.args[0] for c in bot.api.receiving.deleteNotification.call_args_list] == list(range(1, 11))
    bot.router.route_event.assert_not_called()


def test_message_is_stored_before_it_is_acknowledged(app):
    bot = _bot(app, [_body(1)])
    seen = []
    bot.api.receiving.deleteNotification.side_effect = lambda receipt: seen.append(_stored(app))
    bot.run_forever()
    assert seen == [["msg 1"]]


def test_handler_receive_returns_the_prestored_message_and_does_not_store_twice(app):
    bot = _bot(app, [_body(1)])
    bot.run_forever()
    item = app.intake.next_work_item(0.01)
    stored_id = item.message.message_id
    again = app.receive(item.notification)
    assert again is item.message and again.message_id == stored_id
    assert _stored(app) == ["msg 1"]
    session = app.session_manager.get_session(CHAT)
    assert session.message_ids == [stored_id]


def test_a_failed_store_is_not_acknowledged_and_the_loop_carries_on(app, monkeypatch):
    bot = _bot(app, [_body(1), _body(2)])
    real = app.session_manager.add_message_with_tokens
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real(*a, **k)
    monkeypatch.setattr(app.session_manager, "add_message_with_tokens", flaky)
    with patch("src.utils.green_api_bot.time.sleep") as sleeper:
        bot.run_forever()
    assert [c.args[0] for c in bot.api.receiving.deleteNotification.call_args_list] == [2]
    sleeper.assert_called_once_with(5.0)
    assert _stored(app) == ["msg 2"]


def test_full_intake_drops_without_storing_but_acknowledges(app, caplog):
    cfg = make_config(data_root=app.config.data_root, memory=app.config.memory, message_queues={"worker_queue_max": 2})
    app.config = cfg
    app.intake = IntakeCoordinator(app)  # no dispatcher running: nothing is taken out
    bot = _bot(app, [_body(i) for i in range(4)])
    with caplog.at_level("ERROR"):
        bot.run_forever()
    assert _stored(app) == ["msg 0", "msg 1"]
    assert [c.args[0] for c in bot.api.receiving.deleteNotification.call_args_list] == [1, 2, 3, 4]
    assert any("QUEUE LIMIT EXCEEDED" in r.getMessage() for r in caplog.records)


def test_non_incoming_webhooks_still_go_through_the_router_as_before(app):
    body = {"typeWebhook": "outgoingMessageStatus", "idMessage": "X"}
    bot = _bot(app, [body])
    bot.run_forever()
    bot.router.route_event.assert_called_once_with(body)
    bot.api.receiving.deleteNotification.assert_called_once_with(1)


def test_types_a_handler_stores_itself_are_queued_without_prestoring(app):
    bot = _bot(app, [_body(1, "interactiveButtonsResponse")])
    bot.run_forever()
    item = app.intake.next_work_item(0.01)
    assert item.type_message == "interactiveButtonsResponse" and item.message is None
    assert _stored(app) == []


def test_media_is_prestored_with_the_caption_the_media_handler_uses(app):
    bot = _bot(app, [_body(1, "imageMessage")])
    bot.run_forever()
    assert _stored(app) == ["cap 1"]


def test_without_an_intake_the_loop_is_todays_synchronous_router_path(app):
    bot = _bot(app, [_body(1)])
    bot.intake = None
    bot.run_forever()
    bot.router.route_event.assert_called_once()
    assert _stored(app) == []


# ---------------------------------------------------------------- media fits in (US6)

def test_media_arriving_while_a_text_request_is_handled_is_noted_then_handled_on_its_own(app):
    import threading
    inside = threading.Event()
    release = threading.Event()
    log = []

    def dispatch(type_message, notification):
        message = app.receive(notification)
        log.append((type_message, message.text_content))
        if type_message == "textMessage" and message.text_content == "msg 1":
            inside.set()
            assert release.wait(3)
            # the model hands back to the app: what arrived meanwhile
            drained = app.receive_pending(message.chat_id)
            log.append(("drained", [i.type_message for i in drained.ordered]))
    disp = DeniDinDispatcher(app.intake, dispatch, poll_seconds=0.01)
    disp.start()
    try:
        first_only = _bot(app, [_body(1)])
        first_only.run_forever()
        assert inside.wait(3)
        later = _bot(app, [_body(2, "imageMessage"), _body(3)])
        later.run_forever()
        release.set()
        assert _wait(lambda: len(log) >= 3)
        time.sleep(0.1)  # nothing else may be dispatched
    finally:
        release.set()
        disp.stop()
    assert log[1] == ("drained", ["imageMessage", "textMessage"])
    assert log[2][0] == "imageMessage"  # the image is dispatched on its own after the current work
    assert len(log) == 3  # the text was attached, not dispatched a second time
