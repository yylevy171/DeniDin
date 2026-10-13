"""Feature 067 (REQ-RMH-001..004, 019, 033): IntakeCoordinator ordering, classification, limits."""
from types import SimpleNamespace

import pytest

from src.intake.intake_coordinator import IntakeCoordinator, PendingItem
from src.utils.bounded_queue import QueueLimitExceeded
from tests.denidin_test_support import make_config


def _event(id_message, type_message="textMessage", chat="c1@c.us", sender=None):
    return {"typeWebhook": "incomingMessageReceived", "idMessage": id_message,
            "senderData": {"chatId": chat, "sender": sender or chat},
            "messageData": {"typeMessage": type_message}}


class _Users:
    def __init__(self, blocked=()):
        self.blocked = set(blocked)

    def get_user(self, phone):
        return SimpleNamespace(is_blocked=phone in self.blocked)


def _denidin(blocked=(), **queues):
    stored = []

    def prestore(notification):
        stored.append(notification.event["idMessage"])
        ev = notification.event
        return SimpleNamespace(sender_id=ev["senderData"]["sender"], chat_id=ev["senderData"]["chatId"])
    d = SimpleNamespace(config=make_config(message_queues=queues), user_manager=_Users(blocked), prestore=prestore)
    d.stored = stored
    return d


def _submit(coord, id_message, type_message="textMessage", chat="c1@c.us", sender=None):
    n = SimpleNamespace(event=_event(id_message, type_message, chat, sender))
    item = coord.prepare(n)
    coord.submit(item)
    return item


def _ids(items):
    return [i.id_message for i in items]


def test_items_come_out_in_arrival_order_across_chats():
    coord = IntakeCoordinator(_denidin())
    for i, chat in enumerate(["a", "b", "a", "c"]):
        _submit(coord, f"m{i}", chat=chat)
    got = [coord.next_work_item(0.01).id_message for _ in range(4)]
    assert got == ["m0", "m1", "m2", "m3"]
    assert coord.next_work_item(0.01) is None


def test_drain_returns_text_and_contact_in_order_and_empties_chat():
    coord = IntakeCoordinator(_denidin())
    _submit(coord, "m0")
    _submit(coord, "m1", "extendedTextMessage")
    _submit(coord, "m2", "contactMessage")
    first = coord.next_work_item(0.01)
    drained = coord.drain_attachable("c1@c.us")
    assert first.id_message == "m0"
    assert _ids(drained.attachable) == ["m1", "m2"] and drained.media == []
    assert coord.next_work_item(0.01) is None


def test_taps_edits_deletes_contacts_array_are_deferred_in_order_not_attached():
    coord = IntakeCoordinator(_denidin())
    _submit(coord, "m0")
    coord.next_work_item(0.01)
    for i, t in enumerate(["interactiveButtonsResponse", "editedMessage", "deletedMessage", "contactsArrayMessage"], 1):
        _submit(coord, f"m{i}", t)
    drained = coord.drain_attachable("c1@c.us")
    assert drained.attachable == [] and drained.media == []
    assert [coord.next_work_item(0.01).id_message for _ in range(4)] == ["m1", "m2", "m3", "m4"]


def test_media_is_returned_for_noting_and_deferred_for_its_own_handling():
    coord = IntakeCoordinator(_denidin())
    _submit(coord, "m0")
    coord.next_work_item(0.01)
    _submit(coord, "m1", "imageMessage")
    _submit(coord, "m2")
    drained = coord.drain_attachable("c1@c.us")
    assert _ids(drained.attachable) == ["m2"] and _ids(drained.media) == ["m1"]
    assert coord.next_work_item(0.01).id_message == "m1"  # handled on its own right after


def test_blocked_sender_is_never_attached():
    coord = IntakeCoordinator(_denidin(blocked={"bad@c.us"}))
    _submit(coord, "m0")
    coord.next_work_item(0.01)
    _submit(coord, "m1", sender="bad@c.us")
    drained = coord.drain_attachable("c1@c.us")
    assert drained.attachable == []
    assert coord.next_work_item(0.01).id_message == "m1"


