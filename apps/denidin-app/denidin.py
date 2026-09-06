#!/usr/bin/env python3
"""
DeniDin WhatsApp AI Application - Main Entry Point
Integrates Green API for WhatsApp messaging with OpenAI ChatGPT.
Phase 6: US4 - Configuration & Deployment
"""
import logging
import os
import sys
import signal
import time
from typing import Any, Callable, Dict, Optional
from whatsapp_chatbot_python import Notification
from openai import OpenAI
from src.models.config import AppConfiguration
from src.utils.logger import get_logger, reconfigure_file_rotation
from src.sources.green_api_source import GreenAPIMessageSource
from src.utils.green_api_bot import (
    DeniDinGreenAPIBot,
    mark_message_read,
    send_typing_indicator,
)
from src.utils.whatsapp_audit_log import log_inbound, log_outbound
from src.constants.error_messages import (
    APP_NOT_READY_RETRY_LATER,
    UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES,
    ERROR_PROCESSING_MESSAGE_TRY_AGAIN,
    FAILED_TO_PROCESS_FILE_DEFAULT,
    CONTACT_CARD_ONE_AT_A_TIME
)
from src.handlers.ai_handler import AIHandler
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.handlers.media_handler import MediaHandler
from src.managers.session_manager import SessionManager
from src.managers.memory_manager import MemoryManager
from src.managers.group_membership_resolver import GroupMembershipResolver
from src.services.reminder_delivery_service import (
    run_startup_reminder_sweep, start_reminder_scheduler,
)
from src.services.accounting_reconciliation_service import (
    run_startup_accounting_reconciliation_sweep, start_accounting_reconciliation_scheduler,
)
from src.services.daily_summary_roll_service import (
    run_startup_daily_roll_sweep, start_daily_roll_scheduler,
)

# Configuration
CONFIG_PATH = 'config/config.json'

# Load and validate configuration
try:
    config = AppConfiguration.from_file(CONFIG_PATH)
    config.validate()
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
logging.getLogger().setLevel(getattr(logging, config.log_level))
# Feature 070 (US5): every module created its logger at import time (above) with
# logger.py's built-in rotation defaults, before config was loaded. Now that we
# have config.logging, rebuild the root file handler with the real values (a
# no-op when they match the defaults, the common case).
reconfigure_file_rotation(
    rotation_when=config.logging.get('rotation_when', 'midnight'),
    backup_count=config.logging.get('backup_count', 0),
    log_level=config.log_level,
)
logger = get_logger(__name__, log_level=config.log_level)


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


# Initialize OpenAI client
# NOTE: this module-level client is never actually used - initialize_app()
# (the real, single entry point used by both __main__ and every test/the
# player) constructs its own, separately, from its own `config` argument.
# Kept in sync with that one anyway (max_retries=config.max_retries, 2026-08-19
# fix - see AppConfiguration.max_retries' own docstring) so this dead code
# doesn't silently drift from the real behavior if it's ever wired up.
ai_client = OpenAI(
    api_key=config.ai_api_key,
    timeout=30.0,
    max_retries=config.max_retries
)

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


