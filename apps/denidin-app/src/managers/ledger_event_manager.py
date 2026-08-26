"""
LedgerEventManager - Ledger Event Persistence (Feature 033).

Persists each captured `capture_ledger_event` result (or each fee-component of a
multi-component capture) as its own file under {data_root}/events/{event_id}.json,
matching the real downstream Events.csv schema column-for-column. Sibling to
MemoryManager/MediaFileManager - never a SessionManager concern (session.json no
longer holds any ledger-event state).

See specs/in-progress/033-ledger-event-persistence/data-model.md for the full field
list and population rules, and contracts/ledger-event-manager.md for the
integration contract this class fulfills.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from src.utils.time_utils import LOCAL_TZ, local_from_timestamp, now_local

logger = logging.getLogger(__name__)

# Events.csv's date/time columns are Asia/Jerusalem local time (confirmed with the
# user 2026-07-29). As of bugfix-037 (2026-08-10) that is no longer a per-field
# exception converted at the formatting boundary - it is what the whole system
# uses, so message_timestamp/captured_at are local too and every field on a
# persisted event now describes the same instant in the same zone.
ISRAEL_TZ = LOCAL_TZ  # retained name; the canonical definition lives in time_utils

# event_id letter prefix, matches Events.csv's existing convention exactly (verified
# by direct inspection of all 1159 rows - see research.md). "H"/חשבונית IS produced
# by capture_ledger_event as of Feature 025 (2026-08-21) - but only via the
# accounting-document reconciliation sweep's own handler, never via the ordinary
# conversational capture path (_handle_ledger_event_capture stays unmodified).
_LETTER_BY_SOURCE_TYPE = {
    "הסכם": "A",
    "בנק": "B",
    "חשבונית": "H",
}


class AccountingDocumentCacheEntry(NamedTuple):
    """Feature 025 (round 3): one entry in LedgerEventManager's in-memory
    accounting-document cache - a (creation_timestamp, event_id) pair, so an
    "anomaly" detection can name the real prior event_id in
    pending_review.json rather than just its timestamp."""
    timestamp: datetime
    event_id: str


# Safety-cap margin (spec.md Clarifications, round 3): 5-day catch-up cap
# (services/accounting_reconciliation_service.py's MAX_CATCHUP_LOOKBACK) plus
# a ~2-day safety margin before prune_accounting_document_cache drops an
# entry - the forward-only watermark can never legitimately re-reach a
# document older than this. Flagged for live confirmation of Morning's
# from_date filter semantics (data-model.md's "Pruning" note) before this
# exact margin is trusted as precisely right.
_ACCOUNTING_DOCUMENT_CACHE_RETENTION = timedelta(days=7)

# Literal placeholder written into reference when reference_hint is present - signals
# a later human/script needs to resolve the real prior event id (REQ-DATA-002).
# Named REFERENCE_PLACEHOLDER (not REPLACED_EVENT_PLACEHOLDER) since Phase 11's
# 2026-08-16 real-data audit found replaced_event_id/reference were never actually two
# different things in the real historical ledger - both hold real event_id(s), the
# only difference being direction (replaced_event_id: one-directional, the new event
# names what it supersedes; reference: found to be genuinely bidirectional in
# practice - two unrelated-by-supersession events pointing at each other). Folded into
# one field/mechanism; the direction/multi-ref question itself stays open, deferred.
REFERENCE_PLACEHOLDER = "צריך למצוא"

# Canonical status vocabulary -> Hebrew, mirroring morning-mcp-app's own
# formatters. Feature 025 Phase 9 keeps Morning's LITERAL label separately
# (accounting_document_status_label) because the canonical mapping is an
# interpretation: Morning's real axis is open/closed, not paid/unpaid.
_STATUS_HE = {"paid": "שולם", "unpaid": "לא שולם", "cancelled": "בוטל", "overdue": "פג תוקף"}

# Feature 043, US5: identifies which rule-set generation (LEDGER_EVENT_TOOL's schema +
# this file's field-population rules) produced a given persisted record - bumped by
# hand in the same commit as any future schema-affecting change. Written by both live
# capture and the player (both go through add_ledger_event, the single shared
# persistence method) - NEVER retro-applied to pre-existing files (see
# specs/in-progress/043-production-data-setup-tooling/data-model.md SS1 for why:
# retro-applying would require guessing which historical rule generation actually
# produced each old record, exactly the problem this field exists to avoid).
# Reset to 1 (Phase 11, 2026-08-16, human decision): today's real-Events.csv-grounded
# audit revised enough of the original Feature 033 shape (see data-model.md SS1b) that
# the result is treated as a new baseline generation, not an increment on the old one.
# Safe to reset because no real persisted file has EVER carried schema_version=1 (or
# any value) - confirmed by inspecting all 29 real files under test_data/events/, all
# predate the field entirely (MISSING), so there is no collision with an old "v1".
#
# whatsapp_chat removed (2026-08-19): redundant with session_id (the session it
# points at already carries its own whatsapp_chat) and message_id, both already
# sufficient traceability. Stays schema_version=1 (human decision) - v1 has never
# been deployed to real dev/prod data, same reset-safety reasoning as above still
# applies, so this is folded into the same baseline rather than bumped.
#
# Bumped 1->2 (Feature 025, 2026-08-21, per spec.md Clarifications - no
# config.feature_flags gate, this bump IS the gate): applies globally to every
# new write regardless of source_type, not just חשבונית - הסכם/בנק captures get
# schema_version=2 too, once this feature ships.
#
# Bumped 2->3 (Feature 025 Phase 9, 2026-08-23, commit 0ed64ea), then REVERTED
# 3->2 (2026-08-26, human decision - see CLAUDE.md's "LEDGER SCHEMA VERSION
# BUMPS ARE HUMAN-ONLY" rule): the 2->3 bump shipped with the numeric constant
# changed but no matching "Bumped 2->3" comment/decision record ever added - a
# real governance gap, caught only after the fact during unrelated Feature 061
# work. Phase 9's real new fields (accounting_document_status_code/
# _status_label/_payment_method, etc.) are genuine and stay - this revert is
# about the VERSION NUMBER's governance, not about removing those fields.
# Newly-written events therefore carry schema_version=2 while actually having
# v3's real shape; SCHEMA_VERSION_HISTORY below records this explicitly so a
# future reader isn't misled by the number alone.
CURRENT_SCHEMA_VERSION = 2

# Every entry here is a human-approved decision, added in the SAME commit that
# changes CURRENT_SCHEMA_VERSION above it - never after the fact.
# _verify_schema_version_history() (below) fails loudly at import time if the
# two ever drift apart - the exact enforcement this file was missing when the
# undocumented 2->3 bump above happened (2026-08-26 incident).
SCHEMA_VERSION_HISTORY = [
    {
        "version": 1,
        "date": "2026-08-16",
        "feature": "Phase 11 (043)",
        "decision": "Reset to 1 - human decision, see the comment block above this constant.",
    },
    {
        "version": 2,
        "date": "2026-08-21",
        "feature": "025",
        "decision": (
            "Bumped 1->2 per spec.md Clarifications - no config.feature_flags gate, this "
            "bump IS the gate."
        ),
    },
    {
        "version": 2,
        "date": "2026-08-26",
        "feature": "025 (post-hoc correction)",
        "decision": (
            "REVERTED from 3 back to 2 - the 2->3 bump (commit 0ed64ea, 2026-08-23) shipped "
            "without a matching human-approved decision record here. Phase 9's real schema "
            "changes (accounting_document_status_code/_status_label/_payment_method, etc.) "
            "stay unchanged; only the version NUMBER's governance is what changed."
        ),
    },
]


def _verify_schema_version_history() -> None:
    """Fails loudly at import time if CURRENT_SCHEMA_VERSION has no matching, human-approved
    SCHEMA_VERSION_HISTORY entry as its last item - see the constant's own comment and
    CLAUDE.md's "LEDGER SCHEMA VERSION BUMPS ARE HUMAN-ONLY" rule for why this exists."""
    if not SCHEMA_VERSION_HISTORY or SCHEMA_VERSION_HISTORY[-1]["version"] != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION} has no matching "
            "SCHEMA_VERSION_HISTORY entry as its last item - every schema_version change "
            "requires an explicit, human-approved decision recorded here, added in the same "
            "commit that changes the constant. See CLAUDE.md's 'LEDGER SCHEMA VERSION BUMPS "
            "ARE HUMAN-ONLY' rule."
        )


