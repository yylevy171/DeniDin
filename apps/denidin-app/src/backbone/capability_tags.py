"""
CapabilityTag — the canonical, closed set of capabilities the Backbone
can invoke, per data-model.md's CapabilityTag table (063).

Every tag is a domain capability the model can `load_capabilities` (there are no
meta tags: the backbone is one tool-driven loop, see
contracts/capability-resolution-loop.md).
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class CapabilityTag(str, Enum):
    """The canonical capability tags. Value == prompt filename stem under
    config/prompts/capabilities/<value>.md.

    Every capability (and every flow) carries the `cap_`/`flow_` prefix so a
    name is unmistakable wherever it is mentioned. `cap_approval_with_buttons`
    is domain-agnostic and on-demand - flows that need a sign-off load it.
    The four ALWAYS_PRESENT_CAPABILITIES below are deliberately NOT tags:
    they can't be loaded or unloaded."""

    INVOICING_WRITE = "cap_invoicing_write"
    INVOICING_READ = "cap_invoicing_read"
    CLIENT_WRITE = "cap_client_write"
    CLIENT_READ = "cap_client_read"
    LEDGER_QUERY = "cap_ledger_query"
    REMINDERS_WRITE = "cap_reminders_write"
    REMINDERS_READ = "cap_reminders_read"
    MEDIA_ANALYSIS = "cap_media_analysis"
    DOCX_WRITE = "cap_docx_write"
    APPROVAL_WITH_BUTTONS = "cap_approval_with_buttons"


# Capabilities that are always in the instructions, in THIS fixed order (right
# after the backbone text, for a byte-stable cacheable prefix), whose tools are
# always attached, and that can never be unloaded. Each has its own prompt file
# under config/prompts/capabilities/<name>.md; flows and capabilities refer to
# them by name and nudge when to use them.
ALWAYS_PRESENT_CAPABILITIES: tuple = (
    "cap_send_to_user",
    "cap_react_to_message",
    "cap_send_progress_update",
    "cap_record_planning_status",
)


@dataclass(frozen=True)
class CapabilityInfo:
    tag: CapabilityTag
    # A few-sentence summary of the DOMAIN this capability covers - not how to call it,
    # not its internal mechanics. This is the single place that knowledge is
    # authored; the backbone's instructions render it generically as the
    # capability catalog (capability_catalog_text below), so the model can
    # recognize which domain a request touches and `load_capabilities` it.
    description: Optional[str] = None


# Canonical order. Matters for cache-hit consistency of the rendered catalog
# (REQ-063-06).
CAPABILITY_INFO: tuple = (
    CapabilityInfo(
        CapabilityTag.INVOICING_WRITE,
        "Creating a Morning DOCUMENT for a client - an invoice, a receipt, a "
        "transaction account, a credit note, or a combo tax-invoice/receipt - or "
        "cancelling a transaction account. Writes only: finding the client or the "
        "existing document, and getting approval, are the calling flow's job, so "
        "load it only through that flow (flow_issue_*, flow_cancel_*, "
        "flow_payment_received_*), never directly. Not for creating or updating a "
        "client record - see cap_client_write.",
    ),
    CapabilityInfo(
        CapabilityTag.INVOICING_READ,
        "Reading from the invoicing system (Morning): a specific document's own "
        "status and details, recent documents, a financial summary, a download "
        "link. It is given an already-resolved client name or document id. Not "
        "for a client's own details - see cap_client_read - and not the first "
        "choice for a general owed/paid amount question - see cap_ledger_query.",
    ),
    CapabilityInfo(
        CapabilityTag.CLIENT_WRITE,
        "Creating a new client record, or updating an existing client's own "
        "details (name/email/phone) in Morning. Writes only: load it only through "
        "flow_add_client or flow_modify_client, never directly. Never for producing "
        "any document - see cap_invoicing_write.",
    ),
    CapabilityInfo(
        CapabilityTag.CLIENT_READ,
        "Looking up an existing client's own details (name/email/phone/id), "
        "listing clients, and resolving a client name to its exact stored Morning "
        "spelling. Never for a client's financial history - see cap_ledger_query "
        "and cap_invoicing_read.",
    ),
    CapabilityInfo(
        CapabilityTag.LEDGER_QUERY,
        "Answering questions about PAST fee agreements or bank deposits already "
        "recorded, including how much a client/payer owes or has paid - whether or "
        "not a formal Morning invoice exists. The ledger is a fast cache over "
        "Morning and covers agreement-level amounts Morning cannot see at all.",
    ),
    CapabilityInfo(
        CapabilityTag.REMINDERS_WRITE,
        "Creating, changing, or cancelling a reminder (one-time or recurring) for "
        "the user. Writes only: load it only through flow_create_reminder or "
        "flow_modify_reminder, never directly.",
    ),
    CapabilityInfo(
        CapabilityTag.REMINDERS_READ,
        "Looking up the user's own existing reminders - what's scheduled, for when.",
    ),
    CapabilityInfo(
        CapabilityTag.MEDIA_ANALYSIS,
        "Reading/extracting the content of an image or document the user sent. "
        "Used inside a larger flow, or on its own to work out what a piece of "
        "media is for.",
    ),
    CapabilityInfo(
        CapabilityTag.DOCX_WRITE,
        "Composing and sending a fee agreement document (הסכם שכר טרחה) to a "
        "client as a .docx file. Never for invoices/receipts/transaction accounts "
        "or reminders. Load it only through flow_generate_fee_agreement_docx, never "
        "directly.",
    ),
    CapabilityInfo(
        CapabilityTag.APPROVAL_WITH_BUTTONS,
        "Asking the user for an explicit yes/no sign-off with tappable buttons, "
        "before a write. Domain-agnostic: it just asks; the write capability "
        "defines which details the approval must state.",
    ),
)

_INFO_BY_TAG = {info.tag: info for info in CAPABILITY_INFO}


def capability_catalog_text(tags: List[CapabilityTag]) -> str:
    """Renders `tags` as one "- name: description" line per capability, in
    canonical CAPABILITY_INFO order regardless of `tags`' own order - one
    authored description per capability, in capability_tags.py only."""
    ordered = [info for info in CAPABILITY_INFO if info.tag in set(tags) and info.description]
    return "\n".join(f"- {info.tag.value}: {info.description}" for info in ordered)
