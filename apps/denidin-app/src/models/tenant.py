"""Tenant model for multi-tenancy (Feature 055).

See specs/in-progress/055-multiple-clients-godfathers/data-model.md for the full field
list ("Tenant Identity" / "Tenant Credentials" tables) and spec.md's
REQ-TENANT-001..005/REQ-CAP-005/REQ-PARITY-001 for the requirements this derives from.

A Tenant is both:
1. Static identity + this-environment credentials (the "joined" view TenantManager
   builds from tenants.json + config.<env>.json) — the original Phase 2 shape.
2. A fully self-contained messaging endpoint at runtime (added 2026-08-17, after
   direct discussion with the user about the App/Tenant split): once started, a
   Tenant owns its own Bot, AIHandler, WhatsAppHandler, MediaHandler, and
   GroupMembershipResolver, and registers its own 9 message-type handlers as BOUND
   METHODS on its own bot's router — never a module-level global, never a
   tenant_id parameter threaded through calls. Each handler only ever sees `self`;
   it doesn't know any other tenant exists. Outbound routing is automatically
   correct by construction (Green API's Notification.answer() is tied to whichever
   bot received it) — no separate gateway/dispatch layer needed.
"""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from whatsapp_chatbot_python import Notification

from src.constants.error_messages import (
    CONTACT_CARD_ONE_AT_A_TIME,
    ERROR_PROCESSING_MESSAGE_TRY_AGAIN,
)
from src.handlers.media_handler import MediaHandler
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.managers.group_membership_resolver import GroupMembershipResolver
from src.utils.green_api_bot import DeniDinGreenAPIBot, mark_message_read, send_typing_indicator
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Tenant:
    """One tenant: identity + credentials (always present), plus runtime state
    (bot/ai_handler/whatsapp_handler/group_membership_resolver — None until
    start() is called)."""

    tenant_id: str
    account_name: str
    bot_name: str
    godfathers: List[str]
    admins: List[str]
    constitution_supplement_file: str
    capability_selection: Dict[str, str]
    environment_data_root: str
    green_api: Optional[Dict[str, str]] = None
    openai: Optional[Dict[str, str]] = None
    mcp_auth_token: Optional[str] = None

    # Runtime state — set by start(), None until then.
    bot: Optional[Any] = field(default=None, repr=False)
    ai_handler: Optional[Any] = field(default=None, repr=False)
    whatsapp_handler: Optional[Any] = field(default=None, repr=False)
    media_handler: Optional[Any] = field(default=None, repr=False)
    group_membership_resolver: Optional[Any] = field(default=None, repr=False)
    config: Optional[Any] = field(default=None, repr=False)
    _listener_thread: Optional[threading.Thread] = field(default=None, repr=False)

    def __post_init__(self):
        """Validate required identity/credential fields."""
        if not self.tenant_id:
            raise ValueError("Tenant tenant_id cannot be empty")
        if not self.account_name:
            raise ValueError("Tenant account_name cannot be empty")
        if not self.bot_name:
            raise ValueError("Tenant bot_name cannot be empty")
        if not self.openai:
            raise ValueError(
                f"Tenant '{self.account_name}' is missing its required openai credential "
                "(REQ-TENANT-003: OpenAI credential is per-tenant, not optional)"
            )
        if not self.green_api:
            raise ValueError(
                f"Tenant '{self.account_name}' is missing its required green_api credential "
                "(a tenant needs a messaging provider to start at all — REQ-CAP-005)"
            )
        if "messaging_provider" not in self.capability_selection:
            raise ValueError(
                f"Tenant '{self.account_name}' capability_selection is missing "
                "'messaging_provider' (REQ-CAP-001/REQ-CAP-005: required to start at all)"
            )

    @property
    def data_root(self) -> Path:
        """Derived, read-only: {environment_data_root}/{tenant_id}/ — never a stored field."""
        return Path(self.environment_data_root) / self.tenant_id

    @property
    def has_invoicing_provider(self) -> bool:
        """REQ-CAP-005: a tenant may legitimately have no invoicing provider configured.

        True only when both an implementation is selected AND credentials (the MCP bearer
        token) actually exist for it — a dangling capability_selection entry with no token
        is not a working capability.
        """
        return bool(self.mcp_auth_token) and "invoicing_provider" in self.capability_selection

    # ------------------------------------------------------------------
    # Runtime startup
    # ------------------------------------------------------------------

    def start(self, base_config, bot_factory: Callable[..., Any] = DeniDinGreenAPIBot) -> None:
        """Build this tenant's complete, self-contained messaging stack and start
        listening — its own AIHandler, WhatsAppHandler, MediaHandler,
        GroupMembershipResolver, and Bot, with all 9 message-type handlers
        registered as bound methods on its own bot's router.

        `bot_factory` is injectable (default: the real DeniDinGreenAPIBot) so tests
        can supply a fake bot instead of making real Green API calls — construction
        of the real bot class always makes at least one real HTTP call.
        """
        # Local import: breaks a circular import (tenant_ai_handler_factory.py
        # imports Tenant for its type hint).
        from src.managers.tenant_ai_handler_factory import TenantAIHandlerFactory

        self.ai_handler = TenantAIHandlerFactory.build(self, base_config)
        self.config = self.ai_handler.config

        self.whatsapp_handler = WhatsAppHandler()
        self.media_handler = MediaHandler(self)
        self.whatsapp_handler.media_handler = self.media_handler

        self.bot = bot_factory(self.green_api["instance_id"], self.green_api["api_token"])

        self.group_membership_resolver = GroupMembershipResolver(
            self.bot.api.groups, self.ai_handler.user_manager
        )

        self.ai_handler.own_whatsapp_number = self._fetch_own_whatsapp_number()

        def _on_notification_received(body: dict) -> None:
            """Feature 045: mark every non-blocked sender's message as read, as
            early as possible — before route_event dispatches to any handler."""
            chat_id = body.get("senderData", {}).get("chatId", "")
            is_blocked = bool(chat_id) and self.ai_handler.user_manager.get_user(chat_id).is_blocked
            mark_message_read(self.bot, body, is_blocked=is_blocked)

        self.bot.on_notification_received = _on_notification_received

        self._register_handlers()

        self._listener_thread = threading.Thread(target=self.bot.run_forever, daemon=True)
        self._listener_thread.start()

    def _register_handlers(self) -> None:
        """Register all 9 message-type handlers as bound methods on this tenant's
        own bot.router — each one only ever sees `self`, never any other tenant."""
        router = self.bot.router
        router.message(type_message=["textMessage", "extendedTextMessage"])(
            self._handle_text_message
        )
        router.message(type_message="contactMessage")(self._handle_contact_message)
        router.message(type_message="contactsArrayMessage")(
            self._handle_contacts_array_message
        )
        router.message(type_message="imageMessage")(self._handle_image_message)
        router.message(type_message="documentMessage")(self._handle_document_message)
        router.message(type_message="videoMessage")(self._handle_video_message)
        router.message(type_message="audioMessage")(self._handle_audio_message)
        router.message(type_message="interactiveButtonsResponse")(self._handle_button_tap)
        router.message()(self._handle_unsupported_message_default)

    def _fetch_own_whatsapp_number(self) -> str:
        """bugfix-024, ported per-tenant: fetch this tenant's own WhatsApp phone
        number once via its own bot's real getWaSettings call — needed to
        deterministically recognize a self-mention (WhatsApp inserts the raw
        phone number, never a display name). Never raises — fails open to "".
        """
        try:
            response = self.bot.api.account.getWaSettings()
            if response.code == 200 and isinstance(response.data, dict):
                phone = response.data.get("phone", "")
                if phone:
                    logger.info(
                        f"[{self.bot_name}] Resolved own WhatsApp number for "
                        f"self-mention detection: {phone}"
                    )
                    return phone
            logger.warning(
                f"[{self.bot_name}] getWaSettings did not return a usable 'phone' field "
                f"(code={response.code}) — self-mention-by-number detection unavailable"
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                f"[{self.bot_name}] Failed to fetch own WhatsApp number: {e} — "
                "self-mention-by-number detection unavailable"
            )
        return ""

    # ------------------------------------------------------------------
    # Message-type handlers (bound methods — ported from denidin.py's former
    # module-level free functions, `denidin_app.X` → `self.X`, `bot` → `self.bot`;
    # the old `if denidin_app is None` guard is gone by construction — these are
    # never registered until self.ai_handler etc. already exist, see start()).
    # ------------------------------------------------------------------

    def _handle_text_message(self, notification: Notification) -> None:
        self._process_conversational_message(notification)

    def _handle_contact_message(self, notification: Notification) -> None:
        """Feature 030: a shared WhatsApp contact card flows into the same
        conversational pipeline as typed text."""
        self._process_conversational_message(notification)

    def _handle_contacts_array_message(self, notification: Notification) -> None:
        """Feature 030: multiple contacts shared at once are declined outright,
        no AIHandler/OpenAI call at all."""
        notification.answer(CONTACT_CARD_ONE_AT_A_TIME)

    def _handle_image_message(self, notification: Notification) -> None:
        self._process_media_message(notification)

    def _handle_document_message(self, notification: Notification) -> None:
        self._process_media_message(notification)

    def _handle_video_message(self, notification: Notification) -> None:
        self._process_media_message(notification)

    def _handle_audio_message(self, notification: Notification) -> None:
        self._process_media_message(notification)

    def _handle_button_tap(self, notification: Notification) -> None:
        """Feature 047: resolve a WhatsApp interactive-buttons tap against this
        tenant's own pending-approval state."""
        from src.models.message import WhatsAppMessage  # local import - matches existing style

        message = WhatsAppMessage.from_notification(notification)
        button_data = notification.event.get("messageData", {}).get(
            "interactiveButtonsResponse", {}
        )
        selected_id = button_data.get("selectedId", "")
        stanza_id = button_data.get("stanzaId", "")

        ai_response = self.ai_handler.resolve_button_tap(
            chat_id=message.chat_id,
            selected_id=selected_id,
            stanza_id=stanza_id,
            message_id=message.message_id,
            user_phone=message.sender_id,
            sender=message.sender_display_name,
        )

        if ai_response is None:
            # Stale/superseded tap, or no pending approval at all — silently
            # ignore, send nothing at all.
            logger.info(
                f"[{self.bot_name}] Button tap produced no resolution for "
                f"chat={message.chat_id!r} (selected_id={selected_id!r}, "
                f"stanza_id={stanza_id!r}) — sending nothing"
            )
            return

        sent_id_message = self.whatsapp_handler.send_response(notification, ai_response)
        if sent_id_message is not None:
            self.ai_handler.pending_approval_manager.attach_sent_message_id(
                message.chat_id, sent_id_message
            )
        logger.info(
            f"[{self.bot_name}] Button tap resolved and response sent for "
            f"chat={message.chat_id!r}"
        )

    def _handle_unsupported_message_default(self, notification: Notification) -> None:
        """Catch-all — prevents silent drops for any message type without a
        specific handler."""
        self.whatsapp_handler.handle_unsupported_message(notification)

    # ------------------------------------------------------------------
    # Shared processing logic (ported from denidin.py's former module-level
    # _process_conversational_message/_process_media_message/
    # _resolve_group_user_phone free functions)
    # ------------------------------------------------------------------

    def _resolve_group_user_phone(self, message) -> Optional[str]:
        """Feature 039 (US4): for a group message, resolve the most-permissive
        member's phone via this tenant's own GroupMembershipResolver."""
        if not message.is_group or self.group_membership_resolver is None:
            return None

        resolution = self.group_membership_resolver.resolve(message.chat_id)
        return resolution.phone if resolution else None

    def _process_conversational_message(self, notification: Notification) -> None:
        """Shared turn-processing logic for any message type that flows into the
        conversational AIHandler pipeline. Ported verbatim from denidin.py's former
        module-level function, operating on self instead of a module global."""
        try:
            if not self.whatsapp_handler.validate_message_type(notification):
                self.whatsapp_handler.handle_unsupported_message(notification)
                return

            message = self.whatsapp_handler.process_notification(notification)

            tracking = (
                f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp.isoformat()}]"
            )

            logger.info(
                f"[{self.bot_name}] {tracking} Received message from "
                f"{message.sender_name} ({message.sender_id}): {message.text_content[:100]}..."
            )

            group_user_phone = self._resolve_group_user_phone(message)

            ai_request = self.ai_handler.create_request(message, user_phone=group_user_phone)
            logger.debug(f"[{self.bot_name}] {tracking} Created AI request {ai_request.request_id}")

            is_blocked = self.ai_handler.user_manager.get_user(message.sender_id).is_blocked
            send_typing_indicator(self.bot, message.chat_id, is_blocked)

            ai_response = self.ai_handler.get_response(
                ai_request,
                sender=message.sender_display_name,
                user_phone=group_user_phone or message.sender_id,
            )
            logger.info(
                f"[{self.bot_name}] {tracking} AI response generated: "
                f"{ai_response.tokens_used} tokens, {len(ai_response.response_text)} chars"
            )

            if not ai_response.should_reply:
                logger.info(
                    f"[{self.bot_name}] {tracking} No reply sent "
                    "(should_reply=False, no-reply sentinel)"
                )
                return

            sent_id_message = self.whatsapp_handler.send_response(notification, ai_response)
            if sent_id_message is not None:
                self.ai_handler.pending_approval_manager.attach_sent_message_id(
                    message.chat_id, sent_id_message
                )
            logger.info(f"[{self.bot_name}] {tracking} Response sent to {message.sender_name}")

        except Exception as e:  # pylint: disable=broad-except
            try:
                tracking = (
                    f"[msg_id={message.message_id}] "
                    f"[recv_ts={message.received_timestamp.isoformat()}]"
                )
                logger.error(
                    f"[{self.bot_name}] {tracking} Unexpected error processing message: {e}",
                    exc_info=True,
                )
            except (NameError, AttributeError, UnboundLocalError):
                logger.error(
                    f"[{self.bot_name}] Unexpected error processing message "
                    f"(no tracking available): {e}",
                    exc_info=True,
                )

            try:
                notification.answer(ERROR_PROCESSING_MESSAGE_TRY_AGAIN)
                logger.info(f"[{self.bot_name}] Generic fallback message sent to user")
            except Exception as fallback_error:  # pylint: disable=broad-except
                logger.error(
                    f"[{self.bot_name}] Failed to send fallback message: {fallback_error}",
                    exc_info=True,
                )

    def _process_media_message(self, notification: Notification) -> None:
        """Feature 048: shared wrapper adding the typing indicator around media
        processing. Ported verbatim from denidin.py's former module-level function."""
        from src.models.message import WhatsAppMessage  # local import - matches existing style

        message = WhatsAppMessage.from_notification(notification)
        is_blocked = self.ai_handler.user_manager.get_user(message.sender_id).is_blocked
        send_typing_indicator(self.bot, message.chat_id, is_blocked)

        self.whatsapp_handler.handle_media_message(notification)
