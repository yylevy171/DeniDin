"""bugfix-071 acceptance - the VAT rule per document type, from the user's side.

Real webhook -> real OpenAI Responses API -> real Morning MCP server over its
real ngrok tunnel -> real Morning sandbox. NO MOCKING. @pytest.mark.billed.

The rule (approved 2026-10-05):
  - 305 / 300: VAT must be stated; "included" -> total = X, "not included" ->
    total = X + VAT.
  - 320 / 400 standalone: record money actually paid, VAT inside it - never
    asked; "not included" is a conflict the bot must ask about.
  - 400 against a 305, 320 closing a 300, 330: VAT comes from the original -
    never asked; "not included" is a conflict the bot must ask about.

Each scenario checks three things a user would: what the bot asks (or does not
ask), what the approval says about VAT, and what Morning actually stored -
read from the create tool's own output, which re-reads the new document from
Morning. Every reply also passes the shared approval-VAT check
(tests/e2e_helpers.assert_document_approval_states_vat, wired into _send_turn).

Amounts relative to the original document are out of scope (spec, 2026-10-05).
Amounts stay under 100, per this suite's sandbox convention.

Run one at a time:
    scripts/run_single_test.sh "tests/billed/test_bugfix_071_vat_rules_billed.py::<test>"
"""
from __future__ import annotations

import json
from typing import List, Optional, Tuple

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (  # noqa: F401
    GODFATHER_CHAT_ID,
    VAT_FROM_ORIGINAL,
    VAT_INCLUDED,
    VAT_NOT_INCLUDED,
    _calls_for,
    _is_real_approval_prompt,
    _random_description,
    _send_turn,
    _send_turn_and_approve,
    approval_vat_label,
    assert_document_approval_states_vat,
    assert_stored_receipt,
    assert_stored_vat,
    pick_existing_client,
    require_live_morning_tunnel,
)

pytestmark = pytest.mark.billed

AMOUNT = 50
GROSS = round(AMOUNT * 1.18, 2)  # 59.0 - AMOUNT "not included"
_VAT_WORDS = ('מע"מ', "מע״מ", "מעמ")
_MAX_CLARIFYING_TURNS = 2


# --------------------------------------------------------------------- helpers
def _asks_about_vat(reply: Optional[str]) -> bool:
    """Whether the bot's own words (not the approval block) ask about VAT."""
    text = reply or ""
    if "📋 לאישור:" in text:
        text = text[:text.rindex("📋 לאישור:")]
    return any(any(w in line for w in _VAT_WORDS) and "?" in line for line in text.splitlines())


def _seed_document(kind: str, vat_words: str, id_prefix: str) -> Tuple[str, str]:
    """Create a fresh 305 ("חשבונית מס") or 300 ("חשבון עסקה") of AMOUNT with the
    VAT stated, through the real conversation. Returns (client_name, display_number)."""
    client_name = pick_existing_client()["name"]
    tool = {"חשבונית מס": "create_invoice", "חשבון עסקה": "create_transaction_account"}[kind]
    _, (_, ai_response) = _send_turn_and_approve(
        GODFATHER_CHAT_ID,
        f"תפיק {kind} ללקוח {client_name} על סך {AMOUNT} ₪ {vat_words}, עבור {_random_description()}",
        id_prefix=id_prefix,
    )
    calls = _calls_for(ai_response, tool)
    assert calls and calls[0]["error"] is None, (
        f"precondition: could not seed the {kind}: {ai_response.mcp_calls if ai_response else None!r}"
    )
    return client_name, str(json.loads(calls[0]["output"])["display_number"])


def _drive_to_approval(text: str, tool: str, id_prefix: str) -> Tuple[List[str], str, object]:
    """Send `text`, answer up to two clarifying questions with "היום" (the only
    thing a request may still lack here is the payment date), then approve.
    Returns (every bot reply before the approval turn, the approval text, the
    approving turn's AIResponse). `tool` must not run before the approval."""
    replies: List[str] = []
    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, text, id_prefix=f"{id_prefix}_ASK")
    replies.append(reply or "")
    for i in range(_MAX_CLARIFYING_TURNS):
        assert not _calls_for(ai_response, tool), f"{tool} ran before approval: {ai_response.mcp_calls!r}"
        if _is_real_approval_prompt(reply):
            break
        reply, ai_response = _send_turn(GODFATHER_CHAT_ID, "היום", id_prefix=f"{id_prefix}_CLARIFY{i}")
        replies.append(reply or "")
    assert not _calls_for(ai_response, tool), f"{tool} ran before approval: {ai_response.mcp_calls!r}"
    assert _is_real_approval_prompt(reply), f"never reached an approval; replies: {replies!r}"
    _, approve_ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix=f"{id_prefix}_APPROVE")
    return replies, reply, approve_ai_response


