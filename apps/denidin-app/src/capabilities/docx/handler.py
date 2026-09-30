"""
cap_docx_write capability (Feature 063, fee agreement documents) — see
specs/repo/features/063-refactor-oversized-handlers/contracts/docx-write-capability.md.

Reuses `FeeAgreementToolHandler`/`DocTemplateEngine`/`WhatsAppHandler.
send_document_response` (Feature 083) completely unmodified. 2026-09-24 "resolution"
redesign: the four fee-agreement tools are plain local tools attached by
`load_capabilities(["cap_docx_write"])` to the SAME ongoing chain (get_template →
render → verify → send, no approval gate - 2026-09-13 human decision,
unchanged); the backbone's own loop dispatches each call here - there is
no separate inner loop any more.
"""
import json
import logging
from typing import Any, Dict, List


logger = logging.getLogger(__name__)



class _RoleShim:
    """Minimal duck-typed stand-in for the `user_obj` FeeAgreementToolHandler.
    build_tools() expects (just needs `.role`) — avoids pulling in the real
    User model construction machinery for what is purely an RBAC-gate check
    already performed once upstream by the backbone's role resolution."""

    def __init__(self, role):
        self.role = role


def build_tools(backbone, turn_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The four fee-agreement tools, RBAC-gated (empty for a non-godfather/
    admin role or when the feature isn't configured)."""
    fee_agreement_tools = getattr(backbone, "fee_agreement_tools", None)
    if fee_agreement_tools is None:
        return []
    return list(fee_agreement_tools.build_tools(_RoleShim(turn_context.get("role"))) or [])


def dispatch_direct_tool_call(backbone, tool_name: str, args: Dict[str, Any],
                               turn_context: Dict[str, Any]) -> str:
    """Executes one fee-agreement tool call directly."""
    fee_agreement_tools = getattr(backbone, "fee_agreement_tools", None)
    if fee_agreement_tools is None:
        return json.dumps({"error": "יצירת מסמכי הסכם שכר טרחה אינה מוגדרת כרגע."}, ensure_ascii=False)
    chat_id = turn_context.get("chat_id")
    whatsapp_handler = getattr(backbone, "whatsapp_handler", None)
    if tool_name == "get_fee_agreement_template":
        result = fee_agreement_tools.handle_get_template(args.get("variant_id"))
    elif tool_name == "render_fee_agreement_document":
        result = fee_agreement_tools.handle_render(args)
    elif tool_name == "verify_fee_agreement_document":
        result = fee_agreement_tools.handle_verify(args.get("document_id"))
    elif tool_name == "send_fee_agreement_document":
        if whatsapp_handler is None:
            result = {"error": "שליחת מסמכים אינה מוגדרת כרגע."}
        else:
            result = fee_agreement_tools.handle_send(
                args.get("document_id"), whatsapp_handler, chat_id, args.get("caption", ""),
            )
    else:
        result = {"error": f"unknown tool: {tool_name!r}"}
    return json.dumps(result, ensure_ascii=False)
