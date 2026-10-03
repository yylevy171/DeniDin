"""
WhatsAppHandler - Handles WhatsApp message processing with retry logic
Phase 5: US3 - Error Handling & Resilience
"""
from dataclasses import dataclass
from typing import Any, cast, Optional
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    retry_if_exception,
)
from whatsapp_chatbot_python import Notification
from src.constants.error_messages import APPROVAL_BUTTONS_SEND_FAILED
from src.managers.pending_approval_manager import BUTTON_ID_APPROVE, BUTTON_ID_DECLINE
from src.models.message import WhatsAppMessage, AIResponse
from src.models.fee_agreement import GeneratedDocument
from src.utils.green_api_bot import send_reaction
from src.utils.logger import get_logger
from src.utils.wire_log import audit_wire, debug_wire

logger = get_logger(__name__)


@dataclass(frozen=True)
class SentMessage:
    """A message this handler just sent: its text and WhatsApp idMessage (None when
    Green API didn't return one). `as_buttons` - sent as interactive approval
    buttons; `is_notice` - a notice sent instead of the requested reply (the
    approval buttons could not be sent)."""
    text: str
    whatsapp_id_message: Optional[str] = None
    as_buttons: bool = False
    is_notice: bool = False


def _id_message_of(result: Any) -> Optional[str]:
    """The idMessage off a Green API send result, or None."""
    data = getattr(result, "data", None)
    return data.get("idMessage") if isinstance(data, dict) else None


def _is_retryable_send_error(exception: BaseException) -> bool:
    """True for a timeout/connection error, or an HTTPError NOT in the
    4xx range - the actual gate that makes "never retry a 4xx" real,
    since a plain `retry_if_exception_type` would match every
    requests.HTTPError regardless of status code (re-raising inside the
    function body does not change what the retry decorator itself sees)."""
    if isinstance(exception, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exception, requests.HTTPError):
        status_code = getattr(getattr(exception, 'response', None), 'status_code', None)
        return not (status_code is not None and 400 <= status_code < 500)
    return False


