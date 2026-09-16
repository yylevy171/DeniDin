"""
Reminders capability (Feature 063) — read + write steps (one-time creation,
recurring creation, and modify/delete are all implemented — see propose_write and
_propose_modify_or_delete below). Wraps the existing, unmodified
`src/managers/reminder_manager.py` and
`src/managers/pending_local_tool_approval_manager.py` (REQ-063-03) — this module owns
no storage of its own.
"""
import logging
from typing import Any, Dict, Optional

from src.backbone.capability_tags import CapabilityTag
from src.capabilities.reminders.tools import (
    CREATE_REMINDER_TOOL,
    DELETE_REMINDER_TOOL,
    MODIFY_DELETE_REMINDER_TOOLS,
    MODIFY_REMINDER_TOOL,
    extract_any_function_call,
    extract_function_call_id,
    is_affirmative_reply,
    list_active_reminders_text,
)
from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval
from src.managers.reminder_manager import (
    InvalidRecurrenceError,
    OccurrenceNotFoundError,
    ReminderNotFoundError,
)
from src.models.message import AIRequest, AIResponse, NO_REPLY_SENTINEL
from src.models.user import Role
from src.utils.time_utils import now_local

logger = logging.getLogger(__name__)

APPROVAL_QUESTION = "לאשר? (כן/לא)"


def read(orchestrator, request: AIRequest, accumulated_context: str, note: str,
         turn_context: Dict[str, Any]) -> str:
    """Reminders — Read step: lists active reminders. Read-only, no approval needed
    (mirrors AIHandler's list_reminders being an immediate-dispatch tool)."""
    del note, turn_context
    if orchestrator.reminder_manager is None:
        return BACKBONE_CAPABILITY_NOT_CONFIGURED
    reminders = orchestrator.reminder_manager.list_active()
    orchestrator.call_capability_step(
        tag=CapabilityTag.REMINDERS_READ,
        request=request,
        accumulated_context=accumulated_context + f"\n\nActive reminders: {reminders}",
    )
    return list_active_reminders_text(reminders)


def propose_write(orchestrator, request: AIRequest, accumulated_context: str, note: str,
                   turn_context: Dict[str, Any]) -> str:
    """Reminders — Write step: proposes creating a NEW one-time reminder, OR
    changing/cancelling an EXISTING one - all three tools (create/modify/delete)
    are offered in the same call, since REMINDERS_WRITE covers "creating,
    changing, or cancelling a reminder" as one domain (capability_tags.py) and
    Planning only ever names the one tag. Whichever tool the model actually
    calls (at most one, since each is mutually exclusive by construction)
    decides which proposal branch runs below. Creates a PendingLocalToolApproval
    the same way AIHandler._handle_reminder_creation_proposal /
    _propose_reminder_modify_or_delete do today, reimplemented as new,
    standalone code (REQ-063-07).

    2026-09-16 (closing the same structural gap found+fixed in
    invoicing_write's own propose_write - this handler had the identical bug):
    this used to make its own bare API call with input=[current message only],
    bypassing orchestrator.call_capability_step (so never getting
    _turn_conversation_history/BACKBONE_TOOLS) because it needs the raw
    response object to extract a function_call, not just output_text. Fixed
    at the root - call_capability_step's own return_response=True hands back
    the raw response - rather than by forking the call path."""
    del note
    if orchestrator.pending_local_tool_approval_manager is None or orchestrator.reminder_manager is None:
        return BACKBONE_CAPABILITY_NOT_CONFIGURED

    reminders = orchestrator.reminder_manager.list_active()
    response = orchestrator.call_capability_step(
        tag=CapabilityTag.REMINDERS_WRITE,
        request=request,
        accumulated_context=accumulated_context + f"\n\nActive reminders: {reminders}",
        tools=[CREATE_REMINDER_TOOL] + MODIFY_DELETE_REMINDER_TOOLS,
        return_response=True,
    )

    tool_name, args = extract_any_function_call(
        response, [CREATE_REMINDER_TOOL["name"], MODIFY_REMINDER_TOOL["name"], DELETE_REMINDER_TOOL["name"]],
    )
    if not tool_name or args is None:
        return getattr(response, "output_text", "") or "לא זוהתה בקשה לתזכורת."

    if tool_name == CREATE_REMINDER_TOOL["name"]:
        chat_id = turn_context.get("chat_id") or request.chat_id
        call_id = extract_function_call_id(response, tool_name) or ""
        orchestrator.pending_local_tool_approval_manager.set(
            chat_id,
            PendingLocalToolApproval(
                tool_name=tool_name,
                response_id=getattr(response, "id", ""),
                call_id=call_id,
                arguments=args,
                created_at=now_local().isoformat(),
            ),
        )
        if args.get("schedule_type") == "recurring":
            when = (args.get("recurrence") or {}).get("first_occurrence_at", "")
            schedule_label = f"חוזרת, החל מ-{when}"
        else:
            schedule_label = f"בתאריך {args.get('one_time_due_at', '')}"
        return (
            f"📋 לאישור — תזכורת חדשה: \"{args.get('message_text', '')}\" "
            f"({schedule_label})\n\n{APPROVAL_QUESTION}"
        )

    return _propose_modify_or_delete(orchestrator, request, turn_context, response, tool_name, args)


