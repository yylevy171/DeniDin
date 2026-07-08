"""Hebrew/₪/VAT/date formatting helpers for MCP tool responses.

Responses are Hebrew by default (spec.md §REQ-I18N-001): ₪ currency,
DD/MM/YYYY dates, Hebrew status terms.
"""
from datetime import date

from .models import Invoice

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


def format_invoice_confirmation(invoice: Invoice) -> str:
    """Build a Hebrew, human-readable confirmation message for an invoice."""
    display_amount = invoice.total_amount if invoice.total_amount is not None else invoice.amount

    lines = [
        f"חשבונית #{invoice.number or invoice.id}",
        f"לקוח: {invoice.client_name}",
        f"סכום: {format_currency_ils(display_amount)}",
    ]
    if invoice.status:
        lines.append(f"סטטוס: {translate_status(invoice.status)}")
    if invoice.due_date:
        lines.append(f"תאריך יעד: {format_date_il(invoice.due_date)}")

    return "\n".join(lines)
