"""
Corrected GreenAPIBot subclass (bugfix-020).

whatsapp_chatbot_python.Bot._delete_notifications_at_startup and Bot.run_forever both assume
Response.data is always a dict once the HTTP status is 200. Green API's own docs state an empty
notification queue can end in a genuinely empty HTTP body (not the JSON literal `null`), and
whatsapp_api_client_python.Response.__init__ turns any JSON-decode failure - including that empty
body - into the fallback STRING "[]" rather than None/[]. A non-empty string is truthy, so neither
library method's `if not response.data` guard fires, and both crash indexing that string with a
dict key ("receiptId"/"body") - a hard crash at startup, and a caught-but-noisy 5s stall on every
empty poll cycle during run_forever().

Re-implements both call sites with an is-it-actually-a-dict check instead, via subclassing
(Template Method) rather than monkey-patching the third-party library (CONSTITUTION XVII).
"""
import logging
import time
from typing import Any, Callable, Optional

from whatsapp_chatbot_python import GreenAPIBot, GreenAPIBotError

from src.utils.logger import get_logger
from src.utils.whatsapp_audit_log import log_outbound

logger = get_logger(__name__)


def _notification_data_or_none(data: Any) -> Optional[dict]:
    """Returns `data` if it is a real notification payload (a dict), else None.

    Treats every other shape Response.data can take - None (documented `null` body), "[]" (the
    library's own JSON-decode-failure fallback for a truly empty body), or any other non-dict -
    as "queue empty, nothing to do here".
    """
    return data if isinstance(data, dict) else None


def _extract_read_receipt_target(body: dict) -> Optional[tuple]:
    """Feature 045: pulls (chatId, idMessage) out of a raw Green API notification body,
    or None if either is missing - the body shape is a plain dict straight off the wire
    (not yet parsed into a WhatsAppMessage), so this is a defensive best-effort lookup,
    not a validated-schema read.
    """
    id_message = body.get("idMessage")
    chat_id = body.get("senderData", {}).get("chatId")
    if not id_message or not chat_id:
        return None
    return (chat_id, id_message)


def mark_message_read(bot: Any, body: dict, is_blocked: bool) -> None:
    """Feature 045: best-effort read-receipt for an incoming message, fired as early as
    possible (before RBAC/session/AI processing) for every non-blocked sender. Never
    raises - a failure here is purely cosmetic and must never break message processing;
    it is logged only, never retried (see spec.md Q5).
    """
    if is_blocked:
        return

    target = _extract_read_receipt_target(body)
    if target is None:
        return

    chat_id, id_message = target
    try:
        bot.api.marking.readChat(chat_id, idMessage=id_message)
    except Exception as error:  # pylint: disable=broad-except
        logger.warning(
            f"Failed to mark message as read (chatId={chat_id}, idMessage={id_message}): {error}"
        )


def send_proactive_message(bot: Any, chat_id: str, message: str) -> Optional[str]:
    """Feature 054 (reminders): send an unprompted WhatsApp message - NOT a reply
    to any incoming notification, unlike every other send in this codebase
    (WhatsAppHandler.send_response always answers a real Notification). Called
    from the reminder delivery sweep, a background thread with no Notification
    object to answer through.

    Calls straight through to bot.api.sending.sendMessage(chatId, message) on
    the shared module-level `bot` object (never construct a second GreenAPIBot -
    its constructor drains pending notifications as a side effect, must only
    ever happen once for the one real bot instance, per denidin.py's existing
    documented constraint).

    Returns the sent idMessage on success, None on failure - logged, never
    raises, same best-effort-response-checking convention as
    WhatsAppHandler._send_approval_buttons (the library's raise_errors default
    is False, so a failed send returns a Response rather than raising).

    No lock around this call, by explicit user decision (2026-08-16) -
    bot.api.session (a plain requests.Session) is shared with the existing
    polling loop's own concurrent HTTP calls, not a proven-thread-safe pattern,
    but an accepted, unmitigated residual risk (low probability, low impact if
    it manifests - an occasional HTTP hiccup, not data corruption). See
    specs/in-progress/054-reminders-functionality-mgmt/research.md's Gate Zero
    for the live verification this call still needs before being trusted.
    """
    try:
        response = bot.api.sending.sendMessage(chat_id, message)
    except Exception as error:  # pylint: disable=broad-except
        logger.error(f"Failed to send proactive message (chatId={chat_id}): {error}", exc_info=True)
        return None

    if response is None or getattr(response, "code", None) != 200 or not isinstance(response.data, dict):
        logger.error(
            f"Proactive message send did not succeed (chatId={chat_id}): "
            f"code={getattr(response, 'code', None)!r}, data={getattr(response, 'data', None)!r}"
        )
        return None

    id_message = response.data.get("idMessage")
    logger.info(f"Sent proactive message (chatId={chat_id}, idMessage={id_message})")
    log_outbound(chat_id, message, kind="proactive")
    return id_message