def _propose_modify_or_delete(orchestrator, request: AIRequest, turn_context: Dict[str, Any],  # pylint: disable=too-many-positional-arguments
                               response, tool_name: str, args: Dict[str, Any]) -> str:
    """The modify/delete branch of propose_write above - split out only for
    readability, not a separate capability-step entry point."""
    reminder_id = args.get("reminder_id")
    scope = args.get("scope")
    if scope not in ("single_occurrence", "whole_series"):
        return "⚠️ לא ברור אילו תזכורות/מופע לשנות. נסו שוב."

    current = orchestrator.reminder_manager.get_reminder(str(reminder_id))
    if current is None:
        return "⚠️ לא נמצאה תזכורת כזו."
    if scope == "single_occurrence" and not args.get("occurrence_date_hint"):
        return "⚠️ חסר תאריך מופע ספציפי. נסו שוב."
    if scope == "single_occurrence" and current.get("rrule") is None:
        return "⚠️ אי אפשר לשנות מופע בודד בתזכורת חד-פעמית. נסו שוב."

    # Proposal-time validation only, discarded not persisted (re-validated at
    # approval time - contracts/local-tool-approval-gate.md's TOCTOU-closing pattern).
    try:
        if scope == "single_occurrence":
            orchestrator.reminder_manager.resolve_occurrence_datetime(
                str(reminder_id), current, str(args.get("occurrence_date_hint")),
            )
    except (InvalidRecurrenceError, OccurrenceNotFoundError, ReminderNotFoundError) as exc:
        logger.warning("%s proposal rejected during validation: %s", tool_name, exc)
        return "⚠️ הבקשה לא תקפה. נסו שוב."

    chat_id = turn_context.get("chat_id") or request.chat_id
    call_id = extract_function_call_id(response, tool_name) or ""
    orchestrator.pending_local_tool_approval_manager.set(
        chat_id,
        PendingLocalToolApproval(
            tool_name=tool_name,
            response_id=getattr(response, "id", ""),
            call_id=call_id,
            arguments=args,
            created_at=now_local().isoformat(),
        ),
    )

    action_label = "לשנות" if tool_name == MODIFY_REMINDER_TOOL["name"] else "לבטל"
    scope_label = "מופע בודד" if scope == "single_occurrence" else "כל הסדרה"
    return (
        f"📋 לאישור — {action_label} תזכורת \"{current.get('message_text', '')}\" "
        f"({scope_label})\n\n{APPROVAL_QUESTION}"
    )


def _approve_and_execute(orchestrator, pending, chat_id: str,
                          created_by_phone: str, created_by_role: str) -> str:
    """Shared approve-branch logic for a button tap or typed 'כן' reply, across all
    three reminders write tools (create/modify/delete) - the two entry points
    converge on the same real ReminderManager calls, TOCTOU-checked fresh at
    persist time either way (contracts/local-tool-approval-gate.md)."""
    try:
        if pending.tool_name == CREATE_REMINDER_TOOL["name"]:
            schedule_type = pending.arguments.get("schedule_type", "one_time")
            result = orchestrator.reminder_manager.create_reminder(
                message_text=pending.arguments.get("message_text", ""),
                schedule_type=schedule_type,
                one_time_due_at=pending.arguments.get("one_time_due_at"),
                recurrence=pending.arguments.get("recurrence"),
                created_by_phone=created_by_phone,
                created_by_role=created_by_role,
                delivery_chat_id=chat_id,
            )
            return f"✅ נוצרה תזכורת (מזהה {result['reminder_id']}), מועד: {result['due_at']}"

        if pending.tool_name == MODIFY_REMINDER_TOOL["name"]:
            reminder_id = str(pending.arguments.get("reminder_id"))
            scope = pending.arguments.get("scope")
            if scope == "whole_series":
                orchestrator.reminder_manager.modify_whole_series(
                    reminder_id,
                    new_message_text=pending.arguments.get("new_message_text"),
                    new_due_at=pending.arguments.get("new_due_at"),
                )
            else:
                orchestrator.reminder_manager.modify_single_occurrence(
                    reminder_id,
                    occurrence_date_hint=pending.arguments.get("occurrence_date_hint"),
                    new_message_text=pending.arguments.get("new_message_text"),
                    new_due_at=pending.arguments.get("new_due_at"),
                )
            return "✅ התזכורת עודכנה."

        if pending.tool_name == DELETE_REMINDER_TOOL["name"]:
            reminder_id = str(pending.arguments.get("reminder_id"))
            scope = pending.arguments.get("scope")
            if scope == "whole_series":
                orchestrator.reminder_manager.delete_whole_series(reminder_id)
            else:
                orchestrator.reminder_manager.delete_single_occurrence(
                    reminder_id, occurrence_date_hint=pending.arguments.get("occurrence_date_hint"),
                )
            return "✅ התזכורת בוטלה."

        logger.error("Unknown pending reminders tool_name: %r", pending.tool_name)
        return "⚠️ הפעולה נכשלה. נסו שוב."
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Reminder %s failed on approval: %s", pending.tool_name, exc)
        return "⚠️ הפעולה נכשלה. נסו שוב."


