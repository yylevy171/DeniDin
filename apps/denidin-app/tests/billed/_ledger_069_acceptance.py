"""Feature 069 — Phase 11 acceptance-tier shared helpers (C9,
`contracts/payload-fidelity-manifest.md`).

This is **test code for the billed/expensive tier**, written in the Acceptance
phase (METHODOLOGY §VI) — not a fixture, mocks nothing. Importable from both
`tests/billed/` and `tests/expensive/`.

What it provides:
  - `PROVENANCE_IGNORE`                    — the C9 ignore set for the backward check
  - `load_manifest(name)`                  — read a `tests/fixtures/ledger_069/<name>.manifest.json`
  - `assert_event_matches_manifest(...)`   — bidirectional (no drop / no hallucination) — T036
  - `assert_event_matches_manifest_two_hop(...)` — extractor-output ↔ event ↔ manifest — T037
  - `ledger_events_for_chat(...)`          — the persisted `LedgerEvent` files for one chat
  - `resolution_answer_bank(...)`          — a `ClarificationAnswerBank` for the new-client
                                            (full name + email + phone) resolution detour — T038

No test asserts `schema_version`'s value anywhere (CLAUDE.md — ledger schema is
human-only); it is in `PROVENANCE_IGNORE` purely so the backward check does not
flag it as an unexplained field.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests.e2e_helpers import ClarificationAnswerBank

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "ledger_069"

# C9 — bookkeeping / provenance fields the backward "no hallucination" check skips.
PROVENANCE_IGNORE = {
    "event_id",
    "event_datetime",
    "captured_at",
    "session_id",
    "message_id",
    "schema_version",
    "reference_hint",
    "agreement_id",
    "component_id",
    "_linked_document",
}

# Fields the ledgerer force-populates for a בנק event regardless of the source —
# a manifest is allowed not to mention them, and the backward check must not flag
# them as unexplained.
_BANK_FORCED_KEYS = {"vat_status"}

# בנק banking data read straight off the slip. A manifest lists these when the
# ground truth is legible; when it is not (older fixtures never transcribed the
# routing digits), the backward check still tolerates them because they are
# inherently source-traced — never model-invented specifics about the *client*.
_BANK_SOURCE_KEYS = {"bank_number", "bank_branch", "bank_account", "reference"}

# Structural / always-present keys the backward check tolerates even when a
# manifest is silent about them (they carry no invented specifics).
_STRUCTURAL_OK = {"source_type", "event_subtype", "split_partner", "split_percent"}


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
    fixture reused by reference — see each manifest's `source_file`)."""
    p = FIXTURES_DIR / filename
    if p.exists():
        return p
    media = FIXTURES_DIR.parent / "media" / "ledger_events" / filename
    return media


def _norm(value: Any) -> Optional[str]:
    """String-normalise for a fidelity compare: `None`/`""` → `None`; numbers →
    their plain integer/decimal string; strings → trimmed, whitespace-collapsed.
    So a manifest `"4000"` matches a persisted `4000`, and `"12 / 07 / 2026"`
    matches `"12/07/2026"` only after an explicit date normalise (below)."""
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
    """Normalise a date to `DD/MM/YYYY` (the persisted `txn_date` form) from
    either that form or ISO `YYYY-MM-DD`."""
    s = _norm(value)
    if s is None:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return s.replace(" ", "")


_DATE_KEYS = {"txn_date"}
_PERCENT_KEYS = {"percent", "split_percent", "percent_base"}


def _norm_percent(value: Any) -> Optional[str]:
    """Normalise a percentage for a fidelity compare so a manifest `"15"` matches
    a persisted `"15%"` (the ledgerer stores percent components with the sign).
    Strips a trailing `%`, surrounding whitespace, and a leading currency mark,
    then reuses `_norm` for the numeric collapse (`"15.0"` → `"15"`)."""
    s = _norm(value)
    if s is None:
        return None
    s = s.replace("%", "").replace("\u200f", "").strip()  # strip a leading RTL mark
    return _norm(s)


def _values_match(expected: Any, actual: Any, key: str) -> bool:
    if key in _DATE_KEYS:
        return _norm_date(expected) == _norm_date(actual)
    if key in _PERCENT_KEYS:
        return _norm_percent(expected) == _norm_percent(actual)
    return _norm(expected) == _norm(actual)


