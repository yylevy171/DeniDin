"""
CapabilityTag — the canonical, closed set of capabilities the Backbone orchestrator
can invoke, per data-model.md's CapabilityTag table (063).

Two kinds: META (about orchestration itself — always implicitly the first two steps
of every turn, never named inside a Plan) and DOMAIN (business logic, named by
Planning's output).
"""
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, List, Optional


class CapabilityKind(str, Enum):
    """Meta capabilities are about how the orchestrator thinks; domain capabilities
    are business logic invoked per the Planning capability's plan."""

    META = "meta"
    DOMAIN = "domain"


class CapabilityTag(str, Enum):
    """The 9 canonical capability tags (data-model.md). Value == prompt filename stem
    under config/prompts/capabilities/<value>.md."""

    INTENT_IDENTIFICATION = "intent_identification"
    PLANNING = "planning"
    INVOICING_WRITE = "invoicing_write"
    INVOICING_READ = "invoicing_read"
    LEDGER_CAPTURE = "ledger_capture"
    LEDGER_QUERY = "ledger_query"
    REMINDERS_WRITE = "reminders_write"
    REMINDERS_READ = "reminders_read"
    MEDIA_ANALYSIS = "media_analysis"


@dataclass(frozen=True)
class CapabilityInfo:
    tag: CapabilityTag
    kind: CapabilityKind
    # One-line, capability-agnostic-consumer-facing summary of the DOMAIN this
    # capability covers - not how to call it, not its internal mechanics. This is
    # the single place that knowledge is authored; Intent Identification and
    # Planning both render it generically (capability_catalog_text below) rather
    # than needing their own prompt files hand-edited per capability, which is
    # exactly the coupling a 2026-09-14 billed-test failure exposed: Intent
    # Identification had zero visibility into what capabilities even exist, so a
    # request landing squarely in an existing domain (a past-agreement lookup,
    # Ledger Query's job) got answered directly - and wrongly - instead of being
    # recognized as needing that domain at all. description is None for the two
    # META tags (never offered to a role, never part of the rendered catalog).
    description: Optional[str] = None


# Canonical order — the data-model.md table's row order. Matters for cache-hit
# consistency of individual capability prompts (REQ-063-06), not for concatenation
# order of a multi-capability union (the superseded design).
CAPABILITY_INFO: tuple = (
    CapabilityInfo(CapabilityTag.INTENT_IDENTIFICATION, CapabilityKind.META),
    CapabilityInfo(CapabilityTag.PLANNING, CapabilityKind.META),
    CapabilityInfo(
        CapabilityTag.INVOICING_WRITE, CapabilityKind.DOMAIN,
        "Creating/modifying a Morning document for a named client - an invoice, "
        "a receipt, a transaction account, a credit note, a client record, OR a "
        "combo tax-invoice/receipt (חשבונית מס/קבלה) for money already received. "
        "Applies whenever the user explicitly asks to produce/issue/close a "
        "document (e.g. \"תפיק חשבונית\", \"תסגור\"), even when the same message "
        "also reports a payment having arrived - reporting the payment is a "
        "separate, automatic Ledger Capture concern, but the explicit ask to "
        "produce a document is this domain's job, not Ledger Query's (which only "
        "ever looks up past amounts - it can't create anything).",
    ),
    CapabilityInfo(
        CapabilityTag.INVOICING_READ, CapabilityKind.DOMAIN,
        "Looking up a SPECIFIC existing Morning invoice/document's own status - has "
        "THIS invoice been paid, listing recent documents. NOT the first choice for "
        "a general owed/paid amount question - see Ledger Query, which is the "
        "preferred first domain for that shape of question.",
    ),
    CapabilityInfo(
        CapabilityTag.LEDGER_CAPTURE, CapabilityKind.DOMAIN,
        "Recognizing and recording a new fee agreement or bank deposit mentioned "
        "in conversation as a structured ledger event.",
    ),
    CapabilityInfo(
        CapabilityTag.LEDGER_QUERY, CapabilityKind.DOMAIN,
        "Answering questions about PAST fee agreements or bank deposits already "
        "recorded, INCLUDING how much a client/payer owes or has paid - covers "
        "amounts owed/paid whether or not a formal Morning invoice exists. For a "
        "lookup-shaped owed/paid question, this is the preferred first domain over "
        "Invoicing - Read (the ledger is a cache over Morning invoicing, faster to "
        "check, and covers agreement-level amounts Invoicing - Read cannot see at "
        "all); reach for Invoicing - Read only when the request is unmistakably "
        "about a live invoice/document's own status.",
    ),
    CapabilityInfo(
        CapabilityTag.REMINDERS_WRITE, CapabilityKind.DOMAIN,
        "Creating, changing, or cancelling a reminder (one-time or recurring) for "
        "the user.",
    ),
    CapabilityInfo(
        CapabilityTag.REMINDERS_READ, CapabilityKind.DOMAIN,
        "Looking up the user's own existing reminders - what's scheduled, for when.",
    ),
    CapabilityInfo(
        CapabilityTag.MEDIA_ANALYSIS, CapabilityKind.DOMAIN,
        "Reading/extracting the content of an image or document the user sent.",
    ),
)

DOMAIN_CAPABILITY_TAGS: FrozenSet[CapabilityTag] = frozenset(
    info.tag for info in CAPABILITY_INFO if info.kind == CapabilityKind.DOMAIN
)

_VALID_VALUES: FrozenSet[str] = frozenset(tag.value for tag in CapabilityTag)


_INFO_BY_TAG = {info.tag: info for info in CAPABILITY_INFO}


def capability_catalog_text(tags: List[CapabilityTag]) -> str:
    """Renders `tags` (always a role's allowed DOMAIN tags - never the META ones,
    which carry no description) as one "- name: description" line per capability,
    in canonical CAPABILITY_INFO order regardless of `tags`' own order. Shared by
    Intent Identification (so it can recognize which domain a request touches
    without per-capability hardcoded prompt text) and Planning (so its own "which
    tag do I name" step is grounded in the same descriptions, not just bare tag
    values) - one authored description per capability, in capability_tags.py only."""
    ordered = [info for info in CAPABILITY_INFO if info.tag in set(tags) and info.description]
    return "\n".join(f"- {info.tag.value}: {info.description}" for info in ordered)


def is_valid_domain_capability(value: str) -> bool:
    """True iff `value` names one of the 7 domain CapabilityTags (never a meta tag —
    Planning's output must never name Intent Identification/Planning themselves,
    per data-model.md's Plan section)."""
    try:
        tag = CapabilityTag(value)
    except ValueError:
        return False
    return tag in DOMAIN_CAPABILITY_TAGS