def resolve_button_tap(orchestrator, chat_id: str, selected_id: str, stanza_id: str,
                        request: Optional[AIRequest]) -> Optional[AIResponse]:
    """Resolves a "כן"/"לא" interactive-button tap against a pending reminders_write
    proposal. Returns None for a stale tap (mirrors AIHandler.resolve_button_tap's
    staleness guard: no pending approval, or stanza_id mismatch)."""
    pending = orchestrator.pending_local_tool_approval_manager.get(chat_id)
    if pending is None or pending.sent_message_id != stanza_id:
        return None

    orchestrator.pending_local_tool_approval_manager.clear(chat_id)

    if selected_id != "denidin_approve":
        return AIResponse(
            request_id=(request.request_id if request else ""),
            response_text="בוטל.",
            tokens_used=0, prompt_tokens=0, completion_tokens=0,
            model=(request.model if request else ""),
            finish_reason="stop",
            timestamp=int(now_local().timestamp()),
        )

    reply_text = _approve_and_execute(orchestrator, pending, chat_id, "", "")
    should_reply = reply_text.strip() != NO_REPLY_SENTINEL
    # 2026-09-15: approval-resolution turns (button tap / typed reply) bypass
    # get_response's normal _finalize_response entirely, so they need their own
    # session-persistence call - same real gap fix as _finalize_response's own
    # (see BackboneOrchestrator._persist_turn's docstring). This tool family is
    # RBAC-gated GODFATHER/ADMIN-only, so Role.GODFATHER is always at least as
    # permissive as the real resolving user's actual role for storage purposes.
    if request is not None:
        orchestrator._persist_turn(  # pylint: disable=protected-access
            request, reply_text, should_reply, chat_id, Role.GODFATHER,
            None, None, None, None, False, None,
        )
    return AIResponse(
        request_id=(request.request_id if request else ""),
        response_text=reply_text,
        tokens_used=0, prompt_tokens=0, completion_tokens=0,
        model=(request.model if request else ""),
        finish_reason="stop",
        timestamp=int(now_local().timestamp()),
        should_reply=should_reply,
    )


def resolve_typed_reply(orchestrator, request: AIRequest, chat_id: str,
                         created_by_phone: str, created_by_role: str) -> Optional[AIResponse]:
    """Resolves a typed "כן"/"לא" reply against a pending reminders_write proposal -
    the local-tool-approval equivalent of AIHandler._resolve_pending_local_tool_approval,
    reimplemented as new code (REQ-063-07). Checked by BackboneOrchestrator.get_response
    BEFORE Intent Identification/Planning run, same as the legacy pending-approval gate.

    Returns the final AIResponse if approved. None if declined/unrecognized - same
    contract as the legacy resolver: the caller then processes this same message as
    a normal fresh turn (Intent Identification -> Planning -> ...)."""
    pending = orchestrator.pending_local_tool_approval_manager.get(chat_id)
    if pending is None:
        return None

    if not is_affirmative_reply(request.user_prompt):
        orchestrator.pending_local_tool_approval_manager.clear(chat_id)
        return None

    orchestrator.pending_local_tool_approval_manager.clear(chat_id)
    reply_text = _approve_and_execute(orchestrator, pending, chat_id, created_by_phone, created_by_role)
    should_reply = reply_text.strip() != NO_REPLY_SENTINEL
    # 2026-09-15: see resolve_button_tap's own comment above - same real gap fix.
    try:
        role = Role(created_by_role.upper())
    except ValueError:
        role = Role.GODFATHER
    orchestrator._persist_turn(  # pylint: disable=protected-access
        request, reply_text, should_reply, chat_id, role,
        None, None, created_by_phone, created_by_phone, False, None,
    )
    return AIResponse(
        request_id=request.request_id,
        response_text=reply_text,
        tokens_used=0, prompt_tokens=0, completion_tokens=0,
        model=request.model,
        finish_reason="stop",
        timestamp=request.timestamp or int(now_local().timestamp()),
        should_reply=should_reply,
    )
