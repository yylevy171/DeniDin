"""Feature 098 acceptance - DeniDin asks for the client's ID before issuing a
tax invoice (305) or tax invoice/receipt (320) above the allocation threshold
(5,000 ₪ before VAT). UATs 1.1-3.5 of
specs/repo/features/098-mandatory-id-above-5000-nis/user-stories.md, plus the
two edge cases listed there.

Real webhook -> real router -> real OpenAI Responses API -> real Morning MCP
server over its live dev tunnel -> real Morning sandbox. NO MOCKING.

App-wall (denidin_mcp_e2e_helpers.py's module docstring): this file never
imports morning-mcp-app code and never calls Morning's REST API. Every
"Then, in Morning" check is a further, natural WhatsApp turn asking DeniDin to
read Morning directly, verified from that turn's real mcp_call output. For the
same reason UAT 1.3's open transaction account is created through DeniDin
(an approved create_transaction_account turn), not "directly in the sandbox".

@pytest.mark.billed. RUN STATUS: deferred (PM D-3) - run once Feature 063 has
merged, on the backbone, against a dev Morning-MCP rebuilt with Feature 098.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

import pytest

from src.managers.pending_approval_manager import BUTTON_ID_APPROVE
from tests.e2e_helpers import assert_no_errors_sent_to_user

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _is_genuine_document_creation,
    _is_real_approval_prompt,
    approval_buttons_on_screen,
    _random_seed_email,
    _seed_client,
    _send_button_tap,
    _send_turn,
    _send_turn_and_approve,
    _unique_client_name,
)

logger = logging.getLogger(__name__)

CHAT = GODFATHER_CHAT_ID
VALID_ID = "308253681"
QUALIFYING_TOOLS = ("create_invoice", "create_combo_document", "create_combo_document_as_reference")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _digits(text: Optional[str]) -> str:
    """Reply text with thousands separators removed, for amount checks."""
    return (text or "").replace(",", "")


def _pending():
    """The approval-buttons message on the chat's screen (063: the Backbone keeps no
    pending-approval record, so this is what a real user sees)."""
    return approval_buttons_on_screen(CHAT)


def _assert_nothing_issued(ai_response) -> None:
    for tool in QUALIFYING_TOOLS + ("update_client",):
        assert not _calls_for(ai_response, tool), (
            f"{tool} was called: {ai_response.mcp_calls if ai_response else None!r}"
        )


def _assert_plain_text_no_buttons(response: Optional[str]) -> None:
    assert response, "CRITICAL: no reply at all (silent drop)"
    assert _pending() is None, f"an approval (with buttons) is pending: {_pending()!r}"
    assert not _is_real_approval_prompt(response), f"reply is an approval prompt: {response!r}"


def _assert_asks_for_the_id(response, ai_response, client_name: str, amount: str) -> None:
    """UAT 1.1 Step 3: one plain-text reply naming the client and amount,
    saying the ID is needed for the allocation number above 5,000 ₪ before
    VAT, asking for it - and nothing created."""
    _assert_nothing_issued(ai_response)
    _assert_plain_text_no_buttons(response)
    assert client_name.split()[0] in response, f"client not named: {response!r}"
    assert amount in _digits(response), f"amount {amount} not stated: {response!r}"
    assert "ת.ז" in response or "ח.פ" in response or "תעודת זהות" in response, (
        f"does not ask for the client's ID: {response!r}"
    )
    assert "הקצאה" in response, f"does not mention the allocation number: {response!r}"
    assert "5000" in _digits(response), f"does not mention the 5,000 threshold: {response!r}"


def _seed_id_less_client(id_prefix: str) -> str:
    name, _, _ = _seed_client(CHAT, id_prefix)
    return name


def _seed_client_with_id(id_prefix: str) -> str:
    name = _unique_client_name()
    email = _random_seed_email()
    _seed_client(
        CHAT, id_prefix, name=name, email=email,
        text=f"תוסיף לקוח חדש בשם {name}, מייל {email}, טלפון 050-1234567, ח.פ {VALID_ID}",
    )
    return name


def _morning_tax_id(client_name: str, id_prefix: str) -> Optional[str]:
    """Ask DeniDin to read the client from Morning directly; return the
    tax_id from the real get_client_details output."""
    _, ai_response = _send_turn(
        CHAT,
        f"תבדוק ישירות במערכת החשבוניות את פרטי הלקוח {client_name}, כולל ת.ז / ח.פ.",
        id_prefix=f"{id_prefix}_VERIFY_CLIENT",
    )
    calls = [c for c in _calls_for(ai_response, "get_client_details") if c["output"]]
    assert calls, f"no get_client_details call: {ai_response.mcp_calls if ai_response else None!r}"
    return (json.loads(calls[-1]["output"]).get("client") or {}).get("tax_id") or None


def _morning_documents(client_name: str, id_prefix: str) -> List[dict]:
    """Ask DeniDin to list the client's documents from Morning directly;
    return the documents from the real list_invoices output."""
    _, ai_response = _send_turn(
        CHAT,
        f"תביא ישירות ממערכת החשבוניות את כל המסמכים של {client_name}.",
        id_prefix=f"{id_prefix}_VERIFY_DOCS",
    )
    calls = [c for c in _calls_for(ai_response, "list_invoices") if c["output"]]
    assert calls, f"no list_invoices call: {ai_response.mcp_calls if ai_response else None!r}"
    docs: List[dict] = []
    for call in calls:
        payload = json.loads(call["output"])
        if isinstance(payload, dict):
            docs.extend(payload.get("documents") or [])
    return docs


def _of_type(docs: List[dict], doc_type: int) -> List[dict]:
    return [d for d in docs if d.get("type") == doc_type]


def _ask_until_approval(text: str, id_prefix: str, tool_name: str):
    """Send `text`; if the model asks one clarifying question instead of
    proposing, answer "היום". Returns the turn that carries the approval."""
    response, ai_response = _send_turn(CHAT, text, id_prefix=f"{id_prefix}_ASK")
    assert not _calls_for(ai_response, tool_name), "tool executed before approval"
    if _pending() is None:
        response, ai_response = _send_turn(CHAT, "היום", id_prefix=f"{id_prefix}_CLARIFY")
        assert not _calls_for(ai_response, tool_name), "tool executed before approval"
    return response, ai_response


def _assert_buttons_for(tool_name: str) -> None:
    """An approval with yes/no buttons is on screen. Which write it approves is proven
    on the tap turn, which must run `tool_name` (the Backbone records no pending tool)."""
    assert _pending() is not None, f"expected an approval with buttons for {tool_name}, none on screen"


def _combo_request(client_name: str, amount: str = "12,000") -> str:
    return f'תוציא חשבונית מס קבלה ל{client_name} על {amount} ש"ח כולל מע"מ, שולם בהעברה בנקאית היום'


def _ask_combo_for_id_less_client(id_prefix: str):
    """UAT 1.1 Steps 1-3 - the shared opening of UATs 1.1 and 2.1-2.3."""
    client_name = _seed_id_less_client(id_prefix)
    response, ai_response = _send_turn(CHAT, _combo_request(client_name), id_prefix=f"{id_prefix}_ASK")
    _assert_asks_for_the_id(response, ai_response, client_name, "12000")
    return client_name


def _assert_document_issued_on_tap(tool_name: str, id_prefix: str):
    _assert_buttons_for(tool_name)
    response, ai_response = _send_button_tap(CHAT, BUTTON_ID_APPROVE, id_prefix=f"{id_prefix}_TAP")
    calls = _calls_for(ai_response, tool_name)
    assert calls and _is_genuine_document_creation(calls[0]), (
        f"{tool_name} did not create a document: {ai_response.mcp_calls if ai_response else None!r}"
    )
    assert response, "no confirmation sent"
    assert_no_errors_sent_to_user(CHAT)
    return json.loads(calls[0]["output"])


# ---------------------------------------------------------------------------
# User Story 1 - DeniDin asks for the ID first
# ---------------------------------------------------------------------------


@pytest.mark.billed
def test_uat_1_1_combo_above_threshold_asks_for_id(denidin_app):
    client_name = _ask_combo_for_id_less_client("E2E_098_UAT11")

    assert _morning_tax_id(client_name, "E2E_098_UAT11") is None
    assert _of_type(_morning_documents(client_name, "E2E_098_UAT11"), 320) == []


@pytest.mark.billed
def test_uat_1_2_tax_invoice_above_threshold_asks_for_id(denidin_app):
    client_name = _seed_id_less_client("E2E_098_UAT12")

    response, ai_response = _send_turn(
        CHAT, f'תוציא חשבונית מס ל{client_name} על 8,000 ש"ח לפני מע"מ', id_prefix="E2E_098_UAT12_ASK"
    )

    _assert_asks_for_the_id(response, ai_response, client_name, "8000")
    assert _morning_tax_id(client_name, "E2E_098_UAT12") is None
    assert _of_type(_morning_documents(client_name, "E2E_098_UAT12"), 305) == []


@pytest.mark.billed
def test_uat_1_3_closing_transaction_account_above_threshold_asks_for_id(denidin_app):
    client_name = _seed_id_less_client("E2E_098_UAT13")
    # Given: an open 10,000 ₪ transaction account (created through DeniDin - app-wall).
    _, (_, ta_ai) = _send_turn_and_approve(
        CHAT, f'תפתח חשבון עסקה ל{client_name} על 10,000 ש"ח לפני מע"מ', id_prefix="E2E_098_UAT13_TA"
    )
    ta_calls = _calls_for(ta_ai, "create_transaction_account")
    assert ta_calls and _is_genuine_document_creation(ta_calls[0]), (
        f"setup: transaction account not created: {ta_ai.mcp_calls if ta_ai else None!r}"
    )

    response, ai_response = _send_turn(
        CHAT, f"{client_name} שילם את החשבון עסקה במלואו, בהעברה בנקאית היום", id_prefix="E2E_098_UAT13_ASK"
    )

    _assert_nothing_issued(ai_response)
    _assert_plain_text_no_buttons(response)
    assert client_name.split()[0] in response, f"client not named: {response!r}"
    assert "ת.ז" in response or "ח.פ" in response or "תעודת זהות" in response, response
    assert "הקצאה" in response, response
    docs = _morning_documents(client_name, "E2E_098_UAT13")
    assert _of_type(docs, 320) == [], f"a 320 exists: {docs!r}"
    open_accounts = [d for d in _of_type(docs, 300) if d.get("status_code") == 0]
    assert open_accounts, f"the transaction account is no longer open: {docs!r}"


# ---------------------------------------------------------------------------
# User Story 2 - the User gives the ID and gets the document
# ---------------------------------------------------------------------------


@pytest.mark.billed
def test_uat_2_1_valid_id_saved_then_document_issued(denidin_app):
    client_name = _ask_combo_for_id_less_client("E2E_098_UAT21")

    # Step 4-5: the ID -> an approval, with buttons, to save it.
    response, ai_response = _send_turn(CHAT, VALID_ID, id_prefix="E2E_098_UAT21_ID")
    _assert_nothing_issued(ai_response)
    _assert_buttons_for("update_client")
    assert VALID_ID in (response or ""), f"approval does not show the ID: {response!r}"

    # Step 6-8: tap -> client updated -> an approval, with buttons, for the 320.
    response, ai_response = _send_button_tap(CHAT, BUTTON_ID_APPROVE, id_prefix="E2E_098_UAT21_TAP_ID")
    update_calls = _calls_for(ai_response, "update_client")
    assert update_calls and update_calls[0]["error"] is None, (
        f"update_client did not run cleanly: {ai_response.mcp_calls if ai_response else None!r}"
    )
    assert not any(_calls_for(ai_response, t) for t in QUALIFYING_TOOLS), "document issued without its own approval"

    # Step 9-11: tap -> the 320 is created, without the User restating it.
    document = _assert_document_issued_on_tap("create_combo_document", "E2E_098_UAT21_DOC")
    assert document.get("amount") == 12000, f"wrong amount: {document!r}"

    assert _morning_tax_id(client_name, "E2E_098_UAT21") == VALID_ID
    combos = _of_type(_morning_documents(client_name, "E2E_098_UAT21"), 320)
    assert len(combos) == 1 and combos[0].get("amount") == 12000, f"expected one 12,000 ₪ 320: {combos!r}"


@pytest.mark.billed
def test_uat_2_2_wrong_format_asks_again(denidin_app):
    client_name = _ask_combo_for_id_less_client("E2E_098_UAT22")

    response, ai_response = _send_turn(CHAT, "12345678", id_prefix="E2E_098_UAT22_ID")

    _assert_nothing_issued(ai_response)
    _assert_plain_text_no_buttons(response)
    assert "9" in response, f"does not say an ID is 9 digits: {response!r}"
    assert _morning_tax_id(client_name, "E2E_098_UAT22") is None
    assert _of_type(_morning_documents(client_name, "E2E_098_UAT22"), 320) == []


@pytest.mark.billed
def test_uat_2_3_user_declines(denidin_app):
    client_name = _ask_combo_for_id_less_client("E2E_098_UAT23")

    response, ai_response = _send_turn(CHAT, "עזוב, לא עכשיו", id_prefix="E2E_098_UAT23_NO")

    _assert_nothing_issued(ai_response)
    _assert_plain_text_no_buttons(response)
    assert _morning_tax_id(client_name, "E2E_098_UAT23") is None
    assert _of_type(_morning_documents(client_name, "E2E_098_UAT23"), 320) == []


# ---------------------------------------------------------------------------
# User Story 3 - nothing changes when the rule doesn't apply
# ---------------------------------------------------------------------------


def _assert_issued_without_id_question(text: str, tool_name: str, id_prefix: str) -> dict:
    response, _ = _ask_until_approval(text, id_prefix, tool_name)
    assert "הקצאה" not in (response or ""), f"asked about the allocation number: {response!r}"
    return _assert_document_issued_on_tap(tool_name, id_prefix)


@pytest.mark.billed
def test_uat_3_1_below_threshold(denidin_app):
    client_name = _seed_id_less_client("E2E_098_UAT31")
    document = _assert_issued_without_id_question(
        f'חשבונית מס קבלה ל{client_name} על 4,500 ש"ח כולל מע"מ, שולם בהעברה היום',
        "create_combo_document", "E2E_098_UAT31",
    )
    assert document.get("amount") == 4500


@pytest.mark.billed
def test_uat_3_2_exactly_the_threshold_before_vat(denidin_app):
    """5,900 including 18% VAT is exactly 5,000 before VAT - not above it."""
    client_name = _seed_id_less_client("E2E_098_UAT32")
    document = _assert_issued_without_id_question(
        _combo_request(client_name, "5,900"), "create_combo_document", "E2E_098_UAT32"
    )
    assert document.get("amount") == 5900


@pytest.mark.billed
def test_uat_3_3_client_already_has_an_id(denidin_app):
    client_name = _seed_client_with_id("E2E_098_UAT33")
    document = _assert_issued_without_id_question(
        _combo_request(client_name), "create_combo_document", "E2E_098_UAT33"
    )
    assert document.get("amount") == 12000


@pytest.mark.billed
def test_uat_3_4_transaction_account_is_out_of_scope(denidin_app):
    client_name = _seed_id_less_client("E2E_098_UAT34")
    _assert_issued_without_id_question(
        f'חשבון עסקה ל{client_name} על 12,000 ש"ח', "create_transaction_account", "E2E_098_UAT34"
    )


@pytest.mark.billed
def test_uat_3_5_just_above_the_threshold_asks_for_id(denidin_app):
    client_name = _seed_id_less_client("E2E_098_UAT35")

    response, ai_response = _send_turn(
        CHAT, f'חשבונית מס ל{client_name} על 5,001 ש"ח לפני מע"מ', id_prefix="E2E_098_UAT35_ASK"
    )

    _assert_asks_for_the_id(response, ai_response, client_name, "5001")
    assert _of_type(_morning_documents(client_name, "E2E_098_UAT35"), 305) == []


# ---------------------------------------------------------------------------
# Edge cases (user-stories.md "Edge Cases")
# ---------------------------------------------------------------------------


@pytest.mark.billed
def test_edge_id_given_in_the_original_request(denidin_app):
    """The ID comes with the request -> straight to approving the ID save."""
    client_name = _seed_id_less_client("E2E_098_EDGE_ID")

    response, ai_response = _send_turn(
        CHAT, _combo_request(client_name) + f", ח.פ {VALID_ID}", id_prefix="E2E_098_EDGE_ID_ASK"
    )

    _assert_nothing_issued(ai_response)
    _assert_buttons_for("update_client")
    assert VALID_ID in (response or ""), response


@pytest.mark.billed
def test_edge_id_saved_but_document_declined(denidin_app):
    """Approve saving the ID, decline the document -> ID saved, no document."""
    from src.managers.pending_approval_manager import BUTTON_ID_DECLINE

    client_name = _ask_combo_for_id_less_client("E2E_098_EDGE_DECLINE")
    _send_turn(CHAT, VALID_ID, id_prefix="E2E_098_EDGE_DECLINE_ID")
    _assert_buttons_for("update_client")
    _, ai_response = _send_button_tap(CHAT, BUTTON_ID_APPROVE, id_prefix="E2E_098_EDGE_DECLINE_TAP_ID")
    assert _calls_for(ai_response, "update_client"), "the ID-save tap did not run update_client"
    _assert_buttons_for("create_combo_document")

    _, ai_response = _send_button_tap(CHAT, BUTTON_ID_DECLINE, id_prefix="E2E_098_EDGE_DECLINE_TAP_DOC")

    assert not _calls_for(ai_response, "create_combo_document")
    assert _morning_tax_id(client_name, "E2E_098_EDGE_DECLINE") == VALID_ID
    assert _of_type(_morning_documents(client_name, "E2E_098_EDGE_DECLINE"), 320) == []
