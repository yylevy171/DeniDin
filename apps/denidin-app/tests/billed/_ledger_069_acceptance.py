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
  - ``assert_ledger_event_matches_manifest(...)``          — the per-field check;
        pass ``extractor_output=`` for the media two-hop (OCR carried every
        ``tested`` value, then the persisted event matches)
  - ``load_manifest(name)`` / ``fixture_path(name)``
  - ``assert_no_ledger_event`` (reader itself is
        ``tests.e2e_helpers.persisted_ledger_events_for_chat``)
  - ``resolution_answer_bank(...)`` — the new-client resolution-detour answers
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.managers.ledger_event_manager import LEDGER_EVENT_FIELDS
from tests.e2e_helpers import ClarificationAnswerBank, persisted_ledger_events_for_chat
from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _normalize_hebrew_geresh,
    _random_seed_email,
    _seed_client,
    _unique_client_name,
)

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


def _norm_field(field: str, value: Any) -> Optional[str]:
    """`_norm`, plus the few per-field canonicalisations a `tested` compare
    needs so a value that only *formats* differently still matches:

      - `client_name` — apostrophe→geresh, NFC, bidi-strip (Morning's own store
        behaviour + invisible RTL marks); the shared
        `denidin_mcp_e2e_helpers._normalize_hebrew_geresh`.
      - `txn_date` — ISO `YYYY-MM-DD` ⇄ `DD/MM/YYYY`.
      - `percent` / `percent_base` / `split_percent` — drop a `%` sign / RTL mark.
    """
    if field == "client_name":
        return _norm(_normalize_hebrew_geresh(value))
    s = _norm(value)
    if s is None:
        return None
    if field == "txn_date":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else s.replace(" ", "")
    if field in ("percent", "percent_base", "split_percent"):
        return _norm(s.replace("%", "").replace("‏", "").strip())
    return s


_PURE_NUMBER_RE = re.compile(r"[-+]?[\d.,\s‏₪%]+")
_PURE_DATE_RE = re.compile(r"\d{1,4}[/.\-]\d{1,2}([/.\-]\d{1,4})?")


def _looks_like_bare_number(s: str) -> bool:
    return bool(_PURE_NUMBER_RE.fullmatch(s.strip()))


def _looks_like_bare_date(s: str) -> bool:
    return bool(_PURE_DATE_RE.fullmatch(s.strip()))


# --------------------------------------------------------------------------- #
# manifest loading
# --------------------------------------------------------------------------- #
_MANIFEST_CACHE: Dict[str, Dict[str, Any]] = {}


def reset_manifest_cache() -> None:
    """Autouse-fixture hook (`_ledger_069_post_turn_base.clean_069_chat_history`):
    drop every cached/sentinel-bound manifest so the next test mints its own
    fresh `$unique` / `$email` values."""
    _MANIFEST_CACHE.clear()


def _bind_resolution_sentinels(manifest: Dict[str, Any]) -> None:
    """Resolve the `$unique` / `$email` placeholders **once per test** — the
    runtime-minted client name / email that no static manifest can carry. One
    `$unique` value is shared across `resolution.*` AND every `seed_clients`
    entry so seeding and the `$client` assertion agree."""
    res = manifest.get("resolution", {})
    minted_name = (
        _unique_client_name()
        if "$unique" in json.dumps(manifest, ensure_ascii=False)
        else None
    )
    if res.get("name") == "$unique":
        res["name"] = minted_name
    if res.get("resolves_to") == "$unique":
        res["resolves_to"] = minted_name
    if res.get("email") == "$email":
        res["email"] = _random_seed_email()
    for seed in manifest.get("seed_clients", []):
        if seed.get("name") == "$unique":
            seed["name"] = minted_name


def load_manifest(name: str) -> Dict[str, Any]:
    """Read `tests/fixtures/ledger_069/<name>.manifest.json` (pass the bare stem).

    Memoised per test (cleared by `reset_manifest_cache`) so `$unique`/`$email`
    sentinels resolve to one stable value for the whole test — seed, drive, and
    assert all see the same minted name."""
    if name in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[name]
    path = FIXTURES_DIR / f"{name}.manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"manifest {path} not found — author it per "
            f"contracts/payload-fidelity-manifest.md before running this test"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    _bind_resolution_sentinels(manifest)
    _MANIFEST_CACHE[name] = manifest
    return manifest


