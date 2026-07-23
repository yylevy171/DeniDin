"""Hebrew/₪/VAT/date formatting helpers for MCP tool responses.

Responses are Hebrew by default (spec.md §REQ-I18N-001): ₪ currency,
DD/MM/YYYY dates, Hebrew status terms.
"""
from datetime import date
from typing import List, Optional

from .models import _DOCUMENT_TYPE_NAMES, _PAYMENT_TYPE_NAMES, FinancialSummary, Invoice

_STATUS_HE = {
    "paid": "שולם",
    "unpaid": "לא שולם",
    "overdue": "פג תוקף",
    "cancelled": "בוטל",
}


def format_currency_ils(amount: float) -> str:
    """Format a number as an Israeli New Shekel amount, e.g. 5000 -> '₪5,000.00'."""
    return f"₪{amount:,.2f}"


def format_date_il(value: date) -> str:
    """Format a date in the Israeli DD/MM/YYYY convention."""
    return value.strftime("%d/%m/%Y")


def translate_status(status: str) -> str:
    """Translate an invoice status to Hebrew; unknown statuses pass through unchanged."""
    return _STATUS_HE.get(status, status)


def translate_document_type(type_code: Optional[int]) -> str:
    """Translate a Morning document-type code to its real Hebrew name.

    Table confirmed live against GET /documents/types (2026-07-21/22,
    bugfix-014) - deterministic 1:1 label lookup, not interpretation. Lets
    the model tell a receipt/credit apart from a real invoice in
    list_invoices' own text output, and reason about Morning's document
    flows itself (per runtime_constitution.md) instead of the tool guessing.
    Unknown codes fall back to the raw code as a string; None to "".
    """
    if type_code is None:
        return ""
    return _DOCUMENT_TYPE_NAMES.get(type_code, str(type_code))


def translate_payment_type(payment_type_code: Optional[int]) -> str:
    """Translate a Morning payment-method code to its real Hebrew name.

    Table confirmed live against GET /payments/types (2026-07-22, bugfix-014).
    Unknown codes fall back to the raw code as a string; None to "".
    """
    if payment_type_code is None:
        return ""
    return _PAYMENT_TYPE_NAMES.get(payment_type_code, str(payment_type_code))


def format_invoice_confirmation(invoice: Invoice) -> str:
    """Build a Hebrew, human-readable confirmation message for an invoice."""
    display_amount = invoice.total_amount if invoice.total_amount is not None else invoice.amount

    lines = [
        f"חשבונית #{invoice.number or invoice.id}",
        f'לקוח: "{invoice.client_name}"',
        f"סכום: {format_currency_ils(display_amount)}",
    ]
    if invoice.type is not None:
        lines.append(f"סוג מסמך: {translate_document_type(invoice.type)}")
    if invoice.status:
        lines.append(f"סטטוס: {translate_status(invoice.status)}")
    if invoice.issue_date:
        lines.append(f"תאריך הפקה: {format_date_il(invoice.issue_date)}")
    if invoice.due_date:
        lines.append(f"תאריך יעד: {format_date_il(invoice.due_date)}")
    if invoice.pdf_url:
        lines.append(f"קישור: {invoice.pdf_url}")

    # Internal Morning documentId (GUID) - distinct from the human-readable
    # invoice number above. Without this, an MCP client (e.g. an LLM) that
    # just created/looked up an invoice has no legitimate way to pass the
    # right id to invoice_id-keyed tools (download_invoice_pdf,
    # update_invoice_status, get_invoice_details) later in the same
    # conversation - it would otherwise only ever see the friendly number.
    lines.append(f"מזהה פנימי (invoice_id): {invoice.id}")

    return "\n".join(lines)


def format_invoice_details(invoice: Invoice) -> str:
    """Build a full Hebrew details view (user-stories.md US3): status, dates,
    payments, in addition to the base confirmation fields."""
    lines = [format_invoice_confirmation(invoice)]

    if invoice.issue_date:
        lines.append(f"תאריך הפקה: {format_date_il(invoice.issue_date)}")

    if invoice.payments:
        lines.append("תשלומים:")
        for payment in invoice.payments:
            lines.append(f"  - {format_currency_ils(payment.amount)} ({format_date_il(payment.payment_date)})")

    if invoice.linked_documents:
        # Real, structured, bidirectional linkage (bugfix-014) - a receipt or
        # credit invoice linked to this document. Exposed so the model can
        # net paid/owed itself per runtime_constitution.md's flow guidance,
        # rather than treating each linked document as an independent charge
        # (the exact double-counting mistake this bugfix addresses).
        lines.append("מסמכים מקושרים:")
        for linked in invoice.linked_documents:
            label = translate_document_type(linked.type)
            date_str = f" ({format_date_il(linked.document_date)})" if linked.document_date else ""
            lines.append(f"  - {label} #{linked.number or linked.id}: {format_currency_ils(linked.amount)}{date_str}")

    return "\n".join(lines)


def format_financial_summary(summary: FinancialSummary) -> str:
    """Build a Hebrew, human-readable financial summary (user-stories.md US5)."""
    return "\n".join(
        [
            f"סיכום כספי: {format_date_il(summary.period_start)} - {format_date_il(summary.period_end)}",
            f"סה\"כ הופק: {format_currency_ils(summary.total_invoiced)}",
            f"שולם: {format_currency_ils(summary.total_paid)}",
            f"לא שולם: {format_currency_ils(summary.total_unpaid)}",
            f"מספר חשבוניות: {summary.invoice_count} "
            f"({summary.paid_invoice_count} שולמו, {summary.unpaid_invoice_count} לא שולמו)",
            f"ממוצע לחשבונית: {format_currency_ils(summary.average_invoice_amount)}",
        ]
    )


def format_invoice_list(invoices: List[Invoice], has_more: bool = False) -> str:
    """Build a Hebrew, human-readable list of invoices (user-stories.md US2).

    Args:
        invoices: Already-capped list (caller enforces the max-10 limit).
        has_more: Whether more results exist beyond this page.

    Returns:
        A Hebrew multi-line string; a friendly "no results" message if empty.
    """
    if not invoices:
        return "לא נמצאו חשבוניות התואמות את החיפוש."

    blocks = [format_invoice_confirmation(invoice) for invoice in invoices]
    message = "\n\n".join(blocks)

    if has_more:
        message += "\n\nיש תוצאות נוספות שלא הוצגו."

    return message
