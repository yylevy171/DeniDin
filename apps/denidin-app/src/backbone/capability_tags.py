"""
CapabilityTag — the canonical, closed set of capabilities the Backbone orchestrator
can invoke, per data-model.md's CapabilityTag table (063).

Two kinds: META (about orchestration itself — always implicitly the first two steps
of every turn, never named inside a Plan) and DOMAIN (business logic, named by
Planning's output).
"""
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


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


# Canonical order — the data-model.md table's row order. Matters for cache-hit
# consistency of individual capability prompts (REQ-063-06), not for concatenation
# order of a multi-capability union (the superseded design).
CAPABILITY_INFO: tuple = (
    CapabilityInfo(CapabilityTag.INTENT_IDENTIFICATION, CapabilityKind.META),
    CapabilityInfo(CapabilityTag.PLANNING, CapabilityKind.META),
    CapabilityInfo(CapabilityTag.INVOICING_WRITE, CapabilityKind.DOMAIN),
    CapabilityInfo(CapabilityTag.INVOICING_READ, CapabilityKind.DOMAIN),
    CapabilityInfo(CapabilityTag.LEDGER_CAPTURE, CapabilityKind.DOMAIN),
    CapabilityInfo(CapabilityTag.LEDGER_QUERY, CapabilityKind.DOMAIN),
    CapabilityInfo(CapabilityTag.REMINDERS_WRITE, CapabilityKind.DOMAIN),
    CapabilityInfo(CapabilityTag.REMINDERS_READ, CapabilityKind.DOMAIN),
    CapabilityInfo(CapabilityTag.MEDIA_ANALYSIS, CapabilityKind.DOMAIN),
)

DOMAIN_CAPABILITY_TAGS: FrozenSet[CapabilityTag] = frozenset(
    info.tag for info in CAPABILITY_INFO if info.kind == CapabilityKind.DOMAIN
)

_VALID_VALUES: FrozenSet[str] = frozenset(tag.value for tag in CapabilityTag)


def is_valid_domain_capability(value: str) -> bool:
    """True iff `value` names one of the 7 domain CapabilityTags (never a meta tag —
    Planning's output must never name Intent Identification/Planning themselves,
    per data-model.md's Plan section)."""
    try:
        tag = CapabilityTag(value)
    except ValueError:
        return False
    return tag in DOMAIN_CAPABILITY_TAGS
