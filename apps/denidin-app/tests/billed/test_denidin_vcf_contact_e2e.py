"""
E2E Tests (Feature 030): Godfather shares a WhatsApp contact card (vCard) and DeniDin
proposes adding that person as a Morning client - real webhook, real OpenAI Responses API,
real Morning MCP server, real Morning sandbox.

Flow (entry point is the real Green API webhook, dispatched through the actual
@bot.router.message-decorated `handle_contact_message` - CONSTITUTION SS V):

    Green API contactMessage webhook (godfather sender)
      -> handle_contact_message (real router handler, not a direct internal call)
      -> WhatsAppMessage.from_notification (vCard framed into text_content)
      -> AIHandler.get_response
           -> client.responses.create (real OpenAI Responses API call)
              with the real Morning MCP server registered as a remote tool
      -> bot replies in Hebrew

This feature introduces NO new confirmation/approval mechanism: `add_client` is already in
AIHandler.APPROVAL_REQUIRED_MCP_TOOLS (Feature 026) - a shared vCard just becomes a new
*source* of the same conversational add_client flow typed text already triggers. Tests here
are genuinely two-turn (ASK then APPROVE), exactly like Feature 026's own add_client tests -
see `_send_turn_and_approve` (imported from test_denidin_morning_mcp_e2e).

**Test tier (Feature 029)**: real, text-only OpenAI calls (a vCard is plain text - no vision/
image call involved) -> `billed`, NOT `expensive`. Runs freely, no per-run approval needed, no
one-at-a-time restriction - see CLAUDE.md.

**Assumes the test environment is already up**: apps/morning-mcp-app must already be running
(./run_morning_mcp.sh) - see test_denidin_morning_mcp_e2e.py's module docstring for the full
prerequisite list; `denidin_app`/`live_morning_tunnel` (imported below) fail loudly, not
silently, if it isn't.

NO MOCKING anywhere.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from src.models.message import AIResponse
from tests.billed.denidin_mcp_e2e_helpers import create_real_notification, get_response
from tests.billed.test_denidin_morning_mcp_e2e import (  # noqa: F401
    GODFATHER_CHAT_ID,
    _calls_for,
    denidin_app,
    denidin_config,
    live_morning_tunnel,
)

logger = logging.getLogger(__name__)

_CONTACTS_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "contacts"


def _build_contact_webhook(chat_id: str, sender_name: str, display_name: str, vcard: str, message_id: str) -> dict:
    """Build a real Green API incomingMessageReceived webhook event dict for a contactMessage,
    per contracts/contactMessage.json's confirmed shape (Green API official docs)."""
    return {
        'typeWebhook': 'incomingMessageReceived',
        'timestamp': int(time.time()),
        'idMessage': message_id,
        'instanceData': {
            'idInstance': 7103000000,
            'wid': '972501234567@c.us',
            'typeInstance': 'whatsapp'
        },
        'senderData': {
            'chatId': chat_id,
            'sender': chat_id,
            'senderName': sender_name
        },
        'messageData': {
            'typeMessage': 'contactMessage',
            'contactMessageData': {
                'displayName': display_name,
                'vcard': vcard,
                'forwardingScore': 0,
                'isForwarded': False,
            }
        }
    }


def _send_contact_turn(
    chat_id: str, display_name: str, vcard: str, id_prefix: str
) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Send one real contact-card WhatsApp turn through the real router handler
    (handle_contact_message) and return (reply text, AIResponse with mcp_calls)."""
    from denidin import handle_contact_message

    notification = create_real_notification(_build_contact_webhook(
        chat_id=chat_id,
        sender_name="E2E Godfather",
        display_name=display_name,
        vcard=vcard,
        message_id=f"{id_prefix}_{int(datetime.now(timezone.utc).timestamp())}"
    ))
    handle_contact_message(notification)
    response = get_response(notification)

    import denidin
    ai_response = denidin.denidin_app.ai_handler.last_response

    if ai_response is not None:
        for call in ai_response.mcp_calls:
            logger.info(
                f"mcp_call: name={call['name']} error={call['error']!r} "
                f"arguments={call['arguments']!r} output={call['output']!r}"
            )
    logger.info(f"Bot response: {response}")

    return response, ai_response


def _send_text_turn(chat_id: str, text: str, id_prefix: str) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Send a plain typed-text follow-up turn (e.g. supplying a missing email, or an
    affirmative approval) through the normal text router."""
    from denidin import handle_text_message
    from tests.billed.denidin_mcp_e2e_helpers import build_text_webhook

    notification = create_real_notification(build_text_webhook(
        chat_id=chat_id,
        sender_name="E2E Godfather",
        text=text,
        message_id=f"{id_prefix}_{int(datetime.now(timezone.utc).timestamp())}"
    ))
    handle_text_message(notification)
    response = get_response(notification)

    import denidin
    ai_response = denidin.denidin_app.ai_handler.last_response
    return response, ai_response


def _load_vcard(filename: str) -> str:
    return (_CONTACTS_FIXTURES_DIR / filename).read_text(encoding="utf-8")


