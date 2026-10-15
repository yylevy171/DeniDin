#!/usr/bin/env python3
"""
DeniDin WhatsApp AI Application - Main Entry Point
Integrates Green API for WhatsApp messaging with OpenAI ChatGPT.
Phase 6: US4 - Configuration & Deployment
"""
import logging
import sys
import signal
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple
from whatsapp_chatbot_python import Notification
from openai import OpenAI
from src.models.config import AppConfiguration
from src.utils.logger import get_logger, reconfigure_file_rotation
from src.sources.green_api_source import GreenAPIMessageSource
from src.utils.green_api_bot import (
    start_typing_keepalive,
    stop_typing_keepalive,
)
from src.utils.wire_log import audit_wire, debug_wire
from src.utils.time_utils import local_from_timestamp, sane_source_epoch
from src.constants.error_messages import (
    APP_NOT_READY_RETRY_LATER,
    ERROR_PROCESSING_MESSAGE_TRY_AGAIN,
    FAILED_TO_PROCESS_FILE_DEFAULT,
    FILE_TOO_LARGE_REFUSAL,
    CONTACT_CARD_ONE_AT_A_TIME,
    UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES,
)
from src.handlers.fee_agreement_tools import FeeAgreementToolHandler
from src.handlers.morning_mcp_locator import MorningMcpLocator
from src.managers.doc_template_engine import DocTemplateEngine
from src.managers.agreements_manager import AgreementsManager
from src.services.agreements_api import start_agreements_api
from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.memory_manager import MemoryManager
from src.managers.reminder_manager import ReminderManager
from src.managers.roll_marker_store import RollMarkerStore
from src.managers.session_manager import SessionManager
from src.managers.telemetry_manager import TelemetryManager
from src.managers.user_manager import UserManager
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.handlers.media_handler import MediaHandler
from src.managers.group_membership_resolver import GroupMembershipResolver
from src.managers.media_file_manager import FileTooLargeError
from src.services.reminder_delivery_service import (
    run_startup_reminder_sweep, start_reminder_scheduler,
)
from src.services.capability_reset_service import start_capability_reset_scheduler
from src.intake.denidin_dispatcher import DeniDinDispatcher
from src.intake.intake_coordinator import IntakeCoordinator
from src.services.queue_monitor_service import QueueMonitor, start_queue_monitor_scheduler
from src.services.thread_supervisor import ThreadSupervisor, start_thread_supervisor_scheduler
from src.utils.bounded_queue import QueueSettings
from src.services.accounting_reconciliation_service import (
    run_startup_accounting_reconciliation_sweep, start_accounting_reconciliation_scheduler,
)
from src.services.health_server import (
    build_health_check_fns, build_health_info_fns, resolve_log_path, start_health_server,
    start_heartbeat_thread,
)
from src.services.daily_summary_roll_service import (
    run_startup_daily_roll_sweep, start_daily_roll_scheduler,
)

# Configuration
CONFIG_PATH = 'config/config.json'

# Load and validate configuration
try:
    startup_config = AppConfiguration.from_file(CONFIG_PATH)
    startup_config.validate()
except ValueError as e:
    # Configuration validation failed - exit with clear error message
    print(f"ERROR: Invalid configuration in {CONFIG_PATH}", file=sys.stderr)
    print(f"Validation error: {e}", file=sys.stderr)
    print("Please fix the configuration file and restart the application.", file=sys.stderr)
    sys.exit(2)  # Exit code 2 = configuration error (CONSTITUTION XVI)
except FileNotFoundError:
    print(f"ERROR: Configuration file not found: {CONFIG_PATH}", file=sys.stderr)
    print("Please create config/config.json from config/config.example.json", file=sys.stderr)
    sys.exit(2)  # Exit code 2 = configuration error (CONSTITUTION XVI)
except Exception as e:
    print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
    sys.exit(2)  # Exit code 2 = configuration error (CONSTITUTION XVI)

# Setup logging
# Every other module's logger is created via get_logger(__name__) with no
# explicit log_level, so it defaults to NOTSET and inherits its effective
# level from the root logger. The root logger must therefore have a real
# level set here, or those modules would silently fall back to Python's
# built-in root default (WARNING) instead of honoring config.log_level.
logging.getLogger().setLevel(getattr(logging, startup_config.log_level))
# Feature 070 (US5): every module created its logger at import time (above) with
# logger.py's built-in rotation defaults, before config was loaded. Now that we
# have config.logging, rebuild the root file handler with the real values (a
# no-op when they match the defaults, the common case).
reconfigure_file_rotation(
    rotation_when=startup_config.logging.get('rotation_when', 'midnight'),
    backup_count=startup_config.logging.get('backup_count', 0),
    log_level=startup_config.log_level,
)
logger = get_logger(__name__, log_level=startup_config.log_level)


# A WhatsApp-export player replay stores DeniDin's reply this many seconds after
# the replayed message it answers, so replayed history keeps its original order.
REPLAY_REPLY_OFFSET_SECONDS = 10


def mask_api_key(key: str) -> str:
    """
    Mask API key for secure logging.
    Shows first 4 and last 4 characters (CONSTITUTION IX).

    Args:
        key: API key to mask

    Returns:
        Masked API key string (e.g., "sk-p...z123")
    """
    if len(key) <= 8:
        return "***"  # Too short to safely show any part
    return f"{key[:4]}...{key[-4:]}"


# Global DeniDin instance for WhatsApp message handler
# Will be populated in __main__ block after initialize_app()
denidin_app = None


def _fetch_own_whatsapp_number(green_api: Optional[Any]) -> str:
    """bugfix-024: fetch DeniDin's own WhatsApp phone number ONCE, via a real Green
    API getWaSettings call - confirmed live (2026-08-05) to return {"phone": "<bare
    digits>", ...}, e.g. "972559723730". Needed because WhatsApp's native @-mention
    picker inserts the mentioned contact's raw phone number into message text, never
    a display name (see bugfix-024's spec for the incident this fixes) - the app
    needs its own number to deterministically recognize a self-mention.

    Args:
        green_api: the real Green API client (e.g. a live GreenAPIMessageSource's
            `.connect().api`), constructor-injected (Feature 043 - no module-level
            `bot` global exists anymore, see research.md R3). `None` when the caller
            has no live Green API connection at all (e.g. a replay/player run) -
            degrades to "" exactly like a failed/unreachable real call, via the same
            broad except below.

    Never raises - a failed/unreachable call, or green_api=None, degrades to ""
    (self-mention-by-number detection unavailable this run, everything else
    unaffected), matching this codebase's fail-open convention for non-critical
    startup data (CONSTITUTION §VI). Called once per `initialize_app()` call, never
    per message.
    """
    if green_api is None:
        logger.info(
            "No live Green API client supplied - self-mention-by-number "
            "detection unavailable this run"
        )
        return ""
    try:
        response = green_api.account.getWaSettings()
        if response.code == 200 and isinstance(response.data, dict):
            phone = response.data.get('phone', '')
            if phone:
                logger.info(f"Resolved own WhatsApp number for self-mention detection: {phone}")
                return phone
        logger.warning(
            f"getWaSettings did not return a usable 'phone' field (code={response.code}) - "
            "self-mention-by-number detection unavailable this run"
        )
    except Exception as e:
        logger.warning(
            f"Failed to fetch own WhatsApp number via getWaSettings: {e} - "
            "self-mention-by-number detection unavailable this run"
        )
    return ""


