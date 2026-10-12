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
    assert coord.next_work_item(0.01) is None  # stale arrival ids are skipped


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


def test_full_chat_queue_drops_without_storing_and_keeps_dropping():
    d = _denidin(intake_max_per_chat=2)
    coord = IntakeCoordinator(d)
    _submit(coord, "m0")
    _submit(coord, "m1")
    for i in (2, 3):
        with pytest.raises(QueueLimitExceeded):
            coord.check_room(_event(f"m{i}"))
    assert d.stored == ["m0", "m1"]  # nothing stored for the dropped ones
    assert coord.queues()[1].dropped == 2
    coord.next_work_item(0.01)
    coord.check_room(_event("m4"))  # room again


def test_full_arrival_queue_also_drops():
    coord = IntakeCoordinator(_denidin(intake_max_total=1))
    _submit(coord, "m0", chat="a")
    with pytest.raises(QueueLimitExceeded):
        coord.check_room(_event("m1", chat="b"))


def test_queues_lists_arrival_and_every_chat():
    coord = IntakeCoordinator(_denidin())
    _submit(coord, "m0", chat="a")
    _submit(coord, "m1", chat="b")
    assert {q.name for q in coord.queues()} == {"intake:arrival", "intake:a", "intake:b"}


def test_pending_item_for_unstored_type_has_no_message():
    coord = IntakeCoordinator(SimpleNamespace(config=make_config(), user_manager=_Users(), prestore=lambda n: None))
    item = coord.prepare(SimpleNamespace(event=_event("t1", "interactiveButtonsResponse")))
    assert isinstance(item, PendingItem) and item.message is None
