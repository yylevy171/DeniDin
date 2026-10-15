"""Intake (Feature 067): what the poller received and the worker has not handled yet.

The poller thread (``DeniDinGreenAPIBot.run_forever``) receives a webhook, stores the
message (``DeniDin.prestore``), acknowledges it upstream and ``submit``s it to the ONE worker
queue; the ``DeniDinDispatcher`` thread (the worker) takes the next item with ``next_work_item``,
and the backbone takes the following messages of the same chat with ``drain_attachable`` at a
hand-back (REQ-RMH-001..004). The queue is a ``BoundedQueue`` (REQ-RMH-025/033): the one
thread-safe building block, with a hard limit. It is already in arrival order, so the worker
just takes the first one waiting. (Later: one worker per chat/session.)

Single-thread parts: ``deferred`` and ``_current`` belong to the worker thread
(the backbone runs on it too); the poller only calls ``check_room``/``prepare``/``submit``.
"""
import queue
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, List, Optional

from whatsapp_chatbot_python import Notification

from src.utils.bounded_queue import BoundedQueue, QueueLimitExceeded, QueueSettings
from src.utils.logger import get_logger
from src.utils.wire_log import audit_wire, debug_wire

logger = get_logger(__name__)

# Message types that can join the model's running work as a user message.
ATTACHABLE_TYPES = frozenset({"textMessage", "extendedTextMessage", "contactMessage"})
# Media: stored, noted to the model, handled on its own afterwards (REQ-RMH-019).
MEDIA_TYPES = frozenset({"imageMessage", "documentMessage", "videoMessage"})

WORKER_QUEUE_NAME = "worker"


@dataclass
class PendingItem:
    """One inbound webhook: the notification, its type, and the stored message (None
    for types the poller does not store - button taps, edits, deletes, unsupported)."""
    notification: Notification
    type_message: str
    chat_id: str
    id_message: str
    message: Optional[Any] = None  # WhatsAppMessage
    inbound_logged: bool = False   # the raw webhook was wire-logged at receipt


@dataclass
class Drained:
    """What a hand-back drain pulled out of the worker queue (arrival order kept in each list)."""
    attachable: List[PendingItem]  # text/contact from non-blocked senders -> go to the model now
    media: List[PendingItem]       # stored; the model is told, handled afterwards
    ordered: List[PendingItem] = field(default_factory=list)  # attachable + media, in arrival order


def _event_chat_id(event: dict) -> str:
    return (event.get("senderData") or {}).get("chatId", "") or ""


def _event_type(event: dict) -> str:
    return (event.get("messageData") or {}).get("typeMessage", "") or ""


class IntakeCoordinator:
    def __init__(self, denidin: Any):
        self._denidin = denidin
        settings = QueueSettings.from_config(denidin.config)
        self._queue: BoundedQueue = BoundedQueue(
            WORKER_QUEUE_NAME, settings.worker_queue_max, settings.warn_size(settings.worker_queue_max))
        self.deferred: Deque[PendingItem] = deque()
        self._current: Optional[PendingItem] = None

    # ------------------------------------------------------------------ monitoring

    def queues(self) -> List[BoundedQueue]:
        return [self._queue]

    # ------------------------------------------------------------------ poller side

    def check_room(self, event: dict) -> None:
        """Raise ``QueueLimitExceeded`` (after logging ERROR and counting the drop) when
        the worker queue is full: the caller then drops the message WITHOUT storing it
        (REQ-RMH-033 - a full queue means something is very wrong)."""
        if not self._queue.has_room():
            self._log_inbound(event)  # received, even though it is dropped
            self._queue.note_drop(str(event.get("idMessage", "?")))
            raise QueueLimitExceeded(f"queue {self._queue.name!r} is full")

    def prepare(self, notification: Notification) -> PendingItem:
        """Store the message if it is one of the stored types (raises if storing fails -
        the caller then does not acknowledge, REQ-RMH-021) and wrap it as a PendingItem."""
        event = notification.event
        self._log_inbound(event)  # logged at receipt: a message merged at a hand-back never reaches a handler
        return PendingItem(
            notification=notification, type_message=_event_type(event), chat_id=_event_chat_id(event),
            id_message=str(event.get("idMessage", "")), message=self._denidin.prestore(notification),
            inbound_logged=True)

    @staticmethod
    def _log_inbound(event: dict) -> None:
        audit_wire("whatsapp", "in", "webhook", event)
        debug_wire("whatsapp", "in", "webhook", event)

    def submit(self, item: PendingItem) -> None:
        self._queue.put_or_raise(item, item_id=item.id_message)

    # ------------------------------------------------------------------ worker side

    def next_work_item(self, timeout: float = 0.5) -> Optional[PendingItem]:
        """The next item to handle: deferred ones first (in the order they were set aside),
        then the first message waiting in the queue; None after ``timeout`` with nothing."""
        self._current = None
        if self.deferred:
            self._current = self.deferred.popleft()
            return self._current
        try:
            self._current = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        return self._current

    def inbound_logged_for(self, notification: Notification) -> bool:
        """Whether the item being handled now had its raw webhook wire-logged at receipt."""
        current = self._current
        return bool(current is not None and current.inbound_logged
                    and current.id_message == str(notification.event.get("idMessage", "")))

    def prestored_for(self, notification: Notification) -> Optional[Any]:
        """The WhatsAppMessage the poller already stored for the item being handled now."""
        current = self._current
        if current is not None and current.message is not None \
                and current.id_message == str(notification.event.get("idMessage", "")):
            return current.message
        return None

    def drain_attachable(self, chat_id: str) -> Drained:
        """At a hand-back: take the messages waiting at the FRONT of the queue for as long as
        they belong to ``chat_id`` - the first message of another chat stops the drain and stays
        in line (nothing is skipped or reordered). Text/contact messages from non-blocked
        senders are returned to join the model's next input; media is returned separately (the
        model is told, REQ-RMH-019) and set aside to be handled on its own afterwards;
        everything else is set aside untouched. Order kept."""
        drained = Drained(attachable=[], media=[])
        while True:
            front = self._queue.peek()
            if front is None or front.chat_id != chat_id:
                break
            item = self._queue.get_nowait()
            if item.type_message in ATTACHABLE_TYPES and item.message is not None \
                    and not self._sender_blocked(item.message):
                drained.attachable.append(item)
                drained.ordered.append(item)
            elif item.type_message in MEDIA_TYPES and item.message is not None \
                    and not self._sender_blocked(item.message):
                drained.media.append(item)
                drained.ordered.append(item)
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
