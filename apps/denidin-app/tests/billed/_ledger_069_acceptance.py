"""Feature 069 — Phase 11 acceptance-tier shared helpers (C9,
`contracts/payload-fidelity-manifest.md`).

This is **test code for the billed/expensive tier**, written in the Acceptance
phase (METHODOLOGY §VI) — not a fixture, mocks nothing. Importable from both
`tests/billed/` and `tests/expensive/`.

Full-payload fidelity — the model of it
--------------------------------------
Contract C9, in the user's words: *"In all scenarios that actually create a
ledger event at the end — assert that ALL the details that we given/extracted in
the initial msg made it to the persisted event."*

The check here proves that **per field, exhaustively**. Every persisted
`LedgerEvent` carries exactly the keys in
`LedgerEventManager.LEDGER_EVENT_FIELDS` (a `src/` assertion keeps that constant
in lockstep with what actually gets written — a new field can never slip past
unasserted). For each scenario, a **manifest** classifies *every one* of those
fields as exactly one of:

  - ``{"tested": <value>}``   — the test supplies the ground-truth value; assert
                                equality (normalised). ``"$client"`` means "use
                                the ``resolved_client_name`` argument".
  - ``{"generated": "<kind>"}`` — the ledgerer mints it; assert it is present
                                **and** conforms to that kind's rule (a format,
                                or an exact value we can compute — e.g.
                                ``event_datetime`` must equal the triggering
                                message's Green API timestamp).
  - ``{"null": true}``        — assert absent / empty.
  - ``{"free_text": true}``   — (``description`` only) assert present, a
                                non-empty string, and not a bare number/date.

A roster field no manifest rule covers ⇒ **fail** (the manifest is incomplete).
A persisted field outside the roster ⇒ **fail**. There are **no** ignore lists,
tolerance sets, or "structural-ok" carve-outs — every constant of that kind was
deleted 2026-09-06 (user directive). ``txn_date`` on a flat/percent ``הסכם``
component is `null` per the recognition tool schema ("Null in every other
case") — if the model populates it, that is a real defect and this check
catches it.

What it provides
----------------
  - ``assert_ledger_event_matches_manifest(...)``          — the per-field check
  - ``assert_ledger_event_matches_manifest_two_hop(...)``  — media: extractor
        output carried every tested value, then the persisted event matches
  - ``load_manifest(name)`` / ``fixture_path(name)``
  - ``ledger_events_for_chat`` / ``assert_no_ledger_event``
  - ``resolution_answer_bank(...)`` — the new-client resolution-detour answers
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.managers.ledger_event_manager import LEDGER_EVENT_FIELDS
from tests.e2e_helpers import ClarificationAnswerBank

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "ledger_069"
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

# Fields that legitimately differ file-to-file for a `הסכם` — the ledgerer
# persists one JSON file per fee component, so these belong under a manifest's
# per-`components` entries; everything else is identical across the set and
# belongs under `shared_fields`.
_COMPONENT_FIELDS = frozenset({
    "amount", "percent", "percent_base", "hours", "hourly_rate",
    "txn_date", "trigger_condition", "component_label", "component_id", "description",
})

# Morning canonicalises an ASCII apostrophe in a client name to a Hebrew geresh
# (׳) on store (bugfix-027), so a name seeded with an apostrophe comes back with
# a geresh. Normalising both sides of a `client_name` compare mirrors that one
# real Morning behaviour — it is not a tolerance for arbitrary divergence.
_GERESH = "׳"
_APOSTROPHES = ("'", "’", "׳")

# Bidi / general-format control codepoints an RTL-aware model or WhatsApp layer
# can silently insert into or drop from a mixed-script name (Hebrew + Arabic
# Israeli names are both in the seed pool). They carry no identity — strip them
# from both sides of a client_name compare, then NFC-normalise.
_BIDI_CONTROLS = dict.fromkeys(
    [0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
     0x2066, 0x2067, 0x2068, 0x2069, 0x061C]
)


def _geresh_normalise(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    out = unicodedata.normalize("NFC", str(text)).translate(_BIDI_CONTROLS)
    for ch in _APOSTROPHES:
        out = out.replace(ch, _GERESH)
    return out


# --------------------------------------------------------------------------- #
# value normalisation for the `tested` compare
# --------------------------------------------------------------------------- #
def _norm(value: Any) -> Optional[str]:
    """`None`/`""` → `None`; numbers → plain int/decimal string; strings →
    trimmed + whitespace-collapsed."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        f = float(value)
        return str(int(f)) if f.is_integer() else str(f)
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _norm_date(value: Any) -> Optional[str]:
    """Normalise to `DD/MM/YYYY` from that form or ISO `YYYY-MM-DD`."""
    s = _norm(value)
    if s is None:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return s.replace(" ", "")


