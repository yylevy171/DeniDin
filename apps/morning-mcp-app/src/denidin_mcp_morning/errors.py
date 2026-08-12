"""Friendly error mapping for MCP tool responses.

CONSTITUTION §X: user-facing errors must be friendly and actionable, never a
raw stack trace or technical detail (status codes, response bodies, internal
URLs). Without this mapping, FastMCP's default behavior surfaces the raw
exception string verbatim to the caller (confirmed live) — this module is
the boundary that prevents that leak. Full technical detail always goes to
logs at ERROR/DEBUG, tagged with a correlation id for tracing.
"""
from __future__ import annotations

import requests

from .tools import ClientNameNotResolvedError, ClientNotFoundError
from .utils.logger import get_logger

logger = get_logger(__name__)

_AUTH_FAILED = "❌ האימות מול Morning נכשל. בדקו את פרטי ה-API."
_RATE_LIMITED = "❌ יותר מדי בקשות. נסו שוב בעוד דקה."
_NOT_FOUND = "❌ לא נמצא. בדקו את מספר החשבונית/הלקוח."
_NETWORK_ERROR = "❌ לא ניתן להתחבר ל-Morning כרגע. נסו שוב מאוחר יותר."
_REQUEST_REJECTED = "❌ הבקשה נדחתה על ידי Morning. בדקו את הפרטים ונסו שוב."
_UNEXPECTED = "❌ משהו השתבש. נסו שוב."
_INVALID_REQUEST = "❌ הבקשה אינה תקינה. בדקו את הפרטים שסיפקתם."


def mask_secret(value: str, keep: int = 4) -> str:
    """Mask a secret for logging, keeping only the first/last `keep` chars (CONSTITUTION §IX)."""
    if not value or len(value) <= keep * 2:
        return "***"
    return f"{value[:keep]}...{value[-keep:]}"


def friendly_error_message(exc: Exception, correlation_id: str) -> str:
    """Map an exception raised by a tool onto a short, friendly message.

    Args:
        exc: The exception raised by a `tools.*` function.
        correlation_id: Per-call id for tracing this error in the logs.

    Returns:
        A short, user-facing message (spec.md §Error Handling). The full
        technical detail (status, body, stack) is logged separately, never
        returned to the caller.
    """
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        logger.error(
            "[corr_id=%s] Morning API error %s: %s",
            correlation_id,
            status,
            exc.response.text,
            exc_info=True,
        )
        if status in (401, 403):
            return _AUTH_FAILED
        if status == 429:
            return _RATE_LIMITED
        if status == 404:
            return _NOT_FOUND
        if 500 <= status < 600:
            return _NETWORK_ERROR
        return _REQUEST_REJECTED

    if isinstance(exc, requests.exceptions.RequestException):
        logger.error("[corr_id=%s] Network error contacting Morning", correlation_id, exc_info=True)
        return _NETWORK_ERROR

    if isinstance(exc, ClientNameNotResolvedError):
        # client-name-resolution architecture fix follow-up (2026-08-12, user
        # decision): a caller that skipped resolve_client_name is a genuine
        # failure now, not ordinary text - same reasoning as ClientNotFoundError
        # below, just a distinct exception class for a distinct cause (a
        # skipped required step, not "this client doesn't exist"). The message
        # is already user-facing Hebrew (format_name_not_resolved()).
        logger.warning("[corr_id=%s] Client name not resolved: %s", correlation_id, exc)
        return str(exc)

    if isinstance(exc, ClientNotFoundError):
        # bugfix-028 B4(c), caught here 2026-08-12 during a post-merge sweep:
        # ClientNotFoundError IS a ValueError, so without this check it fell
        # into the generic branch below and got replaced with the generic
        # "❌ הבקשה אינה תקינה" text - discarding the specific, actionable
        # "לא נמצא לקוח בשם X" message the exception was raised with, and
        # defeating half the point of raising it (the OTHER half - marking
        # the call as a genuine failure, not ordinary output - still held).
        # This message is already user-facing Hebrew (format_client_not_found()
        # + the searched name), unlike the generic ValueError case below.
        logger.warning("[corr_id=%s] Client not found: %s", correlation_id, exc)
        return str(exc)

    if isinstance(exc, ValueError):
        # The English exception text is developer-facing detail (business-rule
        # messages raised in tools.py); log it, but return a generic Hebrew
        # message to the caller rather than echoing English text verbatim
        # (REQ-I18N-001: Hebrew by default).
        logger.warning("[corr_id=%s] Validation/business-rule error: %s", correlation_id, exc)
        return _INVALID_REQUEST

    logger.error("[corr_id=%s] Unexpected error", correlation_id, exc_info=True)
    return _UNEXPECTED