# --------------------------------------------------------------------------- #
# resolution: the ONE scenario-specific knob — mode + params drive both the
# answer bank (in the driver) and the `$client` value (in the asserter).
# --------------------------------------------------------------------------- #
def resolved_client_name_from(manifest: Dict[str, Any]) -> Optional[str]:
    """The exact client name the persisted event's `client_name` must carry —
    derived purely from `resolution.mode`."""
    res = manifest["resolution"]
    mode = res["mode"]
    if mode in ("exact", "none", "new_client", "new_client_distinct_payer", "store_as_stated"):
        return res["name"]
    if mode == "pick_existing":
        return res["resolves_to"]
    raise AssertionError(f"unknown resolution mode {mode!r}")


def _answer_bank_for(resolution: Dict[str, Any]) -> ClarificationAnswerBank:
    """Build the generic-flow answer bank from `resolution.mode` — the
    "pick this not that / yes that one / choose <name>" replies every scenario of
    a given mode needs, contained here once instead of hand-built per test."""
    mode = resolution["mode"]
    if mode == "exact":
        return ClarificationAnswerBank([], fallback="כן, זה נכון, תרשום")
    if mode == "none":
        # No client-resolution detour — only whatever gate the scenario's own
        # flow raises (e.g. US2's mutation-approval gate). Supply the common
        # follow-ups; the shared driver answers the closed כן/לא gate itself.
        return ClarificationAnswerBank(
            [{"topic": "payment_method",
              "keywords": ["אמצעי התשלום", "אמצעי תשלום", "איך שולם", "צורת התשלום"],
              "answer": "שולם בהעברה בנקאית"}],
            fallback="כן",
        )
    if mode == "new_client":
        return _new_client_answer_bank(
            full_name=resolution["name"],
            email=resolution["email"],
            phone=resolution["phone"],
        )
    if mode == "new_client_distinct_payer":
        # The source (an image) names whoever actually PAID - not necessarily
        # the client the deposit should be booked against (runtime_constitution.md:
        # "payer_name ... an intermediary who pays; may differ from the client;
        # never resolved"). The operator rejects treating the payer as the
        # client and states an unrelated new one instead.
        return _new_client_distinct_payer_answer_bank(
            full_name=resolution["name"],
            email=resolution["email"],
            phone=resolution["phone"],
        )
    if mode == "store_as_stated":
        ans = (
            f"אל תיצור לקוח ואל תחפש, תרשום את זה ככה עם השם {resolution['name']} "
            f"כמו שהוא, גם בלי אימות במורנינג"
        )
        return ClarificationAnswerBank(
            [{"topic": "resolve_or_store_anyway",
              "keywords": ["אימייל", "טלפון", "שם מלא", "חדש", "ליצור", "מצאתי", "לקוח"],
              "answer": ans}],
            fallback="תרשום ככה בלי אימות במורנינג",
        )
    if mode == "pick_existing":
        pick = resolution["resolves_to"]
        ans = f"כן, הכוונה ללקוח הקיים {pick}, אל תיצור לקוח חדש"
        return ClarificationAnswerBank(
            [{"topic": "pick_existing",
              "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "דומה", "נכון", "קיים",
                           "חדש", "ליצור", "איזה", "יותר מ", "שתי", "כמה"],
              "answer": ans}],
            fallback=ans,
        )
    raise AssertionError(f"unknown resolution mode {mode!r}")


def seed_scenario(denidin_app, manifest_name: str) -> Dict[str, Any]:
    """Step 1 of every Feature 069 acceptance test: seed every `seed_clients`
    entry the manifest declares (idempotent when `ensure_exists`). Returns the
    (sentinel-bound) manifest so the test can read `source_file` etc."""
    manifest = load_manifest(manifest_name)
    for seed in manifest.get("seed_clients", []):
        kwargs = {"name": seed["name"], "ensure_exists": bool(seed.get("ensure_exists"))}
        if seed.get("phone"):
            kwargs["phone"] = seed["phone"]
        _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], **kwargs)
        time.sleep(2)  # Morning search-index settle
    return manifest