class DeniDin:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """
    DeniDin application instance (REQ-063-08). Owns DeniDin's managers (users,
    sessions, roll markers, long-term memory, ledger events, reminders, the Morning
    MCP locator, the document templates, telemetry), its WhatsApp side
    (`whatsapp_handler`), and exactly one AI implementation, `ai_manager` (the
    Backbone). Every one of
    them takes this object as its only constructor argument and reaches anything else
    it needs through it.

    DeniDin coordinates between its objects by value: it stores every WhatsApp
    message the moment it crosses the boundary (store_inbound/store_outbound - the
    handler sends, the session stores, neither knows the other), and gives the AI
    layer's tools the sends they need (send_progress_update, send_document,
    send_reaction).

    Constructed light - config, the OpenAI client and the Green API client only; every
    other object is None until `initialize_app` builds it. Tests and external apps
    build a DeniDin holding just what they use.
    """
    def __init__(self, config: AppConfiguration, *, ai_client: Optional[OpenAI] = None,
                 green_api: Optional[Any] = None):
        self.config = config
        # The OpenAI client - used by the AI implementation, long-term memory, ledger
        # recognition and the daily-summary roll.
        self.ai_client = ai_client
        # The Green API client (`.groups`, `.account`) - None without a live Green API
        # connection (tests, the player).
        self.green_api = green_api
        # The live bot - set by __main__ once it exists; None in tests and the player.
        self.green_api_bot: Optional[Any] = None
        # Memory system and RBAC are always on (2026-07-14 decision).
        self.memory_enabled = True
        self.rbac_enabled = True

        # DeniDin's objects, built by initialize_app (None = this DeniDin has none).
        self.telemetry_manager: Any = None
        self.user_manager: Any = None
        self.session_manager: Any = None
        self.roll_marker_store: Any = None
        self.ledger_event_manager: Any = None
        # Feature 089: the Agreements DB (the living state of fee agreements).
        self.agreements_manager: Any = None
        self.memory_manager: Any = None  # also None when long-term memory is disabled
        self.morning_mcp_locator: Any = None
        self.reminder_manager: Any = None
        self.doc_template_engine: Any = None
        self.fee_agreement_tools: Any = None
        self.group_membership_resolver: Any = None
        self.whatsapp_handler: Any = None
        self.media_handler: Any = None
        self.ai_manager: Any = None
        # The most recent AIResponse of any turn, for observability / E2E test
        # verification (e.g. a turn's mcp_calls) - set after every turn, both paths.
        self.last_response = None
        # Vestigial (Feature 070 removed the session-cleanup thread) - stopped if set.
        self.cleanup_thread: Any = None
        # Background schedulers - None until __main__ starts them (NEVER initialize_app:
        # tests call initialize_app directly, and a real background poller there would
        # reach live external services unattended - see contracts/
        # accounting-reconciliation-service.md and contracts/daily-summary-roll-service.md).
        self.reminder_scheduler: Any = None  # Feature 054
        self.accounting_reconciliation_scheduler: Any = None  # Feature 025; None when freq == 0
        self.capability_reset_scheduler: Any = None  # Feature 063
        self.daily_roll_scheduler: Any = None  # Feature 070
        # Feature 080: the per-turn typing keep-alive renewal jobs' scheduler (research.md
        # R1) - started by initialize_app.
        self.typing_keepalive_scheduler: Any = None
        # Feature 067: what the poller received and the dispatcher has not handled yet
        # (IntakeCoordinator), the dispatcher thread, and the queue monitor / thread
        # supervisor. All None until __main__ builds them (tests, the player: none).
        self.intake: Any = None
        self.dispatcher: Any = None
        self.queue_monitor: Any = None
        self.thread_supervisor: Any = None
        self.queue_monitor_scheduler: Any = None
        self.thread_supervisor_scheduler: Any = None
        self._logger = get_logger(__name__)

    def get_collection(self):
        """
        Get ChromaDB collection for testing assertions.

        Returns:
            ChromaDB Collection object or None if memory disabled
        """
        if not self.memory_enabled or self.memory_manager is None:
            return None

        return self.memory_manager.client.get_collection(
            name=self.config.memory['longterm']['collection_name']
        )

    def get_session(self, chat_id: str):
        """
        Get active session for a chat ID.

        Args:
            chat_id: WhatsApp chat ID

        Returns:
            Session object or None
        """
        if not self.memory_enabled or self.session_manager is None:
            return None

        return self.session_manager.get_session(chat_id)

    # ------------------------------------------------------------------
    # Storing messages (2026-09-30): every WhatsApp message is stored the moment it
    # crosses the boundary - a message from the user as soon as it's received, a
    # message to the user right after it's successfully sent. Facts learned later
    # (a media file's saved path, its extracted text, ledger event ids) are filled
    # into the stored message via update_message(). Every one is best-effort: a
    # storage failure is logged and never affects the conversation.
    # ------------------------------------------------------------------

    @property
    def _own_jid(self) -> Optional[str]:
        return self.whatsapp_handler.own_jid if self.whatsapp_handler is not None else None

    def _stored_role(self, phone: Optional[str]) -> Any:
        """The stored role: the user's role when known, else "godfather" (the default role)."""
        if self.rbac_enabled and self.user_manager is not None and phone:
            return self.user_manager.get_user(phone).role
        return "godfather"

    def store_inbound(self, message: Any, *, content: Optional[str] = None,
                      internal: bool = False, raise_on_error: bool = False) -> Optional[str]:
        """Stores a message received from the user (a WhatsAppMessage), under its own
        `message.message_id`. `content` defaults to message.text_content. A group
        message is addressed to the group itself.

        `internal=True` marks content DeniDin generated on the user's behalf (the
        Feature 069 ledger-stash turn) - stored without the WhatsApp idMessage, since
        it isn't the user's WhatsApp message itself.

        A Green API redelivery of a message already stored (same idMessage) is not
        stored twice. Returns the stored message_id, or None if nothing was stored.

        ``raise_on_error`` (Feature 067): the poller must not acknowledge a message it
        failed to store, so it asks for the failure instead of the usual log-and-None."""
        if self.session_manager is None or not message.chat_id:
            return None
        try:
            whatsapp_id = None if internal else getattr(message, "whatsapp_id_message", None)
            if whatsapp_id and self.session_manager.has_whatsapp_id_message(message.chat_id, whatsapp_id):
                logger.info(f"Inbound message {whatsapp_id} already stored for {message.chat_id} - not storing again")
                return None
            epoch = sane_source_epoch(message.timestamp)
            return str(self.session_manager.add_message_with_tokens(
                chat_id=message.chat_id, role="user",
                content=message.text_content if content is None else content,
                user_role=self._stored_role(message.sender_id),
                sender=message.sender_id, sender_name=message.sender_display_name,
                recipient=message.chat_id if message.is_group else self._own_jid,
                recipient_name=(message.chat_name or message.chat_id) if message.is_group else "DeniDin",
                message_id=message.message_id,
                timestamp=None if epoch is None else local_from_timestamp(epoch),
                whatsapp_id_message=whatsapp_id,
            ))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to store inbound message for {getattr(message, 'chat_id', None)}: {e}",
                         exc_info=True)
            if raise_on_error:
                raise
            return None

    def store_outbound(self, reply_to: Any, content: str, *,
                       mcp_calls: Optional[List[Dict]] = None) -> Optional[str]:
        """Stores a message DeniDin just sent (or an internal note it never sends - the
        Backbone's [[INTERNAL_PLANNING_NOTE]]) in the conversation of `reply_to`, the
        inbound WhatsAppMessage it answers - used only for addressing and the stored
        role. Call right AFTER a successful send, never for a failed one: the stored
        log is what the user actually saw. Timestamp is the send time (now); for a
        player replay, the replayed message's own time + REPLAY_REPLY_OFFSET_SECONDS."""
        if self.session_manager is None or not (reply_to.chat_id and content):
            return None
        try:
            timestamp = None
            if getattr(reply_to, "is_replay", False):
                epoch = sane_source_epoch(reply_to.timestamp)
                if epoch is not None:
                    timestamp = local_from_timestamp(epoch + REPLAY_REPLY_OFFSET_SECONDS)
            return str(self.session_manager.add_message_with_tokens(
                chat_id=reply_to.chat_id, role="assistant", content=content,
                user_role=self._stored_role(reply_to.sender_id),
                sender=self._own_jid, sender_name="DeniDin",
                recipient=reply_to.chat_id if reply_to.is_group else reply_to.sender_id,
                recipient_name=(reply_to.chat_name or reply_to.chat_id) if reply_to.is_group
                else reply_to.sender_display_name,
                mcp_calls=mcp_calls, timestamp=timestamp,
            ))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to store outbound message for {getattr(reply_to, 'chat_id', None)}: {e}",
                         exc_info=True)
            return None

    def store_outbound_to_chat(self, chat_id: str, content: str, *,
                               mcp_calls: Optional[List[Dict]] = None) -> Optional[str]:
        """Stores a message just sent to `chat_id` when there's no inbound message to
        address it from (e.g. a generated document sent by a tool) - addressed to the
        chat itself."""
        if self.session_manager is None or not (chat_id and content):
            return None
        try:
            return str(self.session_manager.add_message_with_tokens(
                chat_id=chat_id, role="assistant", content=content,
                user_role=self._stored_role(chat_id if chat_id.endswith("@c.us") else None),
                sender=self._own_jid, sender_name="DeniDin",
                recipient=chat_id, recipient_name=chat_id, mcp_calls=mcp_calls,
            ))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to store outbound message for {chat_id}: {e}", exc_info=True)
            return None

    def update_message(self, chat_id: Optional[str], message_id: Optional[str], **fields: Any) -> bool:
        """Fills facts learned after a message was stored (image_path, extracted_text,
        ledger_event_ids, mcp_calls) into it. False - never raises - on any failure."""
        if self.session_manager is None or not (chat_id and message_id and fields):
            return False
        try:
            return bool(self.session_manager.update_message(chat_id, message_id, **fields))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to update message {message_id} in {chat_id}: {e}", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Receiving and sending - WhatsApp sends, the session stores
    # ------------------------------------------------------------------

    def receive(self, notification: Notification, *, content: Optional[str] = None,
                internal: bool = False) -> Any:
        """Parses `notification` (WhatsAppHandler) and stores it the moment it's
        received - before any processing, so it's in the session whatever happens to
        the rest of the turn. Returns the WhatsAppMessage, whose message_id is the
        stored message's id."""
        if self.intake is not None and not internal:
            # Feature 067: the poller already parsed and stored this message (same
            # message_id) before acknowledging it - hand the handler that one.
            prestored = self.intake.prestored_for(notification)
            if prestored is not None:
                return prestored
        message = self.whatsapp_handler.process_notification(notification)
        self.store_inbound(message, content=content, internal=internal)
        return message

    # Feature 067: message types the poller stores before acknowledging them, and the
    # content each is stored with - exactly what its handler stores (a handler's later
    # receive() then finds it already stored). Types not listed (button taps, edits,
    # deletes, unsupported types) are stored by their own handler as before.
    @staticmethod
    def _prestore_content(type_message: str, notification: Notification) -> Tuple[bool, Optional[str]]:
        if type_message in ("textMessage", "extendedTextMessage", "contactMessage"):
            return True, None
        if type_message in ("imageMessage", "documentMessage", "videoMessage"):
            file_data = notification.event.get('messageData', {}).get('fileMessageData', {})
            return True, file_data.get('caption', '') or f"[{file_data.get('fileName', 'file')} sent]"
        if type_message == "contactsArrayMessage":
            return True, "[contacts sent]"
        return False, None

    def prestore(self, notification: Notification) -> Any:
        """Called by the poller, before it acknowledges the webhook: parses and stores the
        message when its type is stored at receipt, and returns the WhatsAppMessage (None
        for other types). A storing failure raises - the poller then does not acknowledge
        and the webhook is redelivered (REQ-RMH-021)."""
        type_message = notification.event.get('messageData', {}).get('typeMessage', '')
        stored_type, content = self._prestore_content(type_message, notification)
        if not stored_type or self.whatsapp_handler is None:
            return None
        message = self.whatsapp_handler.process_notification(notification)
        self.store_inbound(message, content=content, raise_on_error=True)
        return message

    def receive_pending(self, chat_id: str) -> Any:
        """Feature 067, at a model hand-back: the messages that arrived in `chat_id` while
        the model was working (already stored) - a ``Drained`` (text to attach, media to
        mention) or None when there is no intake (tests, the player)."""
        if self.intake is None:
            return None
        return self.intake.drain_attachable(chat_id)

    def start_typing(self, chat_id: str) -> Optional[str]:
        """Switches WhatsApp's typing indicator on for `chat_id` - the AI layer calls it just
        before an OpenAI call goes out (the indicator is on exactly while a call is in
        flight). Returns the keep-alive job id for `stop_typing`, or None without a live bot."""
        if self.green_api_bot is None or self.typing_keepalive_scheduler is None:
            return None
        return start_typing_keepalive(
            self.typing_keepalive_scheduler, self.green_api_bot, chat_id, False, uuid.uuid4().hex)

    def stop_typing(self, job_id: Optional[str]) -> None:
        """Switches the typing indicator off (the call it covered has returned)."""
        if self.typing_keepalive_scheduler is not None:
            stop_typing_keepalive(self.typing_keepalive_scheduler, job_id)

    def send_text(self, notification: Notification, text: str, *, wire_context: str = "text") -> Any:
        """Sends a canned/notice reply in `notification`'s chat, and stores it once sent
        (an exception propagates to the caller unchanged, and nothing is stored)."""
        sent = self.whatsapp_handler.send_text(notification, text, wire_context=wire_context)
        self.store_outbound(self.whatsapp_handler.process_notification(notification), sent.text)
        return sent

    def send_to_user(self, chat_id: Optional[str], text: str, *,
                     mcp_calls: Optional[List[Dict]] = None) -> bool:
        """Sends `text` to `chat_id` right away (the model's send_to_user) and stores it
        once sent. False - never raises - when it was not sent."""
        if not chat_id or self.whatsapp_handler is None:
            logger.warning(f"No chat or no WhatsApp handler - message not sent (chat={chat_id!r})")
            return False
        sent = self.whatsapp_handler.send_to_chat(chat_id, text)
        if sent is None:
            return False
        self.store_outbound_to_chat(chat_id, sent.text, mcp_calls=mcp_calls)
        return True

    def send_approval_buttons(self, chat_id: Optional[str], text: str, *,
                              mcp_calls: Optional[List[Dict]] = None) -> bool:
        """Sends `text` to `chat_id` right away as the "כן"/"לא" approval buttons (the model's
        approval_with_yes_no_buttons), stores it, and remembers the sent message's id on the
        chat so a later tap can be matched against it (the stale-tap guard). False - never
        raises - when nothing was sent; when the buttons could not be sent, the failure
        notice goes out instead and the chat has no outstanding approval."""
        if not chat_id or self.whatsapp_handler is None:
            logger.warning(f"No chat or no WhatsApp handler - approval not sent (chat={chat_id!r})")
            return False
        sent = self.whatsapp_handler.send_buttons_to_chat(chat_id, text)
        if sent is None:
            return False
        self.store_outbound_to_chat(chat_id, sent.text, mcp_calls=None if sent.is_notice else mcp_calls)
        if sent.as_buttons and sent.whatsapp_id_message and self.session_manager is not None:
            self.session_manager.set_approval_message_id(chat_id, sent.whatsapp_id_message)
        return not sent.is_notice

    def send_document(self, chat_id: str, generated: Any, caption: str) -> bool:
        """Feature 083: sends a generated, verified document to `chat_id` and stores it
        once sent (its caption, or a "[מסמך: <name>]" note). False - never raises - on
        any failure."""
        if self.whatsapp_handler is None:
            return False
        if not self.whatsapp_handler.send_document_response(generated, chat_id=chat_id, caption=caption):
            return False
        self.store_outbound_to_chat(chat_id, caption or f"[מסמך: {generated.temp_path.name}]")
        return True

    def send_reaction(self, chat_id: str, id_message: str, emoji: str) -> bool:
        """Feature 084: sets (or, with emoji "", clears) a reaction on a message - not a
        message, so nothing is stored. False - never raises - on any failure."""
        if self.whatsapp_handler is None:
            return False
        return bool(self.whatsapp_handler.send_reaction(chat_id, id_message, emoji))

    def shutdown(self):
        """
        Gracefully shutdown the app context.
        Stops cleanup thread if running, and releases the ChromaDB client's
        reference to its underlying System (refcounted - only actually stops
        the System, and only then, when this was the last live client for its
        storage path; safe alongside other still-open clients on the same
        path). Not releasing this left ChromaDB's per-process System cache
        (chromadb.api.client.SharedSystemClient) holding a stale, now-invalid
        connection whenever something deleted and recreated the storage
        directory on disk without going through this method first - a real,
        billed-test failure (2026-08-03, "attempt to write a readonly
        database") traced to exactly that gap.
        """
        for sched_name in ("queue_monitor_scheduler", "thread_supervisor_scheduler"):
            sched = getattr(self, sched_name)
            if sched is not None:
                sched.shutdown(wait=False)
        if self.dispatcher is not None:
            self._logger.info("Stopping dispatcher thread...")
            self.dispatcher.stop()
        if self.cleanup_thread:
            self._logger.info("Stopping session cleanup thread...")
            self.cleanup_thread.stop()
            self._logger.info("Cleanup thread stopped")
        if self.reminder_scheduler is not None:
            self._logger.info("Stopping reminder delivery scheduler...")
            self.reminder_scheduler.shutdown(wait=False)
            self._logger.info("Reminder delivery scheduler stopped")
        if self.accounting_reconciliation_scheduler is not None:
            self._logger.info("Stopping accounting reconciliation scheduler...")
            self.accounting_reconciliation_scheduler.shutdown(wait=False)
            self._logger.info("Accounting reconciliation scheduler stopped")
        if self.capability_reset_scheduler is not None:
            self._logger.info("Stopping idle capability-reset scheduler...")
            self.capability_reset_scheduler.shutdown(wait=False)
        if self.daily_roll_scheduler is not None:
            self._logger.info("Stopping daily-summary roll scheduler...")
            self.daily_roll_scheduler.shutdown(wait=False)
            self._logger.info("Daily-summary roll scheduler stopped")
        if self.typing_keepalive_scheduler is not None:
            self._logger.info("Stopping typing keep-alive scheduler...")
            self.typing_keepalive_scheduler.shutdown(wait=False)
            self._logger.info("Typing keep-alive scheduler stopped")
        if self.session_manager is not None and hasattr(self.session_manager, "close"):
            self.session_manager.close()
        if self.memory_manager is not None:
            self._logger.info("Closing ChromaDB client...")
            self.memory_manager.client.close()
            self._logger.info("ChromaDB client closed")

