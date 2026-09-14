"""
Reminders capability (Feature 063) — read + write(one-time-creation template) steps.
Wraps the existing, unmodified `src/managers/reminder_manager.py` and
`src/managers/pending_local_tool_approval_manager.py` (REQ-063-03) — this module owns
no storage of its own.

Write-side scope: only ONE-TIME reminder creation's full propose→approve→create flow
is implemented here as the template for the remaining write-capabilities' parity work
(recurring creation, modify/delete are tracked in tasks.md's Deferred section).
"""
import logging
from typing import Any, Dict, Optional

from src.backbone.capability_tags import CapabilityTag
from src.capabilities.reminders.tools import (
    CREATE_REMINDER_TOOL,
    extract_function_call,
    extract_function_call_id,
    is_affirmative_reply,
    list_active_reminders_text,
)
from src.managers.pending_local_tool_approval_manager import PendingLocalToolApproval
from src.models.message import AIRequest, AIResponse, NO_REPLY_SENTINEL
from src.utils.time_utils import now_local

logger = logging.getLogger(__name__)

APPROVAL_QUESTION = "לאשר? (כן/לא)"


def read(orchestrator, request: AIRequest, accumulated_context: str, note: str,
         turn_context: Dict[str, Any]) -> str:
    """Reminders — Read step: lists active reminders. Read-only, no approval needed
    (mirrors AIHandler's list_reminders being an immediate-dispatch tool)."""
    del note, turn_context
    if orchestrator.reminder_manager is None:
        return "Reminders manager not configured."
    reminders = orchestrator.reminder_manager.list_active()
    orchestrator.call_capability_step(
        tag=CapabilityTag.REMINDERS_READ,
        request=request,
        accumulated_context=accumulated_context + f"\n\nActive reminders: {reminders}",
    )
    return list_active_reminders_text(reminders)


def propose_write(orchestrator, request: AIRequest, accumulated_context: str, note: str,
                   turn_context: Dict[str, Any]) -> str:
    """Reminders — Write step: proposes a one-time reminder creation, creating a
    PendingLocalToolApproval the same way AIHandler._handle_reminder_creation_proposal
    does today, reimplemented as new code (REQ-063-07)."""
    del note
    if orchestrator.pending_local_tool_approval_manager is None or orchestrator.reminder_manager is None:
        return "Reminders write path not configured."

    response = orchestrator.client.responses.create(
        model=request.model,
        instructions=orchestrator.build_instructions(
            CapabilityTag.REMINDERS_WRITE, accumulated_context, request.timestamp,
        ),
        input=[{"role": "user", "content": request.user_prompt}],
        max_output_tokens=request.max_tokens,
        tools=[CREATE_REMINDER_TOOL],
    )

    args = extract_function_call(response, CREATE_REMINDER_TOOL["name"])
    if not args:
        return getattr(response, "output_text", "") or "לא זוהתה בקשה ליצירת תזכורת."

    chat_id = turn_context.get("chat_id") or request.chat_id
    call_id = extract_function_call_id(response, CREATE_REMINDER_TOOL["name"]) or ""

    orchestrator.pending_local_tool_approval_manager.set(
        chat_id,
        PendingLocalToolApproval(
            tool_name=CREATE_REMINDER_TOOL["name"],
            response_id=getattr(response, "id", ""),
            call_id=call_id,
            arguments=args,
            created_at=now_local().isoformat(),
        ),
    )

    return (
        f"📋 לאישור — תזכורת חדשה: \"{args.get('message_text', '')}\" "
        f"בתאריך {args.get('one_time_due_at', '')}\n\n{APPROVAL_QUESTION}"
    )


def _approve_and_create(orchestrator, pending, chat_id: str,
                         created_by_phone: str, created_by_role: str) -> str:
    """Shared approve-branch logic for both a button tap and a typed 'כן' reply
    (contracts/local-tool-approval-gate.md: the two entry points converge on the
    same real ReminderManager.create_reminder call, TOCTOU-checked fresh at
    persist time either way)."""
    try:
        result = orchestrator.reminder_manager.create_reminder(
            message_text=pending.arguments.get("message_text", ""),
            schedule_type="one_time",
            one_time_due_at=pending.arguments.get("one_time_due_at"),
            recurrence=None,
            created_by_phone=created_by_phone,
            created_by_role=created_by_role,
            delivery_chat_id=chat_id,
        )
        return f"✅ נוצרה תזכורת (מזהה {result['reminder_id']}), מועד: {result['due_at']}"
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Reminder creation failed on approval: %s", exc)
        return "⚠️ יצירת התזכורת נכשלה. נסו שוב."


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

    reply_text = _approve_and_create(orchestrator, pending, chat_id, "", "")
    return AIResponse(
        request_id=(request.request_id if request else ""),
        response_text=reply_text,
        tokens_used=0, prompt_tokens=0, completion_tokens=0,
        model=(request.model if request else ""),
        finish_reason="stop",
        timestamp=int(now_local().timestamp()),
        should_reply=reply_text.strip() != NO_REPLY_SENTINEL,
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
    reply_text = _approve_and_create(orchestrator, pending, chat_id, created_by_phone, created_by_role)
    return AIResponse(
        request_id=request.request_id,
        response_text=reply_text,
        tokens_used=0, prompt_tokens=0, completion_tokens=0,
        model=request.model,
        finish_reason="stop",
        timestamp=request.timestamp or int(now_local().timestamp()),
        should_reply=reply_text.strip() != NO_REPLY_SENTINEL,
    )
