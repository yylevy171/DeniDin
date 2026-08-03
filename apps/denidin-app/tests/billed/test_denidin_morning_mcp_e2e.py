"""
E2E Tests (Feature 018): Godfather manages Morning invoices via natural WhatsApp
conversation - real webhook, real OpenAI Responses API, real Morning MCP server,
real Morning sandbox.

Flow (entry point is the real Green API webhook, dispatched through the actual
@bot.router.message-decorated `handle_text_message` - CONSTITUTION §V):

    Green API textMessage webhook (godfather sender)
      -> handle_text_message (real router handler, not a direct internal call)
      -> WhatsAppHandler.process_notification
      -> AIHandler.get_response
           -> client.responses.create (real OpenAI Responses API call)
              with the real Morning MCP server registered as a remote tool
              (reached over its already-open ngrok tunnel, bearer-authenticated)
      -> bot replies in Hebrew

**Prompts portray a real, non-technical user (2026-07-14 decision)**: the user
never knows about tools, parameter names, or internal ids (Morning documentId
GUIDs) - only casual references a person would actually use (a client's name,
a date, "the invoice for X"). Whatever normalization/resolution this requires
(mapping "88 שח" to amount=88, resolving "the invoice for יוסי" to a real
invoice_id via list_invoices, asking for missing required fields and waiting
for the reply) is the runtime constitution's job, not the test's - see
data/constitution/runtime_constitution.md's "Understanding invoicing requests"
section.

**Two-tier turn behavior (Feature 022, 2026-07-23; extended by Feature 023,
2026-07-30 and Feature 026, 2026-07-30 - supersedes the prior 2026-07-15
"tests do not retry across turns" decision)**: every document-creating tool
(`create_invoice`, `create_transaction_account`, `create_combo_document`,
`create_credit_note`, `create_receipt`, `close_transaction_account`), plus
`add_client`/`update_client` (Feature 026), now requires explicit human
approval before it actually executes - there is no "status change"
independent of a document (marking paid issues a linked Receipt or combo
document, cancelling issues a linked Credit Invoice; both are document
creation - feature 023 removed the separate `update_invoice_status` tool
entirely, so "mark as paid"/"cancel" phrasing now dispatches directly to one
of these same tools), and creating or changing a client record is the same
category of real, persisted write. Tests exercising any of these tools are
genuinely two-turn: the first turn triggers a pending approval (an
`mcp_approval_request`, not yet executed), and a second turn sends an
explicit Hebrew affirmative ("כן"/"אישור"/"בסדר") to approve it before
asserting on the resulting `mcp_call` - see `_send_turn_and_approve` below.
Every other tool (`list_invoices`, `get_invoice_details`,
`get_financial_summary`, `download_invoice_pdf`, `list_clients`,
`get_client_details` - all in `NO_APPROVAL_MCP_TOOLS`, read-only) remains
single-turn: date resolution via the constitution's year anchor still
happens within one shot, and non-mutating actions still execute immediately
with no approval wait. `add_client` was moved OUT of this bucket by Feature
026 - a real behavior reversal from how it worked before (see
`test_godfather_add_client_requires_approval` below, the CONSTITUTION §VIII
flagged exception for this rewrite).

**Invoice amount/description are randomized per run (2026-07-15 decision)**:
a real, observed failure mode is the model fabricating a plausible-looking
"success" reply (invoice number, fake link) instead of actually calling
`create_invoice`, when the conversation history already contains one or more
near-identical prior create_invoice turns (same amount, same description
shape) - see `_random_amount`/`_random_description` below. Varying these
values on every call reduces the repetition that triggers this pattern
completion; `src/handlers/ai_handler.py` also logs a WARNING
("Possible hallucinated invoicing confirmation") whenever a reply reads like
a state-changing confirmation with no matching `mcp_call`, as a production
detection safety net (not a behavior change).

RBAC and the memory system are always on (no feature flags, 2026-07-14) -
session memory is what makes these natural multi-turn conversations work
correctly (the model actually remembers the prior turn, not just an id smuggled
into the prompt text).

**Assumes the test environment is already up**: apps/morning-mcp-app must
already be running (./run_morning_mcp.sh) against sandbox credentials, with
feature_flags.enable_mcp_server=true, mcp.auth_token set to the SAME value as
this app's own config.test.json mcp.morning_auth_token, and its ngrok tunnel
already open. This test does NOT start the Morning server or ngrok - if the
shared status file shows no live tunnel, the test fails immediately with a
clear "NO TUNNEL" message. Whenever apps/morning-mcp-app changes, restart it
(./stop_morning_mcp.sh && ./run_morning_mcp.sh) before retrying - Python does
not hot-reload (see CLAUDE.md).

**Uses config/config.test.json exclusively** (both apps use their own test
config during testing) - never config/config.json.

**App-wall**: this test never reads morning-mcp-app's config or any other file,
and never imports its code. Verification of tool-call success uses the real
OpenAI Responses API's own `mcp_call` output, exposed on
`AIHandler.last_response.mcp_calls` (see src/handlers/ai_handler.py) - not
Morning's raw REST API, and not Morning's credentials.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run.
Per CLAUDE.md/CONSTITUTION §VII: human approval is required before every single
run of this test, run alone (never as part of a batch), read logs/test_logs/
before re-running, and only re-run after a confident fix. Never re-run a test
yourself once it has actually been billed (reached OpenAI) without fresh
explicit approval - see CLAUDE.md.
"""
from __future__ import annotations

import json
import logging
import random
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from src.models.config import AppConfiguration
from src.models.message import AIResponse
from .denidin_mcp_e2e_helpers import (
    DENIDIN_APP_DIR,
    NoMorningTunnelError,
    build_text_webhook,
    create_real_notification,
    get_response,
    require_live_morning_tunnel,
)

logger = logging.getLogger(__name__)

_DESCRIPTIONS = ("ייעוץ", "עיצוב", "פיתוח", "תחזוקה", "הדרכה", "ליווי עסקי")

# Diverse, realistic Israeli first/family name pools (565/591 unique entries
# spanning Hebrew/Jewish, Arab-Israeli, Russian/FSU, Ethiopian-Israeli, and
# Western/English-transliterated names) - the ONLY source for every randomly-
# generated client name in this file (and in test_denidin_morning_document_
# creation_e2e.py, which imports _unique_client_name from here). Real people's
# names, never synthetic markers - a synthetic numeric marker defeats the
# point of testing real name-search behavior, and 2026-08-03 confirmed again
# (test_godfather_add_client_requires_approval's neighbors) that ad-hoc
# per-test `f"...{random.randint(...)}"` name generation keeps creeping back
# in despite this pool existing for exactly this purpose - use this pool, not
# a new one-off generator, whenever a test needs a random client name.
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
    client - see its own comment further down this file) must never be
    producible here - verified "דורית" is not in _HEBREW_FIRST_NAMES, so no
    combination of this pool can ever collide with it.
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
BLOCKED_ROLE_CHAT_ID = "972500000020@c.us"  # Feature 026 US5 - added to denidin_config's blocked_phones below


@pytest.fixture(scope="module")
def denidin_config():
    """Load denidin-app's own TEST config (real secrets, gitignored) - never
    config.json. Isolated to test_data, this test's godfather identity."""
    config_path = DENIDIN_APP_DIR / "config" / "config.test.json"
    if not config_path.exists():
        pytest.skip("config/config.test.json not found")

    config = AppConfiguration.from_file(str(config_path))
    config.validate()

    if not config.ai_api_key or config.ai_api_key.startswith("sk-test"):
        pytest.skip("No real ai_api_key configured in config/config.test.json")
    if not config.mcp or not config.mcp.get('morning_auth_token'):
        pytest.skip(
            "config/config.test.json has no mcp.morning_auth_token configured - "
            "it must match the already-running Morning server's own mcp.auth_token"
        )

    test_data_root = DENIDIN_APP_DIR / "test_data"
    config.data_root = str(test_data_root)
    sessions_dir = test_data_root / "sessions"
    config.memory['session']['storage_dir'] = str(sessions_dir)
    config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

    # Start every pytest invocation from a CLEAN session store (2026-07-15).
    # The godfather session is persisted to disk and is NOT reset between
    # separate `pytest` runs, so it accumulated dozens of turns across every
    # run today - a real, billed failure had the model load a 7400-token
    # history full of earlier "couldn't find" failures and just imitate that
    # pattern (replying "couldn't find" without even calling a tool) instead
    # of acting on the invoice it had just created one turn earlier. A real
    # user's conversation never carries a different run's history; clearing
    # here makes each invocation an independent conversation. Tests WITHIN one
    # invocation still share the session (the intended multi-turn "one long
    # chat" - create -> mark paid, etc. - is preserved); only cross-run
    # carryover is dropped.
    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)

    # AIHandler._load_constitution() now resolves against
    # constitution_config.base_dir (default 'config'), not data_root - the
    # constitution is shared config content, not per-environment data, so
    # config.test.json's un-overridden default already points straight at
    # the real apps/denidin-app/config/runtime_constitution.md. No mirroring
    # into test_data needed anymore (previously required because the old
    # data_root-relative resolution meant overriding data_root above would
    # otherwise find nothing here).

    config.godfather_phone = GODFATHER_CHAT_ID
    config.user_roles = {'admin_phones': [], 'blocked_phones': [BLOCKED_ROLE_CHAT_ID]}

    return config