class DeniDin:
    """
    DeniDin application instance.
    Provides programmatic API for testing and direct access.
    Used by integration tests to interact with the app without WhatsApp layer.
    Also serves as global context for background threads (e.g., session cleanup).
    """
    def __init__(self, ai_handler, config, whatsapp_handler, cleanup_thread=None,
                 group_membership_resolver=None, reminder_scheduler=None,
                 accounting_reconciliation_scheduler=None, daily_roll_scheduler=None):
        self.ai_handler = ai_handler
        self.config = config
        self.whatsapp_handler = whatsapp_handler
        self.cleanup_thread = cleanup_thread
        # Add references for background thread access
        self.session_manager = ai_handler.session_manager if ai_handler.memory_enabled else None
        self.memory_manager = ai_handler.memory_manager if ai_handler.memory_enabled else None
        # Feature 039: most-permissive-role RBAC resolution for group turns
        self.group_membership_resolver = group_membership_resolver
        # Feature 054: the single shared APScheduler instance driving the
        # reminder delivery sweep - None until initialize_app() sets it (no
        # feature flag, always started - see reminder_delivery_service.py).
        self.reminder_scheduler = reminder_scheduler
        # Feature 025: the single shared APScheduler instance driving the
        # accounting-document reconciliation sweep - None until __main__ sets
        # it (NEVER initialize_app(), unlike reminder_scheduler - see
        # contracts/accounting-reconciliation-service.md: tests/integration/
        # calls initialize_app() directly against a real bot, and a real
        # background poller making real OpenAI+Morning calls there would let
        # an ordinary test run reach live external services unattended).
        # Also None (inactive) whenever config.accounting_ledger_update_freq == 0.
        self.accounting_reconciliation_scheduler = accounting_reconciliation_scheduler
        # Feature 070: the single shared APScheduler instance driving the nightly
        # 02:00 daily-summary roll - None until __main__ sets it (NEVER
        # initialize_app(), same rule as accounting_reconciliation_scheduler -
        # see contracts/daily-summary-roll-service.md).
        self.daily_roll_scheduler = daily_roll_scheduler
        self._logger = get_logger(__name__)
        # Feature 048's typing indicator needs the live bot (bot.api.serviceMethods.
        # sendTyping) at message-processing time, same as mark_message_read needs it
        # at notification-received time - but Feature 043 deliberately removed the
        # module-level `bot` global those used to close over (research.md R3). Set
        # as a post-construction attribute in __main__, same idiom as
        # GreenAPIMessageSource.is_blocked (see its own docstring for why this can't
        # be a constructor param: __main__ constructs GreenAPIMessageSource, then
        # this DeniDin instance, in that order). None here (the default) means "no
        # live bot" - correct for tests/the player, where send_typing_indicator's own
        # broad except degrades this to a harmless logged warning, never a crash.
        self.green_api_bot: Optional[Any] = None
    
    def handle_message(self, chat_id: str, content: str) -> dict:
        """
        Send a message to the AI and get response.
        
        Args:
            chat_id: WhatsApp chat ID (e.g., "972522968679@c.us")
            content: Message text content
            
        Returns:
            dict with keys: response_text, tokens_used, session_id
        """
        from src.models.message import WhatsAppMessage
        from src.utils.time_utils import now_local

        # Create fake WhatsApp message for testing
        timestamp = int(now_local().timestamp())
        message = WhatsAppMessage(
            message_id=f"test_{timestamp}",
            chat_id=chat_id,
            sender_id=chat_id,
            sender_name="Test User",
            text_content=content,
            timestamp=timestamp,
            message_type="textMessage",
            is_group=False,
            received_timestamp=now_local(),
            sender_display_name="Test User"
        )

        # Create AI request
        ai_request = self.ai_handler.create_request(message)

        # Get AI response
        # Feature 039 fix: get_response's RBAC lookup falls back to `sender` only
        # when `user_phone` isn't given - since `sender` is now a display name
        # (not a phone), user_phone must always be passed explicitly, or RBAC
        # silently resolves against a name instead of a phone.
        ai_response = self.ai_handler.get_response(
            ai_request,
            sender=message.sender_display_name,
            user_phone=message.sender_id,
            sender_phone=message.sender_id,
            is_group=message.is_group,
            chat_name=message.chat_name
        )
        
        # Get session_id from session manager
        session = None
        if self.ai_handler.memory_enabled:
            session = self.ai_handler.session_manager.get_session(chat_id)

        return {
            'response_text': ai_response.response_text,
            'tokens_used': ai_response.tokens_used,
            'session_id': session.session_id if session else None
        }
    
    def get_collection(self):
        """
        Get ChromaDB collection for testing assertions.
        
        Returns:
            ChromaDB Collection object or None if memory disabled
        """
        if not self.ai_handler.memory_enabled:
            return None
        
        return self.ai_handler.memory_manager.client.get_collection(
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
        if not self.ai_handler.memory_enabled:
            return None
        
        return self.ai_handler.session_manager.get_session(chat_id)
    
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
        if self.daily_roll_scheduler is not None:
            self._logger.info("Stopping daily-summary roll scheduler...")
            self.daily_roll_scheduler.shutdown(wait=False)
            self._logger.info("Daily-summary roll scheduler stopped")
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
        log_outbound(notification.event.get("senderData", {}).get("chatId", ""), APP_NOT_READY_RETRY_LATER, kind="text")
    except Exception:
        pass


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
        DeniDin instance with handle_message(), get_collection(), shutdown() APIs
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
    
    # Initialize AI handler
    ai_handler = AIHandler(ai_client, config)

    # bugfix-024: resolve DeniDin's own WhatsApp number ONCE at startup (real Green
    # API call, never per-message) - see _fetch_own_whatsapp_number's docstring.
    ai_handler.own_whatsapp_number = _fetch_own_whatsapp_number(green_api)

    # Initialize WhatsApp handler (without media_handler initially)
    whatsapp_handler = WhatsAppHandler()

    # Feature 039: most-permissive-role RBAC resolution for group turns - built off
    # the injected green_api's own Green API groups client (Feature 043: no longer a
    # module-level `bot` global). GroupMembershipResolver.resolve() already degrades
    # gracefully (falls back to sender-only RBAC) if green_api is None here.
    group_membership_resolver = GroupMembershipResolver(
        green_api.groups if green_api is not None else None, ai_handler.user_manager
    )

    # Create DeniDin instance (will be used as context for background threads and MediaHandler)
    denidin = DeniDin(
        ai_handler, config, whatsapp_handler, cleanup_thread=None,
        group_membership_resolver=group_membership_resolver
    )
    
    # Initialize MediaHandler with DeniDin context and attach to WhatsAppHandler
    media_handler = MediaHandler(denidin)
    whatsapp_handler.media_handler = media_handler
    
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
logger.info(f"  Green API Instance: {config.green_api_instance_id}")
logger.info(f"  Green API Token: {mask_api_key(config.green_api_token)}")
logger.info(f"  AI API Key: {mask_api_key(config.ai_api_key)}")
logger.info(f"  AI Model: {config.ai_model}")
logger.info(f"  Max Tokens: {config.ai_reply_max_tokens}")
logger.info(f"  Log Level: {config.log_level}")
logger.info("Handlers initialized: AIHandler, WhatsAppHandler")
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


def _send_ai_response_and_attach(notification: Notification, chat_id: str, ai_response) -> None:
    """Send this turn's AI reply, then - when it carried a freshly-created pending
    approval sent as interactive buttons (Feature 047/054) - bind the returned
    idMessage to whichever pending-approval manager has something outstanding for
    this chat. `attach_sent_message_id` is a documented no-op on whichever manager
    has nothing pending, so calling both unconditionally is safe.

    Extracted verbatim from `_process_conversational_message` (Feature 069) so the
    post-turn ledger-recognition hook has a clean seam to run after.
    """
    sent_id_message = denidin_app.whatsapp_handler.send_response(notification, ai_response)
    if sent_id_message is not None:
        denidin_app.ai_handler.pending_approval_manager.attach_sent_message_id(
            chat_id, sent_id_message
        )
        denidin_app.ai_handler.pending_local_tool_approval_manager.attach_sent_message_id(
            chat_id, sent_id_message
        )


def _run_post_turn_ledger_recognition(
    *, chat_id: str, sender_phone: Optional[str], reply_text: str, turn_mcp_calls
) -> None:
    """Feature 069 (mechanism move): after a godfather/admin conversational turn's
    reply has been sent, run the ONE text-only recognition call + the zero-AI
    ledgerer. Gated by the same RBAC predicate that gates `query_ledger_events`.

    Best-effort and fully self-contained: any failure is logged and swallowed
    (FR-069-006) - the operator's reply is already out and must not change by one
    byte because ledger bookkeeping hit a problem.
    """
    try:
        from src.handlers.ai_handler import LEDGER_QUERY_AUTHORIZED_ROLES

        ai_handler = denidin_app.ai_handler
        user = ai_handler.user_manager.get_user(sender_phone) if sender_phone else None
        if user is None or user.role not in LEDGER_QUERY_AUTHORIZED_ROLES:
            return

        session = ai_handler.session_manager.get_session(chat_id)
        if not session.message_ids:
            return
        completing_message_id = session.message_ids[-1]

        verdict = ai_handler.recognize_ledger_event(
            session=session,
            reply_text=reply_text,
            turn_mcp_calls=turn_mcp_calls or [],
        )
        ai_handler.ledger_event_manager.persist_recognized_event(
            verdict, session, completing_message_id
        )
    except Exception as exc:  # noqa: BLE001 - deliberate: never surface to the operator
        logger.error(
            f"[069] post-turn ledger recognition failed (swallowed): {exc}",
            exc_info=True,
        )


def _process_conversational_message(notification: Notification) -> None:
    """
    Shared turn-processing logic for any message type that flows into the conversational
    AIHandler pipeline: validate -> parse -> AIHandler -> send response, with the same global
    error handling/fallback-message behavior. Feature 039: group messages are no longer
    gated by a mention check - addressed to DeniDin by default, same as 1:1.

    Extracted (Feature 030) from what was previously handle_text_message's own body, so the new
    contactMessage router (a shared WhatsApp contact card - see handle_contact_message) can reuse
    it verbatim instead of duplicating this ~90-line try/except block. Callers MUST have already
    confirmed denidin_app is initialized.

    Args:
        notification: Green API notification object containing message data
    """
    try:
        # Validate message type
        if not denidin_app.whatsapp_handler.validate_message_type(notification):
            denidin_app.whatsapp_handler.handle_unsupported_message(notification)
            return

        # Process notification into WhatsAppMessage (includes message_id and received_timestamp)
        message = denidin_app.whatsapp_handler.process_notification(notification)

        # Create tracking prefix for all logs related to this message
        tracking = f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp.isoformat()}]"

        # Log incoming message with tracking
        logger.info(
            f"{tracking} Received message from {message.sender_name} ({message.sender_id}): "
            f"{message.text_content[:100]}..."
        )

        # Feature 039 (US4): group turns are governed by the most-permissive role
        # present among the group's members, not the individual sender alone.
        # None for 1:1 and for any resolution failure - AIHandler.create_request
        # itself falls back to message.sender_id when user_phone is None, so 1:1
        # RBAC there is unaffected. get_response has no such message-aware
        # fallback (it only knows `sender`, which Feature 039 repurposed to hold
        # the display name, not the phone - see the comment below), so its call
        # must always resolve to a real phone explicitly.
        group_user_phone = _resolve_group_user_phone(message)

        # Create AI request
        ai_request = denidin_app.ai_handler.create_request(message, user_phone=group_user_phone)
        logger.debug(f"{tracking} Created AI request {ai_request.request_id}")

        # Feature 048: show WhatsApp's typing indicator while DeniDin works on a reply to
        # this turn - fires on every inbound conversational turn uniformly, including a
        # user's yes/no reply to a pending approval (same entry point, no special-casing
        # needed - see user-stories.md US1 scenario 4). Best-effort/log-only; skipped for
        # blocked senders (mirrors feature 045's read-receipt precedent). Single call, no
        # renewal (spec.md Q1) - a renewal loop was tried and reverted 2026-08-13 after live
        # testing surfaced an unresolved scheduling delay; accepted limitation that the
        # indicator may lapse before the reply arrives on turns slower than ~20s.
        is_blocked = denidin_app.ai_handler.user_manager.get_user(message.sender_id).is_blocked
        if denidin_app.green_api_bot is not None:
            send_typing_indicator(denidin_app.green_api_bot, message.chat_id, is_blocked)

        # Get AI response (with retry logic and fallbacks built-in)
        # Feature 039: pass the resolved display name (not the raw WhatsApp id) as
        # sender, so Message.sender/recipient hold a readable name, not a phone
        # number - see SessionManager.add_message for the "AI" sentinel retirement.
        # user_phone must be the real phone (group_user_phone for a group, else
        # message.sender_id) - get_response's own RBAC fallback is `user_phone or
        # sender`, and `sender` is now a display name, not a phone (found
        # 2026-08-04: this silently broke RBAC-gated Morning MCP tool attachment
        # for every 1:1 conversation, resolving the display name as an unknown
        # phone -> defaulting to CLIENT role).
        ai_response = denidin_app.ai_handler.get_response(
            ai_request,
            sender=message.sender_display_name,
            user_phone=group_user_phone or message.sender_id,
            sender_phone=message.sender_id,
            is_group=message.is_group,
            chat_name=message.chat_name
        )
        logger.info(
            f"{tracking} AI response generated: {ai_response.tokens_used} tokens, "
            f"{len(ai_response.response_text)} chars"
        )

        # Feature 039 (US4a): should_reply=False means the model determined this
        # message wasn't for DeniDin - not an error, not a failure, just no reply.
        # The user's message was already persisted inside get_response.
        if not ai_response.should_reply:
            logger.info(f"{tracking} No reply sent (should_reply=False, no-reply sentinel)")
            return

        # Send response (with retry logic built-in)
        # Feature 047: when this turn just sent a new pending approval as
        # interactive buttons, send_response returns the sent idMessage - attach it
        # to the pending approval so a later tap's stanzaId can be matched against
        # it (contracts/pending-approval-message-binding.md). None in every other
        # case (plain-text sends, no-reply, or a failed buttons send).
        # Feature 054 bug (caught 2026-08-17 via a real billed test - a button tap
        # was always rejected as stale): a pending approval is EITHER an MCP one
        # (pending_approval_manager) OR a local-tool one, e.g. create/modify/delete
        # reminder (pending_local_tool_approval_manager) - never both at once for
        # the same chat - but this call site only ever attached to the MCP manager.
        # attach_sent_message_id() is a documented no-op (logged, never raises) on
        # whichever manager has nothing pending for this chat, so calling both
        # unconditionally is safe.
        _send_ai_response_and_attach(notification, message.chat_id, ai_response)
        logger.info(f"{tracking} Response sent to {message.sender_name}")

        # Feature 069 (mechanism move): ledger capture is a post-turn recognition
        # step now - it runs LAST, after the operator's reply is already out, "like
        # a finally block", and never changes that reply. Best-effort/self-contained.
        _run_post_turn_ledger_recognition(
            chat_id=message.chat_id,
            sender_phone=group_user_phone or message.sender_id,
            reply_text=ai_response.response_text,
            turn_mcp_calls=ai_response.mcp_calls,
        )

    except Exception as e:
        # Global exception handler - catches anything not handled by specific handlers
        # Try to include tracking if message was processed
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

        # Send generic fallback message to user
        try:
            notification.answer(ERROR_PROCESSING_MESSAGE_TRY_AGAIN)
            log_outbound(
                notification.event.get("senderData", {}).get("chatId", ""),
                ERROR_PROCESSING_MESSAGE_TRY_AGAIN, kind="text",
            )
            try:
                logger.info(f"{tracking} Generic fallback message sent to user")
            except (NameError, AttributeError):
                logger.info("Generic fallback message sent to user (no tracking available)")
        except Exception as fallback_error:
            # Even fallback failed - log and continue
            try:
                logger.error(
                    f"{tracking} Failed to send fallback message: {fallback_error}",
                    exc_info=True
                )
            except (NameError, AttributeError):
                logger.error(
                    f"Failed to send fallback message (no tracking available): {fallback_error}",
                    exc_info=True
                )


