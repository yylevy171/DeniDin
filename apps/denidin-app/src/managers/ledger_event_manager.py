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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.utils.time_utils import LOCAL_TZ, local_from_timestamp, now_local

logger = logging.getLogger(__name__)

# Events.csv's date/time columns are Asia/Jerusalem local time (confirmed with the
# user 2026-07-29). As of bugfix-037 (2026-08-10) that is no longer a per-field
# exception converted at the formatting boundary - it is what the whole system
# uses, so message_timestamp/captured_at are local too and every field on a
# persisted event now describes the same instant in the same zone.
ISRAEL_TZ = LOCAL_TZ  # retained name; the canonical definition lives in time_utils

# event_id letter prefix, matches Events.csv's existing convention exactly (verified
# by direct inspection of all 1159 rows - see research.md). "H"/חשבונית is
# Morning-invoice-sourced and never produced by capture_ledger_event (Feature 025).
_LETTER_BY_SOURCE_TYPE = {
    "הסכם": "A",
    "בנק": "B",
}

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
CURRENT_SCHEMA_VERSION = 1

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
        logger.info(f"LedgerEventManager initialized: storage_dir={self.storage_dir}")

    def _resolve_local_dt(self, message_timestamp: Optional[int]):
        """Shared by add_ledger_event and build_agreement_id: Asia/Jerusalem local
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

    def build_agreement_id(
        self,
        client_name: Optional[str],
        agreement_label: Optional[str],
        message_timestamp: Optional[int],
    ) -> str:
        """REQ-DATA-004: "{MMYY}-{slugify(client_name)}-{slugify(agreement_label)}",
        matching the real Events.csv convention exactly (verified against all 1159
        rows, 2026-07-30). Pure/stateless - exposed so AIHandler can compute this
        once per multi-component batch and pass the identical string into every
        add_ledger_event call for that batch, instead of relying on the AI to repeat
        agreement_label verbatim across separate tool calls."""
        local_dt = self._resolve_local_dt(message_timestamp)
        mmyy = local_dt.strftime("%m%y")
        return f"{mmyy}-{_slugify(client_name)}-{_slugify(agreement_label)}"

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

    def add_ledger_event(
        self,
        session_id: str,
        whatsapp_chat: str,
        event: Dict,
        message_id: Optional[str],
        message_timestamp: Optional[int],
        agreement_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Persist a captured `capture_ledger_event` result as its own file.

        Args:
            session_id: source session (no longer implied by folder nesting)
            whatsapp_chat: source chat JID, same convention as Session.whatsapp_chat
            event: the parsed capture_ledger_event function-call arguments, merged
                shared+component shape - LEDGER_EVENT_TOOL's schema; `component_count`
                is popped separately by add_ledger_events_from_call and never reaches
                this flat shape - never mutated
            message_id: source message id (the traceability pointer this feature adds)
            message_timestamp: Unix epoch of the source message - drives event_datetime/
                event_id generation; falls back to processing time (WARNING logged)
                only if None, since the hard pointer is genuinely unknown, never guessed
            agreement_id: (REQ-DATA-004, added 2026-07-30) caller-supplied agreement_id
                for a multi-component batch - used as-is when given, so every component
                in that batch shares byte-for-byte the same id. When None (a standalone,
                non-batched capture), derived fresh from this event's own
                client_name/agreement_label via build_agreement_id. Ignored entirely
                when event["source_type"] == "בנק" (agreement_id/component_id always
                None for bank events - no agreement concept applies).

        Returns:
            The new event_id on success, or None if REQ-ID-003's exhaustion case
            was hit (all 10 seq digits for this letter+minute already taken) -
            logged as ERROR internally, caller doesn't need to inspect why.
        """
        event = dict(event)  # never mutate caller's dict

        # Phase 11 (schema v2->v1 reset, 2026-08-16): captured_at/event_datetime share
        # one human-readable convention (DD/MM/YYYY HH:MM) instead of ISO+offset -
        # message_timestamp/sender are no longer separately persisted at all (the
        # former is fully covered by event_datetime; the latter had no reader anywhere
        # - see data-model.md SS1b for the full real-data-grounded audit).
        captured_at = now_local().strftime("%d/%m/%Y %H:%M")
        local_dt = self._resolve_local_dt(message_timestamp)

        source_type = event.get("source_type")
        assert source_type is not None, "LEDGER_EVENT_TOOL's schema requires source_type"
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

        # agreement_label (Phase 11): stays a LEDGER_EVENT_TOOL input (stated once, used
        # to build agreement_id below) but is no longer persisted as its own field - see
        # data-model.md SS1b. Every component still shares the identical agreement_id.
        agreement_label = event.get("agreement_label")
        component_label = event.get("component_label")
        if source_type == "הסכם":
            resolved_agreement_id = agreement_id or self.build_agreement_id(
                event.get("client_name"), agreement_label, message_timestamp
            )
            component_id = f"{resolved_agreement_id}-{_slugify(component_label)}"
        else:
            # REQ-DATA-004: no agreement/component concept applies to בנק events
            resolved_agreement_id = None
            component_id = None
            component_label = None

        # Bank details apply only to בנק - forced null for הסכם regardless of what the
        # caller/AI passed, same defensive discipline as component_label above (never
        # trust an inapplicable field to have been left blank on its own).
        if source_type == "בנק":
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
        else:
            payer_name = payer_name_raw

        # vat_status is unconditionally כולל for בנק (finding #6, 2026-08-18 player
        # review: the model got this right only 1 of 15 times across a real run
        # despite the underlying rule already existing elsewhere in the constitution
        # for Morning payment-reference documents - "money already deposited
        # necessarily contains the VAT element already" - so this needs code-side
        # enforcement, not just prompt guidance, same reasoning as payer_name above).
        vat_status = "כולל" if source_type == "בנק" else event.get("vat_status")

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
            "percent": event.get("percent"),
            "percent_base": event.get("percent_base"),
            "hours": hours,
            "hourly_rate": event.get("hourly_rate"),
            "txn_date": txn_date,  # REQ-DATA-005/007 - hours-worked date (הסכם) or transaction date (בנק)
            "vat_status": vat_status,
            "split_partner": None,  # reserved - nuances feature
            "split_percent": None,  # reserved - nuances feature
            "due_date": None,  # reserved - nuances feature
            "invoice_status": None,  # reserved - future Morning-reconciliation feature
            "invoice_number": None,  # reserved - future Morning-reconciliation feature
            "invoice_type": None,  # reserved - future Morning-reconciliation feature
            "morning_document_id": None,  # reserved - future Morning-reconciliation feature
            "invoice_actual_creation_date": None,  # reserved - future Morning-reconciliation feature
            # DeniDin-internal fields, not Events.csv columns - traceability/evidence
            "session_id": session_id,
            "whatsapp_chat": whatsapp_chat,
            "message_id": message_id,
            "captured_at": captured_at,
            "reference_hint": event.get("reference_hint"),
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
        return event_id

    def add_ledger_events_from_call(
        self,
        session_id: str,
        whatsapp_chat: str,
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
        agreement_label, reference_hint, bank_number/bank_branch/bank_account)
        plus a `components` list (>=1 item, even for a
        single-component or בנק capture).
        Each component is merged with the shared agreement-level fields into the same
        flat shape `add_ledger_event`'s `event` parameter already expects, then
        persisted individually - `add_ledger_event` itself is unchanged.

        All components from this ONE call share byte-for-byte the same `agreement_id`
        (computed once here, before the loop - the batch-consistency guarantee is now
        structural at the single-call level, simpler than the old cross-call batching
        this replaces).

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

        if not components:
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
            batch_agreement_id = self.build_agreement_id(
                shared_fields.get("client_name"),
                shared_fields.get("agreement_label"),
                message_timestamp,
            )

        event_ids = []
        for component in components:
            merged_event = {**shared_fields, **component}
            event_id = self.add_ledger_event(
                session_id=session_id,
                whatsapp_chat=whatsapp_chat,
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