@pytest.fixture(scope="module")
def live_morning_tunnel(denidin_config):
    """Fail immediately (not skip) if the Morning MCP server/tunnel isn't live."""
    status_file_path = Path(denidin_config.mcp['morning_status_file'])
    max_age = denidin_config.mcp.get('url_max_age_seconds', 0) or 0
    try:
        server_url = require_live_morning_tunnel(status_file_path, max_age)
    except NoMorningTunnelError as exc:
        pytest.fail(str(exc), pytrace=False)
    return server_url


@pytest.fixture(scope="module")
def denidin_app(denidin_config, live_morning_tunnel):
    """Initialize the full DeniDin app - NO MOCKING - against the live Morning tunnel."""
    import denidin

    config_dict = {
        'green_api_instance_id': denidin_config.green_api_instance_id,
        'green_api_token': denidin_config.green_api_token,
        'ai_api_key': denidin_config.ai_api_key,
        'ai_model': denidin_config.ai_model,
        'ai_vision_model': denidin_config.ai_vision_model,
        'ai_embedding_model': denidin_config.ai_embedding_model,
        'ai_reply_max_tokens': denidin_config.ai_reply_max_tokens,
        'log_level': denidin_config.log_level,
        'data_root': denidin_config.data_root,
        'feature_flags': denidin_config.feature_flags,
        'godfather_phone': denidin_config.godfather_phone,
        'memory': denidin_config.memory,
        'constitution_config': denidin_config.constitution_config,
        'user_roles': denidin_config.user_roles,
        'mcp': denidin_config.mcp,
    }
    # handle_text_message (the real @bot.router.message-decorated handler)
    # checks the module-level denidin.denidin_app global, not a local variable
    # - must assign it here, matching tests/billed/test_simple_text_e2e.py's
    # existing pattern, or the router handler treats the app as uninitialized.
    denidin.denidin_app = denidin.initialize_app(config_dict)
    return denidin.denidin_app


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


# ============================================================================
# create_invoice
# ============================================================================

@pytest.mark.billed
def test_godfather_creates_invoice_via_whatsapp(denidin_app):
    """Godfather asks for a new invoice the way a real, non-technical person
    would - client name, amount, and what it's for, all in one message.
    Since create_invoice creates a document, it now requires explicit
    approval (Feature 022): the ASK turn must NOT execute it yet, and only
    the APPROVE turn (an explicit Hebrew "כן") actually calls the tool.

    Verification (independent signals, not the model's unverified claim alone):
    1. ASK turn: no create_invoice call yet.
    2. APPROVE turn: mcp_calls shows a create_invoice call with no error.
    3. The final reply contains an invoice link - the runtime constitution
       says create_invoice confirmations must always include one, unprompted,
       so this isn't a special ask in the test prompt.

    Uses a fresh unique client per run (2026-07-28) - this test used to
    create a new real invoice under the fixed "יוסי שמואלי" ground-truth
    client (see bugfix-014 tests below) on every single run, which is
    exactly what caused that client to organically grow from 6 to 14
    documents over time and break those other tests' pagination
    assumptions. Never hardcode a shared ground-truth client name here.
    """
    client_name = _unique_client_name()
    amount = _random_amount()
    description = _random_description()

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE",
    )

    assert not _calls_for(ask_ai_response, "create_invoice"), (
        f"create_invoice executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    create_calls = _calls_for(ai_response, "create_invoice")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_invoice via the remote MCP server, even "
        f"after approving. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_invoice call(s) reported an error: {create_calls}"
    )
    assert any(client_name in (c["arguments"] or "") for c in create_calls), (
        f"create_invoice was not called with the client name {client_name!r}: {create_calls!r}"
    )

    # The reply must actually carry a link, not just confirm success in the abstract.
    assert "http" in response, (
        f"Bot reply did not include an invoice link. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_declines_invoice_creation(denidin_app):
    """Godfather asks for a new invoice, then explicitly declines the pending
    approval (Feature 022) - create_invoice must never fire, and the bot's
    reply should read like an acknowledgment of the decline, not a fabricated
    success."""
    client_name = "דנה כהן"
    amount = _random_amount()
    description = _random_description()

    response, ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE_DECLINE",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "create_invoice"), (
        f"create_invoice executed despite an explicit decline: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    assert "http" not in response, (
        f"Bot reply looks like a fabricated success (contains a link) despite "
        f"the decline. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_ignores_pending_approval_with_unrelated_message(denidin_app):
    """Godfather triggers a pending create_invoice approval, then sends an
    unrelated message instead of yes/no (Feature 022). This must be treated
    as an implicit decline: create_invoice never fires, and the unrelated
    message gets a normal, on-topic reply (proves fall-through to a fresh
    turn works, and that the app doesn't get stuck)."""
    client_name = "משה לוי"
    amount = _random_amount()
    description = _random_description()

    _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE_UNRELATED_ASK",
    )
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="מה השעה עכשיו?",
        id_prefix="E2E_CREATE_UNRELATED_FOLLOWUP",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "create_invoice"), (
        f"create_invoice executed despite an unrelated follow-up message: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


@pytest.mark.billed
def test_godfather_approval_survives_intervening_small_talk(denidin_app):
    """An implicitly-declined pending approval (Feature 022) must not leave
    the app stuck: after unrelated small talk clears the pending request,
    the user can simply re-ask and complete the approval flow normally."""
    client_name = "רותי אברהם"
    amount = _random_amount()
    description = _random_description()
    request_text = f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}"

    _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_SMALLTALK_ASK1",
    )
    _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="איזה מזג אוויר יש היום?",
        id_prefix="E2E_SMALLTALK_INTERRUPT",
    )

    # Re-issue the original request and approve normally this time.
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_SMALLTALK_RETRY",
    )
    create_calls = _calls_for(ai_response, "create_invoice")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert create_calls and create_calls[0]["error"] is None, (
        f"Re-issued create_invoice request did not succeed after an "
        f"intervening, implicitly-declined pending approval: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


@pytest.mark.billed
def test_godfather_add_client_requires_approval(denidin_app):
    """🚨 CONSTITUTION §VIII flagged exception (spec.md Clarifications round 1,
    explicitly human-approved): replaces test_godfather_add_client_still_
    single_turn's regression guard. add_client now creates a real, persisted
    client record - Feature 026 moves it into APPROVAL_REQUIRED_MCP_TOOLS,
    reversing its prior single-turn behavior.

    Verification (independent signals, not the model's unverified claim
    alone):
    1. ASK turn: add_client must NOT execute yet.
    2. APPROVE turn: mcp_calls shows an add_client call with no error.
    3. A follow-up get_client_details turn (same test, real WhatsApp
       round-trip) confirms the client was actually created and its phone
       number persisted in normalized Israeli dashed format
       (REQ-CLIENT-016/017), same standard as the sandbox-level
       test_add_client_tool_normalizes_and_persists_phone test.
    """
    client_name = _unique_client_name()
    seed_email = _random_seed_email()
    raw_phone = "+972501234567"  # international input - must normalize on read-back

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {raw_phone}",
        id_prefix="E2E_ADD_CLIENT_APPROVE",
    )

    assert not _calls_for(ask_ai_response, "add_client"), (
        f"add_client executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    add_calls = _calls_for(ai_response, "add_client")
    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert add_calls and add_calls[0]["error"] is None, (
        f"add_client did not succeed on the APPROVE turn: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )

    # Search-index lag (research.md Decision 8) - cost-free local sleep,
    # cheaper than retrying a whole billed conversational turn.
    time.sleep(3)

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_ADD_CLIENT_VERIFY",
    )
    detail_calls = _calls_for(details_ai_response, "get_client_details")

    # Asserts the FINAL user-facing reply is correct and meaningful - NOT
    # that every intermediate get_client_details attempt succeeded. A real
    # run (2026-08-03) showed the model can genuinely recover from its own
    # mistakes within one turn (e.g. a wrong argument casing on one attempt)
    # via a retry or list_clients fallback - exactly the resilience you want
    # from a real assistant, not a bug. What actually matters - and what
    # this checks, deterministically - is whether the user got the client's
    # REAL data back: the normalized phone number appearing in the reply is
    # airtight proof of a genuinely correct answer, since a generic "not
    # found"/failure reply could never accidentally contain it.
    if detail_calls and any(c["error"] is not None for c in detail_calls):
        logger.warning(
            f"get_client_details had at least one failed attempt this turn "
            f"before the final reply was produced - model self-corrected, "
            f"not asserted on here, but worth eyeballing if this recurs: "
            f"{detail_calls!r}"
        )
    assert detail_calls, (
        f"Model never invoked get_client_details when verifying the newly "
        f"created client: "
        f"{details_ai_response.mcp_calls if details_ai_response else None!r}"
    )
    assert "050-1234567" in details_response, (
        f"Expected the normalized Israeli phone format in the follow-up "
        f"details reply, got: {details_response!r}"
    )


@pytest.mark.billed
def test_godfather_add_client_missing_field_is_asked_for(denidin_app):
    """Omitting email or phone must make the model ask for it, never call
    add_client with a guessed/blank value (runtime_constitution.md's
    "add_client needs name, email, AND phone" guidance, added by Feature
    026's T015)."""
    client_name = _unique_client_name()

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}",
        id_prefix="E2E_ADD_CLIENT_MISSING",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "add_client"), (
        f"add_client executed despite missing email/phone - should have "
        f"asked for the missing field(s) instead: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


@pytest.mark.billed
def test_godfather_add_client_rejects_malformed_email(denidin_app):
    """A malformed email must never result in a fabricated success. Two
    acceptable outcomes (asserted on whichever actually happens, not assumed
    in advance): either the model recognizes the malformed address itself
    and asks for a valid one without ever calling add_client (no pending
    approval at all), or it calls add_client anyway, the pending approval is
    granted, and the tool's own _validate_email rejection (ValueError ->
    friendly error, tools.py) surfaces as a real error on that mcp_call - not
    a fabricated "created" confirmation."""
    client_name = _unique_client_name()

    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל not-an-email, טלפון {_SEED_PHONE}",
        id_prefix="E2E_ADD_CLIENT_BADEMAIL_ASK",
    )
    ask_add_calls = _calls_for(ask_ai_response, "add_client")

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"

    if not ask_add_calls:
        # Model itself declined to call the tool with an invalid email - no
        # pending approval was ever created, nothing further to check.
        return

    # Model called add_client anyway (approval gate fires on tool name only,
    # not argument validity - research.md Decision 7) - approve it and
    # confirm the malformed email surfaces as a real error.
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_ADD_CLIENT_BADEMAIL_APPROVE",
    )
    add_calls = _calls_for(ai_response, "add_client")
    assert add_calls, (
        f"Pending add_client approval never resolved into an actual "
        f"mcp_call after approving. "
        f"mcp_calls: {ai_response.mcp_calls if ai_response else None!r}"
    )
    assert any(c["error"] is not None for c in add_calls), (
        f"Expected the malformed email to surface as an error on the "
        f"add_client call, got: {add_calls}"
    )


