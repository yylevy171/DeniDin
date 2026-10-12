# mypy: disable-error-code="no-any-return"
"""
Session Manager (Feature 067, REQ-RMH-029): a serialized actor in front of ``SessionStore``.

Why: the store reloads ``session.json`` from disk on every call and every setter rewrites
the whole file, so the poller thread (storing inbound messages), the dispatcher thread
(handling them) and the scheduler threads would lose updates, duplicate ``order_num`` and
read torn files if they called it concurrently. Here every public operation is put on ONE
bounded ``queue.Queue`` (reads and writes alike) together with a ``Future``; one actor
thread executes them one at a time against the store and completes the future. The public
signatures are the store's, so callers did not change.

``Message`` and ``Session`` live in ``session_store`` and are re-exported here.
"""
import threading
import time
from concurrent.futures import Future, TimeoutError as FutureTimeout
from datetime import datetime
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional

from src.managers.session_store import Message, Session, SessionStore
from src.utils.bounded_queue import BoundedQueue, QueueSettings
from src.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = ["Message", "Session", "SessionManager", "SessionManagerTimeout", "SessionManagerStopped"]

_STOP = object()


class SessionManagerTimeout(Exception):
    """A session operation did not complete within ``session_call_timeout_seconds``."""


class SessionManagerStopped(Exception):
    """The actor thread died or was closed before completing the operation."""


