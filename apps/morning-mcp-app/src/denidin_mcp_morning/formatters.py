"""Hebrew/₪/VAT/date formatting helpers for MCP tool responses.

Responses are Hebrew by default (spec.md §REQ-I18N-001): ₪ currency,
DD/MM/YYYY dates, Hebrew status terms.
"""
from datetime import date
from typing import List, Optional

from .models import _DOCUMENT_TYPE_NAMES, _PAYMENT_TYPE_NAMES, Client, FinancialSummary, Invoice

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
    # get_invoice_details, create_receipt, create_credit_note,
    # close_transaction_account) later in the same conversation - it would
    # otherwise only ever see the friendly number.
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


def format_invoice_list(invoices: List[Invoice], total_matched: int) -> str:
    """Build a Hebrew, human-readable list of invoices (user-stories.md US1/US3).

    Feature 038: the caller (`tools.list_invoices`) has already fetched the
    complete, status-filtered result set (bounded by the fetch cap) and
    decided how much of it fits within the token budget - `invoices` here
    is that possibly-token-budget-truncated list, `total_matched` is always
    the true post-status-filter count (equal to `len(invoices)` when
    nothing was truncated).

    Args:
        invoices: The invoices to display (a prefix of the full match set
            when token-budget truncation occurred).
        total_matched: The true total number of matching invoices.

    Returns:
        A Hebrew multi-line string; a friendly "no results" message if empty.
    """
    if not invoices:
        return "לא נמצאו חשבוניות התואמות את החיפוש."

    blocks = [format_invoice_confirmation(invoice) for invoice in invoices]
    shown = len(invoices)

    if shown < total_matched:
        header = f"מוצגות {shown} מתוך {total_matched} חשבוניות שנמצאו:"
        message = header + "\n\n" + "\n\n".join(blocks)
        message += (
            "\n\nיש תוצאות נוספות שלא הוצגו כי ההודעה ארוכה מדי - "
            "אנא צמצם/י את החיפוש (למשל לפי טווח תאריכים, לקוח, או סטטוס)."
        )
        return message

    header = f"נמצאו {shown} חשבוניות:"
    return header + "\n\n" + "\n\n".join(blocks)


def _format_client_summary_line(client: Client) -> str:
    """One-line summary for format_client_list: name + identifying detail.

    Never includes the internal client_id (REQ-CLIENT-018) - unlike invoices,
    client tools resolve by name, so there's no legitimate reason to surface it.
    """
    details = []
    if client.tax_id:
        details.append(f"ח.פ {client.tax_id}")
    if client.phone:
        details.append(f"טלפון {client.phone}")
    if details:
        return f"{client.name} ({', '.join(details)})"
    return client.name


def format_client_list(clients: List[Client]) -> str:
    """Build a Hebrew, human-readable list of clients (user-stories.md US1)."""
    if not clients:
        return "אין לך לקוחות רשומים כרגע."

    return "\n".join(_format_client_summary_line(c) for c in clients)


def format_client_details(client: Client, is_exact_match: bool = True) -> str:
    """Build a full Hebrew details view for a single client (user-stories.md US2).

    Never includes the internal client_id (REQ-CLIENT-018).

    Args:
        client: The resolved client to display.
        is_exact_match: Whether the search query was an exact (case-
            insensitive) match of the stored name. When False, the client
            was resolved via a partial/prefix reference - the opening line
            explicitly discloses which client was found, rather than
            silently presenting details as if the reference were certain.
    """
    if is_exact_match:
        lines = [f"לקוח: {client.name}"]
    else:
        lines = [f"מצאתי את הלקוח הבא: {client.name}"]
    if client.email:
        lines.append(f"מייל: {client.email}")
    if client.phone:
        lines.append(f"טלפון: {client.phone}")
    if client.tax_id:
        lines.append(f"ח.פ: {client.tax_id}")
    return "\n".join(lines)


def format_client_not_found() -> str:
    """Friendly Hebrew message when a name lookup matches zero clients."""
    return "לא נמצא לקוח בשם הזה."


