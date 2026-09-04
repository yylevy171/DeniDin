"""Feature 069 — Phase 11 acceptance (TEXT fee-agreement flows), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING. Proves the post-turn
recognition mechanism + mandatory client resolution for `הסכם` stated as plain
text (FR-069-005/022). Bidirectional manifest fidelity via `_ledger_069_acceptance`.

Split from the original `test_e2e_ledger_post_turn_capture.py` (2026-09-04) so
`scripts/run_parallel_tests.sh` can run the Feature 069 acceptance files across
xdist workers. Shared driver: `_ledger_069_post_turn_base`.

Morning sandbox roster
----------------------
* US1 / US6 exact-match: a fresh client seeded in-test (`_seed_client(name=...)`).
* US5 ambiguity: two partial matches seeded in-test (`agreement_ambiguous.manifest.json`).
* US4 / US8: a brand-new client the operator supplies name + email + phone for
  during the detour — created by the run, not pre-seeded.

Run (billed — no per-run approval; sound off each result live):
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_text_billed.py::<node>"
    scripts/run_parallel_tests.sh tests/billed/test_e2e_ledger_069_*_billed.py
"""
from __future__ import annotations

import time

import pytest

from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID, _seed_client, _send_turn
from tests.billed._ledger_069_acceptance import (
    assert_event_matches_manifest,
    assert_no_ledger_event,
    load_manifest,
    resolution_answer_bank,
)
from tests.billed._ledger_069_post_turn_base import FIX_DIR, drive_capture_conversation
from tests.e2e_helpers import ClarificationAnswerBank


