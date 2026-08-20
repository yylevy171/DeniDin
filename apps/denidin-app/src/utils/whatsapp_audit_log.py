"""
WhatsApp Audit Log (2026-08-19).

Two-way, INFO-level, complete record of every message that actually crosses
the WhatsApp boundary in either direction - added after a real incident
where a user-reported "I got two approval messages, but only sent one"
question turned out to be unanswerable: nothing anywhere logged the raw
incoming Green API webhook (only a useless default object repr), and
outbound sends were scattered across many call sites with no single record
of what was actually sent, to whom, and when.

Never log binary/base64 content - the one exception. Green API's own
`fileMessageData.jpegThumbnail` (see src/models/green_api.py) is the only
field in this codebase's webhook traffic that can carry inline binary; media
content itself is always fetched separately via `downloadUrl`, never
embedded in the webhook. Every other field (sender, chatId, text, caption,
timestamps, idMessage, button ids, etc.) is plain text/metadata and is
logged in full, unredacted.

Not a substitute for this codebase's existing structured logging (RBAC
decisions, tool calls, delivery outcomes, etc.) - this is specifically the
raw wire-level record: what literally came in, what literally went out.
"""
import copy
from typing import Any, Dict

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Fields anywhere in an incoming webhook event that may carry inline base64
# binary and must never be logged verbatim - confirmed against Green API's
# own documented webhook shape (src/models/green_api.py's FileMessageData:
# "jpegThumbnail: Image preview in base64"). downloadUrl (a plain URL, not
# binary) and everything else in fileMessageData is safe and logged as-is.
_BINARY_FIELD_NAMES = {"jpegThumbnail"}


def _redact_binary_fields(value: Any) -> Any:
    """Deep-copy `value`, replacing any dict value whose key is a known
    binary-carrying field with a short placeholder instead of the real
    (potentially large) base64 content. Recurses through nested
    dicts/lists so this is safe regardless of exactly where Green API
    nests the field for a given message type.
    """
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, val in value.items():
            if key in _BINARY_FIELD_NAMES and isinstance(val, str) and val:
                result[key] = f"<redacted base64, {len(val)} chars>"
            else:
                result[key] = _redact_binary_fields(val)
        return result
    if isinstance(value, list):
        return [_redact_binary_fields(item) for item in value]
    return value


def log_inbound(notification: Any) -> None:
    """Log the complete raw incoming Green API webhook event, verbatim
    except for redacted binary fields (see module docstring). Call this as
    the very first thing every router handler does, before any parsing or
    business logic - so even a message that errors out immediately
    afterward, or is dropped for being an unsupported type, still leaves a
    permanent record of exactly what arrived.
    """
    try:
        redacted = _redact_binary_fields(copy.deepcopy(getattr(notification, "event", {})))
        logger.info(f"[AUDIT-IN] {redacted!r}")
    except Exception as e:  # pylint: disable=broad-except
        # Audit logging must never be the reason a real message fails to
        # process - log the failure itself and move on.
        logger.error(f"[AUDIT-IN] failed to log inbound notification: {e}", exc_info=True)


def log_outbound(chat_id: str, message: str, kind: str = "text") -> None:
    """Log a message actually sent (or attempted) back out to WhatsApp -
    call this at every real send call site (plain text, interactive
    buttons, a proactive reminder delivery, an error/fallback notice),
    right after the send call itself, regardless of whether it succeeded.
    `kind` is a short free-text label distinguishing the send path
    (e.g. "text", "buttons", "proactive") for readability - not a chat
    concept, purely for this log.
    """
    try:
        logger.info(f"[AUDIT-OUT] chat={chat_id!r} kind={kind!r} message={message!r}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[AUDIT-OUT] failed to log outbound message: {e}", exc_info=True)