_verify_schema_version_history()

# Matches ש"ח / ש׳ח / שח (various quote-character renderings of "shekel chadash").
_SHEKEL_WORD_RE = re.compile(r'ש["\'״]?ח')
_NUMERIC_RE = re.compile(r'-?\d+(\.\d+)?')

# REQ-DATA-004: any run of characters that isn't Hebrew/ASCII alphanumeric becomes a
# single underscore, matching the real Events.csv agreement_id/component_id convention
# (e.g. "0726-אתי_אסולין-ערעור_לארצי") - verified against all 1159 rows, 2026-07-30.
_SLUG_DISALLOWED_RE = re.compile(r'[^0-9A-Za-zא-ת]+')

_HOURS_NUMERIC_RE = re.compile(r'^(-?\d+(?:\.\d+)?)\s*(?:שעות|שעה)?$')
_HOURS_AND_HALF_RE = re.compile(r'^(.+?)\s+וחצי$')

# REQ-DATA-009 (added 2026-08-02, user directive: "hours should always be numerical"):
# bounded, common Hebrew hour-count words - deliberately not exhaustive (mirrors
# _normalize_amount's philosophy: a small, reliable dictionary that gives up
# gracefully on anything outside it, rather than guessing).
_HOURS_WORD_MAP = {
    "שעה": 1, "שעתיים": 2,
    "שלוש שעות": 3, "שלוש": 3,
    "ארבע שעות": 4, "ארבע": 4,
    "חמש שעות": 5, "חמש": 5,
    "שש שעות": 6, "שש": 6,
    "שבע שעות": 7, "שבע": 7,
    "שמונה שעות": 8, "שמונה": 8,
    "תשע שעות": 9, "תשע": 9,
    "עשר שעות": 10, "עשר": 10,
    "אחת עשרה שעות": 11, "אחת עשרה": 11,
    "שתים עשרה שעות": 12, "שתים עשרה": 12,
}


def _normalize_hours(raw: Optional[str]) -> Optional[float]:
    """REQ-DATA-009: code-side hours normalization (same "never trust the AI's own
    math/word-form verbatim" discipline as _normalize_amount) - the AI reports hours
    exactly as stated (a digit string or a Hebrew number-word like "שעתיים"/"שעה
    וחצי"), code resolves it to a number so `hours` is always numerical when
    populated. Returns None if the text doesn't match a known numeric or word form
    (never guesses) - caller falls back to blank + preserving the original text in
    notes, exactly like an unparseable amount."""
    if not raw or not raw.strip():
        return None
    text = raw.strip()

    numeric_match = _HOURS_NUMERIC_RE.match(text)
    half_match = _HOURS_AND_HALF_RE.match(text)
    half_base = _HOURS_WORD_MAP.get(half_match.group(1).strip()) if half_match else None

    if numeric_match:
        value = round(float(numeric_match.group(1)), 2)
    elif text in ("חצי שעה", "חצי"):
        value = 0.5
    elif text in ("רבע שעה", "רבע"):
        value = 0.25
    elif half_base is not None:
        value = half_base + 0.5
    elif text in _HOURS_WORD_MAP:
        value = float(_HOURS_WORD_MAP[text])
    else:
        value = None
    return value


def _normalize_amount(raw: Optional[str]) -> Optional[int]:
    """Code-side amount normalization (never AI math, per REQ-DATA-001): strip
    currency symbols/words and thousands commas, round to a signed integer NIS
    value. Returns None if the cleaned text isn't a single number (never guesses)."""
    if raw is None:
        return None
    cleaned = _SHEKEL_WORD_RE.sub('', raw)
    cleaned = cleaned.replace('₪', '').replace(',', '').strip()
    if _NUMERIC_RE.fullmatch(cleaned):
        return round(float(cleaned))
    return None


def _slugify(text: Optional[str]) -> str:
    """REQ-DATA-004: turns a short human-readable label into the underscore-joined
    slug form used in agreement_id/component_id, matching real Events.csv style."""
    if not text:
        return ""
    return _SLUG_DISALLOWED_RE.sub('_', text.strip()).strip('_')


