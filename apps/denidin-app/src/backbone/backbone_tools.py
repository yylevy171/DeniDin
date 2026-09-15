"""
Backbone-level cross-cutting local tools (Feature 063 remaining Deferred item) -
`send_progress_update` (Feature 080) and `react_to_message` (Feature 084).
Unlike every domain capability's own tools, these apply to EVERY capability step
uniformly (backbone.md's own "Proactive Progress Updates"/"Reaction Management"
sections), so BackboneOrchestrator.call_capability_step attaches them to every
Responses API call it makes, regardless of which capability is active.

New, standalone schemas - deliberately NOT imported from `src/handlers/ai_handler.py`
(REQ-063-07: zero coupling to the legacy module), though describing the exact same
real-world tools with the same real-world behavior.

Simplification vs. the legacy path (documented, not silent): resolved in exactly
ONE follow-up round per capability-step call (every backbone-tool call the model
made in the first response is dispatched, then ONE follow-up submits all their
outputs together) rather than the legacy's iterative multi-round dispatch loop -
a call this simple (a fire-and-forget WhatsApp send, a fire-and-forget reaction)
essentially never needs a second round in practice, and this still closes
bugfix-042's exact failure mode (every function_call gets its output submitted,
never left dangling) since ALL calls from one response are resolved together.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SEND_PROGRESS_UPDATE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "send_progress_update",
    "description": (
        "Send ONE short interim WhatsApp message to the user mid-turn, before your real "
        "final answer is ready - use ONLY on a turn you already know will take a while "
        "(e.g. processing a multi-page document, a multi-step tool sequence), never on an "
        "ordinary fast turn. This is NOT your final answer and NEVER counts as one - you "
        "MUST still produce a real final answer as a normal message after this. Never call "
        "this in place of asking a genuine clarifying question, and never send more than one "
        "progress update per turn unless the turn is unusually long."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The short interim status message to show the user right now.",
            },
        },
        "required": ["text"],
        "additionalProperties": False,
    },
}

REACT_TO_MESSAGE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "react_to_message",
    "description": (
        "Call this proactively, every turn where it applies - do not wait to be asked and "
        "do not treat it as optional decoration. Two mandatory moments call for it: (1) the "
        "user asked you to DO something (not just answer a question) - call this as your "
        "very first tool call, before any other tool, with a quick ack emoji; (2) that ask "
        "just became RESOLVED in this reply - success, failure, validation problem, or a "
        "blocked/abandoned action - call this again with a terminal emoji (success/failure) "
        "BEFORE or ALONGSIDE writing that resolution into your reply text. Pass an empty "
        "string for emoji to clear an existing reaction. Omit message_id (pass null) to "
        "react to the CURRENT user turn's incoming message. This is purely cosmetic and "
        "reversible - a failure here is logged and never blocks your reply."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "emoji": {
                "type": "string",
                "description": "A single unicode emoji, or \"\" to clear the reaction.",
            },
            "message_id": {
                "type": ["string", "null"],
                "description": "The target message's id, or null for the current turn's incoming message.",
            },
        },
        "required": ["emoji", "message_id"],
        "additionalProperties": False,
    },
}

BACKBONE_TOOLS: List[Dict[str, Any]] = [SEND_PROGRESS_UPDATE_TOOL, REACT_TO_MESSAGE_TOOL]
_BACKBONE_TOOL_NAMES = {tool["name"] for tool in BACKBONE_TOOLS}


def extract_backbone_tool_calls(response) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every (call_id, tool_name, parsed_args) for a send_progress_update/
    react_to_message function_call item in `response.output`, in order. Never
    raises - a malformed call's arguments are skipped (logged) rather than
    crashing the turn."""
    calls: List[Tuple[str, str, Dict[str, Any]]] = []
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call":
            continue
        name = getattr(item, "name", None)
        if name not in _BACKBONE_TOOL_NAMES:
            continue
        call_id = getattr(item, "call_id", None)
        if not call_id:
            continue
        try:
            args = json.loads(item.arguments)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Malformed %r arguments discarded: %s", name, exc)
            continue
        calls.append((str(call_id), str(name), args))
    return calls


def dispatch_send_progress_update(progress_callback: Optional[Any], chat_id: Optional[str],
                                   args: Dict[str, Any]) -> Dict[str, Any]:
    """The real side effect (Feature 080): sends `args["text"]` via whatever
    callback the current turn activated. Best-effort - a failure here must
    never fail the turn (the real final answer still has to go out)."""
    text = args.get("text")
    sent = False
    if text and progress_callback is not None:
        try:
            progress_callback(text)
            sent = True
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("send_progress_update: failed to send interim message: %s", exc)
    elif not text:
        logger.warning("send_progress_update called with no text argument - nothing sent")
    else:
        logger.debug("send_progress_update called but no progress_callback is active - nothing sent")
    del chat_id  # not needed for this tool's dispatch - kept for a uniform call signature
    return {"sent": sent}


def dispatch_react_to_message(green_api_bot: Optional[Any], chat_id: Optional[str],
                               default_message_id: Optional[str], args: Dict[str, Any]) -> Dict[str, Any]:
    """The real side effect (Feature 084): sets/clears a WhatsApp reaction via the
    unmodified `send_reaction` util. Never raises past this function - a reaction
    failure is logged and never blocks the turn (REQ-084-007)."""
    # pylint: disable=import-outside-toplevel
    from src.utils.green_api_bot import send_reaction

    emoji = args.get("emoji", "")
    target_message_id = args.get("message_id") or default_message_id
    success = False
    if green_api_bot is not None and chat_id and target_message_id:
        try:
            success = send_reaction(green_api_bot, chat_id, target_message_id, emoji)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("react_to_message: failed to set reaction: %s", exc)
    else:
        logger.debug(
            "react_to_message called but green_api_bot/chat_id/message_id unavailable - nothing sent"
        )
    return {"success": success}