def _handle_not_initialized_error(notification: Notification, message_type: str) -> None:
    """
    Handle error response when denidin_app is not initialized.
    Consolidates error handling for all message type routers.

    Args:
        notification: Green API notification to respond to
        message_type: Type of message being processed (for logging)
    """
    logger.error(f"CRITICAL: denidin_app not initialized - cannot process {message_type} messages")
    try:
        notification.answer(APP_NOT_READY_RETRY_LATER)
        _wire_payload = {"chat_id": notification.event.get("senderData", {}).get("chatId", ""),
                         "message": APP_NOT_READY_RETRY_LATER}
        audit_wire("whatsapp", "out", "text", _wire_payload)
        debug_wire("whatsapp", "out", "text", _wire_payload)
    except Exception:
        pass


def start_capability_reset_if_enabled(denidin: "DeniDin"):
    """Feature 063: starts the idle capability-reset scheduler, or returns None.
    Only started when `capabilities_reset_minutes` > 0 (0 = inactive, the default)."""
    return start_capability_reset_scheduler(
        denidin, getattr(denidin.config, "capabilities_reset_minutes", 0)
    )


def build_denidin_objects(denidin: DeniDin) -> None:
    """Builds every object DeniDin owns except its AI implementation (initialize_app
    builds that) onto `denidin`, each constructed with DeniDin
    itself and reading its own settings off DeniDin's config."""
    config = denidin.config
    # Feature 080: the one RequestTelemetry store, shared with the AI implementation's
    # instrumented model calls.
    denidin.telemetry_manager = TelemetryManager(denidin)

    denidin.user_manager = UserManager(denidin)
    logger.info(f"UserManager initialized with godfather: {denidin.user_manager.godfather_phone}, "
                f"admins: {len(denidin.user_manager.admin_phones)}, "
                f"blocked: {len(denidin.user_manager.blocked_phones)}")
    # Feature 070: sessions never expire; there is no cleanup thread.
    denidin.session_manager = SessionManager(denidin)
    # Feature 070: idempotency ledger for the nightly daily-summary roll.
    denidin.roll_marker_store = RollMarkerStore(denidin)
    # Feature 033: own permanent storage under {data_root}/events/ (REQ-STORE-001).
    denidin.ledger_event_manager = LedgerEventManager(denidin)
    # Feature 089: {data_root}/agreements/agreements.db; every agreement write goes here first
    # and produces the ledger events.
    denidin.agreements_manager = AgreementsManager(denidin)
    if ((config.memory or {}).get('longterm', {}) or {}).get('enabled', True):
        denidin.memory_manager = MemoryManager(denidin)
    else:
        logger.info("Long-term memory disabled in config")
    # Morning MCP integration (Feature 018): the current tunnel URL, via the shared
    # status file the morning-mcp-app publishes. No cross-app import.
    denidin.morning_mcp_locator = MorningMcpLocator(denidin)
    # Reminders (Feature 054).
    denidin.reminder_manager = ReminderManager(denidin)
    # Fee Agreement Document Generation (Feature 083).
    denidin.doc_template_engine = DocTemplateEngine(denidin)
    denidin.fee_agreement_tools = FeeAgreementToolHandler(denidin)

    # The WhatsApp side (its own number is set by initialize_app).
    denidin.whatsapp_handler = WhatsAppHandler(denidin)
    # Feature 039: most-permissive-role RBAC resolution for group turns, through the
    # Green API groups client (degrades to sender-only RBAC without one).
    denidin.group_membership_resolver = GroupMembershipResolver(denidin)
    # The media pipeline (its MediaFileManager downloads and archives).
    denidin.media_handler = MediaHandler(denidin)


