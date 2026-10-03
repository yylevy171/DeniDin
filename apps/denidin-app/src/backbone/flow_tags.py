"""
FlowTag - the canonical, closed set of flows the Backbone can load
(Feature 063 "flows" level, sitting between the backbone and the capabilities).

A flow is a BLUEPRINT for a recurring kind of request: which capabilities to
load, in what order, and how their results feed each other - at the flow level
only, never a capability's own internals. The model picks flows from the
low-resolution catalog rendered into the backbone (`flow_catalog_text`) and
loads them with `load_flows([...])`; when no flow fits, it simply loads
capabilities at its own discretion - there is deliberately no fallback flow.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List


class FlowTag(str, Enum):
    """Value == prompt filename stem under config/prompts/flows/<value>.md."""

    ADD_CLIENT = "flow_add_client"
    MODIFY_CLIENT = "flow_modify_client"
    MORNING_DOCUMENT_WRITE = "flow_morning_document_write"
    ISSUE_INVOICE_FOR_PAYMENT_DUE = "flow_issue_invoice_for_payment_due"
    ISSUE_INVOICE_RECEIPT_COMBO = "flow_issue_invoice_receipt_combo"
    ISSUE_TRANSACTION_ACCOUNT = "flow_issue_transaction_account"
    ISSUE_RECEIPT_WITHOUT_INVOICE = "flow_issue_receipt_without_invoice"
    ISSUE_PAYMENT_RECEIVED_WITH_REFERENCE_DOC = "flow_issue_payment_received_with_reference_doc"
    CANCEL_DOCUMENT_WITH_CREDIT_NOTE = "flow_cancel_document_with_credit_note"
    CANCEL_TRANSACTION_ACCOUNT = "flow_cancel_transaction_account"
    FEE_AGREEMENT_PROVIDED_BY_USER = "flow_fee_agreement_provided_by_user"
    DEPOSIT_PROVIDED_BY_USER = "flow_deposit_provided_by_user"
    USER_QUESTION = "flow_user_question"
    INVOICING_QUERY = "flow_invoicing_query"
    GENERATE_FEE_AGREEMENT_DOCX = "flow_generate_fee_agreement_docx"
    CREATE_REMINDER = "flow_create_reminder"
    MODIFY_REMINDER = "flow_modify_reminder"


@dataclass(frozen=True)
class FlowInfo:
    tag: FlowTag
    # A few sentences: the goal of the flow and when it applies (and when it
    # does not) - enough for the model to choose among flows without loading
    # them. The single authored place; rendered generically by flow_catalog_text.
    description: str


# Canonical order (cache-stable rendering of the catalog).
FLOW_INFO: tuple = (
    FlowInfo(
        FlowTag.ADD_CLIENT,
        "Adding a brand-new client record to Morning (\"תוסיף לקוח חדש\", or a shared contact card "
        "the user wants saved). Checks for an existing or similar client first so a duplicate is "
        "never created by accident, tells the user about similar candidates, and creates the record"
        " only with approval. Other flows load it whenever a client turns out not to exist yet."
    ),
    FlowInfo(
        FlowTag.MODIFY_CLIENT,
        "Changing an existing client's own details (name, email, phone) in Morning. Resolves which "
        "real client is meant, relaying candidates when the match is not exact, and updates it with"
        " approval. Not for creating a client and not for documents."
    ),
    FlowInfo(
        FlowTag.MORNING_DOCUMENT_WRITE,
        "Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo "
        "invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a "
        "transaction account (\"תפיק חשבונית\", \"תוציא קבלה\", \"סמן כשולם\", \"בטל את "
        "החשבונית\"). Works out exactly which document the user means - asking when it is unclear "
        "- and then loads the flow for that document. Not for clients and not for reading "
        "documents."
    ),
    FlowInfo(
        FlowTag.ISSUE_INVOICE_FOR_PAYMENT_DUE,
        "Issuing a new tax invoice (305) for a client, for money that is still owed (\"תפיק חשבונית "
        "ללקוח X\"). Never for money that has already arrived. Money that has already arrived "
        "belongs to flow_issue_invoice_receipt_combo instead."
    ),
    FlowInfo(
        FlowTag.ISSUE_INVOICE_RECEIPT_COMBO,
        "Issuing a combined tax invoice/receipt (320) for a payment that has already been received "
        "and that no earlier document covers - the most common way to record incoming money, "
        "whether reported verbally or shown in a bank slip or payment screenshot. Money that an "
        "existing document already covers belongs to "
        "flow_issue_payment_received_with_reference_doc."
    ),
    FlowInfo(
        FlowTag.ISSUE_TRANSACTION_ACCOUNT,
        "Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own "
        "wording names this document type. Ordinary requests for an invoice belong to "
        "flow_issue_invoice_for_payment_due."
    ),
    FlowInfo(
        FlowTag.ISSUE_RECEIPT_WITHOUT_INVOICE,
        "Recording a standalone receipt (400) with no invoice behind it, for example a deposit. "
        "A receipt against an existing invoice belongs to "
        "flow_issue_payment_received_with_reference_doc."
    ),
    FlowInfo(
        FlowTag.ISSUE_PAYMENT_RECEIVED_WITH_REFERENCE_DOC,
        "Recording a payment received against an existing Morning document: a receipt (400) for an "
        "existing invoice (305), or a combo document (320) closing an existing transaction account "
        "(300) (\"סמן כשולם\"). Money that no document covers belongs to "
        "flow_issue_invoice_receipt_combo."
    ),
    FlowInfo(
        FlowTag.CANCEL_DOCUMENT_WITH_CREDIT_NOTE,
        "Cancelling an existing Morning document with a credit note (330) (\"בטל את החשבונית\"). "
        "Finds the one real document and shows its real data in the approval before writing."
    ),
    FlowInfo(
        FlowTag.CANCEL_TRANSACTION_ACCOUNT,
        "Cancelling an open transaction account (300) directly. No document of any kind is created."
        " Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note."
    ),
    FlowInfo(
        FlowTag.FEE_AGREEMENT_PROVIDED_BY_USER,
        "The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a"
        " client, or logs hours worked for a client (e.g. \"רן אורפני 4 שעות על היום\" - a work-log"
        " entry, never a reminder request). An agreement must never belong to a client Morning does"
        " not manage, so this makes sure the client exists first. Recording the agreement in the"
        " ledger happens automatically after the turn."
    ),
    FlowInfo(
        FlowTag.DEPOSIT_PROVIDED_BY_USER,
        "The user reports or forwards a bank deposit or a payment received - as text, or as a bank"
        " slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and"
        " when the user asks for a Morning document for it (or it is unclear whether they do), "
        "hands over to flow_morning_document_write. Recording the deposit in the ledger happens "
        "automatically after the turn."
    ),
    FlowInfo(
        FlowTag.USER_QUESTION,
        "Answering a question about the user's clients, past agreements, deposits, or amounts owed "
        "and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), "
        "and never answers that nothing exists before checking Morning where Morning could hold it."
    ),
    FlowInfo(
        FlowTag.INVOICING_QUERY,
        "Reading from the invoicing system for a client the user names: resolves the client's exact"
        " stored name first, then reads the documents or status. Other flows load it whenever they "
        "need to look up documents in Morning."
    ),
    FlowInfo(
        FlowTag.GENERATE_FEE_AGREEMENT_DOCX,
        "Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a "
        "prospective client. The client does not exist yet, so no client lookup is involved. "
        "Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user."
    ),
    FlowInfo(
        FlowTag.CREATE_REMINDER,
        "Creating a new reminder, one-time or recurring (\"תזכיר לי בעוד שעתיים\", "
        "\"תזכיר לי כל יום ראשון\"). Confirms the text and the schedule, and creates "
        "the reminder only with approval. Use this flow, not cap_reminders_write "
        "directly, whenever a reminder is added.",
    ),
    FlowInfo(
        FlowTag.MODIFY_REMINDER,
        "Changing or cancelling an existing reminder (\"תזיז את התזכורת\", \"תבטל את התזכורת\"). Looks "
        "up the user's real reminders to identify the exact one before modifying or deleting it, "
        "with approval. Adding a brand-new reminder belongs to flow_create_reminder. "
        "Use the reminder flows, not cap_reminders_write directly."
    ),
)


def flow_catalog_text(tags: List[FlowTag]) -> str:
    """Renders `tags` as one "- name: description" line per flow, in canonical
    FLOW_INFO order regardless of `tags`' own order."""
    wanted = set(tags)
    return "\n".join(f"- {info.tag.value}: {info.description}" for info in FLOW_INFO if info.tag in wanted)
