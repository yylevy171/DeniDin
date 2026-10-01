"""
Turn-result primitives shared by the legacy AIHandler and the Feature 063 backbone
(2026-10-01): pulling a response's Morning MCP calls, deriving its finish reason,
fitting the reply to WhatsApp's length limit, and flagging a reply that claims a
Morning action no tool call backs. Moved out of handlers/ai_handler.py with behavior
unchanged - one implementation, used by both paths.
"""
import logging
from typing import Any, Dict, List

from src.models.message import AIResponse

logger = logging.getLogger(__name__)

# WhatsApp reply length limit the reply is cut to (AIResponse.truncate_for_whatsapp).
WHATSAPP_MAX_REPLY_CHARS = 4000

# Phrases of a state-changing Morning confirmation ("issued", "marked paid",
# "cancelled", "added" - all "successfully").
_CONFIRMATION_PHRASES = ("הוצאה בהצלחה", "סומנה כשולמה", "בוטלה בהצלחה", "נוסף בהצלחה")


def extract_mcp_call_items(response) -> List[Dict[str, Any]]:
    """Every `mcp_call` item on one API response's `.output`, as
    {name, error, arguments, output}.

    `error` is normalized to a plain string (2026-09-15, real billed failure): on a
    network-level failure (e.g. a 503 from the MCP tunnel) the SDK's `item.error` can
    be a raw exception object (`HTTPError(...)`), which later crashed message storage
    (`json.dump` -> `TypeError: Object of type HTTPError is not JSON serializable`).
    Normalized once, here, at the boundary."""
    return [
        {
            "name": item.name,
            "error": str(item.error) if item.error is not None else None,
            "arguments": item.arguments,
            "output": item.output,
        }
        for item in (getattr(response, "output", None) or [])
        if getattr(item, "type", None) == "mcp_call"
    ]


def finish_reason_of(response) -> str:
    """The Responses API has no per-choice finish_reason: "stop", unless the response
    carries incomplete_details, then its reason (or "incomplete")."""
    incomplete = getattr(response, "incomplete_details", None)
    if incomplete is not None:
        return getattr(incomplete, "reason", None) or "incomplete"
    return "stop"


def fit_for_whatsapp(ai_response: AIResponse) -> AIResponse:
    """The reply cut to WhatsApp's limit (AIResponse.truncate_for_whatsapp) when it
    is longer, logged; otherwise unchanged."""
    if len(ai_response.response_text) > WHATSAPP_MAX_REPLY_CHARS:
        logger.warning("Response truncated to %d chars for WhatsApp", WHATSAPP_MAX_REPLY_CHARS)
        return ai_response.truncate_for_whatsapp()
    return ai_response


def reply_or_fallback(text: str, fallback: str) -> str:
    """The reply text, or `fallback` when there is none (Item7, 2026-10-01): a turn
    the user sent something to is never left silent by accident. A deliberate
    [[NO_REPLY]] is non-empty text, so it passes through unchanged."""
    return (text or "").strip() or fallback


def log_possible_hallucinated_confirmation(request_id: str, response_text: str,
                                            tools_offered: bool,
                                            mcp_calls: List[Dict[str, Any]]) -> None:
    """Detection safety net, log only: tools were offered this turn and the reply
    reads like a state-changing Morning confirmation, but no MCP call was made - the
    model may have pattern-completed a fabricated success from earlier turns."""
    if mcp_calls or not tools_offered:
        return
    if any(phrase in (response_text or "") for phrase in _CONFIRMATION_PHRASES):
        logger.warning(
            f"Possible hallucinated invoicing confirmation for request "
            f"{request_id}: reply text suggests a state-changing "
            f"action succeeded, but no MCP tool was called. "
            f"Reply: {response_text!r}"
        )
