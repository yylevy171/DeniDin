"""
Shared helpers for Feature 018 real-API E2E tests: DeniDin (WhatsApp bot) driving
the already-running Morning MCP server over its already-open ngrok tunnel via
OpenAI's Responses API.

These tests assume the test environment is already up:
- apps/morning-mcp-app is already running (./run_morning_mcp.sh) against sandbox
  credentials, with feature_flags.enable_mcp_server=true, mcp.auth_token set, and
  its ngrok tunnel already open (mcp.ngrok_authtoken configured).
- The shared status file (mcp.status_file in the Morning app's config, matching
  mcp.morning_status_file in denidin-app's config) is therefore already populated
  with the live tunnel URL.
Tests do NOT start the Morning server, do NOT start ngrok, and do NOT write the
status file. If the environment is not actually up, `require_live_morning_tunnel`
fails immediately with a clear "no tunnel" message - it does not skip, and it
does not try to bring anything up itself.

App-wall (uncrossable, per explicit user instruction): denidin-app and
morning-mcp-app are two distinct apps that happen to share a repo. This module
never reads morning-mcp-app's config or any other file, and never imports its
code. The only things that connect the two apps are: (1) an out-of-band shared
bearer token, independently configured in each app's own config, and (2) the
shared status file (the documented, intentional integration contract of this
feature - the one deliberate crossing point, not a shortcut). Verification of
tool-call success is done via the real OpenAI Responses API's own `mcp_call`
output (exposed on AIResponse.mcp_calls - see src/handlers/ai_handler.py),
never via Morning's raw REST API or Morning's own credentials.

NO MOCKING anywhere: real webhook -> real router handler -> real OpenAI
Responses API -> real Morning MCP server, over the real tunnel.
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from whatsapp_chatbot_python import Notification

logger = logging.getLogger(__name__)

DENIDIN_APP_DIR = Path(__file__).resolve().parents[2]


class NoMorningTunnelError(Exception):
    """Raised when the shared status file reports no live Morning MCP tunnel.

    This means the test environment is not up (Morning server/ngrok tunnel not
    running) - the fix is to start apps/morning-mcp-app (./run_morning_mcp.sh),
    not to retry or mock around it.
    """


def require_live_morning_tunnel(status_file_path: Path, max_age_seconds: int = 0) -> str:
    """Read the shared status file and return the live Morning MCP server URL.

    Mirrors src.handlers.morning_mcp_locator.MorningMcpLocator's freshness logic,
    but FAILS LOUDLY instead of gracefully degrading - these E2E tests require a
    genuinely live environment, so "no tunnel" must surface as an immediate,
    clear test failure rather than a silent skip or a retried startup attempt.

    Raises:
        NoMorningTunnelError: if the status file is missing, unparseable, missing
            `server_url`, or stale (per `max_age_seconds`).
    """
    if not status_file_path.exists():
        raise NoMorningTunnelError(
            f"NO TUNNEL: status file not found at {status_file_path}. "
            f"Start apps/morning-mcp-app first (./run_morning_mcp.sh) with "
            f"feature_flags.enable_mcp_server=true and mcp.ngrok_authtoken configured."
        )

    try:
        status = json.loads(status_file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NoMorningTunnelError(f"NO TUNNEL: failed to read/parse status file {status_file_path}: {exc}") from exc

    if status.get("status") != "running":
        raise NoMorningTunnelError(
            f"NO TUNNEL: Morning MCP server reports status={status.get('status')!r} "
            f"(not 'running') at {status_file_path}. Start apps/morning-mcp-app "
            f"(./run_morning_mcp.sh) with feature_flags.enable_mcp_server=true and "
            f"mcp.ngrok_authtoken configured."
        )

    server_url = status.get("server_url")
    if not server_url:
        raise NoMorningTunnelError(f"NO TUNNEL: status file {status_file_path} has no 'server_url'.")

    if max_age_seconds > 0:
        updated_at_raw = status.get("updated_at")
        if not updated_at_raw:
            raise NoMorningTunnelError(f"NO TUNNEL: status file {status_file_path} missing 'updated_at'.")
        age_seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(updated_at_raw)).total_seconds()
        if age_seconds > max_age_seconds:
            raise NoMorningTunnelError(
                f"NO TUNNEL: status file {status_file_path} is stale "
                f"({age_seconds:.0f}s old, max {max_age_seconds}s) - is the Morning server/tunnel still running?"
            )

    return server_url


def build_text_webhook(chat_id: str, sender_name: str, text: str, message_id: str) -> dict:
    """Build a real Green API incomingMessageReceived webhook event dict for a
    textMessage, matching the shape used by this repo's existing E2E tests."""
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
            'typeMessage': 'textMessage',
            'textMessageData': {
                'textMessage': text
            }
        }
    }