def _norm_percent(value: Any) -> Optional[str]:
    s = _norm(value)
    if s is None:
        return None
    return _norm(s.replace("%", "").replace("‏", "").strip())


def _norm_field(field: str, value: Any) -> Optional[str]:
    if field == "client_name":
        return _norm(_geresh_normalise(value))
    if field == "txn_date":
        return _norm_date(value)
    if field in ("percent", "percent_base", "split_percent"):
        return _norm_percent(value)
    return _norm(value)


_PURE_NUMBER_RE = re.compile(r"[-+]?[\d.,\s‏₪%]+")
_PURE_DATE_RE = re.compile(r"\d{1,4}[/.\-]\d{1,2}([/.\-]\d{1,4})?")


def _looks_like_bare_number(s: str) -> bool:
    return bool(_PURE_NUMBER_RE.fullmatch(s.strip()))


def _looks_like_bare_date(s: str) -> bool:
    return bool(_PURE_DATE_RE.fullmatch(s.strip()))


# --------------------------------------------------------------------------- #
# manifest loading
# --------------------------------------------------------------------------- #
def load_manifest(name: str) -> Dict[str, Any]:
    """Read `tests/fixtures/ledger_069/<name>.manifest.json` (pass the bare stem)."""
    path = FIXTURES_DIR / f"{name}.manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"manifest {path} not found — author it per "
            f"contracts/payload-fidelity-manifest.md before running this test"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_path(filename: str) -> Path:
    """Absolute path to a `tests/fixtures/ledger_069/` artifact (or a media
    fixture reused by reference)."""
    p = FIXTURES_DIR / filename
    if p.exists():
        return p
    return FIXTURES_DIR.parent / "media" / "ledger_events" / filename


# --------------------------------------------------------------------------- #
# the per-field check
# --------------------------------------------------------------------------- #
def _check_generated(field: str, value: Any, kind: str, ev: Dict, *,
                     trigger_epoch: int, session_id: str) -> None:
    assert value not in (None, "", [], {}), (
        f"{field}: manifest says this is generated, so it must be populated — got {value!r}"
    )
    if kind == "event_id":
        assert re.fullmatch(r"[A-Za-z]\d{11}", str(value)), (
            f"event_id malformed (want letter + DDMMYY + HHMM + seq): {value!r}"
        )
    elif kind == "event_datetime":
        want = datetime.fromtimestamp(trigger_epoch, ISRAEL_TZ).strftime("%d/%m/%Y %H:%M")
        assert str(value) == want, (
            f"event_datetime must equal the triggering message's Green API timestamp "
            f"{want!r} (epoch {trigger_epoch}), got {value!r} — the 'hard pointer' must "
            f"survive the whole detour"
        )
    elif kind == "session_id":
        assert str(value) == str(session_id), (
            f"session_id {value!r} != this chat's session {session_id!r}"
        )
    elif kind == "message_id":
        assert isinstance(value, str) and value.strip(), (
            f"message_id must be a non-empty string, got {value!r}"
        )
    elif kind == "captured_at":
        # LedgerEventManager persists captured_at as now_local().strftime(
        # "%d/%m/%Y %H:%M") (Phase 11) — minute-granular Israel wall-clock, NOT
        # ISO-8601. Assert that shape and that it parses.
        assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", str(value)), (
            f"captured_at must be DD/MM/YYYY HH:MM (Israel local), got {value!r}"
        )
        datetime.strptime(str(value), "%d/%m/%Y %H:%M")
    elif kind == "schema_version":
        # value itself is NEVER asserted (CLAUDE.md — ledger schema is human-only);
        # only that it is present and integer-shaped.
        assert isinstance(value, int) or re.fullmatch(r"\d+", str(value)), (
            f"schema_version must be an int, got {value!r}"
        )
    elif kind == "non_empty":
        assert str(value).strip(), f"{field}: generated field must be non-empty, got {value!r}"
    elif kind == "date":
        assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", str(value)) or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", str(value)
        ), f"{field}: expected a DD/MM/YYYY or ISO date, got {value!r}"
    elif kind == "agreement_id":
        assert isinstance(value, str) and value.strip(), (
            f"agreement_id is AI-authored free text — must be a non-empty string, got {value!r}"
        )
    elif kind == "component_id":
        assert isinstance(value, str) and value.strip(), (
            f"component_id must be a non-empty string, got {value!r}"
        )
        aid = ev.get("agreement_id")
        if aid:
            assert str(value).startswith(f"{aid}-"), (
                f"component_id {value!r} must start with '{aid}-' (agreement_id + label slug)"
            )
    else:
        raise AssertionError(f"unknown generated kind {kind!r} for field {field!r}")