def initialize_app(config_dict: dict, green_api: Optional[Any] = None) -> DeniDin:
    """
    Initialize DeniDin app with provided configuration.
    Used by integration tests (and, Feature 043, the WhatsApp export player) to
    create an app instance programmatically.

    Args:
        config_dict: Configuration dictionary (from JSON)
        green_api: the real Green API client (e.g. a live GreenAPIMessageSource's
            `.connect().api`), constructor-injected (Feature 043 - initialize_app
            no longer reaches for a module-level `bot` global, see research.md R3).
            Used only for `_fetch_own_whatsapp_number` and `GroupMembershipResolver`
            - both already degrade gracefully (broad `except Exception`/a `None`
            client caught at call time, never at construction) when this is `None`,
            which is the expected/normal case for a caller with no live Green API
            connection at all (e.g. the player - see spec.md's "player" framing).

    Returns:
        DeniDin instance with get_collection(), shutdown() APIs
    """
    # Create AppConfiguration from dict (using from_dict for proper filtering)
    # Note: We need to write config to temp file and load it properly
    # OR filter unknown keys here similar to from_file()
    from dataclasses import fields
    valid_fields = {f.name for f in fields(AppConfiguration)}
    filtered_config = {k: v for k, v in config_dict.items() if k in valid_fields}

    config = AppConfiguration(**filtered_config)
    config.validate()

    # Initialize OpenAI client. max_retries=config.max_retries (2026-08-19 fix)
    # is the ONLY retry mechanism for OpenAI calls now - the SDK's own
    # retry/backoff/Retry-After-honoring implementation, single source of
    # truth, replacing the ad-hoc per-method tenacity decorators that used
    # to double up with the SDK's own previously-unconfigured default retry
    # behavior (see AppConfiguration.max_retries' own docstring for the
    # incident this closed). PendingApproval resolution
    # (_call_openai_approval_api) still explicitly overrides this to 0 via
    # .with_options(max_retries=0) for its own, different reason (avoiding
    # double-execution of an approved side-effecting action on retry,
    # bugfix-022) - unaffected by this client-level default.
    ai_client = OpenAI(
        api_key=config.ai_api_key,
        timeout=30.0,
        max_retries=config.max_retries
    )

    # REQ-063-08: DeniDin first, then every object it owns - each takes DeniDin as its
    # only constructor argument and reads its own settings off DeniDin's config.
    denidin = DeniDin(config, ai_client=ai_client, green_api=green_api)
    build_denidin_objects(denidin)
    # Feature 080: the typing keep-alive renewal jobs' scheduler (research.md R1).
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
    denidin.typing_keepalive_scheduler = BackgroundScheduler()
    denidin.typing_keepalive_scheduler.start()
    # bugfix-024: DeniDin's own WhatsApp number, resolved ONCE at startup (real Green
    # API call, never per-message) - see _fetch_own_whatsapp_number.
    denidin.whatsapp_handler.own_whatsapp_number = _fetch_own_whatsapp_number(green_api)

    # Feature 063 / REQ-063-08: one-time selection, at startup, of the ONE AI
    # implementation that handles this process's turns - the legacy AIHandler (flag
    # off) or the Backbone (flag on). The other one is never constructed.
    from src.backbone.backbone import Backbone
    denidin.ai_manager = Backbone(denidin)

    # Feature 070: sessions never expire and there is no session-cleanup thread.
    # Aged conversation is rolled to daily summaries by the nightly
    # DailySummaryRollService, wired in __main__ only (like the Feature 054
    # reminder scheduler below).

    # Feature 054: reminder delivery scheduler is deliberately NOT started here.
    # initialize_app() is the shared bootstrap tests/integration/ calls directly
    # (a process-global denidin_app singleton, reused across test files) -
    # starting a real APScheduler against the real bot object here would let
    # an ordinary test run reach bot.api.sending.sendMessage unattended, using
    # config.test.json's real (not sandboxed) Green API credentials. This
    # function no longer has access to the live bot instance itself anyway
    # (Feature 043 - only `green_api`, the `.api` client, is injected) - the
    # reminder scheduler needs the FULL live bot (send_proactive_message calls
    # bot.api.sending.sendMessage), so it's wired in __main__ below instead,
    # alongside message_source.start() itself, using `live_bot` directly. See
    # tasks.md T013's note (2026-08-17) for the incident this design avoided
    # (caught before any real send happened - test_data/reminders/reminders.db
    # had zero rows at the time).

    # Feature 045's read-receipt hook (mark every non-blocked sender's incoming
    # message as read) is wired by GreenAPIMessageSource.start(), not here -
    # this function no longer has access to the live bot instance itself
    # (Feature 043 - only `green_api`, the `.api` client, is injected), and a
    # caller with no live Green API connection at all (e.g. the player) has no
    # bot to mark anything read on anyway. See green_api_source.py's
    # start()/`_build_read_receipt_hook` docstrings.

    return denidin


# Initialize global context (will be populated after startup recovery)
global_context = None

# Log startup information with masked API keys
logger.info("=" * 60)
logger.info("DeniDin application starting...")
logger.info("Configuration:")
logger.info(f"  Green API Instance: {startup_config.green_api_instance_id}")
logger.info(f"  Green API Token: {mask_api_key(startup_config.green_api_token)}")
logger.info(f"  AI API Key: {mask_api_key(startup_config.ai_api_key)}")
logger.info(f"  AI Model: {startup_config.ai_model}")
logger.info(f"  Max Tokens: {startup_config.ai_reply_max_tokens}")
logger.info(f"  Log Level: {startup_config.log_level}")
logger.info("Handlers initialized: WhatsAppHandler")
logger.info("=" * 60)


def _resolve_group_user_phone(message) -> Optional[str]:
    """Feature 039 (US4): for a group message, resolve the most-permissive member's
    phone via GroupMembershipResolver - returns None for 1:1 messages, a missing
    resolver, or any resolution failure (falls back to sender-only RBAC, never
    blocks the turn)."""
    if not message.is_group or denidin_app.group_membership_resolver is None:
        return None

    resolution = denidin_app.group_membership_resolver.resolve(message.chat_id)
    return resolution.phone if resolution else None


def _process_conversational_message(notification: Notification, *, internal: bool = False) -> None:
    """
    Processing for any message type that flows into the conversational pipeline: validate ->
    store on receipt -> hand to the AI implementation, which sends everything the model says
    through its tools the moment the model says it (nothing is sent from here). Feature 039:
    group messages are no longer gated by a mention check - addressed to DeniDin by default,
    same as 1:1.

    Extracted (Feature 030) from what was previously handle_text_message's own body, so the
    contactMessage router (a shared WhatsApp contact card - see handle_contact_message) can
    reuse it. Callers MUST have already confirmed denidin_app is initialized.

    Args:
        notification: Green API notification object containing message data
        internal: the message is DeniDin-generated context re-entering the pipeline, not the
            user's own WhatsApp message - stored without its WhatsApp idMessage.
    """
    try:
        # Validate message type
        if not denidin_app.whatsapp_handler.validate_message_type(notification):
            _reply_unsupported(notification)
            return

        # Parsed into a WhatsAppMessage (message_id, received_timestamp) and stored the
        # moment it's received - before any processing, so it's in the session whatever
        # happens to the rest.
        message = denidin_app.receive(notification, internal=internal)

        # Create tracking prefix for all logs related to this message
        tracking = f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp.isoformat()}]"
        logger.info(
            f"{tracking} Received message from {message.sender_name} ({message.sender_id}): "
            f"{message.text_content[:100]}..."
        )

        # Feature 039 (US4): group turns are governed by the most-permissive role
        # present among the group's members, not the individual sender alone.
        # None for 1:1 and for any resolution failure.
        group_user_phone = _resolve_group_user_phone(message)
        ai_request = denidin_app.ai_manager.create_request(message, user_phone=group_user_phone)
        logger.debug(f"{tracking} Created AI request {ai_request.request_id}")

        # user_phone must be the real phone (group_user_phone for a group, else
        # message.sender_id): `sender` is a display name since Feature 039.
        effective_user_phone = group_user_phone or message.sender_id
        ai_response = denidin_app.ai_manager.handle_message(
            ai_request,
            chat_id=message.chat_id,
            sender=message.sender_display_name,
            user_phone=effective_user_phone,
            sender_phone=message.sender_id,
            is_group=message.is_group,
            chat_name=message.chat_name,
        )
        # What the call did (the texts it sent, its Morning calls, its usage) - for
        # observability / E2E test verification. Nothing is delivered from it.
        denidin_app.last_response = ai_response
        logger.info(f"{tracking} Handled: {ai_response.tokens_used} tokens, {len(ai_response.mcp_calls)} Morning calls")

    except Exception as e:
        # Global exception handler - catches anything not handled by specific handlers
        try:
            tracking = f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp.isoformat()}]"
            logger.error(
                f"{tracking} Unexpected error processing message: {e}",
                exc_info=True  # Full traceback
            )
        except (NameError, AttributeError):
            # message not yet defined or missing tracking fields
            logger.error(
                f"Unexpected error processing message (no tracking available): {e}",
                exc_info=True
            )

        # Send generic fallback message to user (stored once sent, like every message;
        # the user's own message was already stored on receipt).
        try:
            denidin_app.send_text(notification, ERROR_PROCESSING_MESSAGE_TRY_AGAIN)
            logger.info("Generic fallback message sent to user")
        except Exception as fallback_error:
            # Even fallback failed - log and continue
            logger.error(f"Failed to send fallback message: {fallback_error}", exc_info=True)