def _process_media_message(notification: Notification) -> None:
    """
    Feature 048 (2026-08-13, corrected same day): shared wrapper around
    WhatsAppHandler.handle_media_message that adds the typing indicator around media
    processing (images, documents, video, audio) - originally scoped OUT of this feature
    (spec.md Q2), which was wrong: "typing while processing" plainly includes media, not
    just conversational turns. WhatsAppHandler has no `bot`/API reference of its own (only
    MediaHandler), so this lives here at the same level as _process_conversational_message
    rather than inside the handler itself - mirrors that function's shape, not its full
    error handling (handle_media_message already has its own failure path via
    FAILED_TO_PROCESS_FILE_DEFAULT).

    Args:
        notification: Green API notification object containing media message data
    """
    from src.models.message import WhatsAppMessage  # local import - matches existing style

    message = WhatsAppMessage.from_notification(notification)
    is_blocked = denidin_app.ai_handler.user_manager.get_user(message.sender_id).is_blocked
    if denidin_app.green_api_bot is not None:
        send_typing_indicator(denidin_app.green_api_bot, message.chat_id, is_blocked)

    result = denidin_app.whatsapp_handler.handle_media_message(notification)

    # Feature 069 (Phase 9/10): a fee-agreement / bank-deposit image or DOCX was
    # recognised. Instead of replying with the plain extraction summary,
    # re-enter the conversational pipeline with a synthetic textMessage carrying
    # the structured "ledger stash" - so the operator gets a real turn (client
    # resolution question / confirmation), and the post-turn ledger recognition
    # step runs over it exactly as it would for a typed message.
    if isinstance(result, dict) and result.get("ledger_stash"):
        stash_text = result["ledger_stash"]
        logger.info(
            f"[069] routing recognised media ledger event "
            f"(source_type={result.get('ledger_stash_source_type')!r}) as a synthetic "
            f"conversational turn"
        )
        message_data = notification.event.setdefault("messageData", {})
        message_data.clear()
        message_data["typeMessage"] = "textMessage"
        message_data["textMessageData"] = {"textMessage": stash_text}
        _process_conversational_message(notification)


