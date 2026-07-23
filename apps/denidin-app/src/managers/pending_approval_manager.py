"""PendingApprovalManager for Feature 022's explicit document-creation approval gate.

Tracks, per WhatsApp chat, a single OpenAI Responses API MCP tool call that is
currently held pending approval (`mcp_approval_request`) — i.e. a document the
model wants to create in Morning (any tool in
ai_handler.DOCUMENT_CREATING_MCP_TOOLS) but has not yet been authorized to
execute. In-memory only (see class
docstring for why): losing a pending approval on process restart just means
the user re-issues the original request, since nothing was ever created.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PendingApproval:
    """A single MCP tool call awaiting the user's yes/no reply.

    Attributes:
        response_id: The id of the Responses API call that produced the
            `mcp_approval_request` output item — passed back as
            `previous_response_id` on the follow-up call so OpenAI resolves
            the approval against its own server-side state.
        approval_request_id: The `mcp_approval_request` item's own id —
            referenced by the `mcp_approval_response` input item.
        tool_name: The MCP tool name awaiting approval (e.g. "create_invoice").
        arguments: The tool call's arguments as a JSON string, for audit
            logging only.
        server_label: The MCP server label the call was made against.
        created_at: UTC isoformat timestamp, for logging/diagnostics only —
            there is no timeout/expiry: a pending approval stays open until
            the user replies (Feature 022 clarification).
    """
    response_id: str
    approval_request_id: str
    tool_name: str
    arguments: str
    server_label: str
    created_at: str


class PendingApprovalManager:
    """In-memory store of at-most-one pending MCP approval per chat_id.

    At most one pending approval is tracked per chat: only the document-
    creating tools are gated (Feature 022; see ai_handler.DOCUMENT_CREATING_MCP_TOOLS
    for the current list), and a single WhatsApp turn requesting two
    document-creating actions at once is an edge case where only the most
    recent pending request survives — not a silent-danger case, since
    nothing executes without approval either way.
    """

    def __init__(self) -> None:
        self._pending: Dict[str, PendingApproval] = {}
        logger.info(f"[022] PendingApprovalManager created: id={id(self)}")

    def get(self, chat_id: str) -> Optional[PendingApproval]:
        result = self._pending.get(chat_id)
        logger.info(
            f"[022] PendingApprovalManager(id={id(self)}).get({chat_id!r}) -> {result!r} "
            f"(current keys: {list(self._pending.keys())!r})"
        )
        return result

    def set(self, chat_id: str, approval: PendingApproval) -> None:
        self._pending[chat_id] = approval
        logger.info(
            f"[022] PendingApprovalManager(id={id(self)}).set({chat_id!r}, {approval!r}) "
            f"(current keys: {list(self._pending.keys())!r})"
        )

    def clear(self, chat_id: str) -> None:
        self._pending.pop(chat_id, None)
        logger.info(
            f"[022] PendingApprovalManager(id={id(self)}).clear({chat_id!r}) "
            f"(current keys: {list(self._pending.keys())!r})"
        )