def _reply_unsupported(notification: Notification) -> None:
    """The auto-reply for an unsupported message type: the message is stored as
    "[<type> message]", then the canned reply is sent (and stored once sent)."""
    message_type = notification.event.get('messageData', {}).get('typeMessage', 'unknown')
    sender_name = notification.event.get('senderData', {}).get('senderName', 'Unknown')
    logger.info(f"Sending unsupported message auto-reply to {sender_name} for {message_type}")
    try:
        denidin_app.receive(notification, content=f"[{message_type} message]")
        denidin_app.send_text(notification, UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES)
        logger.debug("Unsupported message auto-reply sent successfully")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"Failed to send unsupported message auto-reply: {e}", exc_info=True)


def _process_media_message(notification: Notification) -> None:
    """
    The media message (image, document, video, audio) path: download and validate the file
    up front (MediaFileManager - no extraction), then hand it RAW to the AI implementation.
    The model is told only "media attached, type X, caption Y"; it itself loads
    cap_media_analysis and calls analyze_media, which does the real extraction
    (src/capabilities/media_analysis/handler.py). Ledger recognition of a fee-agreement /
    bank-deposit event happens in the flows that handle them.

    Args:
        notification: Green API notification object containing media message data
    """
    from src.models.media import Media
    from src.models.message import AIRequest

    # 2026-09-30: stored the moment it's received - caption, or "[<filename> sent]" with no
    # caption. The saved file's path and its extracted text are filled into this same stored
    # message later.
    _file_data = notification.event.get('messageData', {}).get('fileMessageData', {})
    message = denidin_app.receive(
        notification,
        content=_file_data.get('caption', '') or f"[{_file_data.get('fileName', 'file')} sent]",
    )

    file_url = _file_data.get('downloadUrl', '')
    filename = _file_data.get('fileName', 'unknown')
    mime_type = _file_data.get('mimeType', '')
    caption = _file_data.get('caption', '')

    file_manager = denidin_app.media_handler.media_file_manager
    try:
        content, download_success = file_manager.download_file(file_url)
        if not download_success:
            raise ValueError("Unable to download this file.")
        file_manager.validate_file_size(len(content))
        media_type = file_manager.validate_format(filename, mime_type)
    except ValueError as exc:
        logger.warning(f"Media download/validation failed: {exc}")
        refusal = FILE_TOO_LARGE_REFUSAL if isinstance(exc, FileTooLargeError) else FAILED_TO_PROCESS_FILE_DEFAULT
        denidin_app.send_text(notification, refusal)
        return

    # Archive the file (2026-09-30) - its data_root-relative path is persisted as the user
    # message's image_path. A storage failure is logged and processing continues on the
    # in-memory bytes (image_path stays None) - the user still gets an answer.
    media_path = None
    try:
        media_path = file_manager.store_media(content, filename, message.sender_id)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(f"Failed to archive incoming media file: {exc}", exc_info=True)
    if media_path:
        denidin_app.update_message(message.chat_id, message.message_id, image_path=media_path)

    media = Media(data=content, mime_type=mime_type, filename=filename, media_type=media_type)
    # user_prompt is the caption only ("" when none) - the backbone prepends the
    # "[ATTACHED MEDIA: ...]" marker itself. The model runs on config.ai_model like for any
    # other message; only analyze_media's extractor uses config.ai_vision_model.
    request = AIRequest(
        user_prompt=caption,
        constitution="",
        max_tokens=denidin_app.config.ai_reply_max_tokens,
        model=denidin_app.config.ai_model,
        chat_id=message.chat_id,
        message_id=message.message_id,
        timestamp=message.timestamp,
        original_message=message,
        media=media,
    )
    denidin_app.last_response = denidin_app.ai_manager.handle_message(
        request, chat_id=message.chat_id,
        sender=message.sender_display_name, user_phone=message.sender_id,
        sender_phone=message.sender_id, is_group=message.is_group, chat_name=message.chat_name,
    )


def _log_inbound_webhook(notification: Notification) -> None:
    """Wire-log the raw inbound webhook - unless it was already logged when the poller
    received it (Feature 067: a message is logged at receipt, because one that joins the
    model's work at a hand-back never reaches a handler)."""
    intake = getattr(denidin_app, "intake", None) if denidin_app is not None else None
    if intake is not None and intake.inbound_logged_for(notification):
        return
    audit_wire("whatsapp", "in", "webhook", notification.event)
    debug_wire("whatsapp", "in", "webhook", notification.event)


def handle_text_message(notification: Notification) -> None:
    """
    Handle incoming text messages from WhatsApp with comprehensive error handling.
    Phase 6: Memory System Integration

    Args:
        notification: Green API notification object containing message data
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "text")
        return

    _process_conversational_message(notification)


def handle_contact_message(notification: Notification) -> None:
    """
    Handle a single shared WhatsApp contact card (Feature 030).

    The vCard's displayName/vcard text is framed into text_content by
    WhatsAppMessage.from_notification and flows into the exact same conversational AIHandler
    pipeline textMessage already uses - the model reads the raw vCard lines itself and, for
    godfather/admin senders, proposes an add_client call exactly as it would from typed text,
    inheriting Feature 026's approval gate and missing-field behavior unchanged.

    Args:
        notification: Green API notification object containing message data
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "contact")
        return

    _process_conversational_message(notification)


def handle_contacts_array_message(notification: Notification) -> None:
    """
    Handle multiple WhatsApp contacts shared at once (Feature 030).

    A genuinely distinct Green API notification type from a single contactMessage (confirmed
    via Green API's official docs), not multiple vCards inside one contactMessage. Per spec.md
    Clarifications (2026-07-30), v1 declines this outright with a friendly "one at a time"
    message - no vCard parsing, no AIHandler/OpenAI call at all, regardless of how many contacts
    the array actually contains.

    Args:
        notification: Green API notification object containing message data
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "contacts array")
        return

    denidin_app.receive(notification, content="[contacts sent]")
    denidin_app.send_text(notification, CONTACT_CARD_ONE_AT_A_TIME)


def handle_image_message(notification: Notification) -> None:
    """
    Handle incoming image messages from WhatsApp.
    Routes to MediaHandler for image analysis.

    Args:
        notification: Green API notification object containing image data
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "image")
        return

    _process_media_message(notification)


def handle_document_message(notification: Notification) -> None:
    """
    Handle incoming document messages from WhatsApp.
    Routes to MediaHandler for document processing (PDF, DOCX, etc.).

    Args:
        notification: Green API notification object containing document data
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "document")
        return

    _process_media_message(notification)


def handle_video_message(notification: Notification) -> None:
    """
    Handle incoming video messages from WhatsApp.
    Routes to MediaHandler for video processing.

    Args:
        notification: Green API notification object containing video data
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "video")
        return

    _process_media_message(notification)


def _append_edit_or_delete_note(notification: Notification, content: str) -> None:
    """
    Feature 076 (FR-001/FR-002/FR-004): shared persistence for the editedMessage/
    deletedMessage note - a plain `role="user"` Message appended via
    SessionManager.add_message, dated from the webhook's own `timestamp`
    (Israel local, per CONSTITUTION §XV), never the current wall-clock time.
    Creates the chat's session on first contact exactly like any other first
    message (SessionManager.get_session, called internally by add_message) -
    no special-casing needed for a chat with no prior session (FR-004).

    Deliberately does NOT resolve, read, or mutate the message referenced by
    the webhook's own `stanzaId` (FR-003) - that's Feature 032 territory.

    Args:
        notification: Green API notification (editedMessage or deletedMessage)
        content: The exact note text to persist (already framed with the
            `[הודעה קודמת נערכה]`/`[המשתמש מחק הודעה קודמת]` marker)
    """
    from src.models.message import WhatsAppMessage  # local import - matches existing style

    message = WhatsAppMessage.from_notification(notification)
    event_timestamp = notification.event.get("timestamp")
    note_timestamp = local_from_timestamp(event_timestamp) if event_timestamp is not None else None
    user_role = denidin_app.user_manager.get_user(message.sender_id).role

    denidin_app.session_manager.add_message(
        chat_id=message.chat_id,
        role="user",
        content=content,
        user_role=user_role,
        sender=message.sender_id,
        sender_name=message.sender_display_name,
        timestamp=note_timestamp,
    )


