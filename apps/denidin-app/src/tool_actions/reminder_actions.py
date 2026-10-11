"""
Reminder actions shared by the legacy AIHandler and the Feature 063 backbone.
Moved out of handlers/ai_handler.py with their bodies unchanged - one
implementation, used by both paths.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from src.managers.reminder_manager import InvalidRecurrenceError
from src.tool_actions.tool_schemas import (
    CREATE_REMINDER_TOOL, DELETE_REMINDER_TOOL, MODIFY_REMINDER_TOOL,
)


def format_reminder_schedule(rrule_str: Optional[str], dtstart_iso: str) -> str:
    """Human-readable Hebrew summary of a reminder's schedule, for the approval
    block (_build_reminder_approval_details). The persisted RRULE string is the
    source of truth for actual firing (ReminderManager/recurring_ical_events) -
    this is display-only and deliberately simple, not a full RFC5545 renderer.
    """
    try:
        when = datetime.fromisoformat(dtstart_iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        when = dtstart_iso

    if not rrule_str:
        return f"חד-פעמי, {when}"

    parts = dict(p.split("=", 1) for p in rrule_str.split(";") if "=" in p)
    freq_labels = {"DAILY": "יומי", "WEEKLY": "שבועי", "MONTHLY": "חודשי"}
    freq_label = freq_labels.get(parts.get("FREQ", ""), parts.get("FREQ", ""))
    interval = parts.get("INTERVAL")
    cadence = f"כל {interval} × {freq_label}" if interval else freq_label

    extra = ""
    if "BYDAY" in parts:
        byday_labels = {
            "SU": "א", "MO": "ב", "TU": "ג", "WE": "ד",
            "TH": "ה", "FR": "ו", "SA": "ש",
        }
        days_he = ",".join(
            byday_labels.get(code, code) for code in parts["BYDAY"].split(",")
        )
        extra = f", בימים {days_he}"
    elif "BYMONTHDAY" in parts:
        extra = f", ביום {parts['BYMONTHDAY']} לחודש"

    end = ""
    if "COUNT" in parts:
        end = f", {parts['COUNT']} פעמים"
    elif "UNTIL" in parts:
        end = f", עד {parts['UNTIL'][:8]}"

    return f"{cadence}{extra}, החל מ-{when}{end}"


def build_list_reminders_summary(reminder_manager) -> List[Dict[str, Any]]:
    """The list_reminders tool's payload body: every active reminder as
    {reminder_id, message_text, schedule}."""
    reminders = reminder_manager.list_active()
    summary = [
        {
            "reminder_id": r["reminder_id"],
            "message_text": r["message_text"],
            "schedule": format_reminder_schedule(r["rrule"], r["dtstart"]),
        }
        for r in reminders
    ]
    return summary


def execute_reminder_action(reminder_manager, tool_name: str, args: Dict[str, Any], *,
                            created_by_phone, created_by_role, delivery_chat_id):
    """Runs one approved create/modify/delete reminder call against the real
    ReminderManager. Raises InvalidRecurrenceError for an unresolvable
    tool_name/scope pair; the manager's own errors propagate to the caller."""
    scope = args.get("scope")
    if tool_name == CREATE_REMINDER_TOOL["name"]:
        result = reminder_manager.create_reminder(
            message_text=cast(str, args.get("message_text")),
            schedule_type=cast(str, args.get("schedule_type")),
            one_time_due_at=args.get("one_time_due_at"),
            recurrence=args.get("recurrence"),
            created_by_phone=created_by_phone,
            created_by_role=created_by_role,
            delivery_chat_id=delivery_chat_id,
        )
    elif tool_name == MODIFY_REMINDER_TOOL["name"] and scope == "single_occurrence":
        result = reminder_manager.modify_single_occurrence(
            reminder_id=cast(str, args.get("reminder_id")),
            occurrence_date_hint=cast(str, args.get("occurrence_date_hint")),
            new_message_text=args.get("new_message_text"),
            new_due_at=args.get("new_due_at"),
        )
    elif tool_name == MODIFY_REMINDER_TOOL["name"]:  # scope == "whole_series"
        result = reminder_manager.modify_whole_series(
            reminder_id=cast(str, args.get("reminder_id")),
            new_message_text=args.get("new_message_text"),
            new_recurrence=args.get("new_recurrence"),
            new_due_at=args.get("new_due_at"),
        )
    elif tool_name == DELETE_REMINDER_TOOL["name"] and scope == "single_occurrence":
        result = reminder_manager.delete_single_occurrence(
            reminder_id=cast(str, args.get("reminder_id")),
            occurrence_date_hint=cast(str, args.get("occurrence_date_hint")),
        )
    elif tool_name == DELETE_REMINDER_TOOL["name"]:  # scope == "whole_series"
        result = reminder_manager.delete_whole_series(
            reminder_id=cast(str, args.get("reminder_id")),
        )
    else:
        raise InvalidRecurrenceError(
            f"unresolvable pending tool_name/scope: {tool_name!r}/{scope!r}"
        )
    return result


def resolve_literal_sender(sender_id, default_role, user_manager):
    """The LITERAL sender's phone and role for created_by traceability: the role
    comes from user_manager when it knows the sender, else `default_role`."""
    literal_sender_phone = sender_id
    literal_sender_role = default_role
    if user_manager:
        literal_user_obj = user_manager.get_user(literal_sender_phone)
        if literal_user_obj:
            literal_sender_role = literal_user_obj.role
    return literal_sender_phone, literal_sender_role