@pytest.mark.billed
def test_godfather_declines_add_client(denidin_app):
    """Godfather asks to add a client, then explicitly declines the pending
    approval - add_client must never fire, and the bot's reply should read
    like an acknowledgment of the decline, not a fabricated success (mirrors
    test_godfather_declines_invoice_creation's pattern)."""
    client_name = _unique_client_name()
    seed_email = _random_seed_email()

    response, ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_ADD_CLIENT_DECLINE",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "add_client"), (
        f"add_client executed despite an explicit decline: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


# ============================================================================
# list_clients (Feature 026, US1)
# ============================================================================


@pytest.mark.billed
def test_godfather_lists_clients_via_whatsapp(denidin_app):
    """Godfather asks who their clients are - read-only, no approval wait
    (list_clients is in NO_APPROVAL_MCP_TOOLS, same bucket as add_client was
    before Feature 026 moved add_client out of it).

    The real sandbox's client count keeps growing (production accounts can
    have hundreds - research.md Decision 11/12) - a bare, unfiltered request
    may now legitimately hit the "too many, narrow your search" branch
    instead of listing the seeded name directly. The assertion below adapts
    to whichever is actually true (read straight from the tool's own real
    output), rather than assuming either outcome in advance."""
    client_name = _unique_client_name()
    seed_email = _random_seed_email()

    _, (add_response, add_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_LIST_CLIENTS_SEED",
    )
    seed_calls = _calls_for(add_ai_response, "add_client")
    assert seed_calls, (
        f"Could not seed a client for the list_clients test. "
        f"mcp_calls: {add_ai_response.mcp_calls if add_ai_response else None!r}. "
        f"Reply: {add_response!r}"
    )

    # The sandbox's search index lags briefly after a write (research.md
    # Decision 8) - a single local sleep here costs nothing, unlike retrying
    # a whole billed conversational turn.
    time.sleep(3)

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="מי הלקוחות שלי?",
        id_prefix="E2E_LIST_CLIENTS",
    )
    list_calls = _calls_for(ai_response, "list_clients")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"Model never invoked list_clients via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in list_calls), (
        f"list_clients call(s) reported an error: {list_calls}"
    )

    tool_output = list_calls[0]["output"]
    if "יותר מדי" in tool_output or "צמצם" in tool_output:
        # Real client count currently exceeds the display cap - correct,
        # intended behavior is to report the real total and ask to narrow,
        # not to list the seeded name among hundreds of others.
        assert re.search(r"\d{2,}", tool_output), (
            f"Expected a real (2+ digit) total in the too-many response: {tool_output!r}"
        )
    else:
        assert client_name in response, (
            f"Expected the just-seeded client {client_name!r} in the reply: {response!r}"
        )


# ============================================================================
# get_client_details (Feature 026, US2)
# ============================================================================


@pytest.mark.billed
def test_godfather_gets_client_details_via_whatsapp(denidin_app):
    """Godfather asks for a specific client's details by name - read-only,
    no approval wait (get_client_details is in NO_APPROVAL_MCP_TOOLS)."""
    client_name = _unique_client_name()
    seed_email = _random_seed_email()

    _, (add_response, add_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_CLIENT_DETAILS_SEED",
    )
    seed_calls = _calls_for(add_ai_response, "add_client")
    assert seed_calls, (
        f"Could not seed a client for the get_client_details test. "
        f"mcp_calls: {add_ai_response.mcp_calls if add_ai_response else None!r}. "
        f"Reply: {add_response!r}"
    )

    # Search-index lag (research.md Decision 8) - cost-free local sleep.
    time.sleep(3)

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_CLIENT_DETAILS",
    )
    detail_calls = _calls_for(ai_response, "get_client_details")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert detail_calls, (
        f"Model never invoked get_client_details via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    # Asserts the FINAL user-facing reply is correct and meaningful - NOT that
    # every intermediate mcp_call was error-free. A real run (2026-08-03)
    # showed the model can genuinely recover from its own mistakes within one
    # turn (a wrong argument casing on one attempt, a Hebrew geresh vs. plain-
    # apostrophe character mismatch causing another attempt to miss) via a
    # list_clients fallback - exactly the resilience you want from a real
    # assistant, not a bug. Penalizing that by requiring every attempt to
    # succeed would fail a turn that actually worked correctly for the real
    # user. What actually matters - and what this checks, deterministically -
    # is whether the user got the client's REAL data back: requiring BOTH the
    # exact seeded name AND the exact seeded email to appear is airtight proof
    # of a genuinely correct answer, since a generic "not found"/failure reply
    # could never accidentally contain a randomly-generated real email address.
    assert client_name in response, (
        f"Expected the client's own name {client_name!r} in the reply: {response!r}"
    )
    assert seed_email in response, (
        f"Expected the client's own email {seed_email!r} in the reply (proves "
        f"the correct record was actually retrieved, not a name echoed back "
        f"or a failure message): {response!r}"
    )


@pytest.mark.billed
def test_godfather_gets_client_details_not_found_via_whatsapp(denidin_app):
    """Asking about a client that doesn't exist gets a friendly reply, not a
    crash or a fabricated answer.

    Real failure (2026-08-02): the fixture name used to be an f-string reading
    "לקוח לא קיים {random}" - literally "client doesn't exist" in Hebrew, a
    natural-language STATEMENT, not obviously a proper name, plus a trailing
    number of ambiguous role (part of the name vs. a separate client id). The
    model asked for clarification instead of calling get_client_details -
    a reasonable reaction to a genuinely confusing fixture, not a real bug.
    Fixed to a fixed, clearly name-shaped nonsense string that will never
    exist as a real client and reads unambiguously as a name."""
    nonexistent_name = "לילילי לאלאלא"

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {nonexistent_name}",
        id_prefix="E2E_CLIENT_DETAILS_NOTFOUND",
    )
    detail_calls = _calls_for(ai_response, "get_client_details")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert detail_calls, (
        f"Model never invoked get_client_details via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    # Same principle as the other get_client_details tests: the final reply
    # is what matters, not whether every intermediate attempt was error-free
    # (see 2026-08-03 notes on those tests for the real self-correction
    # pattern this accounts for). For THIS test specifically, "correct" means
    # a genuine not-found answer, not a fabricated one - checking for "לא
    # נמצא" (not found) is deterministic and distinguishes a real answer from
    # a silent failure or a hallucinated client record.
    assert "לא נמצא" in response, (
        f"Expected a genuine 'not found' reply for a nonexistent client, "
        f"got: {response!r}"
    )


# ============================================================================
# update_client (Feature 026, US4)
# ============================================================================


@pytest.mark.billed
def test_godfather_updates_client_via_whatsapp(denidin_app):
    """update_client is approval-gated (T020), same as add_client. Verifies:
    1. ASK turn: update_client must NOT execute yet.
    2. APPROVE turn: mcp_calls shows an update_client call with no error.
    3. A follow-up get_client_details turn confirms only the intended field
       (phone) changed and round-tripped normalized - name/email untouched
       (research.md Decision 3's partial-payload guarantee, exercised here
       through the full real WhatsApp conversation, not just the sandbox
       tool call)."""
    client_name = _unique_client_name()
    seed_email = _random_seed_email()

    _, (seed_response, seed_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_UPDATE_CLIENT_SEED",
    )
    assert _calls_for(seed_ai_response, "add_client") and _calls_for(seed_ai_response, "add_client")[0]["error"] is None, (
        f"Could not seed a client for the update_client test. "
        f"mcp_calls: {seed_ai_response.mcp_calls if seed_ai_response else None!r}. "
        f"Reply: {seed_response!r}"
    )
    time.sleep(3)  # search-index lag (research.md Decision 8)

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תעדכן את הטלפון של {client_name} ל-0541234567",
        id_prefix="E2E_UPDATE_CLIENT",
    )

    assert not _calls_for(ask_ai_response, "update_client"), (
        f"update_client executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    update_calls = _calls_for(ai_response, "update_client")
    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert update_calls and update_calls[0]["error"] is None, (
        f"update_client did not succeed on the APPROVE turn: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )

    time.sleep(3)  # search-index lag (research.md Decision 8)

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_UPDATE_CLIENT_VERIFY",
    )
    detail_calls = _calls_for(details_ai_response, "get_client_details")

    # Same principle as the other get_client_details tests: the final reply
    # is what matters, not whether every intermediate attempt was error-free
    # (2026-08-03: a real run showed the model self-correcting a wrong
    # argument casing within the turn). The phone/email checks right below
    # are the real, deterministic proof of a correct answer.
    assert detail_calls, (
        f"Model never invoked get_client_details when verifying the update: "
        f"{details_ai_response.mcp_calls if details_ai_response else None!r}"
    )
    assert "054-1234567" in details_response, (
        f"Expected the updated, normalized phone in the follow-up details "
        f"reply, got: {details_response!r}"
    )
    assert seed_email.lower() in details_response.lower(), (
        f"Updating phone must not clobber the untouched email field "
        f"(research.md Decision 3): {details_response!r}"
    )


@pytest.mark.billed
def test_godfather_declines_client_update(denidin_app):
    """Godfather asks to update a client's phone, then explicitly declines -
    update_client must never fire, and a follow-up get_client_details call
    must show the original phone unchanged (mirrors
    test_godfather_declines_add_client's pattern)."""
    client_name = _unique_client_name()
    seed_email = _random_seed_email()

    _, (seed_response, seed_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_UPDATE_DECLINE_SEED",
    )
    assert _calls_for(seed_ai_response, "add_client") and _calls_for(seed_ai_response, "add_client")[0]["error"] is None, (
        f"Could not seed a client for the decline-update test. "
        f"mcp_calls: {seed_ai_response.mcp_calls if seed_ai_response else None!r}. "
        f"Reply: {seed_response!r}"
    )
    time.sleep(3)  # search-index lag (research.md Decision 8)

    response, ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תעדכן את הטלפון של {client_name} ל-0541234567",
        id_prefix="E2E_UPDATE_CLIENT_DECLINE",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "update_client"), (
        f"update_client executed despite an explicit decline: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_UPDATE_CLIENT_DECLINE_VERIFY",
    )
    assert "054-1234567" not in details_response, (
        f"Declined update must not have changed the phone number: "
        f"{details_response!r}"
    )
    assert _SEED_PHONE in details_response, (
        f"Expected the original, unchanged phone in the follow-up details "
        f"reply: {details_response!r}"
    )


