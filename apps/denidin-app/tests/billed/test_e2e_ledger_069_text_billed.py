"""Feature 069 — Phase 11 acceptance (TEXT fee-agreement flows), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING. Proves the post-turn
recognition mechanism + mandatory client resolution for `הסכם` stated as plain
text (FR-069-005/022). Exhaustive per-field manifest fidelity via
`_ledger_069_acceptance.assert_ledger_event_matches_manifest` — every
`LedgerEvent` field is classified tested / generated / null / free_text, and
`event_datetime` is asserted equal to the triggering message's Green API
timestamp on every scenario that persists an event.

The 4-way client-resolution logic is covered across this file + US10:
    US4  — 0 Morning matches → new-client detour
    US5b — exactly 1 partial match → operator picks the existing candidate
    US5  — 2+ partial matches → operator picks one
    US6  — exact match → silent, no question
(US10, `..._docx_billed.py`, adds the 1-partial case for a `.docx` source.)

Run (billed — no per-run approval; sound off each result live):
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_text_billed.py::<node>"
    scripts/run_parallel_tests.sh tests/billed/test_e2e_ledger_069_*_billed.py
"""
from __future__ import annotations

import time

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _random_seed_email,
    _seed_client,
    _send_turn,
    _unique_client_name,
)
from tests.billed._ledger_069_acceptance import (
    assert_ledger_event_matches_manifest,
    assert_no_ledger_event,
    load_manifest,
    resolution_answer_bank,
    session_id_for_chat,
)
from tests.billed._ledger_069_post_turn_base import (
    FIX_DIR,
    drive_capture_conversation,
    reset_069_chat,  # noqa: F401 - autouse fixture, imported to register in this module
)
from tests.e2e_helpers import ClarificationAnswerBank


