"""PendingLocalToolApprovalManager for Feature 054's local-tool approval gate.

Tracks, per WhatsApp chat, a single reminder-related local function tool call
(create_reminder/modify_reminder/delete_reminder) awaiting the user's yes/no
reply - the local-tool equivalent of Feature 022's PendingApprovalManager.

Deliberately a SEPARATE class, not an extension of PendingApprovalManager:
CONSTITUTION's test-immutability rule protects Feature 047's existing
approval-gate tests, and PendingApproval is structurally tied to OpenAI's
MCP-specific mcp_approval_request/mcp_approval_response mechanism
(response_id/approval_request_id) - meaningless for a local `function_call`,
whose arguments are already fully known from response.output with no
server-side pending state to resolve against. See
specs/in-progress/054-reminders-functionality-mgmt/contracts/local-tool-approval-gate.md.

In-memory only, same rationale as PendingApprovalManager: losing a pending
approval on process restart just means the user re-issues the request, since
nothing was ever created.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PendingLocalToolApproval:
    """A single local reminder tool call awaiting the user's yes/no reply.

    Attributes:
        tool_name: "create_reminder" | "modify_reminder" | "delete_reminder".
        arguments: The tool call's already-parsed arguments (a dict, NOT a
            JSON string - unlike PendingApproval.arguments, there is no
            server-side round-trip that needs the raw string for audit
            replay; the ACTION ITSELF dispatches straight to ReminderManager
            with these values, never through OpenAI).
        response_id: The id of the Responses API call that produced this
            tool's `function_call` (the proposal turn). Needed - unlike
            MCP's approval flow, which needs response_id to build an
            `mcp_approval_response` item - purely so the CONFIRMATION
            follow-up call (after approval, asking the model to phrase a
            natural reply) can chain via `previous_response_id` on a LATER
            turn, once the original `response` object is out of scope. An
            earlier draft of this class dropped this field entirely,
            reasoning the local-tool action itself doesn't need it (true)
            without noticing the confirmation call still does.
        call_id: The `function_call` item's own `call_id` (from
            `extract_function_call_id`) - the follow-up's
            `function_call_output` item must reference this exact id, same
            requirement `_call_openai_ledger_followup_api` has, just spread
            across two turns instead of one here.
        created_at: Local isoformat timestamp, diagnostics only - no
            timeout/expiry, matching PendingApproval's own behavior.
        sent_message_id: Feature 047-style WhatsApp idMessage of the
            interactive-buttons message presenting this pending approval,
            once actually sent (None until attach_sent_message_id is
            called). A button tap whose stanzaId doesn't equal this field is
            stale by definition, including the case where it's still None.
    """
    tool_name: str
    response_id: str = ""
    call_id: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    sent_message_id: Optional[str] = None


class PendingLocalToolApprovalManager:
    """In-memory store of at-most-one pending local-tool approval per chat_id.

    At most one pending approval is tracked per chat - same single-pending
    -per-chat model as PendingApprovalManager, and the two are checked in a
    fixed order (MCP pending first, then local-tool pending) by AIHandler,
    since at most one of the two managers will ever be populated for a given
    chat_id in practice.
    """

    def __init__(self) -> None:
        self._pending: Dict[str, PendingLocalToolApproval] = {}
        logger.info(f"[054] PendingLocalToolApprovalManager created: id={id(self)}")

    def get(self, chat_id: str) -> Optional[PendingLocalToolApproval]:
        result = self._pending.get(chat_id)
        logger.info(
            f"[054] PendingLocalToolApprovalManager(id={id(self)}).get({chat_id!r}) -> "
            f"{result!r} (current keys: {list(self._pending.keys())!r})"
        )
        return result

    def set(self, chat_id: str, approval: PendingLocalToolApproval) -> None:
        self._pending[chat_id] = approval
        logger.info(
            f"[054] PendingLocalToolApprovalManager(id={id(self)}).set({chat_id!r}, "
            f"{approval!r}) (current keys: {list(self._pending.keys())!r})"
        )

    def clear(self, chat_id: str) -> None:
        self._pending.pop(chat_id, None)
        logger.info(
            f"[054] PendingLocalToolApprovalManager(id={id(self)}).clear({chat_id!r}) "
            f"(current keys: {list(self._pending.keys())!r})"
        )

    def attach_sent_message_id(self, chat_id: str, id_message: str) -> None:
        """Records the WhatsApp idMessage of the just-sent buttons message for
        chat_id's currently pending approval, if one still exists.

        No-op (logged, never raises) if the pending approval was already
        resolved/cleared/replaced before this call landed - same real-but-
        harmless race as PendingApprovalManager's own version of this method.
        """
        pending = self._pending.get(chat_id)
        if pending is None:
            logger.info(
                f"[054] PendingLocalToolApprovalManager(id={id(self)})."
                f"attach_sent_message_id({chat_id!r}, {id_message!r}) - no pending "
                "approval to attach to, ignored"
            )
            return
        pending.sent_message_id = id_message
        logger.info(
            f"[054] PendingLocalToolApprovalManager(id={id(self)})."
            f"attach_sent_message_id({chat_id!r}, {id_message!r}) - attached"
        )