def test_drain_is_per_chat():
    coord = IntakeCoordinator(_denidin())
    _submit(coord, "a0", chat="a")
    coord.next_work_item(0.01)
    _submit(coord, "b0", chat="b")
    assert coord.drain_attachable("a").attachable == []
    assert coord.next_work_item(0.01).id_message == "b0"


def test_drain_unknown_chat_is_empty():
    drained = IntakeCoordinator(_denidin()).drain_attachable("nobody")
    assert drained.attachable == [] and drained.media == []


def test_prestored_for_matches_only_the_item_being_handled():
    coord = IntakeCoordinator(_denidin())
    item = _submit(coord, "m0")
    other = SimpleNamespace(event=_event("m9"))
    assert coord.prestored_for(SimpleNamespace(event=item.notification.event)) is None  # not taken yet
    taken = coord.next_work_item(0.01)
    assert coord.prestored_for(SimpleNamespace(event=taken.notification.event)) is taken.message
    assert coord.prestored_for(other) is None
    coord.next_work_item(0.01)
    assert coord.prestored_for(SimpleNamespace(event=taken.notification.event)) is None


def test_full_queue_drops_without_storing_and_keeps_dropping():
    d = _denidin(worker_queue_max=2)
    coord = IntakeCoordinator(d)
    _submit(coord, "m1")
    _submit(coord, "m2")
    for i in (3, 4):
        with pytest.raises(QueueLimitExceeded):
            coord.check_room(_event(f"m{i}"))
    assert d.stored == ["m1", "m2"]  # the dropped ones were never stored
    assert coord.queues()[0].dropped == 2
    coord.next_work_item(0.01)
    coord.check_room(_event("m5"))  # room again


def test_there_is_exactly_one_queue():
    coord = IntakeCoordinator(_denidin())
    _submit(coord, "m1", chat="a")
    _submit(coord, "m2", chat="b")
    assert [q.name for q in coord.queues()] == ["worker"]


def test_drain_takes_only_the_same_chat_at_the_front_and_stops_at_another_chat():
    coord = IntakeCoordinator(_denidin())
    _submit(coord, "m0", chat="a")
    coord.next_work_item(0.01)
    _submit(coord, "m1", chat="a")
    _submit(coord, "m2", chat="a")
    _submit(coord, "m3", chat="b")
    _submit(coord, "m4", chat="a")  # behind another chat's message: stays in line
    drained = coord.drain_attachable("a")
    assert _ids(drained.attachable) == ["m1", "m2"]
    assert [coord.next_work_item(0.01).id_message for _ in range(2)] == ["m3", "m4"]



def test_pending_item_for_unstored_type_has_no_message():
    coord = IntakeCoordinator(SimpleNamespace(config=make_config(), user_manager=_Users(), prestore=lambda n: None))
    item = coord.prepare(SimpleNamespace(event=_event("t1", "interactiveButtonsResponse")))
    assert isinstance(item, PendingItem) and item.message is None



def test_inbound_webhook_is_wire_logged_at_receipt_and_the_handler_skips_its_copy(caplog):
    coord = IntakeCoordinator(_denidin())
    with caplog.at_level("INFO", logger="src.utils.wire_log"):
        item = _submit(coord, "m1")
    lines = [r.getMessage() for r in caplog.records if "context='webhook'" in r.getMessage()]
    assert len(lines) == 1 and "m1" in lines[0] and item.inbound_logged
    handled = coord.next_work_item(0.01)
    assert coord.inbound_logged_for(handled.notification)  # the handler must not log it again


def test_a_message_dropped_by_a_full_queue_is_still_logged_as_received(caplog):
    coord = IntakeCoordinator(_denidin(worker_queue_max=1))
    _submit(coord, "m1")
    with caplog.at_level("INFO", logger="src.utils.wire_log"):
        with pytest.raises(QueueLimitExceeded):
            coord.check_room(_event("m2"))
    assert any("m2" in r.getMessage() and "context='webhook'" in r.getMessage() for r in caplog.records)
