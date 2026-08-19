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
from typing import Optional
from whatsapp_chatbot_python import Notification
from openai import OpenAI
from src.models.config import AppConfiguration
from src.utils.logger import get_logger
from src.utils.green_api_bot import (
    DeniDinGreenAPIBot,
    mark_message_read,
    send_typing_indicator,
)
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
from src.services.cleanup_service import SessionCleanupThread, run_startup_cleanup
from src.services.reminder_delivery_service import (
    run_startup_reminder_sweep, start_reminder_scheduler,
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


# Initialize Green API client
bot = DeniDinGreenAPIBot(
    config.green_api_instance_id,
    config.green_api_token
)

# Initialize OpenAI client
ai_client = OpenAI(
    api_key=config.ai_api_key,
    timeout=30.0
)

# Global DeniDin instance for WhatsApp message handler
# Will be populated in __main__ block after initialize_app()
denidin_app = None


def _fetch_own_whatsapp_number() -> str:
    """bugfix-024: fetch DeniDin's own WhatsApp phone number ONCE, via a real Green
    API getWaSettings call - confirmed live (2026-08-05) to return {"phone": "<bare
    digits>", ...}, e.g. "972559723730". Needed because WhatsApp's native @-mention
    picker inserts the mentioned contact's raw phone number into message text, never
    a display name (see bugfix-024's spec for the incident this fixes) - the app
    needs its own number to deterministically recognize a self-mention.

    Reuses the module-level `bot` (never constructs a second GreenAPIBot - its own
    constructor has a real side effect of draining pending incoming notifications
    from the live Green API instance, which must only ever happen once, for the one
    real bot instance).

    Never raises - a failed/unreachable call degrades to "" (self-mention-by-number
    detection unavailable this run, everything else unaffected), matching this
    codebase's fail-open convention for non-critical startup data (CONSTITUTION §VI).
    Called once per `initialize_app()` call, never per message.
    """
    try:
        response = bot.api.account.getWaSettings()
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
                 group_membership_resolver=None, reminder_scheduler=None):
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
        self._logger = get_logger(__name__)
    
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
            user_phone=message.sender_id
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
    except Exception:
        pass


