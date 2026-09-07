"""Feature 069 — Phase 11 acceptance (in-conversation Morning create), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING.

US2: when the operator has DeniDin create a Morning document in-conversation, the
resulting `חשבונית` ledger event is captured **synchronously** that turn (spec
US2/US3), against the exact resolved client, carrying the real Morning document
number — and NO VAT clarifying question is asked (a type-320 combo document
carries VAT by definition).

The manifest is built at runtime from what the test actually asked for + what the
`create_combo_document` call returned, then run through the same exhaustive
per-field checker as every other Feature 069 acceptance scenario.

Run:
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_morning_create_billed.py::<node>"
"""
from __future__ import annotations

import time

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _seed_client,
    _send_turn,
)
from tests.billed._ledger_069_acceptance import (
    assert_ledger_event_matches_manifest,
    ledger_events_for_chat,
    session_id_for_chat,
)
from tests.billed._ledger_069_post_turn_base import (
    reset_069_chat,  # noqa: F401 - autouse fixture, imported to register in this module
)

_CREATE_TOOLS = (
    "create_combo_document", "create_invoice", "create_transaction_account",
    "create_credit_note", "create_receipt",
)

_GEN = {"generated": "non_empty"}
_NULL = {"null": True}


def _us2_manifest(*, amount: str) -> dict:
    """Exhaustive per-field manifest for the synchronous `חשבונית` capture.
    `client_name` is `$client` (the resolved seeded client); `amount` is what the
    operator asked for; the Morning-sourced fields (`event_subtype` = the type
    name, `accounting_document_display_number`, `txn_date`) are asserted present
    and well-shaped, not against a value the test can't know up front."""
    return {
        "files": "single",
        "shared_fields": {
            "event_id":            {"generated": "event_id"},
            "event_datetime":      {"generated": "event_datetime"},
            "source_type":         {"tested": "חשבונית"},
            "event_subtype":       _GEN,
            "client_name":         {"tested": "$client"},
            "payer_name":          _NULL,
            "description":         {"free_text": True},
            "amount":              {"tested": amount},
            # Synchronous capture goes the FLAT path (no accounting_document_json
            # blob): the model maps "שולם היום" → today's date. Format-checked, not
            # value-pinned (ISO vs DD/MM/YYYY normalisation on persist).
            "txn_date":            {"generated": "date"},
            "reference":           _NULL,
            "reference_hint":      _NULL,
            "agreement_id":        _NULL,
            "component_id":        _NULL,
            "component_label":     _NULL,
            "trigger_condition":   _NULL,
            "percent":             _NULL,
            "percent_base":        _NULL,
            "hours":               _NULL,
            "hourly_rate":         _NULL,
            "vat_status":          {"tested": "כולל"},
            "split_partner":       _NULL,
            "split_percent":       _NULL,
            "bank_number":         _NULL,
            "bank_branch":         _NULL,
            "bank_account":        _NULL,
            "accounting_document_display_number": _GEN,
            # The recognition tool schema marks every other accounting_document_*
            # field OPTIONAL ("from the response, if present"). A freshly created
            # combo document's create response carries only the display number —
            # observed None for all four on a real in-conversation create
            # (run 2026-09-06). If a future run legitimately populates one, that
            # is the signal to reclassify it, not a mechanism bug.
            "accounting_document_status":         _NULL,
            "accounting_document_status_code":    _NULL,
            "accounting_document_status_label":   _NULL,
            "accounting_document_payment_method": _NULL,
            "session_id":          {"generated": "session_id"},
            "message_id":          {"generated": "message_id"},
            "captured_at":         {"generated": "captured_at"},
            "schema_version":      {"generated": "schema_version"},
        },
    }


@pytest.mark.billed
class TestLedgerPostTurnCaptureMorningCreate:

    def test_us2_morning_create_is_captured_synchronously(self, denidin_app):
        """A type-320 `create_combo_document` in-conversation → exactly one
        `חשבונית` ledger event that turn, against the exact resolved client, with
        the document's own Morning number — no VAT question anywhere."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US2", phone="0525550104")
        time.sleep(2)
        trigger_epoch = int(time.time())
        ask_reply, last_ai = _send_turn(
            GODFATHER_CHAT_ID,
            # payment method stated up front so the only follow-up is the approval
            # gate (the model legitimately asks for the method otherwise).
            f"תפיק ל{name} חשבונית מס-קבלה על סך 1,200 ש\"ח כולל מע\"מ עבור ייעוץ משפטי. "
            f"שולם היום בהעברה בנקאית.",
            "F069_US2_ASK",
            timestamp=trigger_epoch,
        )
        transcript = [ask_reply or ""]
        reply = ask_reply

        def _creates(ai):
            return [
                c for c in (ai.mcp_calls if ai else [])
                if c["name"] in _CREATE_TOOLS and c.get("error") is None
            ]

        create_calls = _creates(last_ai)
        for round_n in range(1, 6):
            if create_calls:
                break
            # answer whatever the model is waiting on. The approval gate wins
            # (it can mention the payment method while still asking כן/לא).
            _r = reply or ""
            if any(k in _r for k in ("כן או לא", "כן/לא", "אישור", "לאישור")):
                nxt = "כן"
            elif any(k in _r for k in ("אמצעי התשלום", "אמצעי תשלום", "איך שולם", "צורת התשלום")):
                nxt = "שולם בהעברה בנקאית"
            else:
                nxt = "כן"
            reply, last_ai = _send_turn(
                GODFATHER_CHAT_ID, nxt, f"F069_US2_APPROVE{round_n}",
                timestamp=trigger_epoch + round_n * 30,
            )
            transcript.append(reply or "")
            create_calls = _creates(last_ai)
        assert create_calls, (
            f"no successful Morning create call after the approval loop. "
            f"reply={reply!r} last_calls={last_ai.mcp_calls if last_ai else None!r}"
        )

        joined = " ".join(transcript)
        assert not any(k in joined for k in ("כולל מע\"מ או לא", "עם מע\"מ או בלי", "האם המחיר כולל")), (
            f"DeniDin must NOT ask a VAT clarifying question for a type-320 combo document; "
            f"transcript: {transcript!r}"
        )

        events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        invoice_events = [e for e in events if e["source_type"] == "חשבונית"]
        assert len(invoice_events) == 1, (
            f"exactly one חשבונית ledger event expected, got {len(invoice_events)}: {events!r}"
        )
        assert_ledger_event_matches_manifest(
            invoice_events, _us2_manifest(amount="1200"),
            trigger_epoch=trigger_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
            resolved_client_name=name,
        )
