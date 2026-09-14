"""
New, standalone helpers for the Invoicing/Morning — Write capability (Feature 063).
Deliberately NOT imported from `src/handlers/ai_handler.py` (REQ-063-07: zero
coupling to the legacy module) - a smaller, single-pending-request shape rather
than a full port of bugfix-038's Group B reference-document-lookup enrichment
(tracked as a follow-up refinement; the fallback text below still names the
action/client/amount whenever the model's own call arguments carry them, which
covers the common case).
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Same split the legacy path uses (ai_handler.APPROVAL_REQUIRED_MCP_TOOLS /
# NO_APPROVAL_MCP_TOOLS) - reimplemented here as new, standalone data, not
# imported (REQ-063-07). Every Morning tool that creates/changes a real document
# or client record requires approval; pure lookups never do.
APPROVAL_REQUIRED_MCP_TOOLS = (
    "create_invoice",
    "create_transaction_account",
    "create_combo_document",
    "create_credit_note",
    "create_receipt",
    "create_combo_document_as_reference",
    "cancel_transaction_account",
    "add_client",
    "update_client",
)

NO_APPROVAL_MCP_TOOLS = (
    "list_invoices", "get_invoice_details", "get_financial_summary",
    "download_invoice_pdf", "list_clients", "get_client_details",
    "resolve_client_name",
)

_DOCUMENT_TYPE_LABELS = {
    "create_invoice": "חשבונית מס",
    "create_transaction_account": "חשבון עסקה",
    "create_combo_document": "חשבונית מס/קבלה",
    "create_credit_note": "חשבונית זיכוי",
    "create_receipt": "קבלה",
    "create_combo_document_as_reference": "חשבונית מס/קבלה (סגירת חשבון עסקה)",
}


def build_fallback_text(tool_name: str, arguments_json: str) -> str:  # pylint: disable=too-many-return-statements
    """Builds a specific approval-prompt line from a pending action's own
    arguments - same real-world need as ai_handler.py's
    `_build_pending_approval_fallback_text`, reimplemented standalone here
    (REQ-063-07). Never includes `original_internal_morning_id` (a raw internal
    id the constitution forbids ever showing the user) - falls back to naming
    the action/document type only for the three Group B reference tools plus
    cancel_transaction_account, same as the legacy behavior. Never raises."""
    generic = "יש פעולה הממתינה לאישורך לפני שהיא מתבצעת. אישור — כן/לא?"
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except (json.JSONDecodeError, TypeError):
        return generic
    if not isinstance(args, dict):
        return generic

    def _amount_suffix() -> str:
        amount = args.get("amount")
        return f" על סך {amount} ₪" if amount is not None else ""

    try:
        if tool_name == "create_invoice":
            return f"ליצור חשבונית ל{args['client_name']}{_amount_suffix()} עבור {args['description']} — לאשר?"
        if tool_name == "create_transaction_account":
            return f"להפיק חשבון עסקה ל{args['client_name']}{_amount_suffix()} — לאשר?"
        if tool_name == "create_combo_document":
            return f"להפיק חשבונית מס/קבלה ל{args['client_name']}{_amount_suffix()} — לאשר?"
        if tool_name == "create_credit_note":
            return f"להפיק חשבונית זיכוי לחשבונית שזוהתה בשיחה{_amount_suffix()} — לאשר?"
        if tool_name == "create_receipt":
            return f"להפיק קבלה עבור החשבונית שזוהתה בשיחה{_amount_suffix()} — לאשר?"
        if tool_name == "create_combo_document_as_reference":
            return f"לסגור את חשבון העסקה שזוהה בשיחה{_amount_suffix()} — לאשר?"
        if tool_name == "cancel_transaction_account":
            return "לבטל את חשבון העסקה שזוהה בשיחה — לא ייווצר שום מסמך — לאשר?"
        if tool_name == "add_client":
            return f"ליצור לקוח חדש: {args['name']}, {args['email']}, {args['phone']} — לאשר?"
        if tool_name == "update_client":
            display_name = args.get("new_name") or args["name"]
            return f"לעדכן את פרטי הלקוח {display_name} — לאשר?"
    except KeyError:
        return generic
    return generic


def find_approval_request(response) -> Optional[Any]:
    """First `mcp_approval_request` output item, or None."""
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) == "mcp_approval_request":
            return item
    return None


def count_executed_calls(response, tool_name: str) -> int:
    """How many times `tool_name` was actually executed (an `mcp_call` output
    item) in `response` - mirrors ai_handler.py's own duplicate-execution guard
    (a real, billed 2026-08-03 production incident: the approved action must
    never execute more than once)."""
    return sum(
        1 for item in (getattr(response, "output", None) or [])
        if getattr(item, "type", None) == "mcp_call" and getattr(item, "name", None) == tool_name
    )