def handle_edited_message(notification: Notification) -> None:
    """
    Handle a WhatsApp `editedMessage` webhook (Feature 076, FR-001).

    A good-faith correction to an earlier message (Green API delivers the full
    corrected text, not a diff - see spec.md "Research"). Per spec.md
    Clarifications Q2: note the correction into the chat's long-lived session
    as a dated `[הודעה קודמת נערכה] <corrected text>` message - no AI call, no
    WhatsApp reply. The model picks up the correction on its next real turn via
    the 14-day rolling window (SessionManager.get_rolling_window), reconciling
    it against the original message naturally rather than via any code-level
    resolution of `editedMessageData.stanzaId` (out of scope - Feature 032).

    Args:
        notification: Green API notification object containing the edit
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "editedMessage")
        return

    edited_text = notification.event.get("messageData", {}).get(
        "editedMessageData", {}
    ).get("textMessage", "")
    _append_edit_or_delete_note(notification, f"[הודעה קודמת נערכה] {edited_text}")


def handle_deleted_message(notification: Notification) -> None:
    """
    Handle a WhatsApp `deletedMessage` webhook (Feature 076, FR-002).

    Green API delivers only a pointer (`deletedMessageData.stanzaId`) with no
    text and no flag on the original - see spec.md "Research". Per spec.md
    Clarifications Q3: note the retraction into the chat's long-lived session
    as a fixed dated `[המשתמש מחק הודעה קודמת]` message - same no-AI-call,
    no-reply rules as handle_edited_message. The deleted stanzaId is logged for
    traceability only; it is never persisted on the note itself (FR-002/FR-003).

    Args:
        notification: Green API notification object containing the deletion
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "deletedMessage")
        return

    stanza_id = notification.event.get("messageData", {}).get(
        "deletedMessageData", {}
    ).get("stanzaId", "")
    logger.info(f"[076] deletedMessage received for stanzaId={stanza_id!r} - logging note only")
    _append_edit_or_delete_note(notification, "[המשתמש מחק הודעה קודמת]")


def handle_ignored_message_default(notification: Notification) -> None:
    """
    Silent catch-all for trivial/low-value message types (Feature 076, Q7/FR-006).

    Replaces the old `handle_unsupported_message_default` as CATCH_ALL_HANDLER -
    reactions, stickers, locations, poll votes, and any `typeMessage` never seen
    before now get NO WhatsApp reply at all, only the existing verbatim
    `audit_wire`/`debug_wire` record. This deliberately relaxes the old "no message
    type is silently *dropped*" invariant to "no message type is silently
    *lost*" (spec.md "Non-Functional / Constraints" - `audit_wire`/`debug_wire` are
    the thing that keeps it non-lost) - see .github/ARCHITECTURE.md for the same
    note. `denidin_app is None` needs no special handling here (unlike every
    other handler) - there is nothing to reply with either way.

    Args:
        notification: Green API notification object containing message data
    """
    _log_inbound_webhook(notification)
