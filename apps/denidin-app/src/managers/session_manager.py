"""
Session Manager for conversation history.

Manages chat sessions with role-based token limits and message persistence.
Supports UUID-based architecture with separate file storage for messages.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, asdict, field, fields
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

import tiktoken

from src.models.user import Role
from src.utils.logger import get_logger
from src.utils.time_utils import local_calendar_date, n_calendar_days_ago, now_local

logger = get_logger(__name__)


@dataclass
class Message:
    """Individual message in a conversation."""
    message_id: str
    session_id: str  # Session UUID reference
    # 2026-08-19: the REAL role - one of "admin"/"godfather"/"client" (the
    # human sender's actual RBAC role, Role.value.lower()) or "assistant"
    # (DeniDin's own reply). Replaces the old structural "user"/"assistant"
    # value, which conflated "who this message is really from" with "what
    # OpenAI's API needs this turn labeled as" - see ai_required_role below
    # for the latter. Never "blocked": a BLOCKED user's message is rejected
    # upstream at the RBAC gate before it ever reaches persistence.
    role: str
    content: str
    # 2026-08-19: derived, never caller-supplied directly - "user" for
    # admin/godfather/client, "assistant" for assistant. This, NOT `role`,
    # is what get_conversation_history_for_session puts in the "role" key
    # of the dict handed to OpenAI's Responses API - which only accepts
    # literal "user"/"assistant"/"system"/"developer", not an RBAC role
    # name. `role` stays the real, meaningful value for everything else
    # (display, group-turn attribution, future analytics).
    ai_required_role: str = "user"
    # 2026-08-19: the real WhatsApp JID of whoever sent this message - the
    # individual sender's own number for admin/godfather/client (never a
    # group's JID: a group is never a sender), or DeniDin's own number
    # (WhatsAppHandler.own_number) for assistant. Was, until this date, a
    # resolved human-readable display name - see sender_name below for
    # that.
    sender: Optional[str] = None
    # 2026-08-19: renamed from the old `sender` field above - the resolved,
    # human-readable display name (Feature 039's senderContactName ->
    # senderName -> raw-id fallback chain), independent of the real WhatsApp
    # identifier now carried by `sender`.
    sender_name: Optional[str] = None
    # 2026-08-19: the real WhatsApp JID of who this message is addressed
    # to - the other party's number in a 1:1 chat (DeniDin's own number if
    # a human sent it, the human's own number if DeniDin sent it), or the
    # group's own JID in a group (a group message is addressed to the whole
    # group, regardless of which individual sent or DeniDin replied - never
    # null, unlike the old Feature 039 sentinel-retirement scheme this
    # replaces).
    recipient: Optional[str] = None
    # 2026-08-19: resolved display name of whatever `recipient` points at -
    # a person's display name, "DeniDin" for the bot, or a group's own
    # subject/name (Green API's senderData.chatName, real on every group
    # notification already).
    recipient_name: Optional[str] = None
    timestamp: Optional[str] = None
    received_at: Optional[str] = None
    was_received: bool = True
    order_num: int = 0
    image_path: Optional[str] = None
    # Feature 043 (Phase 11 follow-up, 2026-08-18): the raw text a media extractor
    # (image/PDF/DOCX) pulled out of this message's attachment, if any - None/empty
    # when the attachment had no image_path (a text message) or the extractor found
    # no text in it. Replaces LedgerEvent.raw_message_excerpt's old role for media
    # messages: since this message's own message_id/session_id is already the
    # ledger event's traceability pointer, the source content belongs here (once,
    # on the message itself) rather than duplicated into every ledger event
    # captured from it. For a text message, `content` already IS the verbatim
    # source text, so this field stays None there - only ever populated alongside
    # image_path.
    extracted_text: Optional[str] = None
    # Feature 033: id(s) of any LedgerEvent(s) captured from this specific message -
    # the reverse link to LedgerEvent.message_id. Empty for the vast majority of
    # messages (most capture nothing).
    ledger_event_ids: List[str] = field(default_factory=list)


@dataclass
class Session:
    """Chat session with conversation history.

    Feature 070: one long-lived Session per chat - it never expires. The chat ->
    session mapping is authoritative in `chat_index.db` (see SessionManager); the
    in-memory `chat_to_session` dict is a read-through cache over it.
    """
    session_id: str
    whatsapp_chat: str
    message_ids: List[str]
    message_counter: int = 0
    created_at: str = ""
    last_active: str = ""
    total_tokens: int = 0
    # Dead under Feature 070 (no expire->transfer cycle). Kept on the dataclass
    # so an old session.json that still carries it loads without a warning;
    # nothing reads or writes it.
    transferred_to_longterm: bool = False
    storage_path: Optional[str] = None
    # Feature 070 (US3): ids of messages physically moved to
    # {session_dir}/archived/ by the nightly archive step (aged past the 14-day
    # window, or beyond the largest role token limit). Disjoint from
    # message_ids; message_counter == len(message_ids) + len(archived_message_ids).
    archived_message_ids: List[str] = field(default_factory=list)


class SessionManager:
    """
    Manages chat sessions with conversation history.

    Features:
    - UUID-based sessions linked to WhatsApp chat IDs
    - Messages stored as separate JSON files in session directories
    - Background cleanup thread for expired sessions
    - Date-based archival to expired/YYYY-MM-DD/ folders
    """

    def __init__(
        self,
        storage_dir: str = "data/sessions",
    ):
        """
        Initialize SessionManager.

        Args:
            storage_dir: Directory for session storage. The caller composes this
                (SessionManager never reads AppConfiguration). `chat_index.db`
                lives directly under it.

        Feature 070: there is no idle-expiry timeout - sessions never expire.
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory index: whatsapp_chat -> session_id. NON-AUTHORITATIVE cache
        # (Feature 070, REQ-MEM-016) - a read-through over chat_index.db, which
        # is the source of truth. bugfix-044 was caused by this map being the
        # only record and a code path forgetting to populate it.
        self.chat_to_session: Dict[str, str] = {}

        # Feature 070: durable chat -> session index (REQ-MEM-014). Same
        # long-lived-connection idiom as ReminderManager.
        self._index_db_path = self.storage_dir / "chat_index.db"
        self._index_conn = sqlite3.connect(str(self._index_db_path), check_same_thread=False)
        self._index_conn.row_factory = sqlite3.Row
        self._init_chat_index_schema()

        # Load existing sessions from disk (populates the cache) then reconcile
        # the durable index against what's actually on disk.
        self._load_sessions()
        self._reconcile_chat_index()

        logger.info("SessionManager initialized (Feature 070: rolling window, no expiry)")

    def _init_chat_index_schema(self) -> None:
        self._index_conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                chat        TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            """
        )
        self._index_conn.commit()

    def _index_lookup(self, chat_id: str) -> Optional[str]:
        row = self._index_conn.execute(
            "SELECT session_id FROM chat_sessions WHERE chat = ?", (chat_id,)
        ).fetchone()
        return row["session_id"] if row else None

    def _index_upsert(self, chat_id: str, session_id: str) -> None:
        self._index_conn.execute(
            "INSERT INTO chat_sessions (chat, session_id, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(chat) DO UPDATE SET updated_at = excluded.updated_at",
            (chat_id, session_id, now_local().isoformat()),
        )
        self._index_conn.commit()

    def _reconcile_chat_index(self) -> None:
        """Once per construction: make the durable index reflect every session
        actually on disk (active + expired/). INSERT OR IGNORE so an existing
        mapping is never overwritten. A chat that resolves to more than one
        directory keeps the one with the greatest message_counter, logs one
        WARNING, and deletes nothing (REQ-MEM-014)."""
        by_chat: Dict[str, List[Session]] = {}

        def _collect(session_json: Path) -> None:
            try:
                with open(session_json, encoding="utf-8") as f:
                    data = json.load(f)
                sess = self._session_from_dict(data)
            except Exception as e:  # pylint: disable=broad-except
                logger.error(f"reconcile: failed to read {session_json}: {e}")
                return
            by_chat.setdefault(sess.whatsapp_chat, []).append(sess)

        if self.storage_dir.exists():
            for session_dir in self.storage_dir.iterdir():
                if session_dir.is_dir() and session_dir.name != "expired":
                    sj = session_dir / "session.json"
                    if sj.exists():
                        _collect(sj)
            expired_base = self.storage_dir / "expired"
            if expired_base.exists():
                for date_folder in expired_base.iterdir():
                    if date_folder.is_dir():
                        for session_dir in date_folder.iterdir():
                            sj = session_dir / "session.json"
                            if session_dir.is_dir() and sj.exists():
                                _collect(sj)

        for chat, sessions in by_chat.items():
            if len(sessions) > 1:
                winner = max(sessions, key=lambda s: s.message_counter)
                logger.warning(
                    "reconcile: chat %s maps to %d session dirs %s - keeping %s "
                    "(highest message_counter=%d), deleting nothing",
                    chat, len(sessions), [s.session_id for s in sessions],
                    winner.session_id, winner.message_counter,
                )
            else:
                winner = sessions[0]
            self._index_conn.execute(
                "INSERT OR IGNORE INTO chat_sessions (chat, session_id, updated_at) VALUES (?, ?, ?)",
                (chat, winner.session_id, now_local().isoformat()),
            )
        self._index_conn.commit()

        # Refresh the in-memory cache from the durable index.
        self.chat_to_session = {
            r["chat"]: r["session_id"]
            for r in self._index_conn.execute("SELECT chat, session_id FROM chat_sessions")
        }

    @staticmethod
    def _session_from_dict(data: dict) -> Session:
        """Tolerant Session deserialization (Feature 070, REQ-MEM-010, bugfix-035
        H2). Drops any persisted key the current Session model doesn't have and
        logs ONE warning - never raises TypeError. Generic: not an allowlist for
        `pending_ledger_events`, so a future field removal can't strand older
        session.json files either."""
        valid = {f.name for f in fields(Session)}
        unknown = sorted(k for k in data if k not in valid)
        if unknown:
            logger.warning(
                "Session %s: dropping unknown persisted field(s) %s on load",
                data.get("session_id", "<unknown>"), unknown,
            )
        return Session(**{k: v for k, v in data.items() if k in valid})

    def get_session(self, chat_id: str) -> Session:
        """
        Get or create session for a WhatsApp chat.

        Args:
            chat_id: WhatsApp chat ID (e.g., "1234567890@c.us")

        Returns:
            Session object
        """
        # Feature 070: resolve via the durable index (authoritative), falling
        # back to the in-memory cache only as a fast path. One long-lived
        # session per chat - it is never recreated once it exists.
        session_id = self._index_lookup(chat_id) or self.chat_to_session.get(chat_id)
        if session_id:
            self.chat_to_session[chat_id] = session_id
            self._index_upsert(chat_id, session_id)
            return self._load_session(session_id)

        # Create new session (the ONLY path that creates one).
        session_id = str(uuid.uuid4())
        now = now_local().isoformat()

        session = Session(
            session_id=session_id,
            whatsapp_chat=chat_id,
            message_ids=[],
            message_counter=0,
            created_at=now,
            last_active=now,
            total_tokens=0
        )

        self._save_session(session)
        self.chat_to_session[chat_id] = session_id
        self._index_upsert(chat_id, session_id)

        logger.info(f"Created new session {session_id} for chat {chat_id}")
        return session

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_role: str,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
        recipient: Optional[str] = None,
        recipient_name: Optional[str] = None,
        image_path: Optional[str] = None,
        extracted_text: Optional[str] = None,
        ledger_event_ids: Optional[List[str]] = None,
        message_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Add message to session.

        Args:
            chat_id: WhatsApp chat ID
            role: Structural turn role for THIS call - literal "user" or
                "assistant". Kept as a separate parameter from the persisted
                Message.role (see below) purely so every existing call site's
                "user"/"assistant" literal keeps working unchanged; this
                value itself is never persisted.
            content: Message content
            user_role: The real role for a "user" turn - a `Role` enum member
                (Role.ADMIN/GODFATHER/CLIENT) or, on the RBAC-disabled
                fallback path, a plain lowercase string ("client"/"godfather").
                Ignored when role="assistant". Combined with `role` above to
                compute the persisted Message.role (2026-08-19: one of
                "admin"/"godfather"/"client"/"assistant" - see Message's own
                docstring) and Message.ai_required_role ("user"/"assistant",
                what OpenAI's API actually needs this turn labeled as).
            sender: The real WhatsApp JID of whoever sent this message -
                the individual's own number for a user turn, DeniDin's own
                number (WhatsAppHandler.own_number) for an assistant turn.
            sender_name: Resolved human-readable display name of `sender`
                (2026-08-19, renamed from this parameter's old name -
                `sender` itself used to hold this value before real WhatsApp
                numbers were threaded through).
            recipient: The real WhatsApp JID this message is addressed to -
                the other party's number in a 1:1 chat, or the group's own
                JID in a group (never null, never a sentinel string).
            recipient_name: Resolved display name of `recipient` - a
                person's display name, "DeniDin" for the bot, or a group's
                own subject/name.
            image_path: Path to image file (optional)
            extracted_text: Raw text a media extractor pulled out of this
                message's attachment (image/PDF/DOCX), if any (Feature 043,
                optional - see Message.extracted_text's own docstring).
            ledger_event_ids: id(s) of any LedgerEvent(s) captured from this message
                (Feature 033, optional - defaults to empty list)
            message_id: The id decided when this message was first recognized as
                arriving/being created (WhatsAppMessage.from_notification for
                inbound messages) - Feature 033, confirmed design: the same id
                MUST be identical across the persisted message's filename, the
                session's message_ids entry, and LedgerEvent.message_id, never
                regenerated at storage time. Defaults to a fresh UUID when not
                given (correct for a message with no prior identity, e.g. the
                assistant's reply, which is genuinely created at this point).

        Returns:
            Message UUID
        """
        session = self.get_session(chat_id)

        # Increment message counter
        session.message_counter += 1

        # Create message. `timestamp` is a Feature 070 testability seam: a
        # production caller always leaves it None (-> now_local()); tests pass
        # an explicit past datetime to seed a dated conversation through the
        # real persistence API. `received_at` always stays the real wall-clock
        # time this row was written.
        message_id = message_id or str(uuid.uuid4())
        now = (timestamp or now_local()).isoformat()
        received_at = now_local().isoformat()

        # 2026-08-19: compute the real, persisted role + the OpenAI-safe
        # derived role. `role`/`user_role` themselves are never persisted -
        # see this method's docstring for why they still exist as separate
        # parameters. A BLOCKED user_role should structurally never reach
        # here (rejected upstream at the RBAC gate) - normalized the same as
        # any other value rather than special-cased, since there's no real
        # path that exercises it.
        if role == "assistant":
            real_role = "assistant"
            ai_required_role = "assistant"
        else:
            real_role = (
                user_role.value.lower() if isinstance(user_role, Role) else str(user_role).lower()
            )
            ai_required_role = "user"

        message = Message(
            message_id=message_id,
            session_id=session.session_id,  # FK to session UUID
            role=real_role,
            ai_required_role=ai_required_role,
            content=content,
            sender=sender,
            sender_name=sender_name,
            recipient=recipient,
            recipient_name=recipient_name,
            timestamp=now,
            received_at=received_at,
            was_received=True,
            order_num=session.message_counter,
            image_path=image_path,
            extracted_text=extracted_text,
            ledger_event_ids=list(ledger_event_ids) if ledger_event_ids else []
        )

        # Save message to session directory
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"
        messages_dir.mkdir(parents=True, exist_ok=True)

        message_file = messages_dir / f"{message_id}.json"
        with open(message_file, 'w', encoding='utf-8') as f:
            # ensure_ascii=False (2026-08-19): every other JSON persistence path
            # in this codebase (LedgerEventManager) already writes real UTF-8
            # Hebrew instead of \uXXXX escapes - this file never matched that,
            # making every persisted message unreadable via a raw `cat`.
            json.dump(asdict(message), f, indent=2, ensure_ascii=False)

        # Update session
        session.message_ids.append(message_id)
        session.last_active = received_at
        self._save_session(session)
        self._index_upsert(session.whatsapp_chat, session.session_id)

        logger.debug(f"Added message {message_id} to session {session.session_id}")
        return message_id

    def get_conversation_history(self, whatsapp_chat: str, max_tokens: Optional[int] = None) -> List[Dict]:
        """
        Get conversation history in AI format.

        Args:
            whatsapp_chat: WhatsApp chat ID
            max_tokens: Maximum tokens to retrieve (not implemented yet)

        Returns:
            List of messages in format [{"role": "user", "content": "..."}]
        """
        session = self.get_session(whatsapp_chat)
        return self.get_conversation_history_for_session(session, max_tokens)

    def get_conversation_history_for_session(self, session: Session, max_tokens: Optional[int] = None) -> List[Dict]:
        """
        Get conversation history for a specific session in AI format.

        This method works with both active and archived sessions by using
        the session's storage_path to locate messages on disk.

        Args:
            session: Session object
            max_tokens: Maximum tokens to retrieve (not implemented yet)

        Returns:
            List of messages in format [{"role": "user", "content": "..."}]
        """
        if session.storage_path:
            session_dir = self.storage_dir / session.storage_path
        else:
            session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"

        # Feature 039 (US3): a group session's shared history needs to tell members
        # apart, since the model otherwise sees a flat "user said X, user said Y"
        # stream with no way to distinguish godfather from admin. 1:1 sessions have
        # only one human counterpart, so no prefix is needed there.
        is_group_session = '@g.us' in session.whatsapp_chat

        history = []
        for message_id in session.message_ids:
            message_file = messages_dir / f"{message_id}.json"

            if message_file.exists():
                with open(message_file, encoding='utf-8') as f:
                    message_data = json.load(f)

                content = message_data["content"]
                # 2026-08-19: message_data["role"] is now the REAL role
                # ("admin"/"godfather"/"client"/"assistant"), not "user" -
                # ai_required_role is what OpenAI's API needs, and what a
                # "was this a human turn" check must key off. sender_name
                # (renamed from the old `sender`) is the display-name value
                # this prefix was always meant to show.
                if (is_group_session and message_data.get("ai_required_role") == "user"
                        and message_data.get("sender_name")):
                    content = f"[{message_data['sender_name']}] {content}"

                history.append({
                    "role": message_data.get("ai_required_role", message_data["role"]),
                    "content": content
                })

        return history

    # --- Feature 070: rolling 14-day window + per-day gather ------------------

    def _iter_persisted_messages(self, session: Session, *, live_only: bool = False):
        """Yield (message_id, message_data dict) for every persisted message of
        `session` - live `messages/` first, then `archived/` - reading each file
        from disk. A missing file is skipped with a WARNING (never raises). Uses
        `.get(...)` for content/role so a pre-2026-08-19 legacy message dict
        can't KeyError.

        `live_only=True` (Feature 070, task T064) reads ONLY `messages/` and never
        touches `archived/`. `get_rolling_window` uses it so the per-turn cost is
        O(last 14 days) instead of O(every message the chat ever had). Safe:
        a message is in `archived/` only if it aged past the window (out of it by
        definition) or is token-backstop overflow beyond `_BACKSTOP_TOKENS`
        (100k) - and every acting role's `max_tokens` is <= that, so the window's
        own read-only token pass would exclude it regardless. `get_messages_for_local_date`
        (nightly roll / backfill, not per-turn) still reads both."""
        base = self.storage_dir / (session.storage_path or session.session_id)
        sources = [("messages", session.message_ids)]
        if not live_only:
            sources.append(("archived", session.archived_message_ids))
        for sub, ids in sources:
            mdir = base / sub
            for mid in ids:
                mfile = mdir / f"{mid}.json"
                if not mfile.exists():
                    logger.warning(
                        "session %s: message file %s missing on disk - skipped",
                        session.session_id, mfile,
                    )
                    continue
                with open(mfile, encoding="utf-8") as f:
                    yield mid, json.load(f)

    @staticmethod
    def _message_local_date(message_data: dict):
        raw = message_data.get("timestamp") or message_data.get("received_at")
        if not raw:
            return None
        try:
            return local_calendar_date(datetime.fromisoformat(raw))
        except (TypeError, ValueError):
            return None

    def _render_history_item(self, session: Session, message_data: dict) -> Dict:
        """The exact dict shape get_conversation_history_for_session produces:
        {"role": <ai_required_role|role>, "content": <content, group-prefixed>}."""
        content = message_data.get("content", "")
        is_group = "@g.us" in session.whatsapp_chat
        if (is_group and message_data.get("ai_required_role") == "user"
                and message_data.get("sender_name")):
            content = f"[{message_data['sender_name']}] {content}"
        role = (message_data.get("ai_required_role")
                or message_data.get("role") or "user")
        return {"role": role, "content": content}

    def get_rolling_window(
        self,
        whatsapp_chat: str,
        *,
        now: Optional[datetime] = None,
        window_days: int = 14,
        max_tokens: Optional[int] = None,
    ) -> List[Dict]:
        """The per-turn conversation context under Feature 070 (REQ-MEM-001).

        Every message for the chat whose Israel-local calendar date is within
        the last `window_days` calendar days, verbatim, oldest-first, with the
        Feature 039 `[sender_name]` prefix for group user turns - then, if
        `max_tokens` is given, the OLDEST in-window messages are excluded (read
        only - nothing is moved) until the running token total fits. The single
        newest message is always returned even if it alone exceeds `max_tokens`.

        `now` is a test-only seam; production leaves it None. Never raises on a
        future-dated (clock-skew) message, an unloadable session, or a missing
        message file; an empty chat returns [].

        Task T064: reads ONLY the live `messages/` dir - never `archived/` - so
        per-turn cost is O(last 14 days), flat, regardless of how large the
        chat's archive grows. See `_iter_persisted_messages(live_only=...)`.
        """
        try:
            session = self.get_session(whatsapp_chat)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("get_rolling_window: could not resolve session for %s: %s", whatsapp_chat, e)
            return []

        lower = n_calendar_days_ago(max(window_days - 1, 0), now)

        # Collect in-window messages in stored (chronological) order.
        in_window: List[Dict] = []
        for _mid, mdata in self._iter_persisted_messages(session, live_only=True):
            mdate = self._message_local_date(mdata)
            # A future-dated / undatable message is kept (never excludes
            # everything because of one bad timestamp).
            if mdate is not None and mdate < lower:
                continue
            item = self._render_history_item(session, mdata)
            item["_order"] = mdata.get("order_num", 0)
            in_window.append(item)

        in_window.sort(key=lambda d: d["_order"])
        for d in in_window:
            d.pop("_order", None)

        if max_tokens is None or not in_window:
            return in_window

        # Walk newest -> oldest, keep while it fits; drop the oldest.
        kept_reversed: List[Dict] = []
        running = 0
        for item in reversed(in_window):
            cost = self.count_tokens(item["content"])
            if kept_reversed and running + cost > max_tokens:
                break
            kept_reversed.append(item)
            running += cost
        return list(reversed(kept_reversed))

    def get_messages_for_local_date(self, session: Session, date) -> List[Dict]:
        """Every message of `session` whose Israel-local calendar date == `date`
        (live + archived), oldest-first, same item shape as get_rolling_window.
        Used by the nightly roll and the backfill so a backstop-archived message
        is still summarised on its normal schedule (REQ-MEM-036)."""
        items: List[Dict] = []
        for _mid, mdata in self._iter_persisted_messages(session):
            if self._message_local_date(mdata) == date:
                item = self._render_history_item(session, mdata)
                item["_order"] = mdata.get("order_num", 0)
                items.append(item)
        items.sort(key=lambda d: d["_order"])
        for d in items:
            d.pop("_order", None)
        return items

    def known_chats(self) -> List[str]:
        """Every chat that has a session on disk (from the durable index)."""
        return [
            r["chat"]
            for r in self._index_conn.execute("SELECT chat FROM chat_sessions ORDER BY chat")
        ]

    def archive_aged_and_backstopped_messages(
        self,
        session: Session,
        *,
        now: Optional[datetime] = None,
        window_days: int = 14,
        max_backstop_tokens: int = 100000,
    ) -> int:
        """Physically move (rename, NEVER unlink) out of `messages/` and into
        `{session_dir}/archived/` (Feature 070, US3, REQ-MEM-032):
          (a) messages older than the `window_days` cutoff, and
          (b) in-window messages beyond `max_backstop_tokens` counting
              newest->oldest (caller passes the LARGEST role limit, 100000, so
              the on-disk state is deterministic regardless of who spoke last).
        Returns the number of files moved. Idempotent.
        """
        base = self.storage_dir / (session.storage_path or session.session_id)
        live_dir = base / "messages"
        arch_dir = base / "archived"
        if not live_dir.exists():
            return 0

        lower = n_calendar_days_ago(max(window_days - 1, 0), now)

        # Load live messages in chronological order with their dates + token cost.
        live: List[dict] = []
        for mid in list(session.message_ids):
            mfile = live_dir / f"{mid}.json"
            if not mfile.exists():
                continue
            with open(mfile, encoding="utf-8") as f:
                mdata = json.load(f)
            live.append({
                "id": mid,
                "order": mdata.get("order_num", 0),
                "date": self._message_local_date(mdata),
                "cost": self.count_tokens(mdata.get("content", "")),
            })
        live.sort(key=lambda d: d["order"])

        to_archive = set()
        # (a) aged out of the window
        for m in live:
            if m["date"] is not None and m["date"] < lower:
                to_archive.add(m["id"])
        # (b) backstop: keep newest within budget, archive the older overflow.
        # The single newest live message is always retained even if it alone
        # exceeds the budget (mirrors get_rolling_window's read-only cut).
        running = 0
        kept_one = False
        for m in reversed(live):
            if m["id"] in to_archive:
                continue
            running += m["cost"]
            if kept_one and running > max_backstop_tokens:
                to_archive.add(m["id"])
            kept_one = True

        if not to_archive:
            return 0

        arch_dir.mkdir(parents=True, exist_ok=True)
        moved = 0
        for m in live:
            if m["id"] not in to_archive:
                continue
            src = live_dir / f"{m['id']}.json"
            dst = arch_dir / f"{m['id']}.json"
            if src.exists():
                src.rename(dst)  # move, never unlink
                moved += 1
            session.message_ids.remove(m["id"])
            if m["id"] not in session.archived_message_ids:
                session.archived_message_ids.append(m["id"])

        if moved:
            self._save_session(session)
            logger.info(
                "session %s: archived %d aged/backstopped message(s) to archived/",
                session.session_id, moved,
            )
        return moved

    def _save_session(self, session: Session):
        """Save session metadata to disk."""
        if session.storage_path:
            session_dir = self.storage_dir / session.storage_path
        else:
            session_dir = self.storage_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        session_file = session_dir / "session.json"

        # Convert session to dict and ensure timestamps are strings
        session_dict = asdict(session)
        if isinstance(session_dict['last_active'], datetime):
            session_dict['last_active'] = session_dict['last_active'].isoformat()
        if isinstance(session_dict['created_at'], datetime):
            session_dict['created_at'] = session_dict['created_at'].isoformat()

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_dict, f, indent=2, ensure_ascii=False)

    def _load_session(self, session_id: str) -> Session:
        """Load session metadata from disk."""
        session_file = self.storage_dir / session_id / "session.json"

        if not session_file.exists():
            expired_base = self.storage_dir / "expired"
            if expired_base.exists():
                for date_folder in expired_base.iterdir():
                    if date_folder.is_dir():
                        archived_file = date_folder / session_id / "session.json"
                        if archived_file.exists():
                            session_file = archived_file
                            break

        with open(session_file, encoding='utf-8') as f:
            data = json.load(f)

        return self._session_from_dict(data)

    def _load_sessions(self):
        """Load all sessions from disk into the in-memory cache."""
        if not self.storage_dir.exists():
            return

        for session_dir in self.storage_dir.iterdir():
            if not session_dir.is_dir() or session_dir.name == "expired":
                continue

            session_file = session_dir / "session.json"
            if session_file.exists():
                try:
                    session = self._load_session(session_dir.name)
                    self.chat_to_session[session.whatsapp_chat] = session.session_id
                    logger.debug(f"Loaded session {session.session_id}")
                except Exception as e:
                    logger.error(f"Failed to load session {session_dir.name}: {e}")

    def count_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for
            model: Model name for tokenizer

        Returns:
            Token count
        """
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))

    def add_message_with_tokens(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_role: Role,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
        recipient: Optional[str] = None,
        recipient_name: Optional[str] = None,
        ledger_event_ids: Optional[List[str]] = None,
        message_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Add message and update session token count.

        Feature 070: `timestamp` is a testability seam (see add_message). There
        is NO write-time pruning any more - the rolling-window builder caps the
        live context read-only, and the nightly roll physically archives
        (never deletes) aged messages.

        Args:
            chat_id: WhatsApp chat ID
            role: Structural turn role ("user" or "assistant") - see
                add_message's docstring for what this and user_role actually
                compute.
            content: Message content
            user_role: The real role for a "user" turn - see add_message's
                docstring.
            sender: Message sender's real WhatsApp JID (optional)
            sender_name: Sender's resolved display name (optional)
            recipient: Message recipient's real WhatsApp JID (optional)
            recipient_name: Recipient's resolved display name (optional)
            ledger_event_ids: id(s) of any LedgerEvent(s) captured from this message
                (Feature 033, optional)
            message_id: The id decided at message-arrival time (Feature 033) - see
                add_message's docstring.

        Returns:
            Message UUID
        """
        # Add message normally
        message_id = self.add_message(
            chat_id, role, content, user_role,
            sender=sender, sender_name=sender_name,
            recipient=recipient, recipient_name=recipient_name,
            ledger_event_ids=ledger_event_ids, message_id=message_id,
            timestamp=timestamp
        )

        # Count and add tokens
        tokens = self.count_tokens(content)
        session = self.get_session(chat_id)
        session.total_tokens += tokens
        self._save_session(session)

        return message_id

    def calculate_session_tokens(self, chat_id: str) -> int:
        """
        Calculate total tokens for all messages in session.

        Args:
            chat_id: WhatsApp chat ID

        Returns:
            Total token count
        """
        session = self.get_session(chat_id)
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"

        total = 0
        for message_id in session.message_ids:
            message_file = messages_dir / f"{message_id}.json"
            if message_file.exists():
                with open(message_file, encoding='utf-8') as f:
                    message_data = json.load(f)
                total += self.count_tokens(message_data["content"])

        return total

    def get_session_token_count(self, chat_id: str) -> int:
        """
        Get current token count for session.

        Args:
            chat_id: WhatsApp chat ID

        Returns:
            Current token count
        """
        session = self.get_session(chat_id)
        return session.total_tokens