def send_typing_indicator(bot: Any, chat_id: str, is_blocked: bool) -> None:
    """Feature 048 (reverted to single-call design 2026-08-13): best-effort typing
    indicator, fired at the start of DeniDin's turn for every non-blocked sender. Single
    fixed-duration call, no resend/renewal - a background-thread renewal loop was tried and
    reverted the same day after live testing showed the first call itself being delayed by
    ~20s for reasons not pinned down before the attempt was abandoned (spec.md Q1). Accepted
    v1 limitation: on a turn slower than ~20s, the indicator may lapse before the reply
    arrives. Never raises - a failure here is purely cosmetic and must never break message
    processing; it is logged only, never retried.
    """
    if is_blocked:
        return

    try:
        bot.api.serviceMethods.sendTyping(chat_id, typingTime=20000)
    except Exception as error:  # pylint: disable=broad-except
        logger.warning(f"Failed to send typing indicator (chatId={chat_id}): {error}")


class DeniDinGreenAPIBot(GreenAPIBot):
    """GreenAPIBot with a startup-notification-drain and polling loop that survive a Green API
    backend serving a genuinely empty HTTP body for "notification queue is empty" (bugfix-020),
    instead of the upstream crash (startup) / swallowed-exception-and-5s-stall (run_forever).
    """

    def __init__(self, *args: Any, delete_notifications_at_startup: bool = True, **kwargs: Any):
        # Always disable the library's own (buggy) startup drain; run our corrected one after,
        # once self.api/self.logger exist.
        super().__init__(*args, delete_notifications_at_startup=False, **kwargs)
        if delete_notifications_at_startup:
            self._drain_startup_notifications()
        # Feature 045: optional hook invoked with the raw notification body for every
        # notification, before it's dispatched to any router handler. Set by denidin.py once
        # denidin_app exists (needed for the blocked-sender check). None = no-op.
        self.on_notification_received: Optional[Callable[[dict], None]] = None

    def _drain_startup_notifications(self) -> None:
        self.api.session.headers["Connection"] = "keep-alive"
        self.logger.log(logging.DEBUG, "Started deleting old incoming notifications.")

        while True:
            response = self.api.receiving.receiveNotification()
            data = _notification_data_or_none(response.data)
            if data is None:
                break
            self.api.receiving.deleteNotification(data["receiptId"])

        self.api.session.headers["Connection"] = "close"
        self.logger.log(logging.DEBUG, "Stopped deleting old incoming notifications.")
        self.logger.log(logging.INFO, "Deleted old incoming notifications.")

    def run_forever(self) -> None:
        self.api.session.headers["Connection"] = "keep-alive"
        self.logger.log(logging.INFO, "Started receiving incoming notifications.")

        while True:
            try:
                response = self.api.receiving.receiveNotification()
                data = _notification_data_or_none(response.data)
                if data is None:
                    continue

                hook = getattr(self, "on_notification_received", None)
                if hook is not None:
                    try:
                        hook(data["body"])
                    except Exception as hook_error:  # pylint: disable=broad-except
                        # A hook failure must never break notification processing itself.
                        self.logger.log(logging.ERROR, hook_error)

                self.router.route_event(data["body"])
                self.api.receiving.deleteNotification(data["receiptId"])
            except KeyboardInterrupt:
                break
            except Exception as error:  # pylint: disable=broad-except
                if self.raise_errors:
                    raise GreenAPIBotError(error) from error
                self.logger.log(logging.ERROR, error)
                time.sleep(5.0)
                continue

        self.api.session.headers["Connection"] = "close"
        self.logger.log(logging.INFO, "Stopped receiving incoming notifications.")