def _check_field(field: str, value: Any, rule: Dict, ev: Dict, *,
                 trigger_epoch: int, session_id: str,
                 resolved_client_name: Optional[str]) -> None:
    if "null" in rule:
        assert value in (None, "", [], {}), (
            f"{field}: manifest says this must be null/empty for this scenario, got {value!r}"
        )
    elif "free_text" in rule:
        assert isinstance(value, str) and value.strip(), (
            f"{field}: expected a non-empty free-text string, got {value!r}"
        )
        assert not _looks_like_bare_number(value) and not _looks_like_bare_date(value), (
            f"{field}: expected prose, got what parses as a bare number/date: {value!r}"
        )
    elif "tested" in rule:
        expected = rule["tested"]
        if expected == "$client":
            assert resolved_client_name is not None, (
                f"{field}: manifest uses \"$client\" but the test passed no resolved_client_name"
            )
            expected = resolved_client_name
        assert _norm_field(field, value) == _norm_field(field, expected), (
            f"{field}: expected {expected!r}, persisted event has {value!r}"
        )
    elif "generated" in rule:
        _check_generated(field, value, rule["generated"], ev,
                         trigger_epoch=trigger_epoch, session_id=session_id)
    else:
        raise AssertionError(f"{field}: malformed manifest rule {rule!r}")


def _check_one_file(ev: Dict, shared: Dict, comp: Dict, roster: set, *,
                    trigger_epoch: int, session_id: str,
                    resolved_client_name: Optional[str]) -> None:
    for field in roster:
        rule = comp.get(field, shared.get(field))
        assert rule is not None, (
            f"manifest does not classify field {field!r} — every LEDGER_EVENT_FIELDS "
            f"entry must be tested/generated/null/free_text"
        )
        _check_field(field, ev.get(field), rule, ev,
                     trigger_epoch=trigger_epoch, session_id=session_id,
                     resolved_client_name=resolved_client_name)


def _component_discriminator(comp: Dict) -> Dict[str, Any]:
    return {
        k: comp[k]["tested"]
        for k in ("amount", "percent", "hours")
        if k in comp and isinstance(comp[k], dict) and "tested" in comp[k]
    }


def _match_component(events: List[Dict], comp: Dict) -> Optional[Dict]:
    disc = _component_discriminator(comp)
    if not disc:
        return events[0] if events else None
    for ev in events:
        if all(_norm_field(k, ev.get(k)) == _norm_field(k, want) for k, want in disc.items()):
            return ev
    return None