@pytest.mark.billed
def test_godfather_update_client_ambiguous_name_creates_no_pending_approval(denidin_app):
    """When the name resolves to more than one candidate, the bot must list
    them and ask the user to disambiguate BEFORE any approval prompt is ever
    issued (research.md Decision 7's ordering concern - the OpenAI approval
    gate fires on tool name alone, not argument validity, so tools.py itself
    must refuse to proceed on ambiguous input). Proves this is actually
    enforced end-to-end, not just true in the unit/sandbox tests."""
    # A real family name as the per-run uniqueness marker (never a digit
    # marker - see _unique_client_name's docstring for why) - still avoids
    # colliding with a stale prior run's identical shared_stem, since it's
    # drawn from the same 591-entry pool as every other generated name here.
    unique_marker = random.choice(_HEBREW_FAMILY_NAMES)
    shared_stem = f"לקוח בדיקה דו-משמעי {unique_marker}"
    name_a = f"{shared_stem} א"
    name_b = f"{shared_stem} ב"

    _, (seed_a_response, seed_a_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {name_a}, מייל {_random_seed_email()}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_UPDATE_AMBIG_SEED_A",
    )
    _, (seed_b_response, seed_b_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {name_b}, מייל {_random_seed_email()}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_UPDATE_AMBIG_SEED_B",
    )
    assert _calls_for(seed_a_ai_response, "add_client") and _calls_for(seed_a_ai_response, "add_client")[0]["error"] is None, (
        f"Could not seed client A: {seed_a_response!r}"
    )
    assert _calls_for(seed_b_ai_response, "add_client") and _calls_for(seed_b_ai_response, "add_client")[0]["error"] is None, (
        f"Could not seed client B: {seed_b_response!r}"
    )
    time.sleep(3)  # search-index lag (research.md Decision 8)

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תעדכן את הטלפון של {shared_stem} ל-0541234567",
        id_prefix="E2E_UPDATE_CLIENT_AMBIGUOUS",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "update_client"), (
        f"update_client executed (or a pending approval was created) despite "
        f"an ambiguous name match - disambiguation must happen first: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )

    # Confirm no pending approval was left dangling: a follow-up "כן" must
    # NOT retroactively trigger an update_client call.
    followup_response, followup_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_UPDATE_CLIENT_AMBIGUOUS_FOLLOWUP",
    )
    assert not _calls_for(followup_ai_response, "update_client"), (
        f"An affirmative reply after an ambiguous update_client request "
        f"must not retroactively execute anything - no pending approval "
        f"should have existed: "
        f"{followup_ai_response.mcp_calls if followup_ai_response else None!r}"
    )


# ============================================================================
# Real-name search behavior (Feature 026 follow-up): pagination fix,
# strict-prefix-search retry, and non-exact-match disclosure
# ============================================================================