def _extractor_output_for_chat(denidin_app) -> Dict[str, Any]:
    """Best-effort Hop-1 payload for a media source: the synthetic media turn's
    stashed user-message text (verbatim OCR + rendered structured fields), pulled
    back out of session history. The media pipeline rewrites the incoming
    image/document into a synthetic *text* turn whose `content` is the stash
    block; its frame line always contains `שחולץ מה`, which identifies it among
    the detour's plain-text answers. (`ledger_events` stays `[]` — MediaHandler
    does not persist the structured list; the substring match against the blob is
    the meaningful check. Known limitation B4, acceptance-regression-map.md.)"""
    sm = denidin_app.ai_handler.session_manager
    session = sm.get_session(GODFATHER_CHAT_ID)
    for mid in session.message_ids:
        msg = sm.load_message(session, mid)
        if msg is None:
            continue
        content = getattr(msg, "content", None) or ""
        if getattr(msg, "ai_required_role", None) == "user" and "שחולץ מה" in content:
            return {"extracted_text": content, "ledger_events": [], "document_analysis": {}}
    return {"extracted_text": "", "ledger_events": [], "document_analysis": {}}


_MEDIA_SOURCE_KINDS = frozenset({"image", "document"})


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
def _check_field(field: str, value: Any, rule: Dict, ev: Dict, *,
                 trigger_epoch: int, session_id: str,
                 resolved_client_name: Optional[str]) -> None:
    if "null" in rule:
        assert value in (None, "", [], {}), (
            f"{field}: manifest says this must be null/empty for this scenario, got {value!r}"
        )
        return
    if "free_text" in rule:
        assert isinstance(value, str) and value.strip(), (
            f"{field}: expected a non-empty free-text string, got {value!r}"
        )
        assert not _looks_like_bare_number(value) and not _looks_like_bare_date(value), (
            f"{field}: expected prose, got what parses as a bare number/date: {value!r}"
        )
        return
    if "tested" in rule:
        expected = rule["tested"]
        if expected == "$client":
            assert resolved_client_name is not None, (
                f"{field}: manifest uses \"$client\" but the test passed no resolved_client_name"
            )
            expected = resolved_client_name
        assert _norm_field(field, value) == _norm_field(field, expected), (
            f"{field}: expected {expected!r}, persisted event has {value!r}"
        )
        return
    if "generated" not in rule:
        raise AssertionError(f"{field}: malformed manifest rule {rule!r}")

    # {"generated": "<kind>"} — the ledgerer mints it; assert present AND
    # conforming to that kind's rule (a format, or an exact value we can
    # compute). This was a standalone `_check_generated` until 2026-09-10.
    kind = rule["generated"]
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
            f"event_datetime must equal the completing message's Green API timestamp "
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
        # "%d/%m/%Y %H:%M") (Phase 11) — minute-granular Israel wall-clock.
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
    denidin_app,
    persisted_events: List[Dict],
    manifest_name: str,
    trigger_epoch: int,
) -> None:
    """C9 — exhaustive per-field fidelity for every `LedgerEvent` a scenario
    persisted (one file for `בנק`/`חשבונית`; one per fee component for `הסכם`).

    Step 3 of every Feature 069 acceptance test. `manifest_name` is the only
    scenario key — session id, the resolved `$client` name, and (for a media
    source) the Hop-1 extractor output are all derived here from the manifest +
    `denidin_app`, so the test itself carries none of that plumbing.

    `manifest` shape::

        {
          "files": "single" | "per_component",
          "shared_fields": { "<field>": <rule>, ... },   # identical on every file
          "components":    [ { "<field>": <rule>, ... }, ... ]   # per_component only
        }

    Together, `shared_fields` and the union of `components` keys must classify
    **every** field in `LEDGER_EVENT_FIELDS` exactly once.

    `extractor_output` (media sources — US7 images, US9 image, US10 `docx`) turns
    this into the **two-hop** check (was a separate
    `assert_ledger_event_matches_manifest_two_hop` until 2026-09-10):
      Hop 1 — every ``tested`` value is present somewhere in the extractor's own
              output (`extracted_text` / `ledger_events[0]`), so a value lost in
              OCR/vision is distinguishable from one lost in the resolution detour.
      Hop 2 — the persisted event matches the manifest (the check below).
    A media source (`source_kind` image/document) automatically runs Hop 1.
    """
    manifest = load_manifest(manifest_name)
    session_id = session_id_for_chat(denidin_app, GODFATHER_CHAT_ID)
    resolved_client_name = resolved_client_name_from(manifest)

    if manifest.get("source_kind") in _MEDIA_SOURCE_KINDS:
        _assert_extractor_carried_tested_values(
            _extractor_output_for_chat(denidin_app), manifest
        )

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