def handle_button_tap(notification: Notification) -> None:
    """
    Feature 047: handle a WhatsApp interactive-buttons tap resolving a pending
    document-creation approval (Feature 022).

    Registered via the plain router.message mechanism, NOT @bot.router.buttons(...) -
    research.md confirmed the library's own ButtonObserver only matches the older,
    deprecated button-reply types (buttonsResponseMessage/templateButtonsReplyMessage/
    listResponseMessage), never interactiveButtonsResponse (the type a real
    sendInteractiveButtons tap actually produces, per Gate Zero). Registration itself
    happens via GreenAPIMessageSource's explicit message_types list in __main__
    (Feature 043 - no module-level `bot`/decorator, see research.md R3), deliberately
    NOT via HANDLER_REGISTRY/dispatch_notification (that dict's exact-types shape
    is locked by an existing immutable test predating this feature - see
    test_denidin_dispatch.py, updated for Feature 076's own additions) -
    dispatch_notification special-cases this one type instead.

    Args:
        notification: Green API notification object containing the tap
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "interactiveButtonsResponse")
        return

    button_data = notification.event.get("messageData", {}).get("interactiveButtonsResponse", {})
    selected_id = button_data.get("selectedId", "")
    stanza_id = button_data.get("stanzaId", "")
    # 2026-09-30: the tap is a message received from the user - stored on receipt, as the
    # answer it gives ("כן"/"לא"); the synthetic requests below reuse its message_id.
    message = denidin_app.receive(notification, content="כן" if selected_id == "denidin_approve" else "לא")

    # A tap resolves like a typed "כן"/"לא": the AI implementation continues the conversation
    # (None for a stale/superseded tap - nothing is done at all, no reply of any kind).
    ai_response = denidin_app.ai_manager.resolve_button_tap(message, selected_id, stanza_id)
    if ai_response is None:
        logger.info(
            f"[047] Button tap produced no resolution for chat={message.chat_id!r} "
            f"(selected_id={selected_id!r}, stanza_id={stanza_id!r}) - doing nothing"
        )
        return
    denidin_app.last_response = ai_response
    logger.info(f"[047] Button tap resolved for chat={message.chat_id!r}")


def handle_unsupported_message_default(notification: Notification) -> None:
    """
    Catch-all handler for unsupported message types.
    Prevents silent drops - sends Hebrew error message to user.
    Called for any message type without a specific handler.

    Args:
        notification: Green API notification object containing message data
    """
    _log_inbound_webhook(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "unsupported")
        return

    _reply_unsupported(notification)


# Feature 043: handler-dispatch table, replacing the module-scope
# @bot.router.message(...) decorators that used to sit directly above each
# handler function - those required a live `bot` object to exist at module
# import time (see research.md R3), which this feature's MessageSource
# abstraction (src/sources/) eliminates. Every handler function above stays
# a plain, undecorated function; dispatch_notification() plus this registry
# is the single source of truth for "which handler does this message type
# route to," used identically by denidin.py's own live entry point (via
# GreenAPIMessageSource, below) and by anything else that supplies
# notifications through a different MessageSource (e.g. the Feature 043
# player, player/) - both call dispatch_notification the same way.
HANDLER_REGISTRY: Dict[str, Callable[[Notification], None]] = {
    "textMessage": handle_text_message,
    "extendedTextMessage": handle_text_message,
    "contactMessage": handle_contact_message,
    "contactsArrayMessage": handle_contacts_array_message,
    "imageMessage": handle_image_message,
    "documentMessage": handle_document_message,
    "videoMessage": handle_video_message,
    # Feature 076 (FR-001/FR-002): editedMessage/deletedMessage are logged to
    # the session, never replied to - handled here, not via ERROR_REPLY_TYPES
    # or the silent catch-all.
    "editedMessage": handle_edited_message,
    "deletedMessage": handle_deleted_message,
    # audioMessage removed (Feature 076, Q5) - voice notes are not
    # transcribed, so it now falls into ERROR_REPLY_TYPES below instead of
    # routing to the media pipeline.
}

# Feature 076 (Q5/Q6, FR-005/FR-007): each of these gets exactly one canned
# `UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES` reply (`סוג הודעה לא נתמך`), no AI
# call, no session write - checked by dispatch_notification() BEFORE falling
# through to CATCH_ALL_HANDLER (the silent bucket, Q7).
ERROR_REPLY_TYPES = {
    "audioMessage", "pollMessage", "templateMessage",
    "templateButtonsReplyMessage", "listMessage", "listResponseMessage",
}

# Feature 076 (Q7, FR-006): any message type not present in HANDLER_REGISTRY
# and not in ERROR_REPLY_TYPES routes here - silently ignored (audit_wire/debug_wire
# only, no reply). Replaces the old handle_unsupported_message_default
# catch-all, which now serves only ERROR_REPLY_TYPES.
CATCH_ALL_HANDLER: Callable[[Notification], None] = handle_ignored_message_default


class RecentNotificationDeduper:
    """In-memory, TTL-bounded de-duplication of incoming Green API webhook
    notifications by idMessage (2026-08-20, real dev incident).

    Green API's own notification queue can redeliver the same event more
    than once if it isn't acknowledged/deleted fast enough - confirmed live
    via [AUDIT-IN] log lines: an incomingMessageReceived notification with
    an IDENTICAL idMessage and timestamp arrived a second time ~32s after
    the first (that turn's own OpenAI round-trip took ~22s). The redelivery
    landed while a reminder create_reminder approval was already pending,
    and since the app has no concept of "I already processed this exact
    notification," it was interpreted as a (non-affirmative) reply to that
    pending approval - declining it, then re-processing the duplicate as a
    brand-new request, producing a SECOND approval-buttons prompt for one
    real user message. Not reminders-specific - this is a systemic gap in
    incoming-message handling; the reminder approval-gate flow just made it
    highly visible.

    No disk persistence - a restart naturally starts with an empty seen-set,
    matching GroupMembershipResolver's own in-memory-cache precedent
    (src/managers/group_membership_resolver.py). A few minutes of TTL is
    enough to catch a same-session redelivery; losing that window across a
    restart is an acceptable trade, since a genuine redelivery spanning a
    restart couldn't be caught by this mechanism anyway (the first
    delivery's own in-progress processing state wouldn't have survived the
    restart either).
    """

    def __init__(self, ttl_seconds: float = 600.0):
        self._ttl_seconds = ttl_seconds
        self._seen: Dict[str, float] = {}  # idMessage -> first-seen monotonic time

    def seen_recently(self, id_message: str) -> bool:
        """True (without re-recording) if id_message was already recorded
        within the TTL window - the caller should skip processing entirely.
        False (recording this call as the first sighting) otherwise.
        Opportunistically evicts expired entries on every call, bounding
        memory without a separate background thread/timer."""
        now = time.monotonic()
        expired = [key for key, seen_at in self._seen.items() if now - seen_at > self._ttl_seconds]
        for key in expired:
            del self._seen[key]

        if id_message in self._seen:
            return True
        self._seen[id_message] = now
        return False


# Module-level singleton (mirrors denidin_app/global_context's own module-global
# idiom) - one shared seen-set for the whole process, since redelivery can
# happen for any message type, not just one handler's own traffic.
_recent_notifications = RecentNotificationDeduper()


def dispatch_notification(type_message: str, notification: Notification) -> None:
    """The dispatch callable every MessageSource.start() calls - looks up
    HANDLER_REGISTRY, falling back to CATCH_ALL_HANDLER for any type not
    explicitly registered (same behavior the old catch-all decorator gave,
    just explicit instead of relying on router iteration order).

    interactiveButtonsResponse (Feature 047) is special-cased rather than added
    to HANDLER_REGISTRY itself: that dict's exact-8-types shape is locked by an
    existing immutable test (test_denidin_dispatch.py) predating Feature 047's
    merge into this branch - widening it needs its own explicit human sign-off,
    not a side effect of a git merge. __main__ registers this type explicitly
    with GreenAPIMessageSource alongside HANDLER_REGISTRY's own keys, so it
    still reaches here rather than falling through to CATCH_ALL_HANDLER.

    De-duplicates by idMessage (2026-08-20) BEFORE any handler runs - see
    RecentNotificationDeduper's own docstring for the real incident this
    closes. `getattr(notification, "event", None)` (rather than
    `notification.event` directly) so a test double with no `.event`
    attribute at all (test_denidin_dispatch.py's `fake_notification =
    object()`) is simply never deduped, not a crash - matches
    audit_wire/debug_wire's own "never break real processing" discipline.
    """
    event = getattr(notification, "event", None)
    id_message = event.get("idMessage") if isinstance(event, dict) else None
    if id_message and _recent_notifications.seen_recently(id_message):
        logger.info(
            f"Duplicate notification ignored (idMessage={id_message!r}, "
            f"type={type_message!r}) - Green API redelivery, already processed"
        )
        return

    if type_message == "interactiveButtonsResponse":
        handle_button_tap(notification)
        return
    if type_message in ERROR_REPLY_TYPES:
        # Feature 076 (FR-005): checked before HANDLER_REGISTRY.get()'s own
        # fallback so these six types get the canned reply, not the silent
        # CATCH_ALL_HANDLER - none of them are ever also HANDLER_REGISTRY keys.
        handle_unsupported_message_default(notification)
        return
    handler = HANDLER_REGISTRY.get(type_message, CATCH_ALL_HANDLER)
    handler(notification)


def main() -> None:
    """The live app: connect to Green API, initialize, start the background
    services, and run until shut down."""
    global denidin_app  # pylint: disable=global-statement
    # Phase 6: Memory System Integration
    # Initialize app using shared initialization function

    logger.info("=" * 60)
    logger.info("Phase 6: Memory System Startup")
    logger.info("=" * 60)

    # Convert config to dict for initialize_app
    config_dict = {
        'green_api_instance_id': startup_config.green_api_instance_id,
        'green_api_token': startup_config.green_api_token,
        'green_api_host_mode': startup_config.green_api_host_mode,
        'green_api_media_host': startup_config.green_api_media_host,
        'ai_api_key': startup_config.ai_api_key,
        'ai_model': startup_config.ai_model,
        'ai_vision_model': startup_config.ai_vision_model,
        'ai_embedding_model': startup_config.ai_embedding_model,
        'ai_reply_max_tokens': startup_config.ai_reply_max_tokens,
        'max_retries': startup_config.max_retries,
        'log_level': startup_config.log_level,
        'data_root': startup_config.data_root,
        'feature_flags': startup_config.feature_flags,
        'godfather_phone': startup_config.godfather_phone,
        'memory': startup_config.memory,
        'constitution_config': startup_config.constitution_config,
        'backbone_config': startup_config.backbone_config,
        'user_roles': startup_config.user_roles,
        'mcp': startup_config.mcp,
        'reminders': startup_config.reminders,
        # Feature 025: missed here originally (a real bug - AppConfiguration.
        # from_file's own defaults/field list already covered this correctly,
        # but this hand-maintained subset dict for initialize_app() is a
        # separate place every new config field must also be added, same
        # pattern max_retries' own history already warned about) - found
        # live in dev (accounting_ledger_update_freq=60 in config.json, but
        # the scheduler silently never started because this dict dropped it
        # before it ever reached initialize_app()).
        'accounting_ledger_update_freq': startup_config.accounting_ledger_update_freq,
        # Feature 063: idle-reset threshold (minutes) - same must-be-listed-here rule.
        'capabilities_reset_minutes': startup_config.capabilities_reset_minutes,
        'message_queues': startup_config.message_queues,
        # Feature 069: context-window size for the post-turn ledger recognition call.
        'ledger_recognition_context_window_hours': startup_config.ledger_recognition_context_window_hours,
        # Feature 098: fills the constitution's {{ALLOCATION_THRESHOLD_NIS}} -
        # same "must also be listed here or it silently has no effect" rule.
        'allocation_threshold_nis': startup_config.allocation_threshold_nis,
        # bugfix-043: same "hand-maintained subset dict, easy to forget"
        # pattern warned about immediately above - added here explicitly so
        # a config.dev.json/config.prod.json value doesn't silently do
        # nothing, exactly like accounting_ledger_update_freq's own history.
        'health_check_port': startup_config.health_check_port,
        # Feature 089: Agreements API port/token. Same must-be-listed-here rule.
        'agreements_api': startup_config.agreements_api,
        # Feature 070 (US5): log-retention tunables. Same "must also be listed
        # here or it silently has no effect" rule as accounting_ledger_update_freq.
        'logging': startup_config.logging,
        # Feature 083: fee agreement doc generation template/tmp paths. Same
        # "must also be listed here or it silently has no effect" rule.
        'fee_agreements': startup_config.fee_agreements,
    }

    # Feature 043: construct the live Green API bot explicitly here (via
    # GreenAPIMessageSource.connect(), NOT at module import time - see
    # research.md R3) and pass its real client into initialize_app(), which
    # needs it for _fetch_own_whatsapp_number/GroupMembershipResolver before
    # the blocking listen loop (message_source.start(), below) begins.
    # message_types is constructor-injected (not passed to start()) so
    # start(dispatch) has the exact same signature as PlayerExportSource's -
    # see green_api_source.py's own docstring. interactiveButtonsResponse
    # (Feature 047) is appended explicitly rather than folded into
    # HANDLER_REGISTRY itself - see dispatch_notification's docstring for why.
    message_source = GreenAPIMessageSource(
        startup_config,
        # Feature 076 (FR-010): ERROR_REPLY_TYPES added alongside
        # HANDLER_REGISTRY's own keys, so audioMessage/pollMessage/etc.
        # actually reach dispatch_notification() rather than being filtered
        # out by the library before dispatch ever runs.
        message_types=list(HANDLER_REGISTRY.keys()) + list(ERROR_REPLY_TYPES)
        + ["interactiveButtonsResponse"],
    )
    live_bot = message_source.connect()

    # Initialize app (handles memory system, cleanup thread, recovery)
    denidin = initialize_app(config_dict, green_api=live_bot.api)

    # Set global denidin_app for WhatsApp message handler
    denidin_app = denidin

    # The live bot - only exists once we're the real, live-running app, never for
    # initialize_app()'s test-harness callers. Read off DeniDin by everything that
    # needs it: Feature 048's typing indicator, Feature 083's document send
    # (`.api.sending.sendFileByUpload`), Feature 084's reactions.
    denidin_app.green_api_bot = live_bot

    # Feature 045's read-receipt hook: set as a post-construction attribute,
    # not a constructor/start() arg - denidin.user_manager doesn't
    # exist yet at the point message_source itself had to be constructed
    # (connect() -> initialize_app(green_api=...) -> denidin, above). See
    # green_api_source.py's is_blocked docstring for the full reasoning.
    message_source.is_blocked = (
        lambda chat_id: denidin.user_manager.get_user(chat_id).is_blocked
    )

    # Feature 067: the poller (live_bot) only receives, stores and acknowledges; the
    # DeniDinDispatcher thread handles what it queued, one message at a time, through the
    # same dispatch_notification the replay player uses. Queue limits/warnings and thread
    # supervision (REQ-RMH-033..036) are built here too - started HERE, never inside
    # initialize_app() (tests call that and must not get background threads).
    queue_settings = QueueSettings.from_config(denidin.config)
    denidin.intake = IntakeCoordinator(denidin)
    live_bot.intake = denidin.intake
    denidin.dispatcher = DeniDinDispatcher(denidin.intake, dispatch_notification)
    denidin.queue_monitor = QueueMonitor(queue_settings)
    denidin.queue_monitor.register(denidin.intake.queues)
    denidin.queue_monitor.register(lambda: [denidin.session_manager.queue])
    denidin.thread_supervisor = ThreadSupervisor(queue_settings)
    denidin.thread_supervisor.register("dispatcher", denidin.dispatcher.is_alive, denidin.dispatcher.start)
    denidin.thread_supervisor.register(
        "session-manager-actor", denidin.session_manager.is_alive, denidin.session_manager.start)
    denidin.dispatcher.start()
    denidin.queue_monitor_scheduler = start_queue_monitor_scheduler(denidin.queue_monitor, queue_settings)
    denidin.thread_supervisor_scheduler = start_thread_supervisor_scheduler(
        denidin.thread_supervisor, queue_settings)

    # bugfix-076 (2026-09-07): localhost-only /health server + heartbeat writer, for the
    # prod-only external health-check prober. Started FIRST among this block - deliberately
    # BEFORE the reminder/accounting-reconciliation/daily-roll startup sweeps below, which is a
    # change from bugfix-043's original ordering (health server was started LAST). Real prod
    # incident, 2026-09-07: the accounting-reconciliation startup sweep makes a real, synchronous
    # OpenAI+Morning-MCP call before returning: cold real-world latency from watchdog spawning
    # denidin.py to the health server actually binding its port was measured at ~3m23s (log
    # timestamps: LedgerEventManager init ~37s, the reconciliation sweep's OpenAI round-trip
    # ~69s more). Every deploy/restart during that window is a real, unmonitored outage window -
    # nothing responds on the health port at all, so no prober/verify.py-based check could ever
    # see it as anything but "unreachable," and a fresh restart looks identical to a hang. Health
    # server placement doesn't depend on any of the schedulers below (only needs
    # ai_client/live_bot.api/denidin.config.mcp/denidin.memory_manager, all already available
    # immediately after initialize_app() above), so moving it first costs nothing and closes this
    # gap at its source rather than needing a longer prober grace period to paper over it. Same
    # deliberate-placement rule as before (started HERE, never inside initialize_app() - a real
    # listener bound even on 127.0.0.1, plus real OpenAI/Green API/Morning-tunnel/ChromaDB calls
    # on every probe, has no place running unattended during an ordinary test run). Gated by
    # config.health_check_port (0 = inactive, matching accounting_ledger_update_freq's convention
    # below).
    # Feature 089: the Agreements API for the webapp backend. Started here (a real listener),
    # never inside initialize_app(); port 0 = off.
    agreements_api_config = denidin.config.agreements_api or {}
    start_agreements_api(
        denidin.agreements_manager,
        int(agreements_api_config.get("port", 0) or 0),
        agreements_api_config.get("auth_token", ""),
    )

    if denidin.config.health_check_port > 0:
        check_fns = build_health_check_fns(
            ai_client=denidin.ai_client,
            green_api=live_bot.api,
            morning_mcp_locator=denidin.morning_mcp_locator,
            memory_manager=denidin.memory_manager,
            log_path=resolve_log_path(),
            queue_monitor=denidin.queue_monitor,
            thread_supervisor=denidin.thread_supervisor,
        )
        # bugfix-069: report-only fields (e.g. whatsapp_authorized) - never fail status.
        info_fns = build_health_info_fns(green_api=live_bot.api)
        start_health_server(denidin.config.health_check_port, check_fns, info_fns)
        start_heartbeat_thread()

    # Feature 054: reminder delivery scheduler - deliberately started HERE, not
    # inside initialize_app() (see that function's comment for why: this is the
    # real, live-running app, gated the same way message_source.start()'s
    # blocking bot.run_forever() below is - never reachable from
    # initialize_app()'s test-harness callers). Uses `live_bot` (Feature 043 -
    # initialize_app() itself only ever receives `green_api`, the `.api`
    # client, not the full bot object send_proactive_message needs). No
    # feature flag - unconditional, RBAC alone gates reminder *creation*.
    run_startup_reminder_sweep(denidin, live_bot)
    denidin.reminder_scheduler = start_reminder_scheduler(denidin, live_bot)

    # Feature 025: accounting-document reconciliation scheduler - same
    # deliberate-placement rule as reminder_scheduler above (started HERE,
    # never inside initialize_app() - see contracts/
    # accounting-reconciliation-service.md). Gated by
    # config.accounting_ledger_update_freq (0 = inactive - no scheduler
    # started at all, no startup sweep either).
    update_freq = getattr(denidin.config, "accounting_ledger_update_freq", 0)
    if update_freq > 0:
        run_startup_accounting_reconciliation_sweep(denidin)
        denidin.accounting_reconciliation_scheduler = start_accounting_reconciliation_scheduler(
            denidin, update_freq
        )

    # Feature 063: idle capability-reset sweep (capabilities_reset_minutes; 0 =
    # inactive). Same deliberate placement as above.
    denidin.capability_reset_scheduler = start_capability_reset_if_enabled(denidin)

    # Feature 070: nightly 02:00 Israel-local daily-summary roll - same
    # deliberate-placement rule as the two schedulers above (started HERE,
    # never inside initialize_app() - see contracts/daily-summary-roll-service.md).
    # No feature flag; unconditional when the memory system is enabled.
    if denidin.memory_enabled:
        run_startup_daily_roll_sweep(denidin)
        denidin.daily_roll_scheduler = start_daily_roll_scheduler(
            denidin,
            roll_hour=int((denidin.config.memory or {}).get("roll", {}).get("hour", 2)),
        )

    logger.info("=" * 60)

    # Track if shutdown has been requested (to avoid duplicate logging)
    shutdown_requested = [False]  # Use list to allow modification in nested function

    def signal_handler(signum, frame):
        """Handle SIGINT (Ctrl+C) and SIGTERM (systemd stop) gracefully."""
        if not shutdown_requested[0]:
            shutdown_requested[0] = True
            signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            logger.info(f"Received shutdown signal ({signal_name})")
            logger.info("DeniDin application shutting down gracefully...")

            # Stop cleanup thread if memory enabled
            if denidin.memory_enabled and denidin.cleanup_thread:
                logger.info("Stopping session cleanup thread...")
                denidin.cleanup_thread.stop()

            # Feature 054: stop the reminder delivery scheduler (unconditional -
            # no feature flag, always started in __main__ above)
            if denidin.reminder_scheduler is not None:
                logger.info("Stopping reminder delivery scheduler...")
                denidin.reminder_scheduler.shutdown(wait=False)

            # Feature 025: stop the accounting reconciliation scheduler, if active
            if denidin.accounting_reconciliation_scheduler is not None:
                logger.info("Stopping accounting reconciliation scheduler...")
                denidin.accounting_reconciliation_scheduler.shutdown(wait=False)

            # Feature 063: stop the idle capability-reset scheduler, if active
            if denidin.capability_reset_scheduler is not None:
                logger.info("Stopping idle capability-reset scheduler...")
                denidin.capability_reset_scheduler.shutdown(wait=False)

            # Feature 070: stop the daily-summary roll scheduler, if active
            if denidin.daily_roll_scheduler is not None:
                logger.info("Stopping daily-summary roll scheduler...")
                denidin.daily_roll_scheduler.shutdown(wait=False)

            # Feature 067: stop the dispatcher thread and the queue monitor / thread supervisor
            for scheduler in (denidin.queue_monitor_scheduler, denidin.thread_supervisor_scheduler):
                if scheduler is not None:
                    scheduler.shutdown(wait=False)
            if denidin.dispatcher is not None:
                denidin.dispatcher.stop()

            # Raise KeyboardInterrupt to break out of message_source.start()'s
            # blocking bot.run_forever() call, below.
            raise KeyboardInterrupt()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 50)
    logger.info("DeniDin application is now running!")
    logger.info("Waiting for WhatsApp messages...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)

    try:
        # Start the WhatsApp message listener (blocking call) - registers
        # dispatch_notification against every message type configured at
        # construction time (plus the catch-all) on the already-connected
        # live_bot, wires Feature 045's read-receipt hook (is_blocked, set
        # above), then runs live_bot.run_forever(). Signal handlers will
        # raise KeyboardInterrupt for graceful shutdown.
        message_source.start(dispatch_notification)
    except KeyboardInterrupt:
        # This is raised by signal handlers or user Ctrl+C
        # Message already logged by signal handler or is implicit from Ctrl+C
        if not shutdown_requested[0]:
            logger.info("Received shutdown signal (Ctrl+C)")
            logger.info("DeniDin application shutting down gracefully...")

            # Stop cleanup thread if not already stopped
            if denidin.memory_enabled and denidin.cleanup_thread:
                logger.info("Stopping session cleanup thread...")
                denidin.cleanup_thread.stop()

            # Feature 054: stop the reminder delivery scheduler if not already stopped
            if denidin.reminder_scheduler is not None:
                logger.info("Stopping reminder delivery scheduler...")
                denidin.reminder_scheduler.shutdown(wait=False)

            # Feature 025: stop the accounting reconciliation scheduler if not already stopped
            if denidin.accounting_reconciliation_scheduler is not None:
                logger.info("Stopping accounting reconciliation scheduler...")
                denidin.accounting_reconciliation_scheduler.shutdown(wait=False)

            # Feature 063: stop the idle capability-reset scheduler, if active
            if denidin.capability_reset_scheduler is not None:
                logger.info("Stopping idle capability-reset scheduler...")
                denidin.capability_reset_scheduler.shutdown(wait=False)

            # Feature 070: stop the daily-summary roll scheduler if not already stopped
            if denidin.daily_roll_scheduler is not None:
                logger.info("Stopping daily-summary roll scheduler...")
                denidin.daily_roll_scheduler.shutdown(wait=False)
    except Exception as e:
        # Catch any unexpected error to prevent crash
        logger.critical(
            f"Fatal error in message_source.start()/bot.run_forever(): {e}",
            exc_info=True
        )
        logger.error("Application stopped due to fatal error - manual restart required")
        sys.exit(1)


if __name__ == "__main__":
    main()