def create_real_notification(event_dict: dict) -> Notification:
    """Create a real SDK Notification object (no mocking), tracking answer() calls."""
    notification = Notification.__new__(Notification)
    notification.event = event_dict
    notification._test_sent_messages = []

    def track_answer(message):
        notification._test_sent_messages.append(message)
        logger.info(f"Would send to user: {message}")

    notification.answer = track_answer
    return notification


def get_response(notification: Notification) -> Optional[str]:
    return notification._test_sent_messages[0] if notification._test_sent_messages else None


# ============================================================================
# Feature 038 (2026-08-04): shared across all Morning-MCP billed E2E test
# modules - moved here from the former single test_denidin_morning_mcp_e2e.py
# (2094 lines, ~40 tests) when that file was split by topic into
# test_denidin_morning_invoice_creation_e2e.py,
# test_denidin_morning_client_management_e2e.py,
# test_denidin_morning_list_invoices_e2e.py, and
# test_denidin_morning_invoice_lifecycle_e2e.py - human-approved
# reorganization (T012/T013), no test logic changed, only location. The
# module-scoped `denidin_config`/`live_morning_tunnel`/`denidin_app`
# fixtures moved to this directory's conftest.py instead (auto-discovered
# by every test module below, no import needed).
# ============================================================================

from src.models.message import AIResponse  # noqa: E402

_DESCRIPTIONS = ("ייעוץ", "עיצוב", "פיתוח", "תחזוקה", "הדרכה", "ליווי עסקי")

# Diverse, realistic Israeli first/family name pools (565/591 unique entries
# spanning Hebrew/Jewish, Arab-Israeli, Russian/FSU, Ethiopian-Israeli, and
# Western/English-transliterated names) - the ONLY source for every randomly-
# generated client name across every test module in this directory. Real
# people's names, never synthetic markers - a synthetic numeric marker
# defeats the point of testing real name-search behavior, and 2026-08-03
# confirmed again (test_godfather_add_client_requires_approval's neighbors)
# that ad-hoc per-test `f"...{random.randint(...)}"` name generation keeps
# creeping back in despite this pool existing for exactly this purpose - use
# this pool, not a new one-off generator, whenever a test needs a random
# client name.
_NAMES_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_names(filename: str) -> List[str]:
    path = _NAMES_DATA_DIR / filename
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


_HEBREW_FIRST_NAMES = _load_names("hebrew_first_names.txt")
_HEBREW_FAMILY_NAMES = _load_names("hebrew_family_names.txt")

# Known real Hebrew male/chaser (with/without optional vowel letter) first-
# name spelling-variant pairs - NOT randomly generated, since random name
# selection can't produce a genuine spelling-variant relationship on its own.
_HEBREW_NAME_SPELLING_VARIANTS = [
    ("דוד", "דויד"),   # David
    ("אהרן", "אהרון"),  # Aharon
]


def _unique_client_name() -> str:
    """A unique-enough, operation-NEUTRAL client name for a freshly-seeded
    invoice or client record - a real first+family name drawn from
    _HEBREW_FIRST_NAMES x _HEBREW_FAMILY_NAMES (565 x 591 = ~334K
    combinations), never hex/digits/operation words.

    Real, billed failures shaped this - all still apply to the current
    real-name pool, not just the smaller Hebrew-word-stem pool this replaced
    (2026-08-03):
    - Embedding the operation word in the name (e.g. "...CANCEL...") leaked
      intent into a plain *create* request, so the model called what was then
      update_invoice_status(status="cancelled") on it (constitution mapped
      "בטל"/cancel-words to that status). (update_invoice_status has since
      been removed, feature 023; the equivalent risk today is leaked intent
      causing an unwanted create_credit_note call.)
    - A hex/random-number suffix got mistaken by the model for the invoice's
      actual id, causing it to call update_invoice_status with the wrong id
      instead of the real UUID from the preceding create_invoice output -
      never use digits in a generated client name, anywhere in this suite.
    - A "חברת" (company) business-entity prefix (spec 020 test run,
      2026-07-23) caused the model to strip it when re-referencing the same
      client by name a few turns later ("חברת אוריון זהב" -> "אוריון זהב" in
      the list_invoices call), which then failed to match in Morning's
      search - real client names in this app's actual usage never carry a
      generic "חברת"/"בע\"מ" business-entity prefix anyway, so the name
      generated here shouldn't either.
    - A composed stem+qualifier name risked an adjective-like qualifier word
      being read as descriptive rather than part of the proper name (2026-
      07-28: "אומגא ותיק" -> "אומגא" dropped on re-reference, breaking a
      later lookup) - moot now that names are real first+family name pairs,
      not composed Hebrew-word stems, but the underlying lesson (don't make
      the model guess what's part of the name) still applies.

    NOTE: "דורית אשכנזי" (bugfix-014's fixed, specially-seeded ground-truth
    client - see its own comment in test_denidin_morning_list_invoices_e2e.py)
    must never be producible here - verified "דורית" is not in
    _HEBREW_FIRST_NAMES, so no combination of this pool can ever collide
    with it.
    """
    return f"{random.choice(_HEBREW_FIRST_NAMES)} {random.choice(_HEBREW_FAMILY_NAMES)}"