def assert_ledger_event_matches_manifest(
    persisted_events: List[Dict],
    manifest: Dict[str, Any],
    *,
    trigger_epoch: int,
    session_id: str,
    resolved_client_name: Optional[str] = None,
) -> None:
    """C9 — exhaustive per-field fidelity for every `LedgerEvent` a scenario
    persisted (one file for `בנק`/`חשבונית`; one per fee component for `הסכם`).

    `manifest` shape::

        {
          "files": "single" | "per_component",
          "shared_fields": { "<field>": <rule>, ... },   # identical on every file
          "components":    [ { "<field>": <rule>, ... }, ... ]   # per_component only
        }

    Together, `shared_fields` and the union of `components` keys must classify
    **every** field in `LEDGER_EVENT_FIELDS` exactly once.
    """
    roster = set(LEDGER_EVENT_FIELDS)
    assert persisted_events, "no LedgerEvent was persisted for this scenario"

    for ev in persisted_events:
        extra = set(ev) - roster
        missing = roster - set(ev)
        assert not extra and not missing, (
            f"persisted event keys disagree with LEDGER_EVENT_FIELDS — "
            f"extra={extra!r} missing={missing!r} (event_id={ev.get('event_id')!r})"
        )

    layout = manifest["files"]
    shared = manifest["shared_fields"]

    if layout == "single":
        assert len(persisted_events) == 1, (
            f"[no drop] expected exactly one persisted file, got {len(persisted_events)}"
        )
        uncovered = roster - set(shared)
        assert not uncovered, f"manifest shared_fields does not classify: {sorted(uncovered)!r}"
        _check_one_file(persisted_events[0], shared, {}, roster,
                        trigger_epoch=trigger_epoch, session_id=session_id,
                        resolved_client_name=resolved_client_name)
        return

    assert layout == "per_component", f"unknown manifest 'files' layout {layout!r}"
    comps = manifest.get("components") or []
    assert len(persisted_events) == len(comps), (
        f"[no drop] manifest lists {len(comps)} fee component(s) but "
        f"{len(persisted_events)} event file(s) were persisted"
    )
    comp_keys = set().union(*(set(c) for c in comps)) if comps else set()
    overlap = set(shared) & comp_keys
    assert not overlap, f"fields declared in BOTH shared_fields and a component: {sorted(overlap)!r}"
    uncovered = roster - (set(shared) | comp_keys)
    assert not uncovered, (
        f"manifest does not classify every LEDGER_EVENT_FIELDS entry: {sorted(uncovered)!r}"
    )

    remaining = list(persisted_events)
    for comp in comps:
        hit = _match_component(remaining, comp)
        assert hit is not None, (
            f"[no drop] no persisted file matches fee component "
            f"{_component_discriminator(comp)!r}"
        )
        remaining.remove(hit)
        _check_one_file(hit, shared, comp, roster,
                        trigger_epoch=trigger_epoch, session_id=session_id,
                        resolved_client_name=resolved_client_name)
    assert not remaining, (
        f"{len(remaining)} persisted file(s) matched no manifest component "
        f"({[e.get('event_id') for e in remaining]!r})"
    )