@pytest.mark.billed
class TestLedgerPostTurnCaptureText:

    # ---- US1: the mechanism moved (no inline capture tool anymore) ----------
    def test_us1_mechanism_move_agreement_text_exact_client(self, denidin_app):
        """A fee agreement stated as plain text, client already an EXACT Morning
        match → exactly one agreement recorded, post-turn, against the exact
        Morning name. `capture_ledger_event` is not offered to the model anymore
        (the mechanism move) — the only path to a `LedgerEvent` is the post-turn
        recognition call. Exhaustive manifest fidelity."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US1", phone="0525550101")
        time.sleep(2)
        text = (
            f"סגרתי היום הסכם שכר טרחה עם {name}: מקדמה קבועה 5,000 ש\"ח + מע\"מ, "
            f"ובנוסף שכר הצלחה 10% + מע\"מ מכל סכום שייפסק."
        )
        events, transcript, trigger_epoch = drive_capture_conversation(
            denidin_app, text,
            ClarificationAnswerBank([], fallback="כן, זה נכון, תרשום"),
            id_prefix="F069_US1",
        )
        assert_ledger_event_matches_manifest(
            events, load_manifest("agreement_us1"),
            trigger_epoch=trigger_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
            resolved_client_name=name,
        )
        last = denidin_app.ai_handler.last_response
        if last is not None:
            assert not any(
                c["name"] == "capture_ledger_event" for c in last.mcp_calls
            ), "capture_ledger_event must not exist as an inline tool anymore (mechanism move)"

    # ---- US3: false-positive / regression guards ---------------------------
    def test_us3_regression_guard_ordinary_turn_no_capture(self, denidin_app):
        """An ordinary admin question that is not a ledger event → the post-turn
        recognition call returns `none` and nothing is persisted."""
        _send_turn(GODFATHER_CHAT_ID, "מה השעה עכשיו ומה מזג האוויר?", "F069_US3A")
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)

    def test_us3_bare_email_is_not_a_ledger_event(self, denidin_app):
        """A message that is *only* an email address (a client detail supplied
        mid-flow, or noise) must never be recognised as a completed ledger
        event."""
        _send_turn(GODFATHER_CHAT_ID, "yaron.test.f069@example.com", "F069_US3B")
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)

    # ---- US4: FLAGSHIP — 0-match, brand-new client, full resolution detour --
    def test_us4_new_client_agreement_full_detour(self, denidin_app):
        """`agreement_new_client.txt`: a multi-component fee agreement for a
        client Morning has never seen (name drawn fresh via `_unique_client_name`
        and injected — a real name, never a per-run suffix). The turn cannot
        complete until the operator supplies full name + email + phone and
        `add_client` runs; only then does the post-turn recognition call record
        the agreement — every fee component, `payer_name` verbatim as free text
        (≠ `client_name`), against the newly-created exact Morning name.
        Exhaustive bidirectional manifest fidelity — the detour lost nothing and
        invented nothing."""
        manifest = load_manifest("agreement_new_client")
        client_name = _unique_client_name()
        agreement_text = (FIX_DIR / "agreement_new_client.txt").read_text(
            encoding="utf-8"
        ).format(client_name=client_name)
        bank = resolution_answer_bank(
            full_name=client_name,
            email=_random_seed_email(),  # ASCII only — a Hebrew local-part makes add_client reject
            phone="0525550142",
        )
        events, transcript, trigger_epoch = drive_capture_conversation(
            denidin_app,
            "קיבלתי עכשיו את ההסכם הבא, תרשום אותו ביומן:\n\n" + agreement_text,
            bank, id_prefix="F069_US4", max_turns=6,
        )
        assert_ledger_event_matches_manifest(
            events, manifest, trigger_epoch=trigger_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
            resolved_client_name=client_name,
        )

    # ---- US5b: exactly ONE partial match — operator picks the candidate ----
    def test_us5b_one_partial_agreement_operator_picks(self, denidin_app):
        """`agreement_one_partial.txt`: exactly one partial Morning match
        (seeded 'דוד רוזנברג'; the text says 'דויד רוזנברג'). DeniDin states the
        one candidate AND the create-new option; the operator picks the existing
        candidate; the agreement is recorded against that exact seeded Morning
        name. No client is created — repeatable."""
        manifest = load_manifest("agreement_one_partial")
        res = manifest["client_resolution"]
        for seed in manifest["seed_clients"]:
            _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], name=seed["name"],
                         phone="0525550106", ensure_exists=bool(seed.get("ensure_exists")))
            time.sleep(2)
        agreement_text = (FIX_DIR / "agreement_one_partial.txt").read_text(encoding="utf-8")
        bank = ClarificationAnswerBank(
            [{"topic": "one_candidate_or_new",
              "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "דומה", "נכון", "קיים", "חדש", "ליצור"],
              "answer": f"כן, הכוונה ללקוח הקיים {res['operator_picks']}, אל תיצור לקוח חדש"}],
            fallback=f"כן, הלקוח הקיים {res['operator_picks']}, אל תיצור חדש",
        )
        events, transcript, trigger_epoch = drive_capture_conversation(
            denidin_app,
            "תרשום ביומן את ההסכם הזה:\n\n" + agreement_text,
            bank, id_prefix="F069_US5B", max_turns=6,
        )
        assert_ledger_event_matches_manifest(
            events, manifest, trigger_epoch=trigger_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
        )

    # ---- US5: 2+ partial matches — operator picks one --------------------
    def test_us5_ambiguous_agreement_operator_picks(self, denidin_app):
        """`agreement_ambiguous.txt`: two partial Morning matches for the stated
        name. The turn must ask which one; once the operator picks, the agreement
        is recorded against that exact Morning name. Exhaustive manifest
        fidelity."""
        manifest = load_manifest("agreement_ambiguous")
        res = manifest["client_resolution"]
        for seed in manifest["seed_clients"]:
            _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], name=seed["name"],
                         phone="0525550102", ensure_exists=bool(seed.get("ensure_exists")))
            time.sleep(2)  # Morning search-index settle
        agreement_text = (FIX_DIR / "agreement_ambiguous.txt").read_text(encoding="utf-8")
        bank = ClarificationAnswerBank(
            [{"topic": "which_of_the_matches",
              "keywords": ["איזה", "מצאתי", "יותר מ", "האם הכוונה", "שתי", "כמה"],
              "answer": f"הכוונה ל{res['operator_picks']}"}],
            fallback=f"הכוונה ל{res['operator_picks']}",
        )
        events, transcript, trigger_epoch = drive_capture_conversation(
            denidin_app,
            "תרשום ביומן את ההסכם הזה:\n\n" + agreement_text,
            bank, id_prefix="F069_US5", max_turns=6,
        )
        assert_ledger_event_matches_manifest(
            events, manifest, trigger_epoch=trigger_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
        )

    # ---- US6: exact match → silent, no disambiguation question -----------
    def test_us6_exact_match_captures_without_a_question(self, denidin_app):
        """A single EXACT Morning match → the operator is NOT asked to
        disambiguate; the agreement is recorded on the same turn, exhaustive
        manifest fidelity."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US6", phone="0525550103")
        time.sleep(2)
        text = (
            f"רשום ביומן: הסכם שכר טרחה עם {name} מהיום — מקדמה 7,000 ש\"ח + מע\"מ, "
            f"ושכר הצלחה 20% + מע\"מ."
        )
        events, transcript, trigger_epoch = drive_capture_conversation(
            denidin_app, text,
            ClarificationAnswerBank([], fallback="כן תרשום"),
            id_prefix="F069_US6", max_turns=3,
        )
        assert transcript and transcript[0]["reply"], "no reply on turn 1"
        assert len(transcript) <= 2, (
            f"an exact-match client should not trigger a resolution detour, "
            f"took {len(transcript)} turns: {[t['sent'] for t in transcript]!r}"
        )
        assert_ledger_event_matches_manifest(
            events, load_manifest("agreement_us6"),
            trigger_epoch=trigger_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
            resolved_client_name=name,
        )

    # ---- US8: store-anyway election + its refusal twin -------------------
    def test_us8_store_anyway_marks_the_record(self, denidin_app):
        """`agreement_new_client.txt`, but the operator declines to resolve the
        client and explicitly elects to store it as-stated → persisted with the
        operator-stated name (a fresh `_unique_client_name`, never created in
        Morning). No 'בטוח?' turn. Every non-client field is still manifest-exact
        (`description` is free text, not asserted for the marker)."""
        manifest = load_manifest("agreement_new_client")
        stated = _unique_client_name()
        agreement_text = (FIX_DIR / "agreement_new_client.txt").read_text(
            encoding="utf-8"
        ).format(client_name=stated)
        bank = ClarificationAnswerBank(
            [{"topic": "resolve_or_store_anyway",
              "keywords": ["אימייל", "טלפון", "שם מלא", "חדש", "ליצור", "מצאתי", "לקוח"],
              "answer": "אל תיצור לקוח ואל תחפש, תרשום את זה ככה עם השם שנתתי, גם בלי אימות במורנינג"}],
            fallback="תרשום ככה בלי אימות במורנינג",
        )
        events, transcript, trigger_epoch = drive_capture_conversation(
            denidin_app,
            f"תרשום ביומן, ואל תטרח לאמת את הלקוח במורנינג — תרשום עם השם {stated} כמו שהוא:\n\n"
            + agreement_text,
            bank, id_prefix="F069_US8", max_turns=5,
        )
        assert_ledger_event_matches_manifest(
            events, manifest, trigger_epoch=trigger_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
            resolved_client_name=stated,
        )

    def test_us8_dont_store_persists_nothing(self, denidin_app):
        """The twin: operator says not to store it → the recognition call returns
        `declined` and nothing is persisted."""
        _send_turn(
            GODFATHER_CHAT_ID,
            "חשבתי לרשום הסכם עם מישהו חדש אבל עזוב, אל תרשום כלום ביומן בינתיים.",
            "F069_US8B",
        )
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)