def _events_of_agreement(events: List[Dict]) -> List[Dict]:
    """One persisted file per fee component for a `הסכם` — group them back."""
    return sorted(events, key=lambda e: (e.get("component_id") or "", e.get("event_id")))


def assert_event_matches_manifest(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    events: List[Dict],
    manifest: Dict[str, Any],
    *,
    stated_name_for_store_anyway: Optional[str] = None,
) -> None:
    """C9 / T036 — bidirectional full-payload fidelity for the persisted event(s)
    of one scenario.

    `events` is every persisted `LedgerEvent` dict the scenario produced for its
    chat (one for `בנק`; one-per-component for `הסכם`). `manifest` is the parsed
    ground-truth manifest.

    Forward  : every `expected_event` field is present & equal on the event
               (component fields checked across the component files).
    Backward : every populated, non-provenance field on each event is explained
               by the manifest (or is `client_name` / `description` / a structural
               key / a `בנק` forced key).
    Client   : `client_name` == `morning_name_after_resolution` — unless
               `expects_marker_in_description`, in which case `client_name` ==
               the operator-stated name and the marker phrase is in `description`.
    """
    assert events, "no LedgerEvent was persisted for this scenario"

    expected = dict(manifest["expected_event"])
    resolution = manifest["client_resolution"]
    expected_components = expected.pop("components", None)
    marker = "[לקוח לא אומת במורנינג]"
    # store-anyway is active when the manifest declares it OR when the caller
    # explicitly passes the operator-stated name for that branch. US4 and US8
    # share one manifest (`agreement_new_client`) - US4 runs the normal detour
    # (no marker), US8 elects store-anyway (marker) and signals it via
    # `stated_name_for_store_anyway`. Without this the shared manifest's single
    # `expects_marker_in_description: false` made US8 assert the marker was
    # ABSENT and fail on the model's correct behaviour (2026-09-06).
    store_anyway = (
        bool(resolution.get("expects_marker_in_description"))
        or stated_name_for_store_anyway is not None
    )

    # ---- shared (non-component) forward check ------------------------------
    for key, exp_val in expected.items():
        if key == "description":
            continue  # handled below
        # a component-level key may legitimately be null on the shared head and
        # live on the component files — skip here, verified in the component pass
        if expected_components is not None and key in {
            "amount", "percent", "percent_base", "trigger_condition", "hours", "hourly_rate"
        }:
            continue
        matched = any(_values_match(exp_val, ev.get(key), key) for ev in events)
        assert matched, (
            f"[no drop] manifest expected {key}={exp_val!r} but no persisted event "
            f"carries it (got {[ev.get(key) for ev in events]!r})"
        )

    # ---- הסכם component forward check ------------------------------------
    if expected_components is not None:
        comp_events = _events_of_agreement(events)
        assert len(comp_events) == len(expected_components), (
            f"[no drop] manifest lists {len(expected_components)} fee component(s) "
            f"but {len(comp_events)} event file(s) were persisted "
            f"({[(_norm(e.get('amount')), _norm(e.get('percent'))) for e in comp_events]!r})"
        )
        for spec in expected_components:
            kind = spec["kind"]
            value = spec["value"]
            hit = None
            for ev in comp_events:
                if kind == "fixed" and _values_match(value, ev.get("amount"), "amount"):
                    hit = ev
                elif kind == "percent" and _values_match(value, ev.get("percent"), "percent"):
                    hit = ev
                elif kind == "hours" and _values_match(value, ev.get("hours"), "hours"):
                    hit = ev
                if hit is not None:
                    break
            _seen = [
                {"amount": e.get("amount"), "percent": e.get("percent"), "hours": e.get("hours")}
                for e in comp_events
            ]
            assert hit is not None, (
                f"[no drop] fee component {spec!r} did not reach any persisted event ({_seen!r})"
            )
            if spec.get("description"):
                _keys = ("description", "percent_base", "component_label", "trigger_condition")
                blob = " ".join(_norm(hit.get(k)) or "" for k in _keys)
                assert _norm(spec["description"]) in blob or any(
                    w in blob for w in str(spec["description"]).split()
                ), (
                    f"[no drop] component description {spec['description']!r} not reflected "
                    f"anywhere on the matched event ({hit.get('description')!r} / "
                    f"{hit.get('percent_base')!r} / {hit.get('component_label')!r})"
                )

    # ---- client name / store-anyway marker -------------------------------
    if store_anyway:
        stated = stated_name_for_store_anyway or resolution.get("morning_name_after_resolution")
        for ev in events:
            assert _norm(ev.get("client_name")) == _norm(stated), (
                f"[store-anyway] client_name should stay the operator-stated {stated!r}, "
                f"got {ev.get('client_name')!r}"
            )
            assert marker in (ev.get("description") or ""), (
                f"[store-anyway] description must carry {marker!r}, got {ev.get('description')!r}"
            )
    else:
        exact = resolution["morning_name_after_resolution"]
        for ev in events:
            assert _norm(ev.get("client_name")) == _norm(exact), (
                f"[resolution] client_name must equal the exact Morning name {exact!r}, "
                f"got {ev.get('client_name')!r}"
            )
            assert marker not in (ev.get("description") or ""), (
                f"[resolution] description must NOT carry the store-anyway marker for a "
                f"genuinely resolved client, got {ev.get('description')!r}"
            )

    # ---- backward: no hallucinated / unexplained field -------------------
    explained = set(expected) | _STRUCTURAL_OK | {"client_name", "description"}
    if _norm(expected.get("source_type")) == "בנק":
        explained |= _BANK_FORCED_KEYS | _BANK_SOURCE_KEYS
    if expected_components is not None:
        explained |= {
            "amount", "percent", "percent_base", "trigger_condition",
            "hours", "hourly_rate", "component_label",
        }
    for ev in events:
        for key, val in ev.items():
            if key in PROVENANCE_IGNORE or val in (None, "", [], {}):
                continue
            if key.startswith("accounting_document"):
                continue  # 069 never touches חשבונית via this helper's callers
            assert key in explained, (
                f"[no hallucination] persisted event carries an unexplained populated "
                f"field {key}={val!r} — either the model invented it or the manifest is "
                f"missing it"
            )