def _normalize_iso_date(raw: Optional[str]) -> Optional[str]:
    """REQ-DATA-005/007: code-side reformat (never trust the AI's own string format
    verbatim) from the AI-resolved ISO-8601 YYYY-MM-DD to the persisted DD/MM/YYYY
    convention (matching event_datetime's date portion). Used for txn_date - an
    AI-resolved calendar date distinct from the source message's own timestamp,
    whether it's an hours-worked date (הסכם) or a transaction date (בנק). Returns
    None if unparseable (never guesses)."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return None


def is_incomplete_capture(call_arguments: Dict) -> bool:
    """REQ-DATA-008 (added 2026-08-02, real incident): True when a capture_ledger_event
    call's components don't match what it itself claims - either an empty components
    array (the model called the tool, meaning it decided a real event exists, but
    described zero of it - a real, observed billed failure: 2026-07-31, the Mor
    ben-Shaya 6-component agreement image produced ledger_events_captured=1 with an
    empty components array, silently persisting nothing and logging no error) or a
    component_count that doesn't match the actual number of components given (a
    partial/undercounted split that an empty-array check alone wouldn't catch).

    Shared by both call sites so they agree on exactly what "incomplete" means:
    AIHandler.capture_ledger_events_from_text uses this to decide whether to retry
    the classification call once with corrective feedback; add_ledger_events_from_call
    uses it (after any such retry) to decide whether it still needs its own
    never-silently-drop fallback."""
    components = call_arguments.get("components") or []
    if not components:
        return True
    component_count = call_arguments.get("component_count")
    return component_count is not None and len(components) != component_count



def _parse_iso_local(raw: Optional[str]) -> Optional[datetime]:
    """Feature 025 Phase 9: parse morning-mcp-app's ISO-8601 creation timestamp
    into an aware Asia/Jerusalem datetime. Returns None (never guesses) if
    absent or unparseable - the caller then falls back to its normal
    message-timestamp path, which logs its own WARNING.

    Python 3.9's fromisoformat is strict: it rejects a trailing "Z" (only
    accepted from 3.11) and the space-separated variant, both of which a
    real payload could plausibly carry."""
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if len(text) >= 11 and text[10] == " ":
        text = text[:10] + "T" + text[11:]
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        logger.warning(f"Could not parse accounting_document_creation_date={raw!r} as ISO-8601")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ISRAEL_TZ)
    return parsed.astimezone(ISRAEL_TZ)


def _expand_accounting_document_json(event: Dict) -> Optional[Dict]:
    """Feature 025 Phase 9: turn morning-mcp-app's machine-readable document
    JSON into the flat `event` shape add_ledger_event already expects.

    The model's only job for a חשבונית capture is to copy this JSON verbatim
    (see services/accounting_reconciliation_service.py's prompt) - every value
    below is derived HERE, in code, never transcribed or interpreted by the
    AI. That is the whole point: the prose-transcription approach it replaces
    produced a fabricated 00:00 creation time and null amounts/descriptions in
    real live runs.

    Returns the expanded event dict, or None if the payload is missing or
    unparseable (logged as ERROR - never half-persist a garbled document).
    """
    raw = event.get("accounting_document_json")
    if not raw:
        logger.error(
            "חשבונית capture has no accounting_document_json payload - refusing to "
            "persist rather than writing a half-empty record"
        )
        return None
    try:
        # strict=False tolerates literal control characters inside string
        # values. Real live finding (2026-08-23): 3 of 18 documents were
        # silently lost because the MODEL re-emitted the payload with real
        # newlines where json.dumps had written \n escapes. The source from
        # morning-mcp-app is always valid JSON, and the content is intact -
        # only the whitespace escaping was mangled in transit, so rejecting it
        # would discard a perfectly good document. Genuinely malformed JSON
        # still raises and is rejected below.
        doc = json.loads(raw, strict=False) if isinstance(raw, str) else dict(raw)
    except (ValueError, TypeError) as e:
        logger.error(f"Could not parse accounting_document_json ({e}): {raw!r}")
        return None

    expanded = dict(event)
    expanded.pop("accounting_document_json", None)

    payment = doc.get("payment") or {}
    expanded.update({
        "accounting_document_display_number": doc.get("display_number"),
        # User decision (2026-08-23): the Morning document type IS the ledger's
        # event_subtype, using Morning's own retrieved label (never a
        # hand-written string) - e.g. "חשבונית מס", "חשבונית זיכוי", "קבלה".
        # This replaces the previous flat mapping, where all five types
        # collapsed to "הפקה" and the real type survived only in a separate
        # descriptive field, which is now redundant and removed. Whatever the
        # model passed as event_subtype is overridden here, same discipline as
        # every other derived value.
        "event_subtype": doc.get("type_name"),
        "accounting_document_status": _STATUS_HE.get(doc.get("status"), doc.get("status")),
        "accounting_document_status_code": doc.get("status_code"),
        "accounting_document_status_label": doc.get("status_label"),
        "accounting_document_creation_date": doc.get("creation_date"),
        "accounting_document_payment_method": payment.get("method"),
        "client_name": doc.get("client_name"),
        "description": _first_line_item_description(doc),
        # str(): the JSON carries a real number, but _normalize_amount (and the
        # whole existing pipeline) is built for the AI's textual amounts and
        # regex-matches its input. Stringifying here keeps one normalization
        # path for every source rather than branching it.
        "amount": None if doc.get("amount") is None else str(doc.get("amount")),
        # User's catch (2026-08-23): a payment's value date IS txn_date - "the
        # transaction/value date" the field already means for בנק - not a new
        # field. Morning sends ISO YYYY-MM-DD, exactly what _normalize_iso_date
        # expects.
        "txn_date": payment.get("date"),
        "bank_number": payment.get("bank_number"),
        "bank_branch": payment.get("bank_branch"),
        "bank_account": payment.get("bank_account"),
        "vat_status": _derive_vat_status(doc),
        "_linked_document": doc.get("linked_document"),
    })
    return expanded


def _first_line_item_description(doc: Dict) -> Optional[str]:
    """User decision (2026-08-23): "use only the 1st. log and warn if the array
    has more elements" - a multi-line document must never be silently
    half-captured, so the drop is loud rather than invisible.

    Falls back to the document-level description when there are no line items
    at all (a 400/קבלה genuinely has none)."""
    lines = doc.get("line_items") or []
    if len(lines) > 1:
        logger.warning(
            f"חשבונית {doc.get('display_number')}: document has {len(lines)} line items - "
            f"capturing only the first ({lines[0].get('description')!r}); the remaining "
            f"{len(lines) - 1} are NOT recorded in this ledger event"
        )
    if lines and lines[0].get("description"):
        return lines[0]["description"]
    return doc.get("description")


def _derive_vat_status(doc: Dict) -> str:
    """Derived in code, never asked of the model (same discipline as
    _normalize_amount / בנק's forced vat_status).

    A Morning document's `amount` is always the VAT-inclusive total, so a real
    VAT component means the captured amount includes it. When VAT is zero
    (an exempt document) neither "כולל" nor "לא כולל" is true, so we assert
    neither rather than state something false."""
    vat = doc.get("vat_amount")
    if vat:
        return "כולל"
    return "לא צוין"


def _format_linked_reference_hint(linked: Dict, resolved: bool) -> str:
    """Feature 025 Phase 9 (user decision, 2026-08-23): the hint ALWAYS carries
    everything known about the link - the linked document's number AND its type
    translated to Hebrew (never the raw numeric code) - and, when resolution
    failed, says so explicitly.

    Code-generated, never AI-authored. A failed link is relationship metadata,
    so it belongs here rather than in `description` (the component's own
    content) - Phase 11 removed the old `notes` field and split its roles that
    way."""
    type_name = linked.get("type_name") or ""
    number = linked.get("number")
    label = f"{type_name} {number}".strip()
    hint = f"מבטל/מתייחס למסמך {label}".strip()
    if not resolved:
        hint += " - לא אותר אירוע מתאים בליגר"
    return hint


class LedgerEventManager:
    """Owns {data_root}/events/ - one flat JSON file per persisted ledger event."""

    def __init__(self, storage_dir: str):
        """
        Initialize LedgerEventManager.

        Args:
            storage_dir: Directory for ledger-event storage. Callers MUST compose
                this from AppConfiguration.data_root at construction time
                (Path(config.data_root) / "events"), matching MediaFileManager's
                pattern exactly - never a hardcoded absolute path (REQ-STORE-001).
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # Feature 025: lazily built (see _ensure_accounting_document_cache), then
        # mutated in-process for the rest of this instance's lifetime - never
        # re-scanned from disk more than once per process, per spec.md's round-3
        # Clarifications ("ideally no reading and parsing of the ledger events...
        # per tick").
        self._accounting_document_cache: Optional[Dict[str, List["AccountingDocumentCacheEntry"]]] = None
        logger.info(f"LedgerEventManager initialized: storage_dir={self.storage_dir}")

    def _resolve_local_dt(self, message_timestamp: Optional[int]):
        """Shared by add_ledger_event: Asia/Jerusalem local
        datetime for the source message, falling back to processing time (with a
        WARNING) only if message_timestamp is genuinely absent - see spec.md Edge
        Cases. Drives event_datetime/event_id generation.

        Phase 11 (2026-08-16): no longer returns a second (pointer_ts_iso) value -
        that fed the now-removed message_timestamp persisted field (event_datetime
        already covers the same instant; see data-model.md SS1b).
        """
        if message_timestamp is not None:
            return local_from_timestamp(message_timestamp)
        logger.warning(
            "message_timestamp=None - falling back to processing time for "
            "date/time derivation only; the hard pointer itself is genuinely unknown"
        )
        return now_local()

    def _next_seq(self, letter: str, ddmmyy: str, hhmm: str) -> Optional[int]:
        """Smallest unused single digit (0-9) for this letter+date+minute, scoped
        only to files already under self.storage_dir (REQ-ID-002 - never reads
        Events.csv). None if all 10 are taken (REQ-ID-003's rare exhaustion case)."""
        prefix = f"{letter}{ddmmyy}{hhmm}"
        used = set()
        for existing in self.storage_dir.glob(f"{prefix}*.json"):
            stem = existing.stem
            if len(stem) == len(prefix) + 1 and stem[-1].isdigit():
                used.add(int(stem[-1]))
        for seq in range(10):
            if seq not in used:
                return seq
        return None

    def scan_accounting_documents(self) -> Dict[str, List["AccountingDocumentCacheEntry"]]:
        """Feature 025 (round 3): one-time disk-scan bootstrap for the
        in-memory accounting-document cache (_ensure_accounting_document_cache)
        - NEVER called more than once per process. Every persisted
        source_type="חשבונית" event, grouped by accounting_document_display_number
        into the list of distinct (creation_timestamp, event_id) pairs seen
        for it (almost always exactly one; more than one only in the anomaly
        case - see add_ledger_event; event_id is tracked so a later anomaly's
        pending_review.json entry can name the real prior event). Empty dict
        if none exist yet. A malformed/unparseable individual file logs a
        WARNING and is skipped, never raises - same defensive read discipline
        _load_event already uses.
        """
        result: Dict[str, List[AccountingDocumentCacheEntry]] = {}
        for existing in sorted(self.storage_dir.glob("*.json")):
            try:
                with existing.open(encoding="utf-8") as f:
                    record = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Skipping unreadable event file {existing}: {e}")
                continue

            if record.get("source_type") != "חשבונית":
                continue
            display_number = record.get("accounting_document_display_number")
            creation_date_str = record.get("accounting_document_creation_date")
            event_id = record.get("event_id")
            if not display_number or not creation_date_str:
                continue
            try:
                # tzinfo=ISRAEL_TZ: local_dt (add_ledger_event's own comparison
                # value) is always tz-aware - a naive value here would silently
                # never equal it (aware/naive == is always False, never raises),
                # breaking duplicate detection entirely rather than erroring loudly.
                creation_dt = datetime.strptime(
                    creation_date_str, "%d/%m/%Y %H:%M"
                ).replace(tzinfo=ISRAEL_TZ)
            except ValueError:
                logger.warning(
                    f"Skipping event file {existing} with unparseable "
                    f"accounting_document_creation_date={creation_date_str!r}"
                )
                continue
            result.setdefault(display_number, []).append(
                AccountingDocumentCacheEntry(creation_dt, event_id)
            )

        return result

    def _ensure_accounting_document_cache(self) -> Dict[str, List["AccountingDocumentCacheEntry"]]:
        """Lazy-builds self._accounting_document_cache via
        scan_accounting_documents() on first call; every subsequent call in
        this process's lifetime returns the already-built, in-memory-mutated
        cache directly - no re-scan (spec.md's round-3 "no reading and
        parsing of the ledger events... per tick" directive)."""
        if self._accounting_document_cache is None:
            self._accounting_document_cache = self.scan_accounting_documents()
        return self._accounting_document_cache

    def get_accounting_document_watermark(self) -> Optional[datetime]:
        """The max timestamp across the in-memory cache, or None if empty -
        used by the reconciliation service to derive each poll's "since"
        boundary. Triggers the same lazy one-time build as add_ledger_event."""
        cache = self._ensure_accounting_document_cache()
        all_timestamps = [entry.timestamp for entries in cache.values() for entry in entries]
        return max(all_timestamps) if all_timestamps else None

    def prune_accounting_document_cache(self, now: Optional[datetime] = None) -> None:
        """Feature 025 (round 3): drops any cache entry whose EVERY recorded
        timestamp is older than the 5-day safety-cap boundary plus a ~2-day
        margin (7 days total) before `now` (now_local() if not given -
        testability seam only, same convention as
        reminder_delivery_service.py's `now` parameter). Safe because the
        forward-only watermark can never legitimately cause a document that
        old to be re-queried again - see data-model.md's "Pruning" note for
        the still-open live-verification caveat on this exact margin."""
        cache = self._ensure_accounting_document_cache()
        now = now or now_local()
        boundary = now - _ACCOUNTING_DOCUMENT_CACHE_RETENTION
        to_drop = [
            display_number for display_number, entries in cache.items()
            if all(self._as_aware(entry.timestamp) < boundary for entry in entries)
        ]
        for display_number in to_drop:
            del cache[display_number]

    @staticmethod
    def _as_aware(value: datetime) -> datetime:
        """scan_accounting_documents parses naive local datetimes (no tzinfo,
        since they're re-derived from a plain "DD/MM/YYYY HH:MM" string) - a
        freshly-captured local_dt is tz-aware (ISRAEL_TZ). Comparing the two
        directly would raise; this normalizes a naive value to ISRAEL_TZ for
        comparison purposes only, never mutates what's stored."""
        return value if value.tzinfo is not None else value.replace(tzinfo=ISRAEL_TZ)

    def _append_pending_review(
        self,
        display_number: str,
        prior_entries: List["AccountingDocumentCacheEntry"],
        new_timestamp: datetime,
        new_event_id: str,
    ) -> None:
        """Feature 025 (round 3): appends one entry to
        {data_root}/accounting_reconciliation/pending_review.json for the
        "anomaly" case (same accounting_document_display_number, a genuinely
        new creation timestamp) - a human reviews this file out-of-band, same
        "capture now, review later, no notification" philosophy as the rest
        of this feature. Never reads back/resolves entries - no consumer of
        this file exists yet within this feature's own scope."""
        review_dir = self.storage_dir.parent / "accounting_reconciliation"
        review_dir.mkdir(parents=True, exist_ok=True)
        review_file = review_dir / "pending_review.json"

        entries = []
        if review_file.exists():
            try:
                with review_file.open(encoding="utf-8") as f:
                    entries = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"pending_review.json unreadable, starting fresh: {e}")
                entries = []

        most_recent_prior = max(prior_entries, key=lambda e: e.timestamp)
        now_str = now_local().strftime("%d/%m/%Y %H:%M")
        entries.append({
            "accounting_document_display_number": display_number,
            "prior_event_id": most_recent_prior.event_id,
            "prior_creation_date": most_recent_prior.timestamp.strftime("%d/%m/%Y %H:%M"),
            "new_event_id": new_event_id,
            "new_creation_date": new_timestamp.strftime("%d/%m/%Y %H:%M"),
            "detected_at": now_str,
        })

        tmp_path = review_file.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        tmp_path.replace(review_file)

    def add_ledger_event(
        self,
        session_id: str,
        event: Dict,
        message_id: Optional[str],
        message_timestamp: Optional[int],
        agreement_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Persist a captured `capture_ledger_event` result as its own file.

        Args:
            session_id: source session (no longer implied by folder nesting) - the
                session itself already carries its own whatsapp_chat, so the event
                record no longer duplicates it (2026-08-19)
            event: the parsed capture_ledger_event function-call arguments, merged
                shared+component shape - LEDGER_EVENT_TOOL's schema; `component_count`
                is popped separately by add_ledger_events_from_call and never reaches
                this flat shape - never mutated
            message_id: source message id (the traceability pointer this feature adds)
            message_timestamp: Unix epoch of the source message - drives event_datetime/
                event_id generation; falls back to processing time (WARNING logged)
                only if None, since the hard pointer is genuinely unknown, never guessed
            agreement_id: (REQ-DATA-004, added 2026-07-30; AI-authored since bugfix-agreement-label)
                caller-supplied agreement_id for a multi-component batch - used as-is when
                given, so every component in that batch shares byte-for-byte the same id.
                When None (a standalone, non-batched capture), taken directly from
                event["agreement_id"] as built by the AI itself, per LEDGER_EVENT_TOOL's
                schema (it builds the id once, in the documented format, when the matter
                is first created, and repeats the identical string for every later
                component/message referencing that same matter) - code no longer computes
                or slugifies any part of it. Ignored entirely when event["source_type"] ==
                "בנק" (agreement_id/component_id always None for bank events - no
                agreement concept applies).

        Returns:
            The new event_id on success, or None if REQ-ID-003's exhaustion case
            was hit (all 10 seq digits for this letter+minute already taken) -
            logged as ERROR internally, caller doesn't need to inspect why.
        """
        event = dict(event)  # never mutate caller's dict

        # Feature 025 Phase 9: a חשבונית capture arrives as ONE verbatim-copied
        # JSON blob from morning-mcp-app; every field below is derived from it
        # in code rather than transcribed by the model.
        if event.get("source_type") == "חשבונית":
            expanded = _expand_accounting_document_json(event)
            if expanded is None:
                return None
            event = expanded

        # Phase 11 (schema v2->v1 reset, 2026-08-16): captured_at/event_datetime share
        # one human-readable convention (DD/MM/YYYY HH:MM) instead of ISO+offset -
        # message_timestamp/sender are no longer separately persisted at all (the
        # former is fully covered by event_datetime; the latter had no reader anywhere
        # - see data-model.md SS1b for the full real-data-grounded audit).
        captured_at = now_local().strftime("%d/%m/%Y %H:%M")
        # Feature 025 Phase 9: a reconciliation capture has no source message -
        # its event_datetime/event_id come from the document's OWN real creation
        # instant, carried in the JSON payload with full precision.
        accounting_created_dt = _parse_iso_local(event.get("accounting_document_creation_date"))
        local_dt = accounting_created_dt or self._resolve_local_dt(message_timestamp)

        source_type = event.get("source_type")
        assert source_type is not None, "LEDGER_EVENT_TOOL's schema requires source_type"

        # Feature 025 (round 3): tri-state new/duplicate/anomaly guard - REPLACES
        # the old hard-refusal design entirely (user directive: "I don't like the
        # hard refusal... The 'since when' mechanism SHOULD NOT RELY ON A REFUSAL
        # MECHANISM"). Lives here (LedgerEventManager), not ai_handler.py - "it's
        # clearly a ledger requirement regardless of ai." See
        # contracts/ledger-event-manager-extension.md.
        accounting_document_display_number = None
        prior_entries_for_anomaly: List["AccountingDocumentCacheEntry"] = []
        if source_type == "חשבונית":
            accounting_document_display_number = event.get("accounting_document_display_number")
            if accounting_document_display_number is not None:
                cache = self._ensure_accounting_document_cache()
                seen_entries = cache.get(accounting_document_display_number, [])
                seen_timestamps = [entry.timestamp for entry in seen_entries]
                if local_dt in seen_timestamps:
                    logger.info(
                        f"חשבונית re-poll: accounting_document_display_number="
                        f"{accounting_document_display_number!r} at {local_dt!r} already "
                        f"captured - discarding (true duplicate, no new file)"
                    )
                    return None
                if seen_entries:
                    logger.warning(
                        f"חשבונית anomaly: accounting_document_display_number="
                        f"{accounting_document_display_number!r} previously seen at "
                        f"{seen_timestamps!r}, now seen at {local_dt!r} - persisting as a "
                        f"NEW event (not overwriting) and flagging to pending_review.json "
                        f"for human review"
                    )
                    # pending_review.json is written AFTER event_id exists (below) -
                    # this only remembers that it's needed. list(...) copies -
                    # seen_entries IS the cache's own live list object, which the
                    # "new"/"anomaly" cache-append below mutates in place; without
                    # this copy, the append would silently make this snapshot
                    # point at itself (the just-appended entry), not the real
                    # prior one.
                    prior_entries_for_anomaly = list(seen_entries)

        letter = _LETTER_BY_SOURCE_TYPE[source_type]
        ddmmyy = local_dt.strftime("%d%m%y")
        hhmm = local_dt.strftime("%H%M")

        seq = self._next_seq(letter, ddmmyy, hhmm)
        if seq is None:
            logger.error(
                f"No free seq digit (0-9) for {letter}{ddmmyy}{hhmm} - refusing to "
                f"persist this event rather than risk a collision"
            )
            return None

        event_id = f"{letter}{ddmmyy}{hhmm}{seq}"

        # notes (CSV column) was removed (Phase 11): its two roles now go to whichever
        # field actually matches the content - unparseable-value fallback text (this
        # component's own content) appends to description; AI-authored relationship
        # reasoning (why this replaces/relates to a prior event) is the AI's own job to
        # put in reference_hint directly, per the tool schema's updated description.
        amount_raw = event.get("amount")
        amount = _normalize_amount(amount_raw)
        description = event.get("description")
        if amount_raw is not None and amount is None:
            logger.warning(
                f"Could not normalize amount {amount_raw!r} to a single integer - "
                f"leaving 'amount' blank and preserving the original text in description"
            )
            description = f"{description}; {amount_raw}" if description else amount_raw

        # reference (Phase 11): unified mechanism, folding in what used to be the
        # separate replaced_event_id/replaces_hint pair - see data-model.md SS1b for the
        # real-data finding that motivated this (both held real event_ids in practice,
        # replaced_event_id one-directional, reference bidirectional - merged into one
        # field/direction question deferred).
        reference = REFERENCE_PLACEHOLDER if event.get("reference_hint") else None

        hours_raw = event.get("hours")
        hours = _normalize_hours(hours_raw)
        if hours_raw is not None and hours is None:
            logger.warning(
                f"Could not normalize hours {hours_raw!r} to a number - leaving "
                f"'שעות' blank and preserving the original text in description"
            )
            description = f"{description}; {hours_raw}" if description else hours_raw

        txn_date_raw = event.get("txn_date")
        txn_date = _normalize_iso_date(txn_date_raw)
        if txn_date is None:
            if hours_raw is not None:
                logger.warning(
                    f"'hours' is set ({hours_raw!r}) but txn_date {txn_date_raw!r} could "
                    f"not be normalized to YYYY-MM-DD - leaving 'תאריך_ביצוע' blank"
                )
            elif txn_date_raw is not None:
                logger.warning(
                    f"txn_date {txn_date_raw!r} could not be normalized to YYYY-MM-DD - "
                    f"leaving 'תאריך_ביצוע' blank"
                )

        # agreement_id (bugfix-agreement-label): fully AI-authored per LEDGER_EVENT_TOOL's
        # schema - no separate label field exists anywhere, and code no longer computes or
        # slugifies any part of this id, only uses it verbatim as given (see data-model.md
        # SS1b for the earlier Phase 11 history of this field).
        component_label = event.get("component_label")
        if source_type == "הסכם":
            resolved_agreement_id = agreement_id or event.get("agreement_id")
            component_id = f"{resolved_agreement_id}-{_slugify(component_label)}"
        else:
            # REQ-DATA-004: no agreement/component concept applies to בנק events
            resolved_agreement_id = None
            component_id = None
            component_label = None

        # Bank details apply only to בנק - forced null for הסכם regardless of what the
        # caller/AI passed, same defensive discipline as component_label above (never
        # trust an inapplicable field to have been left blank on its own).
        # Feature 025 Phase 9 (user decision, 2026-08-23): the בנק-only
        # restriction is LIFTED - a חשבונית document's own payment block carries
        # the same real-world meaning (which bank account the money moved
        # through), so it reuses these fields rather than duplicating them.
        # הסכם still forces them null: no payment mechanics apply there.
        if source_type in ("בנק", "חשבונית"):
            bank_number = event.get("bank_number")
            bank_branch = event.get("bank_branch")
            bank_account = event.get("bank_account")
        else:
            bank_number = None
            bank_branch = None
            bank_account = None

        # payer_name is a הסכם-only concept (a routed/intermediary payment) - forced
        # null for בנק regardless of what the AI passed, same defensive discipline as
        # bank_number/etc above (finding #4, 2026-08-18 player review: the model put
        # the depositor/account-holder name here about half the time instead of
        # client_name, despite the tool description now forbidding it). Rather than
        # just discarding a misplaced name (real data loss for exactly the mistake
        # this is guarding against), rescue it into client_name when the model left
        # client_name empty - never lose a real captured name to a field-choice
        # mistake, matching this file's existing amount/hours "preserve the original
        # rather than drop it" philosophy.
        client_name = event.get("client_name")
        payer_name_raw = event.get("payer_name")
        if source_type == "בנק":
            if not client_name and payer_name_raw:
                logger.warning(
                    f"בנק event: client_name empty but payer_name={payer_name_raw!r} "
                    f"given - payer_name doesn't apply to בנק, rescuing its value into "
                    f"client_name instead of discarding it"
                )
                client_name = payer_name_raw
            payer_name = None
        elif source_type == "חשבונית":
            # No routed-payment concept applies to a Morning document capture -
            # forced null, same discipline as בנק above (Feature 025).
            payer_name = None
        else:
            payer_name = payer_name_raw

        # Feature 025: no conditional-fee/hours-worked concept applies to a
        # Morning document capture - percent/percent_base/hours/hourly_rate all
        # forced null for חשבונית, same defensive discipline as the other
        # non-applicable fields above (agreement_id/component_id/bank_number/etc).
        is_accounting_document = source_type == "חשבונית"

        # vat_status is unconditionally כולל for בנק (finding #6, 2026-08-18 player
        # review: the model got this right only 1 of 15 times across a real run
        # despite the underlying rule already existing elsewhere in the constitution
        # for Morning payment-reference documents - "money already deposited
        # necessarily contains the VAT element already" - so this needs code-side
        # enforcement, not just prompt guidance, same reasoning as payer_name above).
        vat_status = "כולל" if source_type == "בנק" else event.get("vat_status")

        # Feature 025 Phase 9: document linkage maps onto the EXISTING
        # reference/reference_hint mechanism (user correction, 2026-08-23) -
        # resolve_reference's own docstring names this exact case ("the real
        # prior event id this event relates to (replaces, cancels, or otherwise
        # references)"). Resolved at capture time only, against the in-memory
        # cache; no end-of-sweep second pass.
        linked_document = event.get("_linked_document")
        if linked_document:
            linked_number = str(linked_document.get("number") or "")
            cache = self._ensure_accounting_document_cache()
            entries = cache.get(linked_number) or []
            resolved_event_id = max(entries, key=lambda e: e.timestamp).event_id if entries else None
            reference = resolved_event_id or REFERENCE_PLACEHOLDER
            reference_hint = _format_linked_reference_hint(
                linked_document, resolved=resolved_event_id is not None
            )
            if resolved_event_id is None:
                logger.warning(
                    f"חשבונית {accounting_document_display_number}: linked document "
                    f"{linked_number} is not in the ledger - reference left as "
                    f"{REFERENCE_PLACEHOLDER!r} and the failure noted in reference_hint"
                )
        else:
            reference_hint = event.get("reference_hint")

        record = {
            # CSV-mapped fields
            "event_id": event_id,
            "event_datetime": local_dt.strftime("%d/%m/%Y %H:%M"),  # Phase 11: merged event_date+event_time
            "source_type": source_type,
            "event_subtype": event.get("event_subtype"),
            "client_name": client_name,
            "payer_name": payer_name,
            "description": description,
            "amount": amount,
            "reference": reference,  # Phase 11: unified replaced_event_id/reference mechanism
            "agreement_id": resolved_agreement_id,  # REQ-DATA-004
            "component_id": component_id,  # REQ-DATA-004
            "component_label": component_label,  # REQ-DATA-004
            # Finding #10 (2026-08-18 player review): was hardcoded None regardless of
            # what the AI passed - LEDGER_EVENT_TOOL never even exposed this as a
            # component property, so it was structurally impossible to populate. Now
            # wired to the AI's own component-level input, forced null for בנק (no
            # conditional-fee concept applies there) same as component_label above.
            "trigger_condition": event.get("trigger_condition") if source_type == "הסכם" else None,
            "percent": None if is_accounting_document else event.get("percent"),
            "percent_base": None if is_accounting_document else event.get("percent_base"),
            "hours": None if is_accounting_document else hours,
            "hourly_rate": None if is_accounting_document else event.get("hourly_rate"),
            "txn_date": txn_date,  # REQ-DATA-005/007 - hours-worked date (הסכם) or transaction date (בנק)
            "vat_status": vat_status,
            "split_partner": None,  # reserved - nuances feature
            "split_percent": None,  # reserved - nuances feature
            "due_date": None,  # reserved - nuances feature
            # Feature 025 (round 3, 2026-08-21): 4 fields, not 5 - the originally
            # reserved invoice_id/invoice_number/invoice_type/invoice_status/
            # invoice_actual_creation_date/morning_document_id names are gone;
            # accounting_document_display_number merges what would have been a
            # separate _id/_number pair. Non-null only for source_type=חשבונית.
            "accounting_document_display_number": accounting_document_display_number,
            "accounting_document_status": (
                event.get("accounting_document_status") if source_type == "חשבונית" else None
            ),
            "accounting_document_creation_date": (
                local_dt.strftime("%d/%m/%Y %H:%M") if source_type == "חשבונית" else None
            ),
            # Feature 025 Phase 9: Morning's own raw status int and literal
            # label, kept alongside accounting_document_status's canonical
            # Hebrew interpretation - Morning's axis is open/closed, not
            # paid/unpaid, so the interpretation can be wrong for a proforma.
            "accounting_document_status_code": (
                event.get("accounting_document_status_code") if source_type == "חשבונית" else None
            ),
            "accounting_document_status_label": (
                event.get("accounting_document_status_label") if source_type == "חשבונית" else None
            ),
            "accounting_document_payment_method": (
                event.get("accounting_document_payment_method") if source_type == "חשבונית" else None
            ),
            # DeniDin-internal fields, not Events.csv columns - traceability/evidence
            # (2026-08-19: whatsapp_chat dropped - session_id already points at a
            # session that carries its own whatsapp_chat; message_id+session_id
            # together are already sufficient traceability, no need to duplicate it)
            "session_id": session_id,
            "message_id": message_id,
            "captured_at": captured_at,
            "reference_hint": reference_hint,
            "bank_number": bank_number,
            "bank_branch": bank_branch,
            "bank_account": bank_account,
            "schema_version": CURRENT_SCHEMA_VERSION,  # Feature 043, US5
        }

        file_path = self.storage_dir / f"{event_id}.json"
        tmp_path = file_path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(record, f, sort_keys=True, ensure_ascii=False, indent=2)
        tmp_path.replace(file_path)

        logger.info(
            f"Persisted ledger event {event_id} (source_type={source_type!r}, "
            f"event_subtype={event.get('event_subtype')!r}) for session {session_id}"
        )

        if source_type == "חשבונית" and accounting_document_display_number is not None:
            # Both the "new" and "anomaly" cases fall through to here ("duplicate"
            # already returned early, above) - record this timestamp so a future
            # poll can tell the difference.
            cache = self._ensure_accounting_document_cache()
            cache.setdefault(accounting_document_display_number, []).append(
                AccountingDocumentCacheEntry(local_dt, event_id)
            )
            if prior_entries_for_anomaly:
                self._append_pending_review(
                    accounting_document_display_number, prior_entries_for_anomaly,
                    local_dt, event_id,
                )

        return event_id

    def add_ledger_events_from_call(
        self,
        session_id: str,
        call_arguments: Dict,
        message_id: Optional[str],
        message_timestamp: Optional[int],
    ) -> List[str]:
        """
        Persist every component of one `capture_ledger_event` call (2026-07-30,
        REQ-DATA-004's `components`-array redesign - replaces relying on the model
        choosing to invoke this tool N times for a multi-stage/conditional agreement,
        proven unreliable even with a materially stronger model: two real documents,
        both fully comprehended by extraction, both still produced only one tool call
        each with every component after the first dumped into free-text prose
        instead of split out - see spec.md's Clarifications for the investigation).

        `call_arguments` is one `capture_ledger_event` call's full parsed arguments -
        agreement-level fields (source_type, event_subtype, client_name, payer_name,
        agreement_id, reference_hint, bank_number/bank_branch/bank_account)
        plus a `components` list (>=1 item, even for a
        single-component or בנק capture).
        Each component is merged with the shared agreement-level fields into the same
        flat shape `add_ledger_event`'s `event` parameter already expects, then
        persisted individually - `add_ledger_event` itself is unchanged.

        All components from this ONE call share byte-for-byte the same `agreement_id`
        (read once here, before the loop, straight from the AI-authored
        shared_fields["agreement_id"] - the batch-consistency guarantee is structural at
        the single-call level; code does not compute or slugify any part of this id).

        Returns the list of persisted event_ids, in component order - may be shorter
        than the components list if any individual component hit REQ-ID-003's rare
        seq-exhaustion case (logged internally, never raises for that case).

        (Added 2026-08-02, REQ-DATA-008): by the time this is called, the image path
        (AIHandler.capture_ledger_events_from_text) has already retried once on an
        `is_incomplete_capture` call - but this method is the single path both the
        text and image routes persist through, so it owns the last-resort safety net
        regardless of whether a caller retried: if `components` is STILL empty here,
        never silently return an empty list (a real, observed billed failure -
        2026-07-31, the Mor ben-Shaya 6-component test - persisted nothing and logged
        no error at all). Instead persist a single flagged fallback record from the
        call's own agreement-level fields, with `description` explaining the gap -
        matching this feature's existing philosophy that an explicitly incomplete
        capture is the correct output, not silence. A non-empty but
        `component_count`-mismatched `components` is persisted as given (never drop
        real data) with an ERROR logged for human review, rather than fabricating or
        dropping anything.
        """
        call_arguments = dict(call_arguments)  # never mutate caller's dict
        component_count = call_arguments.pop("component_count", None)
        components = call_arguments.pop("components", [])
        shared_fields = call_arguments

        # Feature 025 Phase 9: a חשבונית capture carries everything in its JSON
        # payload, so the sweep legitimately sends component_count=0/components=[].
        # That is NOT REQ-DATA-008's "AI returned zero components" failure (which
        # means a conversational capture silently lost its content) - synthesize
        # the single component a document always maps to, and stay quiet.
        if not components and shared_fields.get("source_type") == "חשבונית":
            components = [{}]
        elif not components:
            logger.error(
                f"capture_ledger_event call for session {session_id} claimed "
                f"component_count={component_count!r} but components was empty (even "
                f"after any upstream retry) - persisting a single flagged fallback "
                f"record from the agreement-level fields alone rather than silently "
                f"losing this capture entirely. shared_fields={shared_fields!r}"
            )
            components = [{
                "component_label": None,
                "description": (
                    "AI capture returned zero components (even after a retry) - "
                    "needs manual review against the original message/image."
                ),
                "amount": None,
                "percent": None, "percent_base": None, "hours": None,
                "hourly_rate": None, "txn_date": None, "vat_status": "לא צוין",
            }]
        elif component_count is not None and len(components) != component_count:
            logger.error(
                f"capture_ledger_event call for session {session_id} stated "
                f"component_count={component_count!r} but components has "
                f"{len(components)} item(s) - persisting what was given rather than "
                f"dropping any of it, but this mismatch needs human review for "
                f"possibly-missing components. components={components!r}"
            )

        batch_agreement_id = None
        if shared_fields.get("source_type") == "הסכם" and components:
            batch_agreement_id = shared_fields.get("agreement_id")

        event_ids = []
        for component in components:
            merged_event = {**shared_fields, **component}
            event_id = self.add_ledger_event(
                session_id=session_id,
                event=merged_event,
                message_id=message_id,
                message_timestamp=message_timestamp,
                agreement_id=batch_agreement_id,
            )
            if event_id is not None:
                event_ids.append(event_id)
        return event_ids

    def _load_event(self, event_id: str) -> Optional[Dict]:
        """Shared read helper for resolve_reference/apply_review_answer -
        None (logged) if the file doesn't exist, never raises."""
        file_path = self.storage_dir / f"{event_id}.json"
        if not file_path.exists():
            logger.error(f"No ledger event file found for event_id={event_id!r}")
            return None
        with file_path.open(encoding="utf-8") as f:
            record: Dict = json.load(f)
        return record

    def _write_event(self, event_id: str, record: Dict) -> None:
        """Shared atomic-write helper - same tmp-file-then-replace pattern as
        add_ledger_event, so this class stays the sole owner of the on-disk
        JSON format for every mutation, not just fresh writes."""
        file_path = self.storage_dir / f"{event_id}.json"
        tmp_path = file_path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(record, f, sort_keys=True, ensure_ascii=False, indent=2)
        tmp_path.replace(file_path)

    def resolve_reference(self, event_id: str, resolved_target_id: str) -> bool:
        """
        Feature 043, US2 (the player's relevancy/reference-resolution step): in-place
        field update on an already-persisted event file, replacing
        REFERENCE_PLACEHOLDER with the real prior event_id this event relates to
        (replaces, cancels, or otherwise references) - REFERENCE_PLACEHOLDER's own
        docstring already describes this exact purpose ("signals a later human/script
        needs to resolve the real prior event id"); this method is that script's write
        path. Renamed from resolve_replaced_event_id (Phase 11, 2026-08-16): real-data
        audit found replaced_event_id/reference were never two different mechanisms in
        the real historical ledger, just one, folded here - see data-model.md SS1b.

        Never overwrites a `reference` that isn't CURRENTLY the placeholder - not
        `None` (nothing to resolve - reference_hint was never set), and not an
        already-resolved id from a prior run (never silently re-link something a
        previous resolution already settled).

        Returns:
            True on success. False (logged as ERROR internally, never raises) if
            event_id doesn't exist, or its reference isn't currently the placeholder.
        """
        record = self._load_event(event_id)
        if record is None:
            return False

        if record.get("reference") != REFERENCE_PLACEHOLDER:
            logger.error(
                f"resolve_reference: event {event_id!r}'s reference "
                f"is {record.get('reference')!r}, not the placeholder - "
                f"refusing to overwrite (never re-link an already-resolved or "
                f"never-flagged event)"
            )
            return False

        record["reference"] = resolved_target_id
        self._write_event(event_id, record)
        logger.info(
            f"Resolved {event_id}'s reference -> {resolved_target_id}"
        )
        return True

    def apply_review_answer(self, event_id: str, field_updates: Dict) -> bool:
        """
        Feature 043, US3 (the player's second-pass review-queue re-apply mode):
        patches specific fields on one already-persisted event file per an
        operator's answer to a flagged ambiguity - never touches any other event,
        and never touches any field not present in `field_updates`.

        Args:
            event_id: the specific event file to patch.
            field_updates: {field_name: new_value} - merged into the existing
                record (existing keys not present here are left untouched).

        Returns:
            True on success. False (logged as ERROR internally, never raises) if
            event_id doesn't exist.
        """
        record = self._load_event(event_id)
        if record is None:
            return False

        record.update(field_updates)
        self._write_event(event_id, record)
        logger.info(f"Applied review answer to {event_id}: {sorted(field_updates.keys())}")
        return True