def _assert_extractor_carried_tested_values(
    extractor_output: Dict[str, Any], manifest: Dict[str, Any]
) -> None:
    """Hop 1 of the two-hop media check (see
    `assert_ledger_event_matches_manifest`'s `extractor_output` param): every
    ``tested`` value in the manifest is present somewhere in the extractor's own
    output, so a value lost in OCR/vision is distinguishable from one lost in the
    resolution detour."""
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


# --------------------------------------------------------------------------- #
# reading persisted events
# --------------------------------------------------------------------------- #
# The one reader lives in tests/e2e_helpers.py now, as
# `persisted_ledger_events_for_chat` (shared with the pre-069 ledger-capture
# tests). This module's own `ledger_events_for_chat` / `events_reader` copies
# were removed 2026-09-10.


def assert_no_ledger_event(denidin_app, chat_id: str) -> None:
    events = persisted_ledger_events_for_chat(denidin_app, chat_id)
    assert not events, (
        f"expected NO persisted ledger event for {chat_id!r}, found "
        f"{[e.get('event_id') for e in events]!r}"
    )


def session_id_for_chat(denidin_app, chat_id: str) -> str:
    return denidin_app.ai_handler.session_manager.get_session(chat_id).session_id


# --------------------------------------------------------------------------- #
# resolution-detour answer bank (new client)
# --------------------------------------------------------------------------- #
def _new_client_answer_bank(*, full_name: str, email: str, phone: str) -> ClarificationAnswerBank:
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
            {
                # A deposit-slip scenario (US7a) — after add_client succeeds, the
                # model can still ask to confirm the OCR'd transaction date.
                "topic": "confirm_ocr_date",
                "keywords": ["תאריך ההפקדה", "לאשר את התאריך", "לרשום ביומן", "תאריך אחר"],
                "answer": "כן, תרשום עם התאריך שמופיע בתמונה",
            },
            {
                # Same scenario — a receipt that doesn't show bank/account numbers.
                "topic": "missing_banking_details",
                "keywords": ["מספר הבנק", "מספר החשבון", "לא מופיעים באסמכתא", "עדיין חסרים"],
                "answer": "מספר הבנק והחשבון לא מופיעים באסמכתא, תרשום את ההפקדה בלעדיהם",
            },
        ],
        fallback=f"לקוח חדש. {supply_all}",
    )


def _new_client_distinct_payer_answer_bank(
    *, full_name: str, email: str, phone: str
) -> ClarificationAnswerBank:
    """The source names whoever paid, not necessarily the client the event
    should be booked against (`payer_name` — 'an intermediary who pays; may
    differ from the client; never resolved'). The operator explicitly rejects
    treating the payer as the client and states an unrelated new one instead —
    a real conversational path (e.g. a compound/unclear payer name on a bank
    slip), distinct from the plain `new_client` flow where the stated name and
    the source's own name are the same."""
    supply_all = f"שם מלא: {full_name}. אימייל: {email}. טלפון: {phone}."
    override = f"לא, זה לא הלקוח, זה רק מי ששילם. הלקוח הוא {full_name}. {supply_all}"
    return ClarificationAnswerBank(
        [
            {
                "topic": "payer_is_not_the_client",
                "keywords": ["מי הלקוח", "האם הכוונה", "לקוח קיים", "ליצור", "חדש",
                             "השם", "מספר שמות", "משותף", "שני שמות", "מצאתי", "איזה"],
                "answer": override,
            },
            {
                "topic": "full_contact_details",
                "keywords": ["אימייל", "מייל", "טלפון", "שם מלא", "פרטים", "כתובת מייל"],
                "answer": supply_all,
            },
            {
                "topic": "confirm_ocr_date",
                "keywords": ["תאריך ההפקדה", "לאשר את התאריך", "לרשום ביומן", "תאריך אחר"],
                "answer": "כן, תרשום עם התאריך שמופיע בתמונה",
            },
            {
                "topic": "vat",
                "keywords": ['מע"מ', "מעמ", "כולל מע"],
                "answer": "לא צוין מע\"מ, תשאיר כפי שנכתב",
            },
        ],
        fallback=override,
    )
