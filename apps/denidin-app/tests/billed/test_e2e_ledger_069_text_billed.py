"""Feature 069 — Phase 11 acceptance (TEXT fee-agreement flows), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING. Proves the post-turn
recognition mechanism + mandatory client resolution for `הסכם` stated as plain
text (FR-069-005/022). Exhaustive per-field manifest fidelity via
`_ledger_069_acceptance.assert_ledger_event_matches_manifest` — every
`LedgerEvent` field is classified tested / generated / null / free_text, and
`event_datetime` is asserted equal to the triggering message's Green API
timestamp on every scenario that persists an event.

Every test is the same three steps:
    1. `seed_scenario(denidin_app, <manifest>)`      — seed the manifest's clients
    2. `drive_capture(denidin_app, <manifest>, first_text=<trigger>)` — one turn +
       whatever resolution detour the manifest's `resolution.mode` implies
    3. `assert_ledger_event_matches_manifest(denidin_app, events, <manifest>, epoch)`

The 4-way client-resolution logic is covered across this file + US10:
    US4  — 0 Morning matches → new-client detour        (resolution.mode new_client)
    US5b — exactly 1 partial match → operator picks it   (resolution.mode pick_existing)
    US5  — 2+ partial matches → operator picks one       (resolution.mode pick_existing)
    US6  — exact match → silent, no question             (resolution.mode exact)

Run (billed — no per-run approval; sound off each result live):
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_text_billed.py::<node>"
    scripts/run_parallel_tests.sh tests/billed/test_e2e_ledger_069_*_billed.py
"""
from __future__ import annotations

import pytest

from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID, _send_turn
from tests.billed._ledger_069_acceptance import (
    assert_ledger_event_matches_manifest,
    assert_no_ledger_event,
)
from tests.billed._ledger_069_post_turn_base import (
    FIX_DIR,
    drive_capture,
    seed_scenario,
    clean_069_chat_history,  # noqa: F401 - autouse fixture, registers in this module
)