class SessionManager:
    """Thread-safe facade: same public methods as ``SessionStore``, executed by one actor thread."""

    def __init__(self, denidin: Any):
        self.denidin = denidin
        self._settings = QueueSettings.from_config(denidin.config)
        self._store = SessionStore(denidin)
        self.storage_dir: Path = self._store.storage_dir
        self.queue: BoundedQueue = BoundedQueue(
            "session", self._settings.session_max, self._settings.warn_size(self._settings.session_max))
        self._in_flight: Optional[Future] = None
        self._thread: Optional[threading.Thread] = None
        self._closed = False
        self.start()

    # ------------------------------------------------------------------ actor thread

    def start(self) -> None:
        """Start (or restart, after a death) the actor thread. The queue survives."""
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="session-manager-actor", daemon=True)
        self._thread.start()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def close(self) -> None:
        """Stop the actor after the operations already queued; idempotent."""
        self._closed = True
        thread = self._thread
        if thread is not None and thread.is_alive():
            self.queue.put_control(_STOP)
            thread.join(timeout=5)

    def _run(self) -> None:
        try:
            while True:
                item = self.queue.get()
                if item is _STOP:
                    return
                try:
                    op, args, kwargs, future = item
                    if not future.set_running_or_notify_cancel():
                        continue
                except Exception:  # pylint: disable=broad-except - a malformed item never ends the thread
                    logger.error("session actor: discarded a malformed queue item", exc_info=True)
                    continue
                self._in_flight = future
                try:
                    future.set_result(getattr(self._store, op)(*args, **kwargs))
                except Exception as exc:  # pylint: disable=broad-except - an item error never ends the thread
                    future.set_exception(exc)
                finally:
                    self._in_flight = None
        except BaseException:  # pylint: disable=broad-except
            logger.critical("session actor thread is dying", exc_info=True)
            raise
        finally:
            pending = self._in_flight
            if pending is not None and not pending.done():
                pending.set_exception(SessionManagerStopped("session actor thread died during this operation"))

    def _call(self, op: str, *args: Any, **kwargs: Any) -> Any:
        if threading.current_thread() is self._thread:
            return getattr(self._store, op)(*args, **kwargs)  # re-entrant call from the actor itself
        if self._closed:
            raise SessionManagerStopped("SessionManager is closed")
        future: Future = Future()
        self.queue.put_or_raise((op, args, kwargs, future), item_id=op)
        started = time.monotonic()
        try:
            result = future.result(timeout=self._settings.session_call_timeout_seconds)
        except FutureTimeout:
            logger.error("session operation %s timed out after %.0fs", op, self._settings.session_call_timeout_seconds)
            raise SessionManagerTimeout(f"session operation {op!r} timed out") from None
        elapsed = time.monotonic() - started
        if elapsed > self._settings.slow_call_seconds:
            logger.warning("slow session operation: %s took %.1fs (queue size %d)", op, elapsed, self.queue.size())
        return result

    # ------------------------------------------------------------------ store attributes tests and tools read

    @property
    def chat_to_session(self) -> Dict[str, str]:
        return self._store.chat_to_session

    @property
    def _index_conn(self):  # pylint: disable=invalid-name
        return self._store._index_conn  # pylint: disable=protected-access

    # ------------------------------------------------------------------ public operations (explicit forwarding)

    def get_session(self, chat_id: str) -> Session:
        return self._call("get_session", chat_id)

    def set_active_capabilities(self, chat_id: str, capabilities: List[str]) -> None:
        return self._call("set_active_capabilities", chat_id, capabilities)

    def set_active_flows(self, chat_id: str, flows: List[str]) -> None:
        return self._call("set_active_flows", chat_id, flows)

    def set_approval_message_id(self, chat_id: str, message_id: Optional[str]) -> None:
        return self._call("set_approval_message_id", chat_id, message_id)

    def add_message(self, *args: Any, **kwargs: Any) -> Message:
        """Same parameters as ``SessionStore.add_message``."""
        return self._call("add_message", *args, **kwargs)

    def add_message_with_tokens(self, *args: Any, **kwargs: Any) -> Message:
        """Same parameters as ``SessionStore.add_message_with_tokens``."""
        return self._call("add_message_with_tokens", *args, **kwargs)

    def get_conversation_history(self, whatsapp_chat: str, max_tokens: Optional[int] = None) -> List[Dict]:
        return self._call("get_conversation_history", whatsapp_chat, max_tokens)

    def get_conversation_history_for_session(self, session: Session, max_tokens: Optional[int] = None) -> List[Dict]:
        return self._call("get_conversation_history_for_session", session, max_tokens)

    def load_message(self, session: Session, message_id: str) -> Optional[Message]:
        return self._call("load_message", session, message_id)

    def append_ledger_event_ids(self, session: Session, message_id: str, event_ids: List[str]) -> None:
        return self._call("append_ledger_event_ids", session, message_id, event_ids)

    def get_rolling_window(
        self,
        whatsapp_chat: str,
        *,
        now: Optional[datetime] = None,
        window_days: int = 14,
        max_tokens: Optional[int] = None,
        exclude_message_ids: Optional[Collection[str]] = None,
        with_timestamps: bool = False,
    ) -> List[Dict]:
        return self._call("get_rolling_window", whatsapp_chat, now=now, window_days=window_days,
                          max_tokens=max_tokens, exclude_message_ids=exclude_message_ids,
                          with_timestamps=with_timestamps)

    def update_message(self, whatsapp_chat: str, message_id: str, **fields: Any) -> bool:
        return self._call("update_message", whatsapp_chat, message_id, **fields)

    def has_whatsapp_id_message(self, whatsapp_chat: str, whatsapp_id_message: str) -> bool:
        return self._call("has_whatsapp_id_message", whatsapp_chat, whatsapp_id_message)

    def get_messages_for_local_date(self, session: Session, date) -> List[Dict]:
        return self._call("get_messages_for_local_date", session, date)

    def known_chats(self) -> List[str]:
        return self._call("known_chats")

    def archive_aged_and_backstopped_messages(
        self,
        session: Session,
        *,
        now: Optional[datetime] = None,
        window_days: int = 14,
        max_backstop_tokens: int = 100000,
    ) -> int:
        return self._call("archive_aged_and_backstopped_messages", session, now=now, window_days=window_days,
                          max_backstop_tokens=max_backstop_tokens)

    def count_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        return self._call("count_tokens", text, model)

    def calculate_session_tokens(self, chat_id: str) -> int:
        return self._call("calculate_session_tokens", chat_id)

    def get_session_token_count(self, chat_id: str) -> int:
        return self._call("get_session_token_count", chat_id)

    # ------------------------------------------------------------------ store internals tests and tools use

    def _save_session(self, session: Session) -> None:
        return self._call("_save_session", session)

    def _load_session(self, session_id: str) -> Session:
        return self._call("_load_session", session_id)

    def _index_lookup(self, chat_id: str) -> Optional[str]:
        return self._call("_index_lookup", chat_id)

    def _iter_persisted_messages(self, session: Session, *, live_only: bool = False):
        return self._call("_list_persisted_messages", session, live_only=live_only)
