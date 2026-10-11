"""
Reminders capability (Feature 063, 2026-09-24 "resolution" redesign) — real,
directly-attachable domain tools only: `load_capabilities`
attaches list_reminders/create_reminder/modify_reminder/delete_reminder
straight to the ongoing chain the moment reminders_read/reminders_write is
loaded, and the model calls whichever one it needs directly, guided by its
own prompt file (config/prompts/capabilities/cap_reminders_read.md /
cap_reminders_write.md). Wraps the existing, unmodified
`src/managers/reminder_manager.py` (REQ-063-03) — this module owns no storage
of its own.
"""
import json
import logging
from typing import Any, Dict

from src.tool_actions.tool_schemas import (
    CREATE_REMINDER_TOOL,
    DELETE_REMINDER_TOOL,
    LIST_REMINDERS_TOOL,
    MODIFY_REMINDER_TOOL,
)
from src.managers.reminder_manager import (
    InvalidRecurrenceError,
    OccurrenceNotFoundError,
    ReminderError,
    ReminderNotFoundError,
)

from src.tool_actions.reminder_actions import (
    build_list_reminders_summary, execute_reminder_action, resolve_literal_sender,
)

logger = logging.getLogger(__name__)


def dispatch_direct_tool_call(backbone, tool_name: str, args: Dict[str, Any],
                               turn_context: Dict[str, Any]) -> str:
    """Executes one list_reminders/create_reminder/modify_reminder/
    delete_reminder call made directly on the SAME ongoing resolution-loop
    chain (Feature 063 - see backbone.py's `_run_resolution_loop`
    docstring) - no separate, disconnected AI call, no note to re-derive
    anything from. `turn_context` carries chat_id/user_phone/role."""
    if tool_name == LIST_REMINDERS_TOOL["name"]:
        if backbone.reminder_manager is None:
            return "⚠️ שירות התזכורות אינו זמין כרגע."
        return json.dumps({"reminders": build_list_reminders_summary(backbone.reminder_manager)},
                          ensure_ascii=False)

    chat_id: str = turn_context["chat_id"]  # every turn has a chat
    role = turn_context.get("role")
    created_by_phone, literal_role = resolve_literal_sender(
        turn_context.get("sender_phone") or turn_context.get("user_phone") or chat_id, role,
        getattr(backbone, "user_manager", None),
    )
    created_by_role = str(literal_role) if literal_role is not None else ""

    if tool_name == CREATE_REMINDER_TOOL["name"]:
        return _execute(backbone, tool_name, args, chat_id, created_by_phone, created_by_role)
    return _execute_modify_or_delete(backbone, tool_name, args, chat_id, created_by_phone, created_by_role)


def _execute_modify_or_delete(backbone, tool_name: str, args: Dict[str, Any], chat_id: str,  # pylint: disable=too-many-positional-arguments
                               created_by_phone: str, created_by_role: str) -> str:
    """The modify/delete branch of write() above - validates then executes
    immediately, same TOCTOU-safety the old proposal-time validation had
    (re-validated for real inside _execute's own ReminderManager calls)."""
    logger.debug(
        "[RAWLOG] reminders.write._execute_modify_or_delete >>> tool_name=%r args=%r chat_id=%r",
        tool_name, args, chat_id,
    )
    reminder_id = args.get("reminder_id")
    scope = args.get("scope")
    if scope not in ("single_occurrence", "whole_series"):
        result_text = "⚠️ לא ברור אילו תזכורות/מופע לשנות. נסו שוב."
        logger.debug("[RAWLOG] reminders.write._execute_modify_or_delete <<< RESULT: %r", result_text)
        return result_text

    current = backbone.reminder_manager.get_reminder(str(reminder_id))
    if current is None:
        result_text = "⚠️ לא נמצאה תזכורת כזו."
        logger.debug("[RAWLOG] reminders.write._execute_modify_or_delete <<< RESULT: %r", result_text)
        return result_text
    if scope == "single_occurrence" and not args.get("occurrence_date_hint"):
        result_text = "⚠️ חסר תאריך מופע ספציפי. נסו שוב."
        logger.debug("[RAWLOG] reminders.write._execute_modify_or_delete <<< RESULT: %r", result_text)
        return result_text
    if scope == "single_occurrence" and current.get("rrule") is None:
        result_text = "⚠️ אי אפשר לשנות מופע בודד בתזכורת חד-פעמית. נסו שוב."
        logger.debug("[RAWLOG] reminders.write._execute_modify_or_delete <<< RESULT: %r", result_text)
        return result_text

    try:
        if scope == "single_occurrence":
            backbone.reminder_manager.resolve_occurrence_datetime(
                str(reminder_id), current, str(args.get("occurrence_date_hint")),
            )
    except (InvalidRecurrenceError, OccurrenceNotFoundError, ReminderNotFoundError) as exc:
        # 2026-09-16 (same fix as _execute's ReminderError branch): surface
        # the real reason, not a generic "invalid request" - gives the model
        # something concrete to correct on a retry.
        logger.warning("%s rejected during validation: %s", tool_name, exc)
        result_text = f"⚠️ הבקשה לא תקפה: {exc}. נסו שוב עם תאריך/מזהה מתוקן."
        logger.debug("[RAWLOG] reminders.write._execute_modify_or_delete <<< RESULT (validation failure): %r",
                     result_text)
        return result_text

    return _execute(backbone, tool_name, args, chat_id, created_by_phone, created_by_role)


