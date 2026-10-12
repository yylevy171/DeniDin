"""Intake (Feature 067): what the poller received and the dispatcher has not handled yet.

The poller thread (``DeniDinGreenAPIBot.run_forever``) receives a webhook, stores the
message (``DeniDin.prestore``), acknowledges it upstream and ``submit``s it here; the
``DeniDinDispatcher`` thread takes items out with ``next_work_item`` and the backbone
takes the ones that can join a running conversation out with ``drain_attachable`` at a
hand-back (REQ-RMH-001..004). Every queue is a ``BoundedQueue`` (REQ-RMH-025/033): the
one thread-safe building block, with a hard limit.

Single-thread parts: ``deferred`` and ``_current`` belong to the dispatcher thread
(the backbone runs on it too); the poller only calls ``check_room``/``prepare``/``submit``.
"""
import queue
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

from whatsapp_chatbot_python import Notification

from src.utils.bounded_queue import BoundedQueue, QueueLimitExceeded, QueueSettings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Message types that can join the model's running work as a user message.
ATTACHABLE_TYPES = frozenset({"textMessage", "extendedTextMessage", "contactMessage"})
# Media: stored, noted to the model, handled on its own afterwards (REQ-RMH-019).
MEDIA_TYPES = frozenset({"imageMessage", "documentMessage", "videoMessage"})

ARRIVAL_QUEUE_NAME = "intake:arrival"


@dataclass
class PendingItem:
    """One inbound webhook: the notification, its type, and the stored message (None
    for types the poller does not store - button taps, edits, deletes, unsupported)."""
    notification: Notification
    type_message: str
    chat_id: str
    id_message: str
    message: Optional[Any] = None  # WhatsAppMessage


@dataclass
class Drained:
    """What a hand-back drain pulled out of one chat's queue (arrival order kept in each list)."""
    attachable: List[PendingItem]  # text/contact from non-blocked senders -> go to the model now
    media: List[PendingItem]       # stored; the model is told, handled afterwards


def _event_chat_id(event: dict) -> str:
    return (event.get("senderData") or {}).get("chatId", "") or ""


def _event_type(event: dict) -> str:
    return (event.get("messageData") or {}).get("typeMessage", "") or ""


class IntakeCoordinator:
    def __init__(self, denidin: Any):
        self._denidin = denidin
        settings = QueueSettings.from_config(denidin.config)
        self._settings = settings
        self._chats: Dict[str, BoundedQueue] = {}
        self._arrival: BoundedQueue = BoundedQueue(
            ARRIVAL_QUEUE_NAME, settings.intake_max_total, settings.warn_size(settings.intake_max_total))
        self.deferred: Deque[PendingItem] = deque()
        self._current: Optional[PendingItem] = None

    # ------------------------------------------------------------------ monitoring

    def queues(self) -> List[BoundedQueue]:
        return [self._arrival] + list(self._chats.values())

    def _chat_queue(self, chat_id: str) -> BoundedQueue:
        q = self._chats.get(chat_id)
        if q is None:
            limit = self._settings.intake_max_per_chat
            q = self._chats.setdefault(
                chat_id, BoundedQueue(f"intake:{chat_id}", limit, self._settings.warn_size(limit)))
        return q

    # ------------------------------------------------------------------ poller side

    def check_room(self, event: dict) -> None:
        """Raise ``QueueLimitExceeded`` (after logging ERROR and counting the drop) when
        this chat's queue or the arrival queue is full: the caller then drops the message
        WITHOUT storing it (REQ-RMH-033 - a full intake means something is very wrong)."""
        chat_id = _event_chat_id(event)
        item_id = str(event.get("idMessage", "?"))
        chat_queue = self._chat_queue(chat_id)
        for q in (chat_queue, self._arrival):
            if not q.has_room():
                q.note_drop(item_id)
                raise QueueLimitExceeded(f"queue {q.name!r} is full")

    def prepare(self, notification: Notification) -> PendingItem:
        """Store the message if it is one of the stored types (raises if storing fails -
        the caller then does not acknowledge, REQ-RMH-021) and wrap it as a PendingItem."""
        event = notification.event
        return PendingItem(
            notification=notification, type_message=_event_type(event), chat_id=_event_chat_id(event),
            id_message=str(event.get("idMessage", "")), message=self._denidin.prestore(notification))

    def submit(self, item: PendingItem) -> None:
        self._chat_queue(item.chat_id).put_or_raise(item, item_id=item.id_message)
        self._arrival.put_or_raise(item.chat_id, item_id=item.id_message)

    # ------------------------------------------------------------------ dispatcher side

    def next_work_item(self, timeout: float = 0.5) -> Optional[PendingItem]:
        """The next item to handle: deferred ones first (in the order they were set aside),
        then the oldest waiting chat's oldest message; None after ``timeout`` with nothing."""
        self._current = None
        if self.deferred:
            self._current = self.deferred.popleft()
            return self._current
        while True:
            try:
                chat_id = self._arrival.get(timeout=timeout)
            except queue.Empty:
                return None
            try:
                self._current = self._chat_queue(chat_id).get_nowait()
            except queue.Empty:
                continue  # stale id: that message was already drained at a hand-back
            return self._current

    def prestored_for(self, notification: Notification) -> Optional[Any]:
        """The WhatsAppMessage the poller already stored for the item being handled now."""
        current = self._current
        if current is not None and current.message is not None \
                and current.id_message == str(notification.event.get("idMessage", "")):
            return current.message
        return None

    def drain_attachable(self, chat_id: str) -> Drained:
        """At a hand-back: take everything waiting in ``chat_id``'s queue. Text/contact
        messages from non-blocked senders are returned to join the model's next input;
        media is returned separately (the model is told, REQ-RMH-019) and set aside to be
        handled on its own afterwards; everything else is set aside untouched. Order kept."""
        drained = Drained(attachable=[], media=[])
        chat_queue = self._chats.get(chat_id)
        if chat_queue is None:
            return drained
        while True:
            try:
                item = chat_queue.get_nowait()
            except queue.Empty:
                break
            if item.type_message in ATTACHABLE_TYPES and item.message is not None \
                    and not self._sender_blocked(item.message):
                drained.attachable.append(item)
            elif item.type_message in MEDIA_TYPES and item.message is not None \
                    and not self._sender_blocked(item.message):
                drained.media.append(item)
                self.deferred.append(item)
            else:
                self.deferred.append(item)
        return drained

    def _sender_blocked(self, message: Any) -> bool:
        user_manager = getattr(self._denidin, "user_manager", None)
        if user_manager is None:
            return False
        try:
            return bool(user_manager.get_user(message.sender_id).is_blocked)
        except Exception:  # pylint: disable=broad-except
            logger.warning("could not resolve sender role while draining; treating as not blocked", exc_info=True)
            return False
