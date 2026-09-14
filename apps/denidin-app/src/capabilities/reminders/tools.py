"""
New, standalone local-tool schema + response-parsing helpers for the Reminders
capability (Feature 063). Deliberately NOT imported from `src/handlers/ai_handler.py`
(REQ-063-07: zero coupling to the legacy module).

Scope note: only ONE-TIME reminder creation is wired for real in this pass — recurring
creation and modify/delete are tracked as follow-up work in tasks.md's "Deferred"
section, alongside the other write-approval-flow parity items.
"""
import json
import logging
from typing import Any, Dict, List, Optional, cast

logger = logging.getLogger(__name__)

CREATE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "create_reminder",
    "description": (
        "ONLY call this when the user's own message explicitly asks to be reminded of "
        "something at a future, one-time date/time. This call itself does NOT persist "
        "anything - it is presented to the user as an approval summary; the reminder is "
        "only created if the user then explicitly approves."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "message_text": {
                "type": "string",
                "description": "The actual thing to be reminded about, in the user's own words.",
            },
            "one_time_due_at": {
                "type": "string",
                "description": "ISO-8601 local datetime (Asia/Jerusalem), strictly in the future.",
            },
        },
        "required": ["message_text", "one_time_due_at"],
        "additionalProperties": False,
    },
}


def extract_function_call(response, tool_name: str) -> Optional[Dict]:
    """Find a `function_call` item named `tool_name` in a Responses API `response.output`
    and return its parsed arguments, or None if absent. Never raises."""
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        try:
            return cast(Dict, json.loads(item.arguments))
        except json.JSONDecodeError as exc:
            logger.warning("Malformed %r function_call arguments discarded: %s", tool_name, exc)
            return None
    return None


def extract_function_call_id(response, tool_name: str) -> Optional[str]:
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        return getattr(item, "call_id", None)
    return None


def list_active_reminders_text(reminders: List[Dict]) -> str:
    """Plain-text rendering of active reminders, for the reminders_read step's output."""
    if not reminders:
        return "אין תזכורות פעילות כרגע."
    lines = ["התזכורות הפעילות שלך:"]
    for reminder in reminders:
        lines.append(f"- {reminder['message_text']} (מועד: {reminder['dtstart']})")
    return "\n".join(lines)
