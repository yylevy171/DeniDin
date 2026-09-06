"""
Session Manager for conversation history.

Manages chat sessions with role-based token limits and message persistence.
Supports UUID-based architecture with separate file storage for messages.
"""

import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

import tiktoken

from src.models.user import Role
from src.utils.logger import get_logger
from src.utils.time_utils import now_local, local_from_timestamp

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
    # for the latter. Never "blocked": a BLOCKED user's message never
    # reaches persistence (add_message_with_token_limit raises on a 0
    # token_limit before any Message is constructed).
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
    # Feature 069: the Morning MCP tool calls made on this message's turn (an
    # assistant message only), each {"name", "arguments", "result"/"error"} exactly
    # as AIResponse.mcp_calls carried them. Persisted so the post-turn ledger
    # recognition call can see, across its context window, what was actually
    # resolved/created in Morning (a client name in prose is only a candidate; a
    # tool RESULT is the evidence). Empty for every user message and for an
    # assistant turn that called no Morning tool.
    mcp_calls: List[Dict] = field(default_factory=list)


@dataclass
class Session:
    """Chat session with conversation history."""
    session_id: str
    whatsapp_chat: str
    message_ids: List[str]
    message_counter: int = 0
    created_at: str = ""
    last_active: str = ""
    total_tokens: int = 0
    transferred_to_longterm: bool = False
    storage_path: Optional[str] = None


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
        session_timeout_hours: int = 24
    ):
        """
        Initialize SessionManager.

        Args:
            storage_dir: Directory for session storage
            session_timeout_hours: Hours before session expires
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.session_timeout_hours = session_timeout_hours

        # In-memory index: whatsapp_chat -> session_id
        self.chat_to_session: Dict[str, str] = {}

        # Load existing sessions from disk
        self._load_sessions()

        logger.info(f"SessionManager initialized: timeout={session_timeout_hours}h")

    def get_session(self, chat_id: str) -> Session:
        """
        Get or create session for a WhatsApp chat.

        Args:
            chat_id: WhatsApp chat ID (e.g., "1234567890@c.us")

        Returns:
            Session object
        """
        # Check if session exists in index
        if chat_id in self.chat_to_session:
            session_id = self.chat_to_session[chat_id]
            session = self._load_session(session_id)
            return session

        # Create new session
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

        # Save to disk and index
        self._save_session(session)
        self.chat_to_session[chat_id] = session_id

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
        mcp_calls: Optional[List[Dict]] = None,
        source_timestamp: Optional[int] = None
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

        # Create message
        message_id = message_id or str(uuid.uuid4())
        now = now_local().isoformat()
        # Feature 069: Message.timestamp is the time the event actually
        # happened, not when we persisted it. For an inbound turn the caller
        # passes the Green API notification epoch (source_timestamp) - which
        # the WhatsApp-export player injects as the message's ORIGINAL
        # conversation time (player/notification_synth.py) and which
        # WhatsAppMessage.from_notification already surfaces. Falls back to
        # processing time only when genuinely absent (assistant replies,
        # synthetic internal turns). received_at stays processing time.
        event_ts = (
            local_from_timestamp(source_timestamp).isoformat()
            if source_timestamp is not None else now
        )

        # 2026-08-19: compute the real, persisted role + the OpenAI-safe
        # derived role. `role`/`user_role` themselves are never persisted -
        # see this method's docstring for why they still exist as separate
        # parameters. A BLOCKED user_role should structurally never reach
        # here (add_message_with_token_limit raises first on a 0
        # token_limit) - normalized the same as any other value rather than
        # special-cased, since there's no real path that exercises it.
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
            timestamp=event_ts,
            received_at=now,
            was_received=True,
            order_num=session.message_counter,
            image_path=image_path,
            extracted_text=extracted_text,
            ledger_event_ids=list(ledger_event_ids) if ledger_event_ids else [],
            mcp_calls=list(mcp_calls) if mcp_calls else []
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
        session.last_active = now
        self._save_session(session)

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

    def _messages_dir_for(self, session: Session) -> Path:
        base = session.storage_path or session.session_id
        return self.storage_dir / base / "messages"

    def load_message(self, session: Session, message_id: str) -> Optional[Message]:
        """Feature 069: load one persisted Message by id from a session's own
        message directory, or None if no such file exists. Read-only - the
        counterpart writer is append_ledger_event_ids below."""
        message_file = self._messages_dir_for(session) / f"{message_id}.json"
        if not message_file.exists():
            return None
        with open(message_file, encoding="utf-8") as f:
            data = json.load(f)
        known = {f.name for f in Message.__dataclass_fields__.values()}
        return Message(**{k: v for k, v in data.items() if k in known})

    def append_ledger_event_ids(
        self, session: Session, message_id: str, event_ids: List[str]
    ) -> None:
        """Feature 069: append one or more LedgerEvent ids onto a persisted
        message's `ledger_event_ids` list (the reverse link to
        LedgerEvent.message_id), de-duplicated and rewritten to disk in place.
        No-op if the message file is missing or `event_ids` is empty."""
        if not event_ids:
            return
        message_file = self._messages_dir_for(session) / f"{message_id}.json"
        if not message_file.exists():
            logger.warning(
                f"append_ledger_event_ids: message {message_id} not found in "
                f"session {session.session_id} - nothing to link"
            )
            return
        with open(message_file, encoding="utf-8") as f:
            data = json.load(f)
        existing = list(data.get("ledger_event_ids") or [])
        for eid in event_ids:
            if eid not in existing:
                existing.append(eid)
        data["ledger_event_ids"] = existing
        with open(message_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(
            f"Linked ledger events {event_ids} onto message {message_id} "
            f"(session {session.session_id})"
        )

    def clear_session(self, chat_id: str):
        """
        Clear all messages from a session.

        Args:
            chat_id: WhatsApp chat ID
        """
        session = self.get_session(chat_id)

        # Delete message files
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"

        if messages_dir.exists():
            for message_file in messages_dir.glob("*.json"):
                message_file.unlink()

        # Reset session
        session.message_ids = []
        session.total_tokens = 0
        self._save_session(session)

        logger.info(f"Cleared session {session.session_id}")

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

        return Session(**data)

    def _load_sessions(self):
        """Load all sessions from disk into memory index."""
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

    def find_expired_active_sessions(self) -> List[Session]:
        """
        Find active sessions that have expired and need archival.

        Scans the active sessions directory (not expired/) for sessions
        whose last_active timestamp is older than session_timeout_hours.

        Returns:
            List of expired Session objects from active directory
        """
        now = now_local()
        cutoff = now - timedelta(hours=self.session_timeout_hours)
        expired = []

        for session_dir in self.storage_dir.iterdir():
            if not session_dir.is_dir() or session_dir.name == "expired":
                continue

            session_file = session_dir / "session.json"
            if not session_file.exists():
                continue

            try:
                session = self._load_session(session_dir.name)
                last_active = datetime.fromisoformat(session.last_active)

                if last_active < cutoff:
                    expired.append(session)
            except Exception as e:
                logger.error(f"Failed to check session {session_dir.name}: {e}")

        return expired

    def find_untransferred_archived_sessions(self) -> List[Session]:
        """
        Find archived sessions that were not transferred to long-term memory.

        Scans the expired/ folder for sessions with transferred_to_longterm=False.
        This recovers sessions from interrupted cleanup operations.

        Returns:
            List of Session objects in expired/ with transferred_to_longterm=False
        """
        untransferred: List[Session] = []
        expired_base = self.storage_dir / "expired"

        if not expired_base.exists():
            return untransferred

        # Scan all date folders in expired/
        for date_folder in expired_base.iterdir():
            if not date_folder.is_dir():
                continue

            # Scan all session folders in each date folder
            for session_dir in date_folder.iterdir():
                if not session_dir.is_dir():
                    continue

                session_file = session_dir / "session.json"
                if not session_file.exists():
                    continue

                try:
                    with open(session_file, encoding='utf-8') as f:
                        data = json.load(f)

                    # Only include if not yet transferred
                    if not data.get('transferred_to_longterm', False):
                        session = Session(**data)
                        untransferred.append(session)
                        logger.debug(
                            f"Found untransferred archived session {session.session_id} "
                            f"in {date_folder.name}"
                        )
                except Exception as e:
                    logger.error(f"Failed to check archived session {session_dir.name}: {e}")

        return untransferred

    def get_sessions_needing_cleanup(self) -> List[Session]:
        """
        Find all sessions that need cleanup processing.

        Combines:
        1. Active sessions that have expired (need archival + transfer)
        2. Archived sessions not yet transferred (need transfer completion)

        Returns:
            List of Session objects requiring cleanup
        """
        expired_active = self.find_expired_active_sessions()
        untransferred_archived = self.find_untransferred_archived_sessions()

        all_sessions = expired_active + untransferred_archived

        if expired_active:
            logger.info(f"Found {len(expired_active)} expired active sessions")
        if untransferred_archived:
            logger.info(f"Found {len(untransferred_archived)} untransferred archived sessions")

        return all_sessions

    def get_expired_sessions(self) -> List[Session]:
        """
        DEPRECATED: Use get_sessions_needing_cleanup() instead.

        Find all sessions that need cleanup processing.
        Maintained for backward compatibility.

        Returns:
            List of Session objects requiring cleanup
        """
        return self.get_sessions_needing_cleanup()

    def archive_session(self, session: Session) -> bool:
        """
        Move session directory to dated expired folder.

        Args:
            session: Session to archive

        Returns:
            True if successful, False otherwise
        """
        try:
            session_dir = self.storage_dir / session.session_id
            if not session_dir.exists():
                logger.warning(f"Session directory not found: {session.session_id}")
                return False

            # Create dated subfolder
            last_active = datetime.fromisoformat(session.last_active)
            archive_date = last_active.strftime("%Y-%m-%d")
            expired_base = self.storage_dir / "expired"
            archive_dir = expired_base / archive_date
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Move entire session directory
            dest = archive_dir / session.session_id
            session_dir.rename(dest)

            # Update storage path and save to archived location (keep in index for AI transfer)
            session.storage_path = f"expired/{archive_date}/{session.session_id}"
            self._save_session(session)

            logger.info(
                f"Archived session {session.session_id} to expired/{archive_date}/ "
                f"(transferred={session.transferred_to_longterm}, kept in index)"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to archive session {session.session_id}: {e}")
            return False

    def remove_from_index(self, session: Session) -> bool:
        """
        Remove session from in-memory index after AI transfer.

        Args:
            session: Session to remove

        Returns:
            True if removed, False if not found
        """
        if session.whatsapp_chat in self.chat_to_session:
            del self.chat_to_session[session.whatsapp_chat]
            logger.info(f"Removed session {session.session_id} from index")
            return True
        return False

    def is_session_expired(self, session: Session) -> bool:
        """
        Check if a session has expired based on last_active timestamp.

        Args:
            session: Session object to check

        Returns:
            True if session is expired, False otherwise
        """
        now = now_local()
        cutoff = now - timedelta(hours=self.session_timeout_hours)
        last_active = datetime.fromisoformat(session.last_active)

        return last_active < cutoff

    def find_orphaned_sessions(self) -> List[Session]:
        """
        Find all sessions that exist on disk but are not in memory index.
        Used for startup recovery.

        Returns:
            List of Session objects found on disk
        """
        orphaned_sessions = []

        for session_dir in self.storage_dir.iterdir():
            if not session_dir.is_dir() or session_dir.name == "expired":
                continue

            session_file = session_dir / "session.json"
            if not session_file.exists():
                continue

            try:
                session = self._load_session(session_dir.name)
                orphaned_sessions.append(session)
                logger.debug(f"Found orphaned session: {session.session_id}")
            except Exception as e:
                logger.error(f"Failed to load orphaned session {session_dir.name}: {e}")

        return orphaned_sessions

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
        mcp_calls: Optional[List[Dict]] = None,
        source_timestamp: Optional[int] = None
    ) -> str:
        """
        Add message and update session token count.

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
            mcp_calls=mcp_calls, source_timestamp=source_timestamp
        )

        # Count and add tokens
        tokens = self.count_tokens(content)
        session = self.get_session(chat_id)
        session.total_tokens += tokens
        self._save_session(session)

        return message_id

    def add_message_with_token_limit(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_role: Role,
        token_limit: int,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
        recipient: Optional[str] = None,
        recipient_name: Optional[str] = None,
        ledger_event_ids: Optional[List[str]] = None,
        message_id: Optional[str] = None,
        mcp_calls: Optional[List[Dict]] = None,
        source_timestamp: Optional[int] = None
    ) -> str:
        """
        Add message with token limit enforcement and auto-pruning.

        Args:
            chat_id: WhatsApp chat ID
            role: Structural turn role ("user" or "assistant") - see
                add_message's docstring for what this and user_role actually
                compute.
            content: Message content
            user_role: The real role for a "user" turn - see add_message's
                docstring.
            token_limit: Maximum tokens allowed for this role
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

        Raises:
            ValueError: If token limit is exceeded and cannot prune
        """
        # Count tokens for new message
        new_tokens = self.count_tokens(content)

        # Check if blocked user (0 token limit)
        if token_limit == 0:
            raise ValueError("Token limit exceeded: BLOCKED users cannot add messages")

        # Get current session
        session = self.get_session(chat_id)
        current_tokens = session.total_tokens

        # Check if adding this message would exceed limit
        if current_tokens + new_tokens > token_limit:
            # Prune oldest messages until we're under limit
            self._prune_until_under_limit(chat_id, token_limit, new_tokens)

        # Add message with token tracking
        return self.add_message_with_tokens(
            chat_id, role, content, user_role,
            sender=sender, sender_name=sender_name,
            recipient=recipient, recipient_name=recipient_name,
            ledger_event_ids=ledger_event_ids, message_id=message_id,
            mcp_calls=mcp_calls, source_timestamp=source_timestamp
        )

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

    def prune_to_limit(self, chat_id: str, keep_count: int):
        """
        Prune session to keep only specified number of most recent messages.

        Args:
            chat_id: WhatsApp chat ID
            keep_count: Number of messages to keep
        """
        session = self.get_session(chat_id)

        if len(session.message_ids) <= keep_count:
            return

        # Calculate how many to remove
        remove_count = len(session.message_ids) - keep_count

        # Remove oldest messages
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"

        for _ in range(remove_count):
            message_id = session.message_ids.pop(0)
            message_file = messages_dir / f"{message_id}.json"
            if message_file.exists():
                message_file.unlink()

        # Recalculate tokens
        session.total_tokens = self.calculate_session_tokens(chat_id)
        self._save_session(session)

    def _prune_until_under_limit(self, chat_id: str, token_limit: int, new_message_tokens: int):
        """
        Remove oldest messages until session is under limit with room for new message.

        Args:
            chat_id: WhatsApp chat ID
            token_limit: Maximum allowed tokens
            new_message_tokens: Tokens in message to be added
        """
        session = self.get_session(chat_id)
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"

        while session.total_tokens + new_message_tokens > token_limit and session.message_ids:
            # Remove oldest message
            message_id = session.message_ids.pop(0)
            message_file = messages_dir / f"{message_id}.json"

            if message_file.exists():
                with open(message_file, encoding='utf-8') as f:
                    message_data = json.load(f)
                # Subtract tokens from total
                session.total_tokens -= self.count_tokens(message_data["content"])
                message_file.unlink()

        self._save_session(session)
