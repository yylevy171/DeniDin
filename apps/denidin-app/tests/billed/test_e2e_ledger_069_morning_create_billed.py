"""Feature 069 — Phase 11 acceptance (in-conversation Morning create), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING.

US2: when the operator has DeniDin create a Morning document in-conversation, the
resulting `חשבונית` ledger event is captured **synchronously** that turn (spec
US2/US3), against the exact resolved (seeded) client, carrying the real Morning
document number — and NO VAT clarifying question is asked (a type-320 combo
document carries VAT by definition).

Same three steps as every Feature 069 acceptance test — seed / drive / assert —
against the static `morning_create_us2` manifest (`resolution.mode: none`: no
client-resolution detour, only the mutation-approval gate the shared driver
answers itself).

Run:
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_morning_create_billed.py::<node>"
"""
from __future__ import annotations

import time

import pytest

from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID
from tests.billed._ledger_069_acceptance import assert_ledger_event_matches_manifest
from tests.billed._ledger_069_post_turn_base import (
    drive_capture,
    seed_scenario,
    clean_069_chat_history,  # noqa: F401 - autouse fixture, registers in this module
)
from tests.e2e_helpers import persisted_ledger_events_for_chat

_CREATE_TOOLS = (
    "create_combo_document", "create_invoice", "create_transaction_account",
    "create_credit_note", "create_receipt",
)


@pytest.mark.billed
class TestLedgerPostTurnCaptureMorningCreate:

    def test_us2_morning_create_is_captured_synchronously(self, denidin_app):
        """A type-320 `create_combo_document` in-conversation → exactly one
        `חשבונית` ledger event that turn, against the exact resolved client, with
        the document's own Morning number — no VAT question anywhere."""
        manifest = seed_scenario(denidin_app, "morning_create_us2")
        name = manifest["resolution"]["name"]
        trigger_epoch = int(time.time())
        events, transcript, _ = drive_capture(
            denidin_app, "morning_create_us2", id_prefix="F069_US2",
            base_ts=trigger_epoch, max_turns=6,
            first_text=(
                f"תפיק ל{name} חשבונית מס-קבלה על סך 1,200 ש\"ח כולל מע\"מ עבור ייעוץ משפטי. "
                f"שולם היום בהעברה בנקאית."
            ),
        )

        last_ai = denidin_app.ai_handler.last_response
        create_calls = [
            c for c in (last_ai.mcp_calls if last_ai else [])
            if c["name"] in _CREATE_TOOLS and c.get("error") is None
        ]
        assert create_calls, (
            f"no successful Morning create call. "
            f"last_calls={last_ai.mcp_calls if last_ai else None!r}"
        )

        joined = " ".join(t.get("reply") or "" for t in transcript)
        assert not any(
            k in joined for k in ("כולל מע\"מ או לא", "עם מע\"מ או בלי", "האם המחיר כולל")
        ), f"DeniDin must NOT ask a VAT clarifying question for a type-320 combo document"

        events = persisted_ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        invoice_events = [e for e in events if e["source_type"] == "חשבונית"]
        assert len(invoice_events) == 1, (
            f"exactly one חשבונית ledger event expected, got {len(invoice_events)}: {events!r}"
        )
        assert_ledger_event_matches_manifest(
            denidin_app, invoice_events, "morning_create_us2", trigger_epoch,
        )