def initialize_app(config_dict: dict) -> DeniDin:
    """
    Initialize DeniDin app with provided configuration.
    Used by integration tests to create app instance programmatically.
    
    Args:
        config_dict: Configuration dictionary (from JSON)
        
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
    
    # Initialize OpenAI client
    ai_client = OpenAI(
        api_key=config.ai_api_key,
        timeout=30.0
    )
    
    # Initialize AI handler
    ai_handler = AIHandler(ai_client, config)

    # bugfix-024: resolve DeniDin's own WhatsApp number ONCE at startup (real Green
    # API call, never per-message) - see _fetch_own_whatsapp_number's docstring.
    ai_handler.own_whatsapp_number = _fetch_own_whatsapp_number()
    
    # Initialize WhatsApp handler (without media_handler initially)
    whatsapp_handler = WhatsAppHandler()

    # Feature 039: most-permissive-role RBAC resolution for group turns - built off
    # the module-level bot's own Green API groups client, never a new global.
    group_membership_resolver = GroupMembershipResolver(bot.api.groups, ai_handler.user_manager)

    # Create DeniDin instance (will be used as context for background threads and MediaHandler)
    denidin = DeniDin(
        ai_handler, config, whatsapp_handler, cleanup_thread=None,
        group_membership_resolver=group_membership_resolver
    )
    
    # Initialize MediaHandler with DeniDin context and attach to WhatsAppHandler
    media_handler = MediaHandler(denidin)
    whatsapp_handler.media_handler = media_handler
    
    # Initialize memory system if enabled
    if ai_handler.memory_enabled:
        # Run startup cleanup using denidin as context
        run_startup_cleanup(denidin)
        
        # Start cleanup thread - get interval from nested config structure
        cleanup_interval = 3600  # Default
        if hasattr(config, 'memory') and isinstance(config.memory, dict):
            session_config = config.memory.get('session', {})
            cleanup_interval = session_config.get('cleanup_interval_seconds', 3600)
        elif hasattr(config, 'session_cleanup_interval_seconds'):
            cleanup_interval = config.session_cleanup_interval_seconds
        
        cleanup_thread = SessionCleanupThread(denidin, cleanup_interval)
        cleanup_thread.start()

        # Update denidin with cleanup thread reference
        denidin.cleanup_thread = cleanup_thread

    # Feature 054: reminder delivery scheduler is deliberately NOT started here.
    # initialize_app() is the shared bootstrap tests/integration/ calls directly
    # (a process-global denidin_app singleton, reused across test files) -
    # starting a real APScheduler against the real `bot` object here would let
    # an ordinary test run reach bot.api.sending.sendMessage unattended, using
    # config.test.json's real (not sandboxed) Green API credentials. Every
    # OTHER real bot.api call in this codebase (mark_message_read,
    # send_typing_indicator) is safe in tests only because its trigger point
    # (bot.on_notification_received, fired from run_forever()'s live polling
    # loop) is never reached by any test - they dispatch straight to router
    # handler functions instead. The reminder scheduler follows that same
    # discipline: wired in __main__ below, alongside bot.run_forever() itself,
    # never inside this shared bootstrap. See tasks.md T013's note (2026-08-17)
    # for the incident this design avoided (caught before any real send
    # happened - test_data/reminders/reminders.db had zero rows at the time).

    # Feature 045: mark every non-blocked sender's incoming message as read, as early as
    # possible (before route_event dispatches to any handler) - see
    # src/utils/green_api_bot.py's mark_message_read/on_notification_received.
    def _on_notification_received(body: dict) -> None:
        chat_id = body.get("senderData", {}).get("chatId", "")
        is_blocked = bool(chat_id) and ai_handler.user_manager.get_user(chat_id).is_blocked
        mark_message_read(bot, body, is_blocked=is_blocked)

    bot.on_notification_received = _on_notification_received

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
        send_typing_indicator(bot, message.chat_id, is_blocked)

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
            user_phone=group_user_phone or message.sender_id
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
        sent_id_message = denidin_app.whatsapp_handler.send_response(notification, ai_response)
        if sent_id_message is not None:
            denidin_app.ai_handler.pending_approval_manager.attach_sent_message_id(
                message.chat_id, sent_id_message
            )
            denidin_app.ai_handler.pending_local_tool_approval_manager.attach_sent_message_id(
                message.chat_id, sent_id_message
            )
        logger.info(f"{tracking} Response sent to {message.sender_name}")

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
    send_typing_indicator(bot, message.chat_id, is_blocked)

    denidin_app.whatsapp_handler.handle_media_message(notification)


@bot.router.message(type_message=["textMessage", "extendedTextMessage"])
def handle_text_message(notification: Notification) -> None:
    """
    Handle incoming text messages from WhatsApp with comprehensive error handling.
    Phase 6: Memory System Integration

    Args:
        notification: Green API notification object containing message data
    """
    if denidin_app is None:
        _handle_not_initialized_error(notification, "text")
        return

    _process_conversational_message(notification)


@bot.router.message(type_message="contactMessage")
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
    if denidin_app is None:
        _handle_not_initialized_error(notification, "contact")
        return

    _process_conversational_message(notification)


@bot.router.message(type_message="contactsArrayMessage")
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
    if denidin_app is None:
        _handle_not_initialized_error(notification, "contacts array")
        return

    notification.answer(CONTACT_CARD_ONE_AT_A_TIME)


@bot.router.message(type_message="imageMessage")
def handle_image_message(notification: Notification) -> None:
    """
    Handle incoming image messages from WhatsApp.
    Routes to MediaHandler for image analysis.
    
    Args:
        notification: Green API notification object containing image data
    """
    if denidin_app is None:
        _handle_not_initialized_error(notification, "image")
        return
    
    _process_media_message(notification)


@bot.router.message(type_message="documentMessage")
def handle_document_message(notification: Notification) -> None:
    """
    Handle incoming document messages from WhatsApp.
    Routes to MediaHandler for document processing (PDF, DOCX, etc.).
    
    Args:
        notification: Green API notification object containing document data
    """
    if denidin_app is None:
        _handle_not_initialized_error(notification, "document")
        return
    
    _process_media_message(notification)


@bot.router.message(type_message="videoMessage")
def handle_video_message(notification: Notification) -> None:
    """
    Handle incoming video messages from WhatsApp.
    Routes to MediaHandler for video processing.
    
    Args:
        notification: Green API notification object containing video data
    """
    if denidin_app is None:
        _handle_not_initialized_error(notification, "video")
        return
    
    _process_media_message(notification)


@bot.router.message(type_message="audioMessage")
def handle_audio_message(notification: Notification) -> None:
    """
    Handle incoming audio messages from WhatsApp.
    Routes to MediaHandler for audio processing.
    
    Args:
        notification: Green API notification object containing audio data
    """
    if denidin_app is None:
        _handle_not_initialized_error(notification, "audio")
        return
    
    _process_media_message(notification)


@bot.router.message(type_message="interactiveButtonsResponse")
def handle_button_tap(notification: Notification) -> None:
    """
    Feature 047: handle a WhatsApp interactive-buttons tap resolving a pending
    document-creation approval (Feature 022).

    Registered via the plain router.message mechanism, NOT @bot.router.buttons(...) -
    research.md confirmed the library's own ButtonObserver only matches the older,
    deprecated button-reply types (buttonsResponseMessage/templateButtonsReplyMessage/
    listResponseMessage), never interactiveButtonsResponse (the type a real
    sendInteractiveButtons tap actually produces, per Gate Zero).

    Args:
        notification: Green API notification object containing the tap
    """
    if denidin_app is None:
        _handle_not_initialized_error(notification, "interactiveButtonsResponse")
        return

    from src.models.message import WhatsAppMessage  # local import - matches existing style

    message = WhatsAppMessage.from_notification(notification)
    button_data = notification.event.get("messageData", {}).get("interactiveButtonsResponse", {})
    selected_id = button_data.get("selectedId", "")
    stanza_id = button_data.get("stanzaId", "")

    ai_response = denidin_app.ai_handler.resolve_button_tap(
        chat_id=message.chat_id,
        selected_id=selected_id,
        stanza_id=stanza_id,
        message_id=message.message_id,
        user_phone=message.sender_id,
        sender=message.sender_display_name,
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


@bot.router.message()
def handle_unsupported_message_default(notification: Notification) -> None:
    """
    Catch-all handler for unsupported message types.
    Prevents silent drops - sends Hebrew error message to user.
    Called for any message type without a specific handler.
    
    Args:
        notification: Green API notification object containing message data
    """
    if denidin_app is None:
        _handle_not_initialized_error(notification, "unsupported")
        return
    
    denidin_app.whatsapp_handler.handle_unsupported_message(notification)



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
        'log_level': config.log_level,
        'data_root': config.data_root,
        'feature_flags': config.feature_flags,
        'godfather_phone': config.godfather_phone,
        'memory': config.memory,
        'constitution_config': config.constitution_config,
        'user_roles': config.user_roles,
        'mcp': config.mcp,
        'reminders': config.reminders
    }

    # Initialize app (handles memory system, cleanup thread, recovery)
    denidin = initialize_app(config_dict)

    # Set global denidin_app for WhatsApp message handler
    denidin_app = denidin

    # Feature 054: reminder delivery scheduler - deliberately started HERE, not
    # inside initialize_app() (see that function's comment for why: this is the
    # real, live-running app, gated the same way bot.run_forever() below is -
    # never reachable from initialize_app()'s test-harness callers). No feature
    # flag - unconditional, RBAC alone gates reminder *creation*.
    run_startup_reminder_sweep(denidin, bot)
    denidin.reminder_scheduler = start_reminder_scheduler(denidin, bot)
    
    # Perform orphaned session recovery if memory enabled
    if denidin.ai_handler.memory_enabled:
        logger.info("Starting orphaned session recovery...")
        recovery_result = denidin.ai_handler.recover_orphaned_sessions()
        
        logger.info(
            f"Session recovery complete: "
            f"{recovery_result.get('total_found', 0)} found, "
            f"{recovery_result.get('transferred_to_long_term', 0)} transferred, "
            f"{recovery_result.get('loaded_to_short_term', 0)} loaded, "
            f"{recovery_result.get('failed', 0)} failed"
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
            # no feature flag, always started in initialize_app())
            if denidin.reminder_scheduler is not None:
                logger.info("Stopping reminder delivery scheduler...")
                denidin.reminder_scheduler.shutdown(wait=False)

            # Raise KeyboardInterrupt to break out of bot.run_forever()
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
        # Start the WhatsApp message listener (blocking call)
        # Signal handlers will raise KeyboardInterrupt for graceful shutdown
        bot.run_forever()
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
    except Exception as e:
        # Catch any unexpected error to prevent crash
        logger.critical(
            f"Fatal error in bot.run_forever(): {e}",
            exc_info=True
        )
        logger.error("Application stopped due to fatal error - manual restart required")
        sys.exit(1)