class WhatsAppHandler:
    """
    DeniDin's WhatsApp side (REQ-063-08): parses incoming notifications and sends
    messages, with the CONSTITUTION retry policy on Green API calls. Knows nothing
    of sessions - every send returns what was sent (SentMessage), and DeniDin stores it.
    """

    def __init__(self, denidin: Any):
        """
        Args:
            denidin: the DeniDin object - only its live bot (`green_api_bot`) is read.
        """
        self.denidin = denidin
        # bugfix-024: DeniDin's own WhatsApp number (bare digits), resolved once at
        # startup by initialize_app (the player sets it itself); "" when unknown.
        self.own_whatsapp_number = ""
        logger.debug("WhatsAppHandler initialized")

    @property
    def green_api_bot(self) -> Any:
        """The live bot (Feature 083's sendFileByUpload, Feature 084's reactions) -
        set on DeniDin by __main__; None in tests and the player."""
        return getattr(self.denidin, "green_api_bot", None)

    @property
    def own_jid(self) -> Optional[str]:
        """DeniDin's own WhatsApp id ("<number>@c.us"), or None when unknown."""
        return f"{self.own_whatsapp_number}@c.us" if self.own_whatsapp_number else None

    def normalize_self_mentions(self, text: str) -> str:
        """bugfix-024: rewrites "@<DeniDin's own number>" (WhatsApp's wire format for a
        mention of DeniDin) into "@DeniDin" - an exact match on the bare-digit number
        (2026-08-05). No-op when the number is unknown."""
        if not self.own_whatsapp_number:
            return text
        return text.replace(f"@{self.own_whatsapp_number}", "@DeniDin")

    def process_notification(self, notification: Notification) -> WhatsAppMessage:
        """
        Process a Green API notification into a WhatsAppMessage, with mentions of
        DeniDin's own number rewritten to "@DeniDin".

        Args:
            notification: Green API notification object

        Returns:
            WhatsAppMessage object
        """
        # Use the from_notification factory method which handles timestamp, message_id, etc.
        message = WhatsAppMessage.from_notification(notification)
        message.text_content = self.normalize_self_mentions(message.text_content)

        logger.debug(
            f"Processed notification: {message.message_id} from {message.sender_name} "
            f"(group: {message.is_group})"
        )

        return message

    def validate_message_type(self, notification: Notification) -> bool:
        """
        Validate that the message type is supported (textMessage only).

        Args:
            notification: Green API notification

        Returns:
            True if message type is supported, False otherwise
        """
        message_type = notification.event.get('messageData', {}).get('typeMessage', '')
        logger.debug(f"received whatsapp notification: {notification}")

        # contactMessage (Feature 030 - shared WhatsApp contact card) flows through the
        # same conversational pipeline as text messages, see _process_conversational_message.
        if message_type not in ('extendedTextMessage', 'textMessage', 'contactMessage'):
            logger.warning(f"Unsupported message type received: {message_type}")
            return False

        return True

    def send_text(self, notification: Notification, text: str, *, wire_context: str = "text") -> SentMessage:
        """The one plain-text send for a canned/notice reply: sends `text` in
        `notification`'s chat and wire-logs it (an exception propagates to the caller
        unchanged)."""
        result = notification.answer(text)
        _wire_payload = {"chat_id": notification.event.get("senderData", {}).get("chatId", ""), "message": text}
        audit_wire("whatsapp", "out", wire_context, _wire_payload)
        debug_wire("whatsapp", "out", wire_context, _wire_payload)
        return SentMessage(text=text, whatsapp_id_message=_id_message_of(result))

    def send_progress_update(self, notification: Notification, text: str) -> SentMessage:
        """Feature 080: an interim message mid-turn, in `notification`'s chat - the same
        notification.answer send the final reply uses, wire-logged both directions."""
        chat_id = notification.event.get("senderData", {}).get("chatId", "")
        _wire_payload = {"chat_id": chat_id, "message": text}
        audit_wire("whatsapp", "out", "progress_update", _wire_payload)
        debug_wire("whatsapp", "out", "progress_update", _wire_payload)
        result = notification.answer(text)
        audit_wire("whatsapp", "in", "progress_update", {"chat_id": chat_id, "message": repr(result)})
        debug_wire("whatsapp", "in", "progress_update", {"result": repr(result)})
        return SentMessage(text=text, whatsapp_id_message=_id_message_of(result))

    def send_reaction(self, chat_id: str, id_message: str, emoji: str) -> bool:
        """Feature 084: sets (or, with emoji "", clears) a reaction on a message.
        False - never raises - on any failure or without a live bot."""
        if self.green_api_bot is None:
            logger.warning(f"[084] No live bot - reaction on {id_message!r} in {chat_id!r} not sent")
            return False
        return send_reaction(self.green_api_bot, chat_id, id_message, emoji)

    @retry(
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError, requests.HTTPError)),
        stop=stop_after_attempt(2),  # Hardcoded: Initial attempt + 1 retry = 2 total attempts
        wait=wait_fixed(1),  # 1 second wait
        reraise=True
    )
    def _send_with_retry(self, notification: Notification, message: str) -> Any:
        """
        Send message via Green API with retry logic.
        Retries ONCE (max 2 attempts) only on 5xx errors and network errors, waits 1 second.
        Does NOT retry 4xx client errors.

        Args:
            notification: Green API notification to reply to
            message: Message text to send

        Raises:
            requests.RequestException: After 2 attempts (1 retry) or immediately on 4xx errors
        """
        try:
            return notification.answer(message)
        except requests.HTTPError as e:
            # Check if this is a 4xx error that shouldn't be retried
            if hasattr(e, 'response') and e.response is not None:
                if 400 <= e.response.status_code < 500:
                    logger.error(f"HTTP {e.response.status_code} client error - not retrying: {e}")
                    raise  # Don't retry 4xx errors
                # 5xx errors: let tenacity retry them by raising
            raise


    @retry(
        retry=retry_if_exception(_is_retryable_send_error),
        stop=stop_after_attempt(2),  # Initial attempt + 1 retry = 2 total attempts
        wait=wait_fixed(1),
        reraise=True
    )
    def _send_file_with_retry(self, chat_id: str, path: str, file_name: str, caption: str) -> None:
        """Same CONSTITUTION retry policy as _send_with_retry: one retry on
        5xx/timeout/connection error after 1s, never on a 4xx client error."""
        if self.green_api_bot is None:  # send_fee_agreement_document checks first
            raise RuntimeError("no live bot object injected")
        try:
            self.green_api_bot.api.sending.sendFileByUpload(
                chat_id, path, fileName=file_name, caption=caption,
            )
        except requests.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None:
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Green API 400-range error sending file - not retrying: {e}")
            raise

    def send_document_response(
        self, generated: GeneratedDocument, chat_id: str, caption: str,
    ) -> bool:
        """
        Feature 083 (contracts/whatsapp-file-delivery.md): sends a generated
        fee agreement .docx file to `chat_id` via `sendFileByUpload`. Refuses
        outright (no call attempted) if the document has not passed
        verification - the AI's own verify_fee_agreement_document judgment
        is the sole gate for the finished document (research.md #4); this is
        belt-and-suspenders, not the primary gate.

        Deletion of the temp file itself is the caller's responsibility
        (FeeAgreementToolHandler._cleanup, in every case - success or
        failure) - this method never touches the filesystem beyond reading
        the file to upload it.

        Returns True on a confirmed successful send, False on any failure
        (never raises - a friendly, generic failure is what the caller's
        tool-call-error payload surfaces to the model, per CONSTITUTION's
        "no raw exception text to the user" rule).
        """
        if not generated.verified:
            logger.error(
                f"[083] Refusing to send unverified document_id={generated.document_id!r} - "
                "verify_fee_agreement_document must be called and confirmed clean first."
            )
            return False
        if self.green_api_bot is None:
            logger.error("[083] Cannot send fee agreement document - no live bot object injected.")
            return False

        try:
            self._send_file_with_retry(
                chat_id, str(generated.temp_path), generated.temp_path.name, caption,
            )
            logger.info(
                f"[083] Fee agreement document sent: document_id={generated.document_id!r}, "
                f"chat_id={chat_id!r}"
            )
            _wire_payload = {"chat_id": chat_id, "message": f"[fee agreement document: {generated.temp_path.name}]"}
            audit_wire("whatsapp", "out", "file", _wire_payload)
            debug_wire("whatsapp", "out", "file", _wire_payload)
            return True
        except (requests.HTTPError, requests.Timeout, requests.ConnectionError) as e:
            logger.error(
                f"[083] Failed to send fee agreement document_id={generated.document_id!r} "
                f"after retry: {e}", exc_info=True
            )
            return False

    def send_response(self, notification: Notification, response: AIResponse) -> Optional[SentMessage]:
        """
        Send AI response back to WhatsApp with error handling.

        Args:
            notification: Green API notification to reply to
            response: AI response to send

        Returns:
            What was sent - the reply (Feature 047: as_buttons when it went out as
            approval buttons), or the notice sent instead when the buttons failed - or
            None when nothing was sent (should_reply=False, or an empty reply).
        """
        # bugfix-028 B5: the send boundary is the last place that can tell a
        # deliberate silence from a broken turn, and it used to check neither.
        # Anything that didn't raise was logged as "Response sent successfully",
        # including a literally empty message (sessions 047cacb7 turn 22,
        # 12e158e2 turn 16, logged as "0 chars").
        if not response.should_reply:
            logger.info(
                f"No reply owed for request {response.request_id} (should_reply=False) - "
                f"sending nothing, as intended."
            )
            return None
        if not (response.response_text and response.response_text.strip()):
            # Unreachable via AIResponse's own contract, which refuses to build
            # this - kept as a boundary guard because "the user got nothing and
            # nobody noticed" is the failure being eliminated, and defence in
            # depth is cheap here.
            logger.error(
                f"Refusing to send an empty reply for request {response.request_id} - "
                f"a zero-character message is not a response."
            )
            return None

        # Feature 047: a turn that just created/refreshed a pending approval is sent
        # as interactive buttons instead of plain text - a fully separate send path
        # (different Green API endpoint, different failure handling: an error is
        # surfaced rather than silently falling back to plain text, per
        # spec.md Clarifications). Every other turn's behavior below is unchanged.
        if response.offer_approval_buttons:
            return self._send_approval_buttons(notification, response)

        try:
            logger.debug(f"Sending response for request {response.request_id}")

            # Use retry wrapper for actual send
            result = self._send_with_retry(notification, response.response_text)

            logger.info(
                f"Response sent successfully for request {response.request_id}: "
                f"{len(response.response_text)} chars"
            )
            _wire_payload = {"chat_id": notification.event.get("senderData", {}).get("chatId", ""),
                             "message": response.response_text}
            audit_wire("whatsapp", "out", "text", _wire_payload)
            debug_wire("whatsapp", "out", "text", _wire_payload)
            return SentMessage(text=response.response_text, whatsapp_id_message=_id_message_of(result))

        except requests.HTTPError as e:
            # Log specific HTTP error details
            status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'

            if status_code == 400:
                logger.error(f"Green API 400 Bad Request error: {e}", exc_info=True)
            elif status_code == 401:
                logger.error(f"Green API 401 Authentication error: {e}", exc_info=True)
            elif status_code == 429:
                logger.error(f"Green API 429 Rate limit error: {e}", exc_info=True)
            elif status_code == 500:
                logger.error(f"Green API 500 Server error: {e}", exc_info=True)
            else:
                logger.error(f"Green API HTTP {status_code} error: {e}", exc_info=True)

            raise  # Re-raise after logging

        except requests.Timeout as e:
            logger.error(f"Green API timeout error: {e}", exc_info=True)
            raise

        except requests.ConnectionError as e:
            logger.error(f"Green API connection error: {e}", exc_info=True)
            raise

        except requests.RequestException as e:
            logger.error(f"Green API request error: {e}", exc_info=True)
            raise

        except Exception as e:
            logger.error(f"Unexpected error sending response: {e}", exc_info=True)
            raise

    def _send_approval_buttons(self, notification: Notification, response: AIResponse) -> Optional[SentMessage]:
        """
        Feature 047: send response.response_text (the existing 📋 לאישור: block,
        unmodified) as WhatsApp interactive buttons ("כן"/"לא") instead of plain text.

        Per contracts/whatsapp-buttons-send.md: whatsapp_api_client_python's underlying
        GreenAPI client is configured with raise_errors=False (this codebase's actual
        default - confirmed by reading API.py, not assumed), so a failed send does NOT
        raise - it comes back as a Response with code != 200 / data not a dict. Checking
        the Response's own code/data is therefore the correct (and only reliable) way to
        detect failure here, not a try/except around the call.

        Returns:
            The sent buttons message on success. On any failure, the distinct
            plain-text error notice sent instead (is_notice - never a silent fallback
            to the approval prompt itself, per spec.md Clarifications), or None when
            even that could not be sent.
        """
        buttons = [
            {"type": "reply", "buttonId": BUTTON_ID_APPROVE, "buttonText": "כן"},
            {"type": "reply", "buttonId": BUTTON_ID_DECLINE, "buttonText": "לא"},
        ]

        try:
            result = notification.answer_with_interactive_buttons(response.response_text, buttons)
        except Exception as e:  # pylint: disable=broad-except
            # Defensive only (per the note above, this client does not normally raise) -
            # a genuinely unexpected exception (e.g. a bug in the library itself) must
            # still be treated as a send failure, not propagate and crash the turn.
            logger.error(
                f"Unexpected exception sending approval buttons for request "
                f"{response.request_id}: {e}", exc_info=True
            )
            result = None

        id_message = None
        if result is not None and result.code == 200 and isinstance(result.data, dict):
            id_message = result.data.get("idMessage")

        if id_message is None:
            logger.error(
                f"Failed to send approval buttons for request {response.request_id}: "
                f"code={getattr(result, 'code', None)!r}, "
                f"error={getattr(result, 'error', None)!r}"
            )
            try:
                notice = self.send_text(notification, APPROVAL_BUTTONS_SEND_FAILED)
            except Exception as notice_error:  # pylint: disable=broad-except
                logger.error(
                    f"Failed to send approval-buttons failure notice for request "
                    f"{response.request_id}: {notice_error}", exc_info=True
                )
                return None
            return SentMessage(text=notice.text, whatsapp_id_message=notice.whatsapp_id_message,
                               is_notice=True)

        logger.info(
            f"Approval buttons sent successfully for request {response.request_id}: "
            f"idMessage={id_message}"
        )
        _wire_payload = {"chat_id": notification.event.get("senderData", {}).get("chatId", ""),
                         "message": response.response_text}
        audit_wire("whatsapp", "out", "buttons", _wire_payload)
        debug_wire("whatsapp", "out", "buttons", _wire_payload)
        return SentMessage(text=response.response_text, whatsapp_id_message=cast(str, id_message),
                           as_buttons=True)

    def is_media_message(self, notification: Notification) -> bool:
        """
        Check if notification contains a media message.

        Args:
            notification: Green API notification

        Returns:
            True if message is a media type (image, document, video), False otherwise

        Feature 076 (Q5, FR-008): audioMessage removed - voice notes are not
        transcribed (the media pipeline only accepts jpg/png/pdf/docx), so it
        now routes to the canned "unsupported" reply (ERROR_REPLY_TYPES in
        denidin.py) instead of the media pipeline. videoMessage/imageMessage/
        documentMessage are unchanged.
        """
        message_type = notification.event.get('messageData', {}).get('typeMessage', '')
        return message_type in ['imageMessage', 'documentMessage', 'videoMessage']

    def get_media_type(self, notification: Notification) -> str:
        """
        Get the media message type from notification.

        Args:
            notification: Green API notification

        Returns:
            Media type string (e.g., 'imageMessage', 'documentMessage')
        """
        return cast(str, notification.event.get('messageData', {}).get('typeMessage', ''))

    def is_supported_media_message(self, notification: Notification) -> bool:
        """
        Check if the media message type is supported for processing.
        Currently only imageMessage and documentMessage are supported.
        Video and audio are future scope.

        Args:
            notification: Green API notification

        Returns:
            True if media type is supported, False otherwise
        """
        message_type = self.get_media_type(notification)
        return message_type in ['imageMessage', 'documentMessage']