@pytest.mark.billed
def test_godfather_finds_client_via_hebrew_vowel_variant(denidin_app):
    """Morning's real name search is a strict token-prefix match with ZERO
    typo/fuzzy tolerance (confirmed live, research.md Decision 12) - it
    can't bridge Hebrew's optional-vowel-letter (male/chaser) spelling
    variants on its own. The model must compensate: if asking about a
    client by one spelling gets no results, retry using a common alternate
    Hebrew spelling before giving up (runtime_constitution.md's new
    "strict prefix match, not fuzzy" guidance)."""
    chaser_spelling, male_spelling = random.choice(_HEBREW_NAME_SPELLING_VARIANTS)
    family_name = random.choice(_HEBREW_FAMILY_NAMES)
    seed_name = f"{male_spelling} {family_name}"
    query_name = f"{chaser_spelling} {family_name}"
    seed_email = _random_seed_email()

    _, (seed_response, seed_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {seed_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_HEBREW_VARIANT_SEED",
    )
    assert _calls_for(seed_ai_response, "add_client") and _calls_for(seed_ai_response, "add_client")[0]["error"] is None, (
        f"Could not seed client: {seed_response!r}"
    )
    time.sleep(3)  # search-index lag (research.md Decision 8)

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {query_name}",
        id_prefix="E2E_HEBREW_VARIANT_QUERY",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert seed_name in response, (
        f"Expected the model to find {seed_name!r} despite being asked "
        f"about the alternate spelling {query_name!r} - got: {response!r}"
    )


@pytest.mark.billed
def test_godfather_get_client_details_discloses_first_name_prefix_match(denidin_app):
    """When get_client_details resolves to exactly one client via a
    partial/prefix reference (not the literal stored name), the reply must
    explicitly disclose which client was found - never silently proceed as
    if the reference were certain."""
    first_name = random.choice(_HEBREW_FIRST_NAMES)
    family_name = random.choice(_HEBREW_FAMILY_NAMES)
    full_name = f"{first_name} {family_name}"
    # Only a prefix of the first name, alone - Morning's phrase-prefix search
    # only allows the LAST word of a query to be partial (confirmed live),
    # so a truncated first name followed by the full family name would not
    # match at all; querying with just the truncated first name (a single,
    # standalone word) does.
    first_name_prefix = first_name[: max(2, len(first_name) - 2)]
    seed_email = _random_seed_email()

    _, (seed_response, seed_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {full_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_DISCLOSE_FIRSTNAME_SEED",
    )
    assert _calls_for(seed_ai_response, "add_client") and _calls_for(seed_ai_response, "add_client")[0]["error"] is None, (
        f"Could not seed client: {seed_response!r}"
    )
    time.sleep(3)

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {first_name_prefix}",
        id_prefix="E2E_DISCLOSE_FIRSTNAME_QUERY",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert full_name in response, (
        f"Expected the reply to disclose the full resolved client name "
        f"{full_name!r} (not just the prefix {first_name_prefix!r} the "
        f"user typed) - got: {response!r}"
    )


@pytest.mark.billed
def test_godfather_update_client_discloses_family_name_prefix_match_before_approval(denidin_app):
    """Same disclosure requirement, but for update_client via a truncated
    FAMILY name reference (standalone, confirmed live to match) - and since
    approval happens BEFORE the tool executes/resolves (research.md
    Decision 7), the model itself must resolve and name the real client in
    the pending-approval prompt, not just echo back the partial wording."""
    first_name = random.choice(_HEBREW_FIRST_NAMES)
    family_name = random.choice(_HEBREW_FAMILY_NAMES)
    full_name = f"{first_name} {family_name}"
    family_name_prefix = family_name[: max(2, len(family_name) - 2)]
    seed_email = _random_seed_email()
    new_phone = "052-9876543"  # deliberately different from _SEED_PHONE, so a
        # real change is actually being requested

    _, (seed_response, seed_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {full_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_DISCLOSE_FAMILYNAME_SEED",
    )
    assert _calls_for(seed_ai_response, "add_client") and _calls_for(seed_ai_response, "add_client")[0]["error"] is None, (
        f"Could not seed client: {seed_response!r}"
    )
    time.sleep(3)

    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תעדכן את הטלפון של {family_name_prefix} ל-{new_phone}",
        id_prefix="E2E_DISCLOSE_FAMILYNAME_ASK",
    )

    assert not _calls_for(ask_ai_response, "update_client"), (
        f"update_client executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert full_name in ask_response, (
        f"Expected the PENDING-APPROVAL prompt itself to name the full "
        f"resolved client {full_name!r}, not just echo the partial "
        f"reference {family_name_prefix!r} - got: {ask_response!r}"
    )


# ============================================================================
# RBAC denial (Feature 026, US5 - safety net, no new code expected)
# ============================================================================


@pytest.mark.billed
def test_client_role_gets_no_client_management_tools(denidin_app):
    """A client-role sender (any phone not godfather/admin/blocked) asking
    about clients gets a normal reply with zero mcp_calls for any
    client-management tool - existing Feature 018 RBAC gating
    (MORNING_MCP_AUTHORIZED_ROLES = (GODFATHER, ADMIN) in ai_handler.py)
    already covers the whole Morning MCP tool set uniformly, so this is a
    safety net proving it, not new behavior."""
    response, ai_response = _send_turn(
        chat_id=CLIENT_ROLE_CHAT_ID,
        text="מי הלקוחות שלי?",
        id_prefix="E2E_RBAC_CLIENT_ROLE",
    )

    assert response is not None, "CRITICAL: client-role user got NO RESPONSE (silent drop)"
    for tool_name in ("list_clients", "get_client_details", "add_client", "update_client"):
        assert not _calls_for(ai_response, tool_name), (
            f"client-role user's request resulted in a {tool_name} mcp_call - "
            f"Morning tools must never be attached for this role: "
            f"{ai_response.mcp_calls if ai_response else None!r}"
        )


@pytest.mark.billed
def test_blocked_role_gets_no_client_management_tools(denidin_app):
    """A blocked-role sender asking about clients never even reaches
    AIHandler.get_response (create_request raises PermissionError first,
    per existing Feature 018 behavior) - the bot still replies (the generic
    fallback message, denidin.py's global exception handler), no crash, and
    no new AIResponse/mcp_calls is ever produced for this request."""
    import denidin

    last_response_before = denidin.denidin_app.ai_handler.last_response

    response, _ = _send_turn(
        chat_id=BLOCKED_ROLE_CHAT_ID,
        text="מי הלקוחות שלי?",
        id_prefix="E2E_RBAC_BLOCKED_ROLE",
    )

    assert response is not None, "CRITICAL: blocked-role user got NO RESPONSE (silent drop)"
    assert denidin.denidin_app.ai_handler.last_response is last_response_before, (
        "A blocked user's message must never reach AIHandler.get_response at "
        "all (rejected earlier, in create_request) - last_response changing "
        "means a real AI/tool call happened for a blocked user."
    )


# ============================================================================
# list_invoices
# ============================================================================

# Fixed, genuinely closed historical date in the Morning sandbox (verified
# free, no billing, 2026-07-13): exactly 6 real invoices exist for this date,
# well under list_invoices' 10-item display cap, so nothing is truncated, and
# being months in the past it will never gain more invoices (unlike "today").
KNOWN_FIXED_DATE = "2026-02-07"
KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE = ("60001", "60006")  # first and last of the 6


@pytest.mark.billed
def test_godfather_lists_invoices_via_whatsapp(denidin_app):
    """Godfather asks to see invoices from a specific day, the way a real
    person would - no year given (a real user rarely bothers), no format or
    field instructions, no mention of "internal ids" or any technical detail.
    Tests do not retry across turns, so the runtime constitution's date
    guidance must resolve the year correctly on this single shot - that's
    exactly what this test verifies.

    Verification is split two ways:
    1. Tool correctness: the mcp_call's own output (not the model's casual
       reply) must show the real, known ground truth - multiple distinct
       known invoice numbers, all 5 fields present (name, amount, date, id,
       status) - proving list_invoices itself returned complete, correct data
       for the right date.
    2. User experience: the actual reply the user received must exist and
       plausibly reflect that invoices were found (not required to repeat
       internal ids - a real user wouldn't want that, and the runtime
       constitution doesn't ask the model to include it in a casual reply).
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="תראה לי את כל החשבוניות ביום 7 בפברואר",
        id_prefix="E2E_LIST",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert list_calls, (
        f"Model never invoked list_invoices via the remote MCP server, even "
        f"after confirming the year. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in list_calls), (
        f"list_invoices call(s) reported an error: {list_calls}"
    )
    assert any(KNOWN_FIXED_DATE in (c["arguments"] or "") for c in list_calls), (
        f"list_invoices was not called with the resolved date ({KNOWN_FIXED_DATE}) "
        f"in its arguments: {list_calls!r}"
    )

    # Tool correctness: real, known ground truth in the tool's own output.
    combined_output = "\n".join(c["output"] or "" for c in list_calls)
    found_numbers = [n for n in KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE if n in combined_output]
    assert len(found_numbers) >= 2, (
        f"Expected at least 2 known invoice numbers {KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE} "
        f"in the tool output, found {found_numbers}. Tool output: {combined_output!r}"
    )
    assert "₪" in combined_output, f"Tool output missing amount field: {combined_output!r}"
    assert "מזהה" in combined_output, f"Tool output missing invoice id field: {combined_output!r}"
    assert "שולם" in combined_output, f"Tool output missing status field: {combined_output!r}"


# ============================================================================
# Analytical/aggregate questions (bugfix-011)
# ============================================================================

# Real, unprompted decline phrases observed live in dev (2026-07-20) when the
# model had the tool available but didn't call it - if the fix regresses,
# a reply matching any of these (with zero list_invoices/get_financial_summary
# calls) means the model is declining again instead of composing an answer.
_DECLINE_PHRASES_HE = ("זקוק לגישה", "אין לי גישה", "אין לי אפשרות לגשת", "לא ניתן לי גישה")


@pytest.mark.billed
def test_godfather_asks_analytical_debtor_question_via_whatsapp(denidin_app):
    """Godfather asks an analytical/aggregate question that no single Morning
    tool answers directly ("who owes me the most, and how much") - the model
    must recognize it has list_invoices available, call it (filtered to
    unpaid), and compute the ranking/answer itself from the raw results,
    rather than declining as if it lacks access (bugfix-011: this exact
    scenario, reproduced live in dev on 2026-07-20 - the model declined with
    "I need access to your invoice management system" despite the tool being
    attached and working, then correctly answered one turn later only after
    an explicit user nudge to "fetch the list and filter yourself").

    Verification (independent of the model's own claim):
    1. mcp_calls shows at least one list_invoices (or get_financial_summary)
       call with no error - proof it actually reached for the data.
    2. The final reply does not read like an access-decline (none of the
       real, previously-observed decline phrases appear).
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="תן לי שמות של ה-3 שחייבים לי הכי הרבה, וכמה כל אחד חייב",
        id_prefix="E2E_ANALYTICAL",
    )
    relevant_calls = _calls_for(ai_response, "list_invoices") + _calls_for(ai_response, "get_financial_summary")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert relevant_calls, (
        f"Model never invoked list_invoices or get_financial_summary to answer "
        f"an analytical question - it should fetch the raw data and compute the "
        f"answer itself rather than declining. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in relevant_calls), (
        f"Tool call(s) reported an error: {relevant_calls}"
    )
    assert not any(phrase in response for phrase in _DECLINE_PHRASES_HE), (
        f"Bot replied with an access-decline phrase despite having called a "
        f"tool - reply: {response!r}, mcp_calls: {ai_response.mcp_calls!r}"
    )


# ============================================================================
# bugfix-013: client-name garbling and unrequested date-range narrowing
# ============================================================================

# The exact real message from the live prod incident (logs/prod/denidin.log,
# 2026-07-20 20:11:34). The model transcribed the client name incorrectly
# ("זבית", missing ה) and silently added from_date/to_date=2026-07 despite no
# date being requested. Reused verbatim here rather than a paraphrase, per
# instruction, to reproduce with the exact input that misfired in production.
_ZEHAVIT_MESSAGE = "לקוחה בשם זהבית - בדוק לי כמה שילמה ומתי, תן לי הכל"
_ZEHAVIT_NAME = "זהבית"


@pytest.mark.billed
def test_zehavit_client_name_transcribed_exactly(denidin_app):
    """Reproduction test for bugfix-013's client-name-garbling finding.

    Root-cause investigation (read-only, 2026-07-21) found no app-level
    transformation of the client name anywhere between WhatsApp receipt and
    the MCP tool call - whatever the model generates as `client_name` is sent
    verbatim. There is nothing in this repo's code to fix for this specific
    finding, so this test does not guard a code fix; it is a standing,
    probabilistic reproduction check using the EXACT real message and name
    from the live incident log. It is expected to usually PASS (the garbling
    was not observed to be 100% reproducible - a later client name in the
    same live session transcribed correctly) - a passing result here does not
    mean the bug is fixed, only that it didn't reproduce this run. A FAILURE
    is the useful signal: it proves the garbling still happens with today's
    model/config, and is the trigger to reopen this finding.
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=_ZEHAVIT_MESSAGE,
        id_prefix="E2E_BUGFIX013_NAME",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"Model never invoked list_invoices for the Zehavit request. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )

    transcribed_names = []
    for call in list_calls:
        try:
            args = json.loads(call["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        transcribed_names.append(args.get("client_name"))

    assert any(name == _ZEHAVIT_NAME for name in transcribed_names), (
        f"Client name garbled: expected {_ZEHAVIT_NAME!r} to appear exactly "
        f"in at least one list_invoices call, got {transcribed_names!r} "
        f"(mcp_calls: {ai_response.mcp_calls!r})"
    )


@pytest.mark.billed
def test_no_date_mentioned_omits_date_range(denidin_app):
    """BDD failing test for bugfix-013's date-narrowing finding.

    Root cause (approved 2026-07-21): runtime_constitution.md already
    instructs 'add a from_date/to_date/status only if this request itself
    states one' - the model violated this existing rule live in prod,
    silently narrowing an unqualified 'give me everything' request to the
    current month. Test-gap analysis: the only existing list_invoices test
    (test_godfather_lists_invoices_via_whatsapp) always supplies an explicit
    date, so no existing test covers the 'no date mentioned at all' case -
    that gap is why this wasn't caught before reaching prod.

    Uses the exact real message from the incident (no date reference of any
    kind - only "תן לי הכל", give me everything). Expected to FAIL against
    the current constitution wording, and to pass once the wording is
    strengthened per the approved fix direction.
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=_ZEHAVIT_MESSAGE,
        id_prefix="E2E_BUGFIX013_DATE",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"Model never invoked list_invoices for the Zehavit request. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )

    for call in list_calls:
        try:
            args = json.loads(call["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        # The MCP tool schema always includes from_date/to_date keys in the
        # arguments JSON (null when unset), so absence-of-key is not a valid
        # check - the API supports the model either omitting the key entirely
        # or including it with a null value; both are acceptable, only a real
        # (non-null) date value indicates the unrequested-narrowing bug.
        assert args.get("from_date") is None and args.get("to_date") is None, (
            f"list_invoices was called with an unrequested date range despite "
            f"no date being mentioned in the request: {args!r} "
            f"(mcp_calls: {ai_response.mcp_calls!r})"
        )


# ============================================================================
# bugfix-014: "all payments" silently narrowed to status="paid"
# ============================================================================

# Real sandbox ground truth for this regression check. Originally used a
# fixed client "יוסי שמואלי" (verified live 2026-07-21, see
# specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md), but
# that client organically grew from 6 to 14 real documents over time because
# test_godfather_creates_invoice_via_whatsapp (above) kept creating new
# invoices under that same hardcoded name on every run - eventually pushing
# 4 of the 6 known invoices past list_invoices' 10-item page cap and making
# this test fail for a reason unrelated to bugfix-014 (2026-07-28).
# Replaced with a dedicated client, "דורית אשכנזי", never referenced by any
# other test/random-name generator (_unique_client_name's pool can never
# produce this name - "דורית" is not in _HEBREW_FIRST_NAMES, verified
# 2026-08-03), seeded once (2026-07-28) with exactly 6 tax
# invoices (type 305) - 4 left unpaid, 2 marked paid via a real linked
# Morning receipt (type 400) - mirroring the shape of the real Arian Regev
# incident (a request for "all payments" silently narrowed to a
# status="paid" filter, which would have dropped every unpaid invoice from
# the reply). The 2 receipt documents are NOT counted as invoices here -
# that's a separate, unrelated latent gap (list_invoices, unlike
# get_financial_summary, has no document-type filter and will return
# receipts alongside invoices; out of scope for this bugfix).
_GROUND_TRUTH_CLIENT_NAME = "דורית אשכנזי"
_GROUND_TRUTH_UNPAID_INVOICE_NUMBERS = ("50856", "50857", "50858", "50859")  # status=0
_GROUND_TRUTH_PAID_INVOICE_NUMBERS = ("50854", "50855")  # status=1, closed via a linked receipt

_GROUND_TRUTH_ALL_INVOICE_NUMBERS = _GROUND_TRUTH_UNPAID_INVOICE_NUMBERS + _GROUND_TRUTH_PAID_INVOICE_NUMBERS

# Ground truth for the double-counting regression (bugfix-014, Session 2):
# the true amount paid is 52 + 38 = 90 (invoices 50854 and 50855's own
# amounts). The receipts that closed them are the SAME money, not
# additional payments - a model that treats each receipt as an independent
# charge on top of its invoice arrives at 90 + 90 = 180 instead.
_GROUND_TRUTH_CORRECT_TOTAL_PAID = "90"
_GROUND_TRUTH_DOUBLE_COUNTED_TOTAL_PAID = "180"

_GROUND_TRUTH_FIRST_MESSAGE = f"תבדוק כל התשלומים מלקוח בשם {_GROUND_TRUTH_CLIENT_NAME}"
_GROUND_TRUTH_EXPLICIT_ALL_MESSAGE = f"תן לי את כל התשלומים שביצע {_GROUND_TRUTH_CLIENT_NAME}"


def _assert_full_picture(response, ai_response, id_prefix: str) -> None:
    """Shared ground-truth completeness check: a correct answer must reflect
    ALL 6 real invoices (4 unpaid + 2 paid via a linked receipt) - not a
    subset. This is the direct, data-level signature of the suspected bug
    (an unrequested status="paid" filter would silently drop the 4 unpaid
    invoices, leaving only the 2 paid ones)."""
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"[{id_prefix}] Model never invoked list_invoices for the {_GROUND_TRUTH_CLIENT_NAME} "
        f"request. mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )

    combined_output = "\n".join(c["output"] or "" for c in list_calls)
    found = [n for n in _GROUND_TRUTH_ALL_INVOICE_NUMBERS if n in combined_output]
    missing = [n for n in _GROUND_TRUTH_ALL_INVOICE_NUMBERS if n not in found]
    assert not missing, (
        f"[{id_prefix}] list_invoices did not return the complete picture: "
        f"expected all 6 known invoices {_GROUND_TRUTH_ALL_INVOICE_NUMBERS} "
        f"(4 unpaid: {_GROUND_TRUTH_UNPAID_INVOICE_NUMBERS}, 2 paid: "
        f"{_GROUND_TRUTH_PAID_INVOICE_NUMBERS}), missing {missing} - consistent with "
        f"an unrequested status filter silently dropping invoices. "
        f"Tool output: {combined_output!r}"
    )

    # Ground-truth correctness check for bugfix-014's double-counting bug:
    # the reply itself (what the user actually sees) must state the TRUE
    # total paid, never the double-counted figure that results from treating
    # a receipt as a separate charge from the invoice it closes.
    assert _GROUND_TRUTH_DOUBLE_COUNTED_TOTAL_PAID not in response, (
        f"[{id_prefix}] Bot reply states the double-counted total paid "
        f"({_GROUND_TRUTH_DOUBLE_COUNTED_TOTAL_PAID}) instead of the true total "
        f"({_GROUND_TRUTH_CORRECT_TOTAL_PAID}) - a receipt was counted as a separate "
        f"charge on top of the invoice it closes. Full reply: {response!r}"
    )
    assert _GROUND_TRUTH_CORRECT_TOTAL_PAID in response, (
        f"[{id_prefix}] Bot reply does not state the true total paid "
        f"({_GROUND_TRUTH_CORRECT_TOTAL_PAID}) anywhere - expected it to summarize "
        f"the correct, netted total. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_client_all_payments_gets_the_complete_picture(denidin_app):
    """Reproduction test for bugfix-014's strongest root-cause candidate:
    runtime_constitution.md's payment-word -> status="paid" rule
    over-generalizing from the noun "תשלומים" (payments, a request for scope)
    to a hard status filter.

    Root-cause investigation (read-only, 2026-07-21) is unconfirmed/not yet
    human-approved - this test exists to REPRODUCE the reported behavior
    against today's constitution wording, per BDD's "reproduce first" step,
    not to guard a fix. A correct answer to "check all payments from this
    client" is ALL 6 real invoices - 4 unpaid, 2 paid via a linked receipt -
    not just the paid ones. Expected to FAIL currently if the bug still
    reproduces (the unpaid invoices go missing from the result).

    Uses the real, mixed-status "דורית אשכנזי" sandbox client (see ground
    truth above) so the bug's effect on the data itself is directly
    observable, rather than only inspecting the tool call's raw arguments.
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=_GROUND_TRUTH_FIRST_MESSAGE,
        id_prefix="E2E_BUGFIX014_ASK",
    )
    _assert_full_picture(response, ai_response, "initial ask")


@pytest.mark.billed
def test_client_explicit_everything_request_gets_the_complete_picture(denidin_app):
    """Separate, standalone reproduction test for the "give me everything,
    no filtering" phrasing - sent as its own single-turn request, not
    programmatically chained after test_client_all_payments_gets_the_complete_picture's
    turn (each test function here sends exactly one message and asserts on
    it independently). Note: like every test in this module, the underlying
    WhatsApp session for GODFATHER_CHAT_ID is module-scoped, so this turn may
    still carry prior conversation history from earlier tests in the same
    pytest invocation - same as every other test in this file.

    Mirrors the real incident's second message (the user explicitly
    reiterating "I asked for ALL the payments" after feeling the first reply
    was incomplete), but as its own standalone request rather than a scripted
    follow-up - the model is expected to get the complete picture right on
    this phrasing alone, same ground truth and same assertion as the test
    above.
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=_GROUND_TRUTH_EXPLICIT_ALL_MESSAGE,
        id_prefix="E2E_BUGFIX014_EXPLICIT_ALL",
    )
    _assert_full_picture(response, ai_response, "explicit 'all, no filter' request")


# ============================================================================
# get_invoice_details
# ============================================================================

# One fully-known invoice from the fixed 2026-02-07 set (verified free, no
# billing) - referenced here by client name + date only, the way a real user
# would; the model must resolve the actual invoice_id itself.
KNOWN_INVOICE_NUMBER = "60006"
KNOWN_INVOICE_CLIENT = "Test Client DENIDIN_TEST_1770474207"
KNOWN_INVOICE_AMOUNT_IL = "123.45"
KNOWN_INVOICE_STATUS_HE = "שולם"  # paid


@pytest.mark.billed
def test_godfather_gets_invoice_details_via_whatsapp(denidin_app):
    """Godfather asks about a specific invoice by client name and date only -
    never an id. The model must resolve which invoice this is itself (via
    list_invoices and/or get_invoice_details) and reply with the real details.

    Verification checks the FINAL reply (what the user actually saw) against
    known ground truth - this is the tightest test in the suite (one specific,
    fully-known invoice, no pagination/date-range ambiguity) - and does not
    require a specific tool name to have been used, since a real user has no
    way to know or care which tool satisfies their request.
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=(
            f"מה הסטטוס והפרטים המלאים של החשבונית של {KNOWN_INVOICE_CLIENT} "
            f"מהשבעה בפברואר?"
        ),
        id_prefix="E2E_DETAILS",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    relevant_calls = _calls_for(ai_response, "list_invoices") + _calls_for(ai_response, "get_invoice_details")
    assert relevant_calls, (
        f"Model did not look up the invoice via any Morning MCP tool. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Bot reply: {response!r}"
    )
    assert all(c["error"] is None for c in relevant_calls), (
        f"Invoice lookup call(s) reported an error: {relevant_calls}"
    )

    # Exact-match verification against the one fully-known invoice.
    assert KNOWN_INVOICE_NUMBER in response, (
        f"Bot reply missing invoice number {KNOWN_INVOICE_NUMBER}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_AMOUNT_IL in response, (
        f"Bot reply missing amount {KNOWN_INVOICE_AMOUNT_IL}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_STATUS_HE in response, (
        f"Bot reply missing status {KNOWN_INVOICE_STATUS_HE!r}. Full reply: {response!r}"
    )


# ============================================================================
# Direct document-creation dispatch for status-change phrasing (feature 023)
# - "mark as paid"/"cancel" flows, formerly update_invoice_status (removed)
# ============================================================================

def _seed_fresh_invoice(client_name: str, amount: int, description: str) -> None:
    """Seed a fresh invoice via a real WhatsApp exchange (create_invoice now
    requires explicit approval - Feature 022) so the paid/cancel flow tests
    below mutate a fresh invoice each run, never the reusable 2026-02-07 fixed
    set. The seeded client name is what later turns use to reference the
    invoice - never an id."""
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"צור חשבונית ל-{client_name} על {amount} ₪ עבור {description}",
        id_prefix="E2E_SEED",
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert create_calls and create_calls[0]["error"] is None, (
        f"Seed create_invoice failed or was not called: {ai_response.mcp_calls!r}"
    )
    logger.info(f"Seeded fresh invoice for client {client_name!r}")


@pytest.mark.billed
def test_godfather_marks_invoice_paid_via_whatsapp(denidin_app):
    """Full invoice_paid flow: godfather creates a fresh invoice, then - in a
    separate, later turn - asks to mark IT as paid by client name only (never
    an id). The model must resolve the invoice itself (via list_invoices
    and/or session memory), determine its real type is 305, and call
    create_receipt directly (feature 023 - there is no update_invoice_status
    tool anymore; "mark as paid" phrasing dispatches straight to the same
    tool a direct "תפיק לי קבלה" request would use).

    Verifies the resulting status - not just that the tool call didn't error
    - via create_receipt's own returned confirmation (which references the
    original by number) plus a follow-up on the invoice's real status.

    Uses a freshly-created invoice (not the reusable 2026-02-07 fixed set)
    since marking paid is a real, effectively irreversible state change in
    the sandbox (Morning has no supported reversal for a receipt-closed
    invoice).

    Issuing a receipt is a document-creating call, so it now requires
    explicit approval (Feature 022): the ASK turn must NOT execute it yet.
    """
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"סמן את החשבונית של {client_name} כשולמה",
        id_prefix="E2E_PAID",
    )

    assert not _calls_for(ask_ai_response, "create_receipt"), (
        f"create_receipt executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    receipt_calls = _calls_for(ai_response, "create_receipt")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert receipt_calls, (
        f"Model never invoked create_receipt via the remote MCP server for "
        f"'mark as paid' phrasing. mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in receipt_calls), (
        f"create_receipt call(s) reported an error: {receipt_calls}"
    )
    assert any('"original_invoice_id"' in (c["arguments"] or "") for c in receipt_calls), (
        f"create_receipt was not called with a resolved original_invoice_id: {receipt_calls!r}"
    )

    # The resulting status, not just call success, is what this flow proves:
    # create_receipt's confirmation names the new receipt against the
    # original invoice - a follow-up status check confirms it actually paid.
    assert any("קבלה" in (c["output"] or "") for c in receipt_calls), (
        f"create_receipt output did not reflect a new receipt: {receipt_calls!r}"
    )
    # Accept either the masculine "שולם" or feminine "שולמה" — the model may
    # correctly conjugate to agree with a feminine noun (e.g. "החשבונית...
    # שולמה"), which is not a substring of "שולם" (different final letter:
    # sofit-mem ם vs regular מ before the ה).
    assert "שולם" in response or "שולמה" in response, (
        f"Bot reply did not reflect paid status. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_cancels_invoice_via_whatsapp(denidin_app):
    """Full cancel_invoice flow: godfather creates a fresh invoice, then - in a
    separate, later turn - asks to cancel it by client name only (never an
    id). The model must resolve the invoice itself before calling
    create_credit_note directly (feature 023 - there is no
    update_invoice_status tool anymore; "cancel" phrasing dispatches to the
    same tool a direct "תפיק לי חשבונית זיכוי" request would use).

    Verifies the resulting status via create_credit_note's own returned
    confirmation ("הופקה חשבונית זיכוי מספר X עבור חשבונית מספר Y") - Israeli
    law forbids voiding a tax invoice outright, so Morning's real mechanism is
    a linked Credit Invoice, not a status flag flip. The runtime constitution
    now states explicitly that this is a fully legitimate, ordinary action.

    Uses a freshly-created invoice (not the reusable 2026-02-07 fixed set)
    since cancelling is a real, permanent action (issues a real linked credit
    invoice in the sandbox).

    Issuing a credit note is a document-creating call, so it now requires
    explicit approval (Feature 022): the ASK turn must NOT execute it yet.
    """
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את החשבונית של {client_name}",
        id_prefix="E2E_CANCEL",
    )

    assert not _calls_for(ask_ai_response, "create_credit_note"), (
        f"create_credit_note executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    credit_calls = _calls_for(ai_response, "create_credit_note")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert credit_calls, (
        f"Model never invoked create_credit_note via the remote MCP server for "
        f"'cancel' phrasing. mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in credit_calls), (
        f"create_credit_note call(s) reported an error: {credit_calls}"
    )
    assert any('"original_invoice_id"' in (c["arguments"] or "") for c in credit_calls), (
        f"create_credit_note was not called with a resolved original_invoice_id: {credit_calls!r}"
    )

    # The resulting status, not just call success: the confirmation message
    # explicitly names the new credit invoice issued to offset the amount.
    assert any("זיכוי" in (c["output"] or "") for c in credit_calls), (
        f"create_credit_note output did not reflect a new credit note: {credit_calls!r}"
    )
    assert "בוטל" in response or "זיכוי" in response, (
        f"Bot reply did not reflect cancelled status. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_declines_invoice_cancellation(denidin_app):
    """Godfather creates a fresh invoice, asks to cancel it, then explicitly
    declines the pending approval (Feature 022) - create_credit_note must
    never fire, and the original invoice is unaffected (spot-checked via a
    3rd turn's get_invoice_details, still showing an open/unpaid status, not
    cancelled)."""
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    decline_response, decline_ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את החשבונית של {client_name}",
        id_prefix="E2E_CANCEL_DECLINE",
    )

    assert decline_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(decline_ai_response, "create_credit_note"), (
        f"create_credit_note executed despite an explicit decline: "
        f"{decline_ai_response.mcp_calls if decline_ai_response else None!r}"
    )

    # Spot-check: the invoice must still be open (not cancelled) afterwards.
    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה הסטטוס של החשבונית של {client_name}?",
        id_prefix="E2E_CANCEL_DECLINE_VERIFY",
    )
    details_calls = _calls_for(details_ai_response, "get_invoice_details") + _calls_for(
        details_ai_response, "list_invoices"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)
    assert "בוטל" not in combined_output, (
        f"Invoice shows as cancelled despite the decline: {combined_output!r}. "
        f"Bot reply: {details_response!r}"
    )


# ============================================================================
# spec 020: flexible invoice payment-marking methods (bugfix-014 Flow 4)
# ============================================================================

# Document-type Hebrew labels this app already translates (bugfix-014's
# translate_document_type, models.py _DOCUMENT_TYPE_NAMES) - used here to
# distinguish which closing document type actually got linked, since these
# are the exact strings a get_invoice_details reply/tool-output surfaces.
_COMBO_DOCUMENT_LABEL_HE = "חשבונית מס / קבלה"  # type 320
_RECEIPT_DOCUMENT_LABEL_HE = "קבלה"  # type 400 - deliberately NOT a substring of the 320 label above


def _seed_transaction_account_invoice(client_name: str, amount: int, description: str) -> None:
    """Seed a fresh "חשבון עסקה" (type-300) document via a real, two-turn
    approved WhatsApp exchange (create_transaction_account requires approval
    - Feature 022). Spec 021 added create_transaction_account as its own
    dedicated MCP tool (not a document_type param on create_invoice, which
    stays permanently locked to type 305) - the model is expected to route
    this phrasing to that tool, using the real Hebrew terminology a user
    would say ("חשבון עסקה" / "חשבונית עסקה" / "חשבון עיסקה" are all real
    variants).
    """
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפתח חשבון עסקה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_020_SEED_300",
    )
    create_calls = _calls_for(ai_response, "create_transaction_account")
    assert create_calls and create_calls[0]["error"] is None, (
        f"Seed create_transaction_account (חשבון עסקה) failed or was not called: {ai_response.mcp_calls!r}"
    )
    logger.info(f"Seeded fresh חשבון עסקה for client {client_name!r}")
    # Morning's own search index can lag a few seconds behind a just-created
    # document (confirmed live, 2026-07-30: a follow-up list_invoices call 7s
    # after this same seed call returned "no invoices found" for a document
    # that demonstrably existed) - same class of lag test_morning_sandbox_
    # list_invoices_tool.py already retries around on the morning-mcp-app
    # side. This test can't retry the model's own tool call, so it gives
    # Morning's index a fixed head start instead.
    time.sleep(5)


@pytest.mark.billed
def test_godfather_marks_transaction_account_invoice_paid_via_whatsapp(denidin_app):
    """Spec 020 / bugfix-014 Flow 4: a "חשבון עסקה" (type-300 transaction
    account document) must be closed by a linked type-320 combo document when
    marked paid, never the type-400 receipt used for a regular tax invoice.
    Feature 023 removed update_invoice_status - the model must resolve the
    target's real type as 300 and call close_transaction_account directly
    (the same tool a direct "תסגור לי את חשבון העסקה" request would use).

    Issuing a combo document is a document-creating call, so it now requires
    explicit approval (Feature 022): the ASK turn must NOT execute it yet.

    Deliberately does NOT import MorningClient or call Morning's raw REST API
    (this file's app-wall) - verification is entirely through a further,
    natural WhatsApp turn asking for the invoice's details, the same way a
    real user would confirm it themselves.
    """
    client_name = _unique_client_name()
    _seed_transaction_account_invoice(client_name, _random_amount(), _random_description())

    (ask_response, ask_ai_response), (paid_response, paid_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        # States VAT-inclusion explicitly (feature 023's constitution rule
        # otherwise has the model ask "כולל מע״מ?" before calling
        # close_transaction_account, confirmed live 2026-07-30) - this test
        # is about the mark-as-paid dispatch itself, not the VAT-ambiguity
        # question, so the prompt removes that ambiguity up front rather than
        # adding a third conversational turn to answer it.
        text=f"סמן את חשבון העסקה של {client_name} כשולם, כולל מע״מ",
        id_prefix="E2E_020_PAID_300",
    )
    assert not _calls_for(ask_ai_response, "close_transaction_account"), (
        f"close_transaction_account executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    close_calls = _calls_for(paid_ai_response, "close_transaction_account")
    assert paid_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert close_calls, (
        f"Model never invoked close_transaction_account via the remote MCP server for "
        f"'mark as paid' phrasing on a חשבון עסקה. mcp_calls: {paid_ai_response.mcp_calls!r}. "
        f"Final reply: {paid_response!r}"
    )
    assert all(c["error"] is None for c in close_calls), (
        f"close_transaction_account call(s) reported an error: {close_calls}"
    )

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תראה לי את כל הפרטים והמסמכים המקושרים של חשבון העסקה של {client_name}",
        id_prefix="E2E_020_DETAILS_300",
    )
    details_calls = _calls_for(details_ai_response, "get_invoice_details")
    combined_output = "\n".join(c["output"] or "" for c in details_calls)

    assert "מסמכים מקושרים" in combined_output, (
        f"Expected a linked-documents section in the invoice details reply, "
        f"got tool output: {combined_output!r}"
    )
    assert _COMBO_DOCUMENT_LABEL_HE in combined_output, (
        f"Expected a linked type-320 combo document ({_COMBO_DOCUMENT_LABEL_HE!r}) "
        f"for a חשבון עסקה marked paid, got tool output: {combined_output!r}"
    )
    # The bare receipt label ("קבלה") is a substring of the combo label
    # ("חשבונית מס / קבלה"), so strip every combo-label occurrence out first -
    # what remains must not still contain a standalone receipt label.
    without_combo_labels = combined_output.replace(_COMBO_DOCUMENT_LABEL_HE, "")
    assert _RECEIPT_DOCUMENT_LABEL_HE not in without_combo_labels, (
        f"A type-300 document must not be closed by a bare type-400 receipt: {combined_output!r}"
    )


@pytest.mark.billed
def test_godfather_declines_marking_transaction_account_invoice_paid(denidin_app):
    """Decline variant for the 300->320 path (Feature 022 x spec 020, dispatch
    updated per feature 023): godfather asks to mark a חשבון עסקה paid, then
    explicitly declines the pending approval - close_transaction_account must
    never fire, and no closing document (type 320 or otherwise) gets created."""
    client_name = _unique_client_name()
    _seed_transaction_account_invoice(client_name, _random_amount(), _random_description())

    decline_response, decline_ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        # See test_godfather_marks_transaction_account_invoice_paid_via_whatsapp's
        # comment above - states VAT-inclusion explicitly so there's a real
        # close_transaction_account pending approval to decline, rather than
        # the model asking a VAT-clarifying question with nothing yet pending.
        text=f"סמן את חשבון העסקה של {client_name} כשולם, כולל מע״מ",
        id_prefix="E2E_020_PAID_300_DECLINE",
    )

    assert decline_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(decline_ai_response, "close_transaction_account"), (
        f"close_transaction_account executed despite an explicit decline: "
        f"{decline_ai_response.mcp_calls if decline_ai_response else None!r}"
    )

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה הסטטוס של חשבון העסקה של {client_name}?",
        id_prefix="E2E_020_PAID_300_DECLINE_VERIFY",
    )
    details_calls = _calls_for(details_ai_response, "get_invoice_details") + _calls_for(
        details_ai_response, "list_invoices"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)
    assert "לא שולם" in combined_output, (
        f"Expected the חשבון עסקה to still be unpaid after the decline: "
        f"{combined_output!r}. Bot reply: {details_response!r}"
    )


@pytest.mark.billed
def test_godfather_marks_already_paid_credit_invoice_as_paid_is_rejected(denidin_app):
    """Negative case for spec 020/023: a document type neither create_receipt
    (only 305) nor close_transaction_account (only 300) supports as an
    "original" must surface a friendly refusal, not silently create a wrong
    document. Uses a real, achievable-today setup: create an invoice, cancel
    it (issues a real linked type-330 credit invoice - see
    test_godfather_cancels_invoice_via_whatsapp above), then ask to mark THAT
    credit invoice's own number as paid - type 330 is not a valid original
    for either tool. Both the cancellation and the (rejected) paid attempt
    are document-creating calls, so both go through the approve flow
    (Feature 022) even though the paid attempt is expected to fail once it
    actually executes (or be declined by the model outright, without any
    tool call at all, per feature 023's "ask/refuse rather than guess"
    guidance)."""
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    _, (cancel_response, cancel_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את החשבונית של {client_name}",
        id_prefix="E2E_020_CANCEL_SETUP",
    )
    cancel_calls = _calls_for(cancel_ai_response, "create_credit_note")
    assert cancel_calls and cancel_calls[0]["error"] is None, (
        f"Setup cancellation failed or was not called: {cancel_ai_response.mcp_calls!r}"
    )
    credit_output = cancel_calls[0]["output"] or ""
    match = re.search(r"חשבונית זיכוי מספר (\S+)", credit_output)
    assert match, f"Could not find the credit invoice number in cancel output: {credit_output!r}"
    credit_number = match.group(1)

    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"סמן את מסמך מספר {credit_number} כשולם",
        id_prefix="E2E_020_UNSUPPORTED_TYPE",
    )
    # Either tool could plausibly be attempted by the model for "mark as
    # paid" phrasing before it discovers the real type - both must reject a
    # type-330 original if called.
    attempted_calls = _calls_for(ai_response, "create_receipt") + _calls_for(
        ai_response, "close_transaction_account"
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    if attempted_calls:
        # The tool itself must reject it (raises ValueError -> surfaced as a
        # friendly error, not a fabricated success) - never a mcp_call showing
        # success for an unsupported original type.
        assert not any(c["error"] is None for c in attempted_calls), (
            f"A document-creation tool unexpectedly succeeded for an unsupported "
            f"(type-330) original document: {attempted_calls!r}"
        )
    # Either way (a tool refused, or the model declined to call anything at
    # all), the user-facing reply must not claim success. Hebrew can express
    # this refusal via several negation forms - "לא"/"לא ניתן", or
    # "אינה"/"אינו"/"אין" (e.g. "חשבונית זיכוי אינה מסמך שמסמנים כשולם") - so
    # check for any of them rather than assuming one specific phrasing.
    negation_markers = ("לא", "אינה", "אינו", "אין")
    assert "שולם" not in response or any(marker in response for marker in negation_markers), (
        f"Bot reply appears to falsely confirm payment for an unsupported "
        f"document type. Full reply: {response!r}"
    )