def format_client_name_confirmation_question(candidate_name: str) -> str:
    """Hebrew confirmation question (bugfix-039, expanded 2026-08-11 per
    user decision) for ANY tool - read or write - that resolves a
    client_name to exactly one real client whose stored name isn't the
    literal spelling given. Never silently proceed under the guessed name
    (a write tool would create a real Morning document against a possibly-
    wrong client before the user ever sees which one was picked) and never
    silently refuse "not found" either - ask, and let the model re-invoke
    the same tool with the now-confirmed exact name once the user answers.

    A closed yes/no question (bugfix-028 B1: open-ended phrasing like a bare
    "לאשר?" gets misparsed - always end "אישור - כן/לא?" so the parser has
    something reliable to match), not a request for the user to retype
    anything themselves."""
    return f'מצאתי לקוח בשם "{candidate_name}" - האם לזה התכוונת? אישור - כן/לא?'


def format_client_name_resolved(resolved_name: str) -> str:
    """Hebrew confirmation for resolve_client_name's EXACT-match case
    (client-name-resolution architecture fix, bugfix-028 sub-piece) - the
    model should copy resolved_name verbatim into whichever tool it calls
    next, together with name_resolved=True. Deliberately plain/short (no
    client_id, REQ-CLIENT-018) - quoted, matching the existing convention
    (format_invoice_confirmation's 'לקוח: "..."') that names appear in
    "quotes" specifically so the model can spot-and-copy them as one atomic
    token (see runtime_constitution.md's "reuse an id AND name" rule)."""
    return f'שם הלקוח המדויק במורנינג: "{resolved_name}"'


def format_name_not_resolved() -> str:
    """Hebrew message when a client-resolving tool is called with
    name_resolved not True (client-name-resolution architecture fix,
    bugfix-028 sub-piece). Returned as ORDINARY tool output, never raised -
    this is a procedural instruction for the calling model to act on
    immediately in the same turn (call resolve_client_name, then retry),
    not a domain question meant for the end user to see."""
    return (
        "יש לפנות תחילה לכלי resolve_client_name עם שם הלקוח, לוודא שם מדויק "
        "התואם למאוחסן במורנינג, ולקרוא לכלי הזה שוב עם name_resolved=true "
        "והשם המדויק שהוחזר."
    )


def format_original_not_linked_to_client() -> str:
    """Friendly Hebrew message when a Group B tool's linked original document
    has no real client attached (feature 027, REQ-INV-013) - a pre-feature,
    bare-name-only document. Deliberately does not imply a fix exists (no
    "try again" phrasing) - this feature builds no remediation path
    (spec.md Clarifications 2026-08-06)."""
    return "לא ניתן להפיק מסמך מקושר עבור חשבונית זו - היא לא מקושרת ללקוח קיים במערכת."


def format_too_many_invoices_message(total: int) -> str:
    """Hebrew message when list_invoices' real Morning total exceeds the
    fetch cap (user-stories.md US2, REQ-INVOICE-003) - states the real
    total (never silently truncated) and asks for a narrower search rather
    than fetching further pages or dumping a huge, unusable reply. Mirrors
    format_too_many_clients_message's structure and tone."""
    return (
        f"נמצאו {total} חשבוניות התואמות את החיפוש - יותר מדי להצגה כרשימה אחת. "
        f"אנא צמצם/י את החיפוש (למשל לפי טווח תאריכים, לקוח, או סטטוס)."
    )


def format_too_many_clients_message(total: int) -> str:
    """Hebrew message when a client search/list matches more results than
    can reasonably be displayed - states the real total (never silently
    truncated) and asks for a narrower search rather than dumping a huge,
    unusable reply."""
    return (
        f"נמצאו {total} לקוחות התואמים את החיפוש - יותר מדי להצגה כרשימה אחת. "
        f"אנא צמצם/י את החיפוש (למשל לפי חלק מהשם)."
    )


def format_ambiguous_clients_message(candidates: List[Client]) -> str:
    """Build a Hebrew disambiguation message when a name lookup matches more
    than one client (REQ-CLIENT-003/007) - lists each candidate's
    name/tax_id/phone (never the internal client_id, REQ-CLIENT-018) and asks
    the user to be more specific, without disclosing full details for either."""
    lines = ["נמצאו כמה לקוחות בשם דומה, אנא ציין/י באופן מדויק יותר:"]
    lines.extend(f"- {_format_client_summary_line(c)}" for c in candidates)
    return "\n".join(lines)
