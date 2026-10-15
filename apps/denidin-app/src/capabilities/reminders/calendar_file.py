"""
Feature 102 - the calendar (.ics) file sent alongside a reminder.

Builds the file(s) for the reminders a turn created/changed/deleted (`flush_queued_files`, called by the
Backbone once the conversation has ended so the file arrives AFTER the model's confirmation text) and for an
on-demand request (`send_files_for`). Wraps ReminderManager (for the data and the per-reminder SEQUENCE) and
`src/utils/reminder_ics.py` (the format); sends through `DeniDin.send_calendar_file`. Never raises - a file
that cannot be built or sent never turns a saved reminder into an error.
"""
import json
import logging
from typing import Any, Dict, List, Sequence

from src.utils.reminder_ics import (
    CalendarEntry, CalendarException, build_ics, ics_file_name,
)
from src.utils.time_utils import now_local

logger = logging.getLogger(__name__)

PUBLISH = "PUBLISH"
CANCEL = "CANCEL"
NOTICE_SEND_FAILED = "⚠️ התזכורת נשמרה, אבל לא הצלחתי לשלוח את קובץ היומן."


def _entry_for(reminder_manager: Any, reminder_id: str) -> "CalendarEntry | None":
    """The calendar entry for one reminder, with a freshly claimed SEQUENCE; None if it doesn't exist."""
    stored = reminder_manager.get_for_calendar(reminder_id)
    if stored is None:
        return None
    sequence = reminder_manager.claim_ics_sequence(reminder_id)
    return CalendarEntry(
        reminder_id=stored["reminder_id"], message_text=stored["message_text"],
        dtstart=stored["dtstart"], rrule=stored["rrule"], sequence=sequence,
        exceptions=tuple(
            CalendarException(
                recurrence_id=exc["recurrence_id"], dtstart_override=exc["dtstart_override"],
                summary_override=exc["summary_override"], status=exc["status"],
            ) for exc in stored["exceptions"]
        ),
    )


def _send(denidin: Any, chat_id: str, entries: Sequence[CalendarEntry], method: str) -> "str | None":
    """Builds one file from `entries` and sends it; returns the file name, or None on failure."""
    file_name = ics_file_name(entries, now_local().date())
    content = build_ics(list(entries), method=method)
    return file_name if denidin.send_calendar_file(chat_id, file_name, content) else None


def flush_queued_files(denidin: Any, reminder_manager: Any, chat_id: str, queue: Dict[str, str]) -> None:
    """Sends the files for `queue` ({reminder_id: PUBLISH|CANCEL}): all PUBLISH entries together in one
    file, each CANCEL in a file of its own. On any failure the user is told once that the reminder was
    saved but the file could not be sent. Never raises."""
    if not queue or reminder_manager is None:
        return
    failed = False
    try:
        publish: List[CalendarEntry] = []
        cancels: List[CalendarEntry] = []
        for reminder_id, method in queue.items():
            entry = _entry_for(reminder_manager, reminder_id)
            if entry is None:
                logger.warning(f"[102] Queued calendar file for unknown reminder {reminder_id} - skipped")
                continue
            (cancels if method == CANCEL else publish).append(entry)
        if publish and _send(denidin, chat_id, publish, PUBLISH) is None:
            failed = True
        for entry in cancels:
            if _send(denidin, chat_id, [entry], CANCEL) is None:
                failed = True
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[102] Failed to build/send calendar files for chat {chat_id}: {e}", exc_info=True)
        failed = True
    if failed:
        denidin.send_to_user(chat_id, NOTICE_SEND_FAILED)


def send_files_for(denidin: Any, reminder_manager: Any, chat_id: str, reminder_ids: List[str]) -> str:
    """On request: ONE PUBLISH file with every given ACTIVE reminder. Nothing is sent if any id is unknown
    or no longer active. Returns the tool-result text for the model (JSON on success, a ⚠️ line else)."""
    if reminder_manager is None:
        return "⚠️ שירות התזכורות אינו זמין כרגע."
    unique_ids = list(dict.fromkeys(reminder_ids))
    found = {entry["reminder_id"] for entry in reminder_manager.list_for_calendar(unique_ids)}
    missing = [reminder_id for reminder_id in unique_ids if reminder_id not in found]
    if missing or not unique_ids:
        return f"⚠️ לא נמצאה תזכורת פעילה עם המזהה: {', '.join(missing) or '(none given)'}"
    try:
        entries = [entry for entry in (_entry_for(reminder_manager, rid) for rid in unique_ids) if entry]
        file_name = _send(denidin, chat_id, entries, PUBLISH)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[102] On-demand calendar file failed for chat {chat_id}: {e}", exc_info=True)
        file_name = None
    if file_name is None:
        return "⚠️ לא הצלחתי לשלוח את קובץ היומן."
    return json.dumps({"sent": True, "reminders": len(entries), "file_name": file_name}, ensure_ascii=False)