def _random_amount() -> int:
    """A varied, non-round amount - avoids the exact repeated shape
    (same amount every call) that has been observed to trigger the model
    fabricating a plausible-looking success reply instead of actually
    calling create_invoice. Kept strictly under 100 NIS - a deliberately
    small, consistent range for sandbox test documents."""
    return random.randint(10, 99)


def _random_description() -> str:
    return random.choice(_DESCRIPTIONS)


def _random_seed_email() -> str:
    """A unique, always-valid email for seeding a client via add_client
    (mandatory since Feature 026's rework - see REQ-CLIENT-012)."""
    return f"e2e-client-{random.randint(100000, 999999)}@example.com"


_SEED_PHONE = "050-1234567"  # a plausible, always-valid Israeli mobile number

GODFATHER_CHAT_ID = "972500000018@c.us"  # Feature 018 E2E test godfather identity
CLIENT_ROLE_CHAT_ID = "972500000019@c.us"  # Feature 026 US5 - defaults to Role.CLIENT (not godfather/admin/blocked)
BLOCKED_ROLE_CHAT_ID = "972500000020@c.us"  # Feature 026 US5 - added to denidin_config's blocked_phones in conftest.py


def _send_turn(chat_id: str, text: str, id_prefix: str) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Send one real WhatsApp turn through the real router handler and return
    (reply text, AIResponse with mcp_calls) for inspection."""
    from denidin import handle_text_message

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

    if ai_response is not None:
        for call in ai_response.mcp_calls:
            logger.info(
                f"mcp_call: name={call['name']} error={call['error']!r} "
                f"arguments={call['arguments']!r} output={call['output']!r}"
            )
    logger.info(f"Bot response: {response}")

    return response, ai_response


def _calls_for(ai_response: Optional[AIResponse], tool_name: str) -> List[dict]:
    if ai_response is None:
        return []
    return [c for c in ai_response.mcp_calls if c["name"] == tool_name]


def _send_turn_and_approve(
    chat_id: str, text: str, id_prefix: str, approval_text: str = "כן"
) -> Tuple[Tuple[Optional[str], Optional[AIResponse]], Tuple[Optional[str], Optional[AIResponse]]]:
    """Send a turn expected to trigger a pending MCP document-creation
    approval (any of create_invoice/create_transaction_account/
    create_combo_document/create_credit_note/create_receipt/
    close_transaction_account - Feature 022), then send a second turn with a
    Hebrew affirmative to approve it.

    Returns ((ask_response, ask_ai_response), (approve_response, approve_ai_response))
    - callers typically assert on the ASK turn that nothing executed yet, and
    on the APPROVE turn (the one carrying the real mcp_call) for the actual
    outcome.
    """
    ask_result = _send_turn(chat_id, text, id_prefix=f"{id_prefix}_ASK")
    approve_result = _send_turn(chat_id, approval_text, id_prefix=f"{id_prefix}_APPROVE")
    return ask_result, approve_result


def _send_turn_and_decline(
    chat_id: str, text: str, id_prefix: str, decline_text: str = "לא"
) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Send a turn expected to trigger a pending MCP document-creation
    approval, then decline it. Returns the DECLINE turn's (response,
    ai_response) - the tool must never have executed."""
    _send_turn(chat_id, text, id_prefix=f"{id_prefix}_ASK")
    return _send_turn(chat_id, decline_text, id_prefix=f"{id_prefix}_DECLINE")


# Tests do not retry for most tools: each prompt is a single, natural,
# non-technical message, and the model is expected to call the right tool
# immediately. Ambiguity that a real production conversation would resolve
# across turns (date year) is instead resolved by the runtime constitution's
# own date-anchor guidance - not by scripting a follow-up turn here.
#
# EXCEPTION (Feature 022, 2026-07-23; tool list updated for feature 023):
# every document-creating tool (create_invoice, create_transaction_account,
# create_combo_document, create_credit_note, create_receipt,
# close_transaction_account) creates a Morning document when it executes (an
# invoice, a linked Receipt, a linked combo document, or a linked Credit
# Invoice - there is no "status change" that isn't also document creation;
# update_invoice_status, which used to be one more tool in this list, was
# removed entirely by feature 023), so all of them require an explicit
# approval turn before they execute. Tests exercising any of these tools use
# `_send_turn_and_approve`/`_send_turn_and_decline` instead of a bare
# `_send_turn`, and are genuinely two-turn.