def assert_ledger_event_matches_manifest_two_hop(
    extractor_output: Dict[str, Any],
    persisted_events: List[Dict],
    manifest: Dict[str, Any],
    *,
    trigger_epoch: int,
    session_id: str,
    resolved_client_name: Optional[str] = None,
) -> None:
    """Media sources (US7 images incl. 7d, US9 image, US10 `docx`): two hops.

    Hop 1 — every ``tested`` value in the manifest is present somewhere in the
            extractor's own output (`extracted_text` or `ledger_events[0]`), so a
            value lost in OCR/vision is distinguishable from one lost in the
            resolution detour.
    Hop 2 — the persisted event matches the manifest (delegates to
            `assert_ledger_event_matches_manifest`).
    """
    text_blob = _norm(extractor_output.get("extracted_text")) or ""
    ev_list = extractor_output.get("ledger_events") or []
    flat = json.dumps(ev_list[0], ensure_ascii=False) if ev_list else ""

    def _present(value: Any) -> bool:
        s = _norm(value)
        if s is None or s == "$client":
            return True
        if s in text_blob or s in flat:
            return True
        # a bare number in the manifest ("18000") vs the source's own grouping
        # ("18,000") — compare digit-runs with separators stripped from both sides
        if re.fullmatch(r"\d[\d,.\s]*", s):
            digits = re.sub(r"[,.\s]", "", s)
            stripped_blob = re.sub(r"[,.\s]", "", text_blob + " " + flat)
            return digits in stripped_blob
        return False

    # Hop 1 verifies a *content* value survived OCR/vision. Derived classifications
    # (`vat_status` = לא כולל/כולל, `source_type`, `event_subtype`) are the model's
    # own reading of "+ מע"מ" / the document shape — never a verbatim substring —
    # so they belong to Hop 2's manifest check only, not this one.
    _HOP1_SKIP = {"client_name", "vat_status", "source_type", "event_subtype"}

    def _walk(rules: Dict) -> None:
        for field, rule in rules.items():
            if isinstance(rule, dict) and "tested" in rule and field not in _HOP1_SKIP:
                assert _present(rule["tested"]), (
                    f"[hop 1 — extraction] manifest field {field}={rule['tested']!r} is "
                    f"not in the extractor output — vision/OCR lost it before the detour"
                )

    _walk(manifest.get("shared_fields", {}))
    for comp in manifest.get("components", []) or []:
        _walk(comp)

    assert_ledger_event_matches_manifest(
        persisted_events, manifest,
        trigger_epoch=trigger_epoch, session_id=session_id,
        resolved_client_name=resolved_client_name,
    )


# --------------------------------------------------------------------------- #
# reading persisted events
# --------------------------------------------------------------------------- #
def ledger_events_for_chat(denidin_app, chat_id: str) -> List[Dict]:
    """Every persisted `LedgerEvent` JSON whose `session_id` is this chat's
    current session — sorted by `captured_at` then `event_id`."""
    session_id = denidin_app.ai_handler.session_manager.get_session(chat_id).session_id
    events_dir = Path(denidin_app.ai_handler.ledger_event_manager.storage_dir)
    out: List[Dict] = []
    for f in events_dir.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("session_id") == session_id:
            out.append(data)
    out.sort(key=lambda d: (d.get("captured_at", ""), d.get("event_id", "")))
    return out


def assert_no_ledger_event(denidin_app, chat_id: str) -> None:
    events = ledger_events_for_chat(denidin_app, chat_id)
    assert not events, (
        f"expected NO persisted ledger event for {chat_id!r}, found "
        f"{[e.get('event_id') for e in events]!r}"
    )


def session_id_for_chat(denidin_app, chat_id: str) -> str:
    return denidin_app.ai_handler.session_manager.get_session(chat_id).session_id


# --------------------------------------------------------------------------- #
# resolution-detour answer bank (new client)
# --------------------------------------------------------------------------- #
def resolution_answer_bank(*, full_name: str, email: str, phone: str) -> ClarificationAnswerBank:
    """The deterministic answer bank for the new-client resolution detour
    (`resolve_client_name` → 0 matches → "give me full name + email + phone").
    One reply supplies all three, so the model can go straight to `add_client`."""
    supply_all = f"שם מלא: {full_name}. אימייל: {email}. טלפון: {phone}."
    return ClarificationAnswerBank(
        [
            {
                "topic": "full_contact_details",
                "keywords": ["אימייל", "מייל", "טלפון", "שם מלא", "פרטים", "כתובת מייל"],
                "answer": supply_all,
            },
            {
                "topic": "which_client_or_new",
                "keywords": ["חדש", "איזה", "מצאתי", "האם הכוונה", "לקוח קיים", "ליצור"],
                "answer": f"לקוח חדש. {supply_all}",
            },
            {
                "topic": "vat",
                "keywords": ['מע"מ', "מעמ", "כולל מע"],
                "answer": "לא צוין מע\"מ, תשאיר כפי שנכתב",
            },
        ],
        fallback=f"לקוח חדש. {supply_all}",
    )