@pytest.mark.billed
class TestLedgerPostTurnCaptureText:

    # ---- US1: the mechanism moved (no inline capture tool anymore) ----------
    def test_us1_mechanism_move_agreement_text_exact_client(self, denidin_app):
        """A fee agreement stated as plain text, client already an EXACT Morning
        match → exactly one agreement recorded, post-turn, against the exact
        Morning name. `capture_ledger_event` is not offered to the model anymore
        (the mechanism move) — the only path to a `LedgerEvent` is the post-turn
        recognition call."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US1", phone="0525550101")
        text = (
            f"סגרתי היום הסכם שכר טרחה עם {name}: מקדמה קבועה 5,000 ש\"ח + מע\"מ, "
            f"ובנוסף שכר הצלחה 10% + מע\"מ מכל סכום שייפסק."
        )
        events, _ = drive_capture_conversation(
            denidin_app, text,
            ClarificationAnswerBank([], fallback="כן, זה נכון, תרשום"),
            id_prefix="F069_US1",
        )
        assert events, "no LedgerEvent recorded for a clear fee-agreement turn"
        for ev in events:
            assert ev["source_type"] == "הסכם"
            assert ev["client_name"] == name, (
                f"client_name must be the exact seeded Morning name {name!r}, got {ev['client_name']!r}"
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
        """T041b / T008c guard: a message that is *only* an email address (a
        client detail the operator is supplying mid-flow, or noise) must never be
        recognised as a completed ledger event."""
        _send_turn(GODFATHER_CHAT_ID, "yaron.test.f069@example.com", "F069_US3B")
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)

    # ---- US4: FLAGSHIP — brand-new client, full resolution detour ----------
    def test_us4_new_client_agreement_full_detour(self, denidin_app):
        """`agreement_new_client.txt`: the operator states a multi-component fee
        agreement for a client Morning has never seen. The turn cannot complete
        until the operator supplies full name + email + phone and `add_client`
        runs; only then does the post-turn recognition call record the agreement,
        every fee component, against the newly-created exact Morning name.
        Bidirectional manifest fidelity — the detour lost nothing."""
        manifest = load_manifest("agreement_new_client")
        res = manifest["client_resolution"]
        agreement_text = (FIX_DIR / "agreement_new_client.txt").read_text(encoding="utf-8")
        bank = resolution_answer_bank(
            full_name=res["operator_stated_name"],
            email=res["new_client_email"],
            phone=res["new_client_phone"],
        )
        events, _ = drive_capture_conversation(
            denidin_app,
            "קיבלתי עכשיו את ההסכם הבא, תרשום אותו ביומן:\n\n" + agreement_text,
            bank, id_prefix="F069_US4", max_turns=6,
        )
        assert_event_matches_manifest(events, manifest)

    # ---- US5: ambiguous client — operator picks one ----------------------
    def test_us5_ambiguous_agreement_operator_picks(self, denidin_app):
        """`agreement_ambiguous.txt`: two partial Morning matches for the stated
        name. The turn must ask which one; once the operator picks, the agreement
        is recorded against that exact Morning name."""
        manifest = load_manifest("agreement_ambiguous")
        res = manifest["client_resolution"]
        for seed in manifest["seed_clients"]:
            _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], name=seed["name"],
                         phone="0525550102")
            time.sleep(2)  # Morning search-index settle
        agreement_text = (FIX_DIR / "agreement_ambiguous.txt").read_text(encoding="utf-8")
        bank = ClarificationAnswerBank(
            [{"topic": "which_of_the_matches",
              "keywords": ["איזה", "מצאתי", "יותר מ", "האם הכוונה", "שתי", "כמה"],
              "answer": f"הכוונה ל{res['operator_picks']}"}],
            fallback=f"הכוונה ל{res['operator_picks']}",
        )
        events, _ = drive_capture_conversation(
            denidin_app,
            "תרשום ביומן את ההסכם הזה:\n\n" + agreement_text,
            bank, id_prefix="F069_US5", max_turns=6,
        )
        assert_event_matches_manifest(events, manifest)

    # ---- US6: exact match → silent, no disambiguation question -----------
    def test_us6_exact_match_captures_without_a_question(self, denidin_app):
        """A single EXACT Morning match → the operator is NOT asked to
        disambiguate; the agreement is recorded on the same turn."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US6", phone="0525550103")
        time.sleep(2)
        text = (
            f"רשום ביומן: הסכם שכר טרחה עם {name} מהיום — מקדמה 7,000 ש\"ח + מע\"מ, "
            f"ושכר הצלחה 20% + מע\"מ."
        )
        events, transcript = drive_capture_conversation(
            denidin_app, text,
            ClarificationAnswerBank([], fallback="כן תרשום"),
            id_prefix="F069_US6", max_turns=3,
        )
        assert events, "exact-match agreement was not recorded"
        assert transcript[0]["reply"], "no reply on turn 1"
        assert len(transcript) <= 2, (
            f"an exact-match client should not trigger a resolution detour, "
            f"took {len(transcript)} turns: {[t['sent'] for t in transcript]!r}"
        )
        for ev in events:
            assert ev["client_name"] == name

    # ---- US8: store-anyway election + its refusal twin -------------------
    def test_us8_store_anyway_marks_the_record(self, denidin_app):
        """`agreement_new_client.txt`, but the operator declines to resolve the
        client and explicitly elects to store it as-stated → persisted with the
        operator-stated name and `[לקוח לא אומת במורנינג]` in the description. No
        'בטוח?' turn — a proactive election is honoured directly."""
        manifest = load_manifest("agreement_new_client")
        stated = manifest["client_resolution"]["operator_stated_name"]
        agreement_text = (FIX_DIR / "agreement_new_client.txt").read_text(encoding="utf-8")
        bank = ClarificationAnswerBank(
            [{"topic": "resolve_or_store_anyway",
              "keywords": ["אימייל", "טלפון", "שם מלא", "חדש", "ליצור", "מצאתי", "לקוח"],
              "answer": "אל תיצור לקוח ואל תחפש, תרשום את זה ככה עם השם שנתתי, גם בלי אימות במורנינג"}],
            fallback="תרשום ככה בלי אימות במורנינג",
        )
        events, _ = drive_capture_conversation(
            denidin_app,
            f"תרשום ביומן, ואל תטרח לאמת את הלקוח במורנינג — תרשום עם השם {stated} כמו שהוא:\n\n"
            + agreement_text,
            bank, id_prefix="F069_US8", max_turns=5,
        )
        assert_event_matches_manifest(events, manifest, stated_name_for_store_anyway=stated)

    def test_us8_dont_store_persists_nothing(self, denidin_app):
        """The twin: operator says not to store it → the recognition call returns
        `declined` and nothing is persisted."""
        _send_turn(
            GODFATHER_CHAT_ID,
            "חשבתי לרשום הסכם עם מישהו חדש אבל עזוב, אל תרשום כלום ביומן בינתיים.",
            "F069_US8B",
        )
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)
