"""Feature 069 — Phase 11 acceptance (in-conversation Morning create), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING.

US2: when the operator has DeniDin create a Morning document in-conversation, the
resulting `חשבונית` ledger event is captured **synchronously** from that turn
(spec US2/US3), against the exact resolved client, carrying the real document
number.

Split from the original `test_e2e_ledger_post_turn_capture.py` (2026-09-04).

Run:
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_morning_create_billed.py::<node>"
"""
from __future__ import annotations

import time

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _seed_client,
    _send_turn_and_approve,
)
from tests.billed._ledger_069_acceptance import ledger_events_for_chat


@pytest.mark.billed
class TestLedgerPostTurnCaptureMorningCreate:

    def test_us2_morning_create_is_captured_synchronously(self, denidin_app):
        """A type-320 `create_combo_document` in-conversation → exactly one
        `חשבונית` ledger event that turn, against the exact resolved client, with
        the document's own Morning number."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US2", phone="0525550104")
        time.sleep(2)
        (_ask, _ask_ai), (reply, approve_ai) = _send_turn_and_approve(
            GODFATHER_CHAT_ID,
            f"תפיק ל{name} חשבונית מס-קבלה על סך 1,200 ש\"ח כולל מע\"מ עבור ייעוץ משפטי.",
            "F069_US2",
        )
        assert approve_ai is not None
        create_calls = [
            c for c in approve_ai.mcp_calls
            if c["name"] in (
                "create_combo_document", "create_invoice", "create_transaction_account",
                "create_credit_note", "create_receipt",
            ) and c.get("error") is None
        ]
        assert create_calls, f"no successful Morning create call. reply={reply!r}"
        events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        invoice_events = [e for e in events if e["source_type"] == "חשבונית"]
        assert len(invoice_events) == 1, (
            f"exactly one חשבונית ledger event expected, got {len(invoice_events)}: {events!r}"
        )
        ev = invoice_events[0]
        assert ev["client_name"] == name, (
            f"חשבונית ledger event client must be the exact resolved name {name!r}, "
            f"got {ev['client_name']!r}"
        )
        assert ev.get("accounting_document_display_number"), (
            "the synchronous חשבונית capture must carry the real Morning document number"
        )