def handle_text_message(notification: Notification) -> None:
    """
    Handle incoming text messages from WhatsApp with comprehensive error handling.
    Phase 6: Memory System Integration

    Args:
        notification: Green API notification object containing message data
    """
    log_inbound(notification)
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
    log_inbound(notification)
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
    log_inbound(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "contacts array")
        return

    notification.answer(CONTACT_CARD_ONE_AT_A_TIME)
    log_outbound(notification.event.get("senderData", {}).get("chatId", ""), CONTACT_CARD_ONE_AT_A_TIME, kind="text")


def handle_image_message(notification: Notification) -> None:
    """
    Handle incoming image messages from WhatsApp.
    Routes to MediaHandler for image analysis.
    
    Args:
        notification: Green API notification object containing image data
    """
    log_inbound(notification)
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
    log_inbound(notification)
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
    log_inbound(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "video")
        return

    _process_media_message(notification)


def handle_audio_message(notification: Notification) -> None:
    """
    Handle incoming audio messages from WhatsApp.
    Routes to MediaHandler for audio processing.
    
    Args:
        notification: Green API notification object containing audio data
    """
    log_inbound(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "audio")
        return

    _process_media_message(notification)


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
    NOT via HANDLER_REGISTRY/dispatch_notification (that dict's exact-8-types shape
    is locked by an existing immutable test predating this feature) - dispatch_notification
    special-cases this one type instead.

    Args:
        notification: Green API notification object containing the tap
    """
    log_inbound(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "interactiveButtonsResponse")
        return

    from src.models.message import WhatsAppMessage  # local import - matches existing style

    message = WhatsAppMessage.from_notification(notification)
    button_data = notification.event.get("messageData", {}).get("interactiveButtonsResponse", {})
    selected_id = button_data.get("selectedId", "")
    stanza_id = button_data.get("stanzaId", "")

    ai_response = denidin_app.ai_handler.resolve_button_tap(
        message=message,
        selected_id=selected_id,
        stanza_id=stanza_id,
    )

    if ai_response is None:
        # Stale/superseded tap, or no pending approval at all - spec.md
        # Clarifications: silently ignore, send nothing at all (no send_response
        # call, no notification.answer call).
        logger.info(
            f"[047] Button tap produced no resolution for chat={message.chat_id!r} "
            f"(selected_id={selected_id!r}, stanza_id={stanza_id!r}) - sending nothing"
        )
        return

    sent_id_message = denidin_app.whatsapp_handler.send_response(notification, ai_response)
    if sent_id_message is not None:
        # A resolution reply is always plain text (never offer_approval_buttons)
        # per contracts/button-tap-resolution.md, so this should never actually
        # fire - kept only for symmetry with _process_conversational_message's
        # identical wiring (now both managers, Feature 054 - see the comment
        # there), in case a future change ever chains a fresh pending approval
        # directly off a button resolution.
        denidin_app.ai_handler.pending_approval_manager.attach_sent_message_id(
            message.chat_id, sent_id_message
        )
        denidin_app.ai_handler.pending_local_tool_approval_manager.attach_sent_message_id(
            message.chat_id, sent_id_message
        )
    logger.info(f"[047] Button tap resolved and response sent for chat={message.chat_id!r}")

    # Feature 069: a button tap that resolved an approval (e.g. an add_client or a
    # create_* document) is a real turn - run the same post-turn ledger recognition
    # the typed-reply path runs, so a חשבונית/הסכם/בנק completed via a tap is
    # captured identically. Best-effort/self-contained (see the function's docstring).
    _run_post_turn_ledger_recognition(
        chat_id=message.chat_id,
        sender_phone=message.sender_id,
        reply_text=ai_response.response_text,
        turn_mcp_calls=ai_response.mcp_calls,
    )


def handle_unsupported_message_default(notification: Notification) -> None:
    """
    Catch-all handler for unsupported message types.
    Prevents silent drops - sends Hebrew error message to user.
    Called for any message type without a specific handler.
    
    Args:
        notification: Green API notification object containing message data
    """
    log_inbound(notification)
    if denidin_app is None:
        _handle_not_initialized_error(notification, "unsupported")
        return

    denidin_app.whatsapp_handler.handle_unsupported_message(notification)


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
    "audioMessage": handle_audio_message,
}

# Matches the old bare `@bot.router.message()` catch-all exactly - any
# message type not present in HANDLER_REGISTRY routes here.
CATCH_ALL_HANDLER: Callable[[Notification], None] = handle_unsupported_message_default


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
    log_inbound/log_outbound's own "never break real processing" discipline.
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
    handler = HANDLER_REGISTRY.get(type_message, CATCH_ALL_HANDLER)
    handler(notification)


if __name__ == "__main__":
    # Phase 6: Memory System Integration
    # Initialize app using shared initialization function
    
    logger.info("=" * 60)
    logger.info("Phase 6: Memory System Startup")
    logger.info("=" * 60)
    
    # Convert config to dict for initialize_app
    config_dict = {
        'green_api_instance_id': config.green_api_instance_id,
        'green_api_token': config.green_api_token,
        'ai_api_key': config.ai_api_key,
        'ai_model': config.ai_model,
        'ai_vision_model': config.ai_vision_model,
        'ai_embedding_model': config.ai_embedding_model,
        'ai_reply_max_tokens': config.ai_reply_max_tokens,
        'max_retries': config.max_retries,
        'log_level': config.log_level,
        'data_root': config.data_root,
        'feature_flags': config.feature_flags,
        'godfather_phone': config.godfather_phone,
        'memory': config.memory,
        'constitution_config': config.constitution_config,
        'user_roles': config.user_roles,
        'mcp': config.mcp,
        'reminders': config.reminders,
        # Feature 025: missed here originally (a real bug - AppConfiguration.
        # from_file's own defaults/field list already covered this correctly,
        # but this hand-maintained subset dict for initialize_app() is a
        # separate place every new config field must also be added, same
        # pattern max_retries' own history already warned about) - found
        # live in dev (accounting_ledger_update_freq=60 in config.json, but
        # the scheduler silently never started because this dict dropped it
        # before it ever reached initialize_app()).
        'accounting_ledger_update_freq': config.accounting_ledger_update_freq,
        # Feature 069: context-window size for the post-turn ledger recognition call.
        'ledger_recognition_context_window_hours': config.ledger_recognition_context_window_hours,
        # Feature 070 (US5): log-retention tunables. Same "must also be listed
        # here or it silently has no effect" rule as accounting_ledger_update_freq.
        'logging': config.logging,
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
        config, message_types=list(HANDLER_REGISTRY.keys()) + ["interactiveButtonsResponse"]
    )
    live_bot = message_source.connect()

    # Initialize app (handles memory system, cleanup thread, recovery)
    denidin = initialize_app(config_dict, green_api=live_bot.api)

    # Set global denidin_app for WhatsApp message handler
    denidin_app = denidin

    # Feature 048's typing indicator: same post-construction-attribute idiom as
    # message_source.is_blocked below - see DeniDin.__init__'s green_api_bot
    # docstring for why this can't be a constructor/initialize_app() arg either.
    denidin_app.green_api_bot = live_bot

    # Feature 045's read-receipt hook: set as a post-construction attribute,
    # not a constructor/start() arg - denidin.ai_handler.user_manager doesn't
    # exist yet at the point message_source itself had to be constructed
    # (connect() -> initialize_app(green_api=...) -> denidin, above). See
    # green_api_source.py's is_blocked docstring for the full reasoning.
    message_source.is_blocked = (
        lambda chat_id: denidin.ai_handler.user_manager.get_user(chat_id).is_blocked
    )

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

    # Feature 070: nightly 02:00 Israel-local daily-summary roll - same
    # deliberate-placement rule as the two schedulers above (started HERE,
    # never inside initialize_app() - see contracts/daily-summary-roll-service.md).
    # No feature flag; unconditional when the memory system is enabled.
    if denidin.ai_handler.memory_enabled:
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
            if denidin.ai_handler.memory_enabled and denidin.cleanup_thread:
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

            # Feature 070: stop the daily-summary roll scheduler, if active
            if denidin.daily_roll_scheduler is not None:
                logger.info("Stopping daily-summary roll scheduler...")
                denidin.daily_roll_scheduler.shutdown(wait=False)

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
            if denidin.ai_handler.memory_enabled and denidin.cleanup_thread:
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