@pytest.mark.billed
class TestLedgerPostTurnCaptureText:

    # ---- US1: the mechanism moved (no inline capture tool anymore) ----------
    def test_us1_mechanism_move_agreement_text_exact_client(self, denidin_app):
        """A fee agreement stated as plain text, client already an EXACT Morning
        match → exactly one agreement recorded, post-turn, against the exact
        Morning name. `capture_ledger_event` is not offered to the model anymore
        (the mechanism move) — the only path to a `LedgerEvent` is the post-turn
        recognition call. Exhaustive manifest fidelity."""
        manifest = seed_scenario(denidin_app, "agreement_us1")
        name = manifest["resolution"]["name"]
        text = (
            f"סגרתי היום הסכם שכר טרחה עם {name}: מקדמה קבועה 5,000 ש\"ח + מע\"מ, "
            f"ובנוסף שכר הצלחה 10% + מע\"מ מכל סכום שייפסק."
        )
        events, _, trigger_epoch = drive_capture(
            denidin_app, "agreement_us1", first_text=text, id_prefix="F069_US1",
        )
        assert_ledger_event_matches_manifest(
            denidin_app, events, "agreement_us1", trigger_epoch,
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
    @pytest.mark.sanity
    def test_us4_new_client_agreement_full_detour(self, denidin_app):
        """`agreement_new_client.txt`: a multi-component fee agreement for a
        client Morning has never seen (name minted fresh via the manifest's
        `$unique` sentinel — a real name, never a per-run suffix). The turn cannot
        complete until the operator supplies full name + email + phone and
        `add_client` runs; only then does the post-turn recognition call record
        the agreement — every fee component, `payer_name` verbatim as free text
        (≠ `client_name`), against the newly-created exact Morning name.
        Exhaustive bidirectional manifest fidelity — the detour lost nothing and
        invented nothing."""
        manifest = seed_scenario(denidin_app, "agreement_new_client")
        agreement_text = (FIX_DIR / manifest["source_file"]).read_text(
            encoding="utf-8"
        ).format(client_name=manifest["resolution"]["name"])
        events, _, trigger_epoch = drive_capture(
            denidin_app, "agreement_new_client", id_prefix="F069_US4", max_turns=6,
            first_text="קיבלתי עכשיו את ההסכם הבא, תרשום אותו ביומן:\n\n" + agreement_text,
        )
        assert_ledger_event_matches_manifest(
            denidin_app, events, "agreement_new_client", trigger_epoch,
        )

    # ---- US5b: exactly ONE partial match — operator picks the candidate ----
    def test_us5b_one_partial_agreement_operator_picks(self, denidin_app):
        """`agreement_one_partial.txt`: exactly one partial Morning match
        (seeded 'דוד רוזנברג'; the text says 'דויד רוזנברג'). DeniDin states the
        one candidate AND the create-new option; the operator picks the existing
        candidate; the agreement is recorded against that exact seeded Morning
        name. No client is created — repeatable."""
        manifest = seed_scenario(denidin_app, "agreement_one_partial")
        agreement_text = (FIX_DIR / manifest["source_file"]).read_text(encoding="utf-8")
        events, _, trigger_epoch = drive_capture(
            denidin_app, "agreement_one_partial", id_prefix="F069_US5B", max_turns=6,
            first_text="תרשום ביומן את ההסכם הזה:\n\n" + agreement_text,
        )
        assert_ledger_event_matches_manifest(
            denidin_app, events, "agreement_one_partial", trigger_epoch,
        )

    # ---- US5: 2+ partial matches — operator picks one --------------------
    @pytest.mark.sanity
    def test_us5_ambiguous_agreement_operator_picks(self, denidin_app):
        """`agreement_ambiguous.txt`: two partial Morning matches for the stated
        name. The turn must ask which one; once the operator picks, the agreement
        is recorded against that exact Morning name. Exhaustive manifest
        fidelity."""
        manifest = seed_scenario(denidin_app, "agreement_ambiguous")
        agreement_text = (FIX_DIR / manifest["source_file"]).read_text(encoding="utf-8")
        events, _, trigger_epoch = drive_capture(
            denidin_app, "agreement_ambiguous", id_prefix="F069_US5", max_turns=6,
            first_text="תרשום ביומן את ההסכם הזה:\n\n" + agreement_text,
        )
        assert_ledger_event_matches_manifest(
            denidin_app, events, "agreement_ambiguous", trigger_epoch,
        )

    # ---- US6: exact match → silent, no disambiguation question -----------
    @pytest.mark.sanity
    def test_us6_exact_match_captures_without_a_question(self, denidin_app):
        """A single EXACT Morning match → the operator is NOT asked to
        disambiguate; the agreement is recorded on the same turn (the
        exact-mode no-detour assertion lives in `drive_capture`), exhaustive
        manifest fidelity."""
        manifest = seed_scenario(denidin_app, "agreement_us6")
        name = manifest["resolution"]["name"]
        text = (
            f"רשום ביומן: הסכם שכר טרחה עם {name} מהיום — מקדמה 7,000 ש\"ח + מע\"מ, "
            f"ושכר הצלחה 20% + מע\"מ."
        )
        events, transcript, trigger_epoch = drive_capture(
            denidin_app, "agreement_us6", first_text=text, id_prefix="F069_US6",
            max_turns=3,
        )
        assert transcript and transcript[0]["reply"], "no reply on turn 1"
        assert_ledger_event_matches_manifest(
            denidin_app, events, "agreement_us6", trigger_epoch,
        )

    # ---- US8: store-anyway election + its refusal twin -------------------
    def test_us8_store_anyway_marks_the_record(self, denidin_app):
        """`agreement_store_anyway`: same agreement as US4, but the operator
        declines to resolve the client and explicitly elects to store it
        as-stated → persisted with the operator-stated name (a fresh `$unique`,
        never created in Morning). No 'בטוח?' turn. Every non-client field is
        still manifest-exact (`description` is free text, not asserted)."""
        manifest = seed_scenario(denidin_app, "agreement_store_anyway")
        stated = manifest["resolution"]["name"]
        agreement_text = (FIX_DIR / manifest["source_file"]).read_text(
            encoding="utf-8"
        ).format(client_name=stated)
        events, _, trigger_epoch = drive_capture(
            denidin_app, "agreement_store_anyway", id_prefix="F069_US8", max_turns=5,
            first_text=(
                f"תרשום ביומן, ואל תטרח לאמת את הלקוח במורנינג — תרשום עם השם {stated} כמו שהוא:\n\n"
                + agreement_text
            ),
        )
        assert_ledger_event_matches_manifest(
            denidin_app, events, "agreement_store_anyway", trigger_epoch,
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