def _ledger_event_count_for_chat(denidin_app, chat_id: str) -> int:
    """Counts real persisted LedgerEvent files (data/events/*.json, Feature 033) for this
    chat_id - used as a before/after false-positive guard: a shared vCard's raw text goes
    through the exact same conversational AIHandler pipeline (and the same always-attached
    LEDGER_EVENT_TOOL) as any text message, so nothing structurally prevents the model from
    misreading contact-card fields as fee-agreement/bank-deposit content. Same
    before/after-count pattern as test_ledger_event_capture_e2e.py's ordinary-chatter guard."""
    storage_dir = denidin_app.ai_handler.ledger_event_manager.storage_dir
    count = 0
    for f in storage_dir.glob("*.json"):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("whatsapp_chat") == chat_id:
            count += 1
    return count


@pytest.mark.billed
def test_godfather_shares_contact_card_complete_requires_approval(denidin_app):
    """US1: a shared contact card with name+phone+email all present proposes add_client
    exactly like a typed request would - the existing Feature 026 approval gate must
    intercept the ASK turn (no add_client call yet), and only the APPROVE turn (an explicit
    Hebrew "כן") actually calls the tool.

    Uses the synthetic complete_card_dana_cohen.vcf fixture (the real captured fixture has
    no email - see US2 below for that case).
    """
    vcard = _load_vcard("complete_card_dana_cohen.vcf")
    ledger_count_before = _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID)

    ask_response, ask_ai_response = _send_contact_turn(
        chat_id=GODFATHER_CHAT_ID,
        display_name="Dana Cohen",
        vcard=vcard,
        id_prefix="E2E_VCF_COMPLETE_ASK",
    )

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ask_ai_response, "add_client"), (
        f"add_client executed on the ASK turn (from a shared contact card) before approval "
        f"was given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called on a raw vCard - contact-card fields "
        "(name/phone/email) must never be misread as fee-agreement/bank-deposit content"
    )

    response, ai_response = _send_text_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_VCF_COMPLETE_APPROVE",
    )

    add_calls = _calls_for(ai_response, "add_client")
    assert add_calls and all(c["error"] is None for c in add_calls), (
        f"add_client did not succeed on the APPROVE turn after a complete contact card: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    assert any("Dana Cohen" in (c["arguments"] or "") for c in add_calls), (
        f"add_client was not called with the vCard's name 'Dana Cohen': {add_calls!r}"
    )


@pytest.mark.billed
def test_godfather_shares_contact_card_missing_email_is_asked_for(denidin_app):
    """US2: the real fixture (00005372-גיל ברטל .vcf) has no EMAIL field at all - the common
    case for real WhatsApp contact shares (per its own README). The bot must ask for the
    missing email before any add_client call or pending-approval state - inherits Feature
    026's REQ-CLIENT-012 "ask for what's missing" behavior unchanged.

    Once the email is supplied in a follow-up turn, the flow proceeds exactly as US1
    (confirmation -> approve -> creation).
    """
    vcard = _load_vcard("00005372-גיל ברטל .vcf")
    assert "EMAIL" not in vcard  # sanity: this fixture genuinely has no email
    ledger_count_before = _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID)

    ask_response, ask_ai_response = _send_contact_turn(
        chat_id=GODFATHER_CHAT_ID,
        display_name="גיל ברטל",
        vcard=vcard,
        id_prefix="E2E_VCF_NOEMAIL_ASK",
    )

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ask_ai_response, "add_client"), (
        f"add_client executed despite a missing email on the shared contact card: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    # "דוא"ל" (the formal Hebrew abbreviation for "דואר אלקטרוני") is an equally
    # correct answer the model gave for real (2026-08-02) that "מייל"/"אימייל"
    # alone didn't catch - "דוא" as a substring covers "דוא״ל"/"דואל"/"דוא'ל"
    # regardless of which quote-character renders the geresh.
    assert "מייל" in ask_response or "אימייל" in ask_response or "דוא" in ask_response, (
        f"Expected the bot to ask for the missing email, got: {ask_response!r}"
    )
    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called on a raw vCard - contact-card fields "
        "(name/phone/email) must never be misread as fee-agreement/bank-deposit content"
    )

    supply_response, supply_ai_response = _send_text_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="gil.bartal.qs@example.com",
        id_prefix="E2E_VCF_NOEMAIL_SUPPLY",
    )
    assert not _calls_for(supply_ai_response, "add_client"), (
        f"add_client executed immediately after supplying the email, without a confirmation "
        f"turn: {supply_ai_response.mcp_calls if supply_ai_response else None!r}"
    )

    approve_response, approve_ai_response = _send_text_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_VCF_NOEMAIL_APPROVE",
    )
    add_calls = _calls_for(approve_ai_response, "add_client")
    assert add_calls and all(c["error"] is None for c in add_calls), (
        f"add_client did not succeed after supplying the missing email and approving: "
        f"{approve_ai_response.mcp_calls if approve_ai_response else None!r}"
    )
