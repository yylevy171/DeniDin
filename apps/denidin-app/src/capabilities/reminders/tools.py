"""
New, standalone local-tool schema + response-parsing helpers for the Reminders
capability (Feature 063). Deliberately NOT imported from `src/handlers/ai_handler.py`
(REQ-063-07: zero coupling to the legacy module).

Scope note: one-time reminder creation, plus modify/delete (single-occurrence and
whole-series) are wired for real. Recurring reminder CREATION is still tracked as
follow-up work in tasks.md's "Deferred" section.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, cast

logger = logging.getLogger(__name__)

# Free-form affirmative replies recognized as approval of a pending reminder-write
# proposal - matched against the trimmed, casefolded message (or its leading word
# token), never as a substring-anywhere check (avoids false positives on unrelated
# longer sentences). Deliberately NOT imported from ai_handler.py's own
# _AFFIRMATIVE_REPLIES/_is_affirmative_reply (REQ-063-07) - independent new code,
# same word set/matching approach since it's the same real-world behavior users
# already expect.
_AFFIRMATIVE_REPLIES = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "go ahead",
    "כן", "אישור", "בסדר", "אוקיי", "אוקי", "מאשר", "מאשרת", "בטח", "סבבה", "לאשר",
}


def is_affirmative_reply(text: str) -> bool:
    """Whether `text` reads as a free-form yes/no approval of a pending reminder
    creation - matched as the whole trimmed message or its leading word token
    (anchored on the FIRST word so a longer refusal like "לא, תבטל" is never
    misread as approval)."""
    normalized = text.strip().casefold()
    if not normalized:
        return False
    if normalized in _AFFIRMATIVE_REPLIES:
        return True
    leading_match = re.search(r"\w+", normalized, flags=re.UNICODE)
    if leading_match is None:
        return False
    return leading_match.group(0) in _AFFIRMATIVE_REPLIES

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


MODIFY_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "modify_reminder",
    "description": (
        "ONLY call this when the user explicitly asks to change an EXISTING reminder "
        "(its text and/or its schedule) - never to create a new one. This call itself "
        "does NOT persist anything - it is presented to the user as an approval "
        "summary; the change is only applied if the user then explicitly approves."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {
                "type": "string",
                "description": "The id of the existing reminder to modify, from the active reminders list.",
            },
            "scope": {
                "type": "string",
                "enum": ["single_occurrence", "whole_series"],
                "description": (
                    "whole_series for a one-time reminder, or to change a recurring "
                    "reminder's schedule/text going forward. single_occurrence to change "
                    "just one upcoming occurrence of a recurring reminder, leaving the "
                    "rest of the series untouched."
                ),
            },
            "occurrence_date_hint": {
                "type": ["string", "null"],
                "description": (
                    "Required when scope=single_occurrence: the calendar date "
                    "(YYYY-MM-DD) of the specific occurrence being changed. Null for "
                    "whole_series."
                ),
            },
            "new_message_text": {
                "type": ["string", "null"],
                "description": "New reminder text, or null to leave it unchanged.",
            },
            "new_due_at": {
                "type": ["string", "null"],
                "description": (
                    "New ISO-8601 local datetime (Asia/Jerusalem), for a one-time "
                    "reminder or a single occurrence - null to leave unchanged."
                ),
            },
        },
        "required": ["reminder_id", "scope", "occurrence_date_hint", "new_message_text", "new_due_at"],
        "additionalProperties": False,
    },
}

DELETE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "delete_reminder",
    "description": (
        "ONLY call this when the user explicitly asks to cancel/delete an EXISTING "
        "reminder. This call itself does NOT persist anything - it is presented to "
        "the user as an approval summary; the cancellation only happens if the user "
        "then explicitly approves."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {
                "type": "string",
                "description": "The id of the existing reminder to delete, from the active reminders list.",
            },
            "scope": {
                "type": "string",
                "enum": ["single_occurrence", "whole_series"],
                "description": (
                    "whole_series to cancel the reminder entirely (one-time or "
                    "recurring). single_occurrence to cancel just one upcoming "
                    "occurrence of a recurring reminder, leaving the rest of the "
                    "series untouched."
                ),
            },
            "occurrence_date_hint": {
                "type": ["string", "null"],
                "description": (
                    "Required when scope=single_occurrence: the calendar date "
                    "(YYYY-MM-DD) of the specific occurrence being cancelled. Null for "
                    "whole_series."
                ),
            },
        },
        "required": ["reminder_id", "scope", "occurrence_date_hint"],
        "additionalProperties": False,
    },
}

MODIFY_DELETE_REMINDER_TOOLS: List[Dict[str, Any]] = [MODIFY_REMINDER_TOOL, DELETE_REMINDER_TOOL]


def extract_any_function_call(response, tool_names: List[str]):
    """Like extract_function_call, but for the first matching tool among
    `tool_names` (in that order) - returns (tool_name, args) or (None, None)."""
    for tool_name in tool_names:
        args = extract_function_call(response, tool_name)
        if args is not None:
            return tool_name, args
    return None, None


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