def _execute(backbone, tool_name: str, arguments: Dict[str, Any], chat_id: str,  # pylint: disable=too-many-positional-arguments
             created_by_phone: str, created_by_role: str) -> str:
    """Executes one of the three reminders-write tools immediately against the
    real ReminderManager - the direct-execute equivalent of the old
    _approve_and_execute, now taking (tool_name, arguments) directly instead
    of unwrapping a PendingLocalToolApproval object.

    2026-09-16 (CAPABILITIES_SANITY.md T3/T4 incident): a validation failure
    here used to return a fully generic "⚠️ הפעולה נכשלה. נסו שוב." with no
    indication of WHAT was wrong - the model had nothing to self-correct on,
    so a retry (when it even attempted one, see T4) just guessed a different
    wrong value. `ReminderError` failures (the expected, user-caused-input
    validation class - past dates, malformed recurrence, missing reminder,
    etc, all defined in reminder_manager.py) now return the real validation
    message verbatim plus an explicit pointer back at "the current date/time
    already given to you in your instructions", so the model has an actual
    basis to recompute and retry - see cap_reminders_write.md's own "On a
    creation/modification failure" section for the model-facing half of this
    contract. A genuinely unexpected exception (anything not a ReminderError)
    still logs full detail (exc_info=True, not just the message) and returns
    a generic failure text, since there's no user-input-correctable reason to
    surface for those."""
    logger.debug(
        "[RAWLOG] reminders.write._execute >>> tool_name=%r arguments=%r chat_id=%r "
        "created_by_phone=%r created_by_role=%r",
        tool_name, arguments, chat_id, created_by_phone, created_by_role,
    )
    try:
        if tool_name in (CREATE_REMINDER_TOOL["name"], MODIFY_REMINDER_TOOL["name"], DELETE_REMINDER_TOOL["name"]):
            result = execute_reminder_action(
                backbone.reminder_manager, tool_name, arguments,
                created_by_phone=created_by_phone, created_by_role=created_by_role,
                delivery_chat_id=chat_id,
            )
            if tool_name == CREATE_REMINDER_TOOL["name"]:
                result_text = f"✅ נוצרה תזכורת (מזהה {result['reminder_id']}), מועד: {result['due_at']}"
            elif tool_name == MODIFY_REMINDER_TOOL["name"]:
                result_text = "✅ התזכורת עודכנה."
            else:
                result_text = "✅ התזכורת בוטלה."
            logger.debug("[RAWLOG] reminders.write._execute <<< RESULT (success): %r", result_text)
            return result_text

        logger.error("Unknown reminders tool_name: %r", tool_name)
        result_text = "⚠️ הפעולה נכשלה. נסו שוב."
        logger.debug("[RAWLOG] reminders.write._execute <<< RESULT: %r", result_text)
        return result_text
    except ReminderError as exc:
        # Expected, user-input-shaped validation failure (past date, bad
        # recurrence, missing reminder, etc) - surface the REAL reason so the
        # model (and the next human reading these logs) can tell exactly why,
        # not just that something failed. See this function's own docstring.
        logger.error("Reminder %s rejected by validation: %s", tool_name, exc)
        result_text = (
            f"⚠️ הפעולה נכשלה: {exc}. שים לב: התאריך/שעה הנוכחיים האמיתיים כבר "
            f"ניתנו לך בהוראות הקריאה הזו (\"THE CURRENT DATE AND TIME IS...\") - "
            f"חשב מחדש את הערך ביחס אליהם ונסה שוב פעם אחת; רק אם זה נכשל שוב, "
            f"דווח למשתמש שהפעולה לא הצליחה."
        )
        logger.debug("[RAWLOG] reminders.write._execute <<< RESULT (validation failure): %r", result_text)
        return result_text
    except Exception as exc:  # pylint: disable=broad-except
        # Genuinely unexpected - no user-input-correctable reason to surface,
        # so keep the reply generic, but log the FULL traceback (not just the
        # message) since this is the case most worth a human's attention.
        logger.error("Reminder %s failed on execution: %s", tool_name, exc, exc_info=True)
        result_text = "⚠️ הפעולה נכשלה. נסו שוב."
        logger.debug("[RAWLOG] reminders.write._execute <<< RESULT (unexpected exception): %r", result_text)
        return result_text