def _created(ai_response, tool: str) -> dict:
    calls = _calls_for(ai_response, tool)
    assert calls and calls[0]["error"] is None, (
        f"{tool} was not created after approval: {ai_response.mcp_calls if ai_response else None!r}"
    )
    return calls[0]


def _assert_conflict_is_asked(text: str, tools: Tuple[str, ...], id_prefix: str) -> str:
    """The user stated "not included" where it contradicts the document's VAT
    rule: nothing is created, nothing is put up for approval, and the bot asks
    what the user meant."""
    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, text, id_prefix=id_prefix)
    for tool in tools:
        assert not _calls_for(ai_response, tool), (
            f"a VAT conflict reached {tool}: {ai_response.mcp_calls if ai_response else None!r}"
        )
    assert approval_vat_label(reply) is None, (
        f"a VAT conflict was put up for approval instead of asked about: {reply!r}"
    )
    assert _asks_about_vat(reply), f"expected the bot to ask what was meant about VAT; it said: {reply!r}"
    return reply


# ------------------------------------------------------------------- 305 / 300
def test_305_vat_included_is_stored_with_vat_inside(denidin_app):
    """Scenario 1: "... 50 ₪ כולל מע״מ" -> no VAT question, the approval says
    כולל מע״מ, Morning stores total 50 with the VAT inside it."""
    client_name = pick_existing_client()["name"]
    (ask_reply, _), (_, ai_response) = _send_turn_and_approve(
        GODFATHER_CHAT_ID,
        f"תפיק חשבונית מס ללקוח {client_name} על סך {AMOUNT} ₪ כולל מע״מ, עבור {_random_description()}",
        id_prefix="BF071_S1",
    )
    assert not _asks_about_vat(ask_reply), f"VAT was stated; the bot asked anyway: {ask_reply!r}"
    assert_document_approval_states_vat(ask_reply, VAT_INCLUDED)
    assert_stored_vat(_created(ai_response, "create_invoice"), AMOUNT)


def test_305_vat_not_included_is_stored_with_vat_added(denidin_app):
    """Scenario 2: "... 50 ₪ לא כולל מע״מ" -> the approval says לא כולל מע״מ,
    Morning stores total 59 (50 + VAT)."""
    client_name = pick_existing_client()["name"]
    (ask_reply, _), (_, ai_response) = _send_turn_and_approve(
        GODFATHER_CHAT_ID,
        f"תפיק חשבונית מס ללקוח {client_name} על סך {AMOUNT} ₪ לא כולל מע״מ, עבור {_random_description()}",
        id_prefix="BF071_S2",
    )
    assert not _asks_about_vat(ask_reply), f"VAT was stated; the bot asked anyway: {ask_reply!r}"
    assert_document_approval_states_vat(ask_reply, VAT_NOT_INCLUDED)
    assert_stored_vat(_created(ai_response, "create_invoice"), GROSS)


# ------------------------------------------------------------ 320 / 400 alone
def test_320_standalone_not_included_is_asked_then_created_with_vat_inside(denidin_app):
    """Scenario 3: "X paid 50 ₪ today, not including VAT - issue a tax
    invoice/receipt" -> nothing is created; the bot asks what was actually paid.
    The user answers that 59 ₪ was paid -> the approval says כולל מע״מ and Morning
    stores a 320 of 59 with the VAT inside it."""
    client_name = pick_existing_client()["name"]
    description = _random_description()
    _assert_conflict_is_asked(
        f"{client_name} שילם היום {AMOUNT} ₪ לא כולל מע״מ, עבור {description}. תפיק חשבונית מס קבלה",
        ("create_combo_document",), id_prefix="BF071_S3_CONFLICT",
    )

    replies, approval, ai_response = _drive_to_approval(
        f"שולמו בפועל {GROSS:g} ₪, המע״מ כלול בסכום הזה. התשלום התקבל היום.",
        "create_combo_document", id_prefix="BF071_S3_RESOLVED",
    )
    assert not any(_asks_about_vat(r) for r in replies[1:]), f"asked about VAT again: {replies!r}"
    assert_document_approval_states_vat(approval, VAT_INCLUDED)
    assert_stored_vat(_created(ai_response, "create_combo_document"), GROSS)