def assert_event_matches_manifest_two_hop(
    extractor_output: Dict[str, Any],
    events: List[Dict],
    manifest: Dict[str, Any],
    *,
    stated_name_for_store_anyway: Optional[str] = None,
) -> None:
    """C9 / T037 — two-hop fidelity for a media source (US7 incl. 7d, US9, US10).

    Hop 1: the extractor's `analyze_media()` output already carried every field
           the manifest lists (catches OCR / vision loss *before* the resolution
           detour). `extractor_output` is the raw dict `MediaHandler` got back —
           `{"ledger_events": [...], "document_analysis": {...}, "extracted_text": "..."}`.
    Hop 2: the persisted event matches the manifest (delegates to
           `assert_event_matches_manifest`) — catches a field dropped *in* the
           detour / recognition call.
    """
    expected = manifest["expected_event"]
    text_blob = _norm(extractor_output.get("extracted_text")) or ""
    ev_list = extractor_output.get("ledger_events") or []
    ev0 = ev_list[0] if ev_list else {}
    comp0 = ev0.get("components") or []

    def _in_hop1(value: Any) -> bool:
        s = _norm(value)
        if s is None:
            return True
        if s in text_blob:
            return True
        # any structured extractor field
        flat = json.dumps(ev0, ensure_ascii=False)
        return s in flat

    for key, val in expected.items():
        if key in {"components", "source_type", "event_subtype", "description", "reference"}:
            continue
        assert _in_hop1(val), (
            f"[hop 1 — extraction] manifest field {key}={val!r} is not present in the "
            f"extractor output (extracted_text or ledger_events[0]) — vision/OCR lost it "
            f"before the resolution detour"
        )
    for spec in expected.get("components", []) or []:
        assert _in_hop1(spec["value"]) or any(
            _norm(spec["value"]) in (json.dumps(c, ensure_ascii=False)) for c in comp0
        ), (
            f"[hop 1 — extraction] fee component {spec!r} is not in the extractor output "
            f"— the model did not read it off the source"
        )

    # Hop 2
    assert_event_matches_manifest(
        events, manifest, stated_name_for_store_anyway=stated_name_for_store_anyway
    )


def ledger_events_for_chat(denidin_app, chat_id: str) -> List[Dict]:
    """Every persisted `LedgerEvent` JSON file whose `session_id` is this chat's
    current session — read off disk, sorted by `captured_at` then `event_id`."""
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


def recognition_breadcrumbs(caplog) -> List[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("[069]")]


def resolution_answer_bank(*, full_name: str, email: str, phone: str) -> ClarificationAnswerBank:
    """T038 — the deterministic answer bank for the new-client resolution detour
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