def test_400_standalone_not_included_is_asked(denidin_app):
    """Scenario 4: "I received a 50 ₪ deposit from X today in cash, not
    including VAT - issue a receipt" -> nothing is created or put up for
    approval; the bot asks what was meant."""
    client_name = pick_existing_client()["name"]
    _assert_conflict_is_asked(
        f"קיבלתי היום מהלקוח {client_name} פיקדון של {AMOUNT} ₪ במזומן, לא כולל מע״מ. תפיק קבלה",
        ("create_receipt", "create_combo_document"), id_prefix="BF071_S4",
    )


# --------------------------------------------------- against an existing one
def test_400_against_a_305_takes_vat_from_the_invoice(denidin_app):
    """Scenario 5: given a 305 of 50 ₪ כולל מע״מ, "X paid invoice N today -
    issue a receipt" -> no VAT question at any turn, the approval says לפי
    המסמך המקורי, and the receipt records 50 with no VAT of its own."""
    client_name, number = _seed_document("חשבונית מס", "כולל מע״מ", "BF071_S5_SEED")
    replies, approval, ai_response = _drive_to_approval(
        f"{client_name} שילם היום את חשבונית מספר {number}. תפיק קבלה",
        "create_receipt", id_prefix="BF071_S5",
    )
    assert not any(_asks_about_vat(r) for r in replies), f"asked about VAT on a receipt: {replies!r}"
    assert_document_approval_states_vat(approval, VAT_FROM_ORIGINAL)
    assert_stored_receipt(_created(ai_response, "create_receipt"), AMOUNT)


def test_320_closing_a_not_included_300_takes_vat_from_it(denidin_app):
    """Scenario 6: given a 300 of 50 ₪ לא כולל מע״מ (59 with VAT), "mark
    transaction account N as paid, paid today" -> no VAT question, the approval
    says לפי המסמך המקורי, Morning stores a 320 of 59 with the VAT inside it."""
    _, number = _seed_document("חשבון עסקה", "לא כולל מע״מ", "BF071_S6_SEED")
    replies, approval, ai_response = _drive_to_approval(
        f"סמן את חשבון העסקה מספר {number} כשולם, התשלום התקבל היום",
        "create_combo_document_as_reference", id_prefix="BF071_S6",
    )
    assert not any(_asks_about_vat(r) for r in replies), f"asked about VAT on a closing: {replies!r}"
    assert_document_approval_states_vat(approval, VAT_FROM_ORIGINAL)
    assert_stored_vat(_created(ai_response, "create_combo_document_as_reference"), GROSS)


def test_320_closing_a_300_not_included_is_asked(denidin_app):
    """Scenario 7: the same 300, "mark it as paid today, not including VAT" ->
    nothing is created or put up for approval; the bot asks what was meant."""
    _, number = _seed_document("חשבון עסקה", "לא כולל מע״מ", "BF071_S7_SEED")
    _assert_conflict_is_asked(
        f"סמן את חשבון העסקה מספר {number} כשולם, התשלום התקבל היום, לא כולל מע״מ",
        ("create_combo_document_as_reference", "create_combo_document"), id_prefix="BF071_S7",
    )


def test_330_against_a_taxable_305_takes_vat_from_it(denidin_app):
    """Scenario 8: given a 305 of 50 ₪ לא כולל מע״מ (59 with VAT), "issue a
    credit note for invoice N" -> no VAT question, the approval says לפי המסמך
    המקורי, Morning stores a credit of 59 with the VAT inside it."""
    _, number = _seed_document("חשבונית מס", "לא כולל מע״מ", "BF071_S8_SEED")
    replies, approval, ai_response = _drive_to_approval(
        f"תפיק חשבונית זיכוי לחשבונית מספר {number}",
        "create_credit_note", id_prefix="BF071_S8",
    )
    assert not any(_asks_about_vat(r) for r in replies), f"asked about VAT on a credit note: {replies!r}"
    assert_document_approval_states_vat(approval, VAT_FROM_ORIGINAL)
    assert_stored_vat(_created(ai_response, "create_credit_note"), GROSS)


def test_330_not_included_is_asked(denidin_app):
    """Scenario 9: "issue a credit note for invoice N, not including VAT" ->
    nothing is created or put up for approval; the bot asks what was meant."""
    _, number = _seed_document("חשבונית מס", "לא כולל מע״מ", "BF071_S9_SEED")
    _assert_conflict_is_asked(
        f"תפיק חשבונית זיכוי לחשבונית מספר {number}, לא כולל מע״מ",
        ("create_credit_note",), id_prefix="BF071_S9",
    )
