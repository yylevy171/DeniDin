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

A few tests in this suite depend on a small number of PERMANENT real
sandbox clients, seeded once and never re-created per run (as opposed to
`_unique_client_name`/`_seed_client_via_conversation` below, the default
fresh-per-run pattern) - see GROUND_TRUTH_CLIENTS.md in this same directory
for the full registry, why each one exists, and what to do if the sandbox
is ever wiped.
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

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

GODFATHER_CHAT_ID = "972500000021@c.us"  # Feature 018 E2E test godfather identity (rotated 2026-08-12, bugfix-028: 972500000018's persisted session had accumulated a long, noisy history that was confusing the model across turns)
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


_HEBREW_GERESH = "׳"
_APOSTROPHE_VARIANTS = ("'", "’")  # ASCII ' and typographic '


def _normalize_hebrew_geresh(name: str) -> str:
    """Replace any apostrophe-like character with the Hebrew geresh - mirrors
    denidin_mcp_morning.tools._normalize_hebrew_geresh exactly (independently
    reimplemented, never imported - see this module's App-wall docstring
    above). Morning normalizes any client name it stores this way, so a name
    containing an apostrophe (e.g. "ריצ'רד") comes back from Morning's own
    formatted output as "ריצ׳רד" - a caller comparing against the raw,
    un-normalized name (as typed/generated) against that OUTPUT (not
    against a tool call's own arguments, which stay un-normalized) needs
    this to avoid a false negative (caught in a post-merge sweep 2026-08-12,
    a real run drew "ריצ'רד" from _unique_client_name()'s pool)."""
    for variant in _APOSTROPHE_VARIANTS:
        name = name.replace(variant, _HEBREW_GERESH)
    return name


def _is_genuine_document_creation(call: dict) -> bool:
    """Whether a create_invoice/create_transaction_account/create_combo_document
    mcp_call actually created a document, vs. refused (bugfix-039, caught in a
    post-merge sweep 2026-08-12).

    `call["error"] is None` is NOT sufficient on its own: bugfix-039's
    refuse-and-ask-for-confirmation on a non-exact client match (and the
    ambiguous/ - not-found refusal messages) are ALL ordinary string returns,
    same as a genuine success - `error` stays None either way, since none of
    those paths raise (only a true zero-candidate match raises
    ClientNotFoundError, and even that gets caught and turned into an
    ordinary string by server.py's error boundary - see errors.py). The one
    reliable signal is the output's own shape: format_invoice_confirmation
    always starts with "חשבונית #", which no refusal/confirmation-question/
    ambiguous-candidates message ever does."""
    return bool(call.get("error") is None and (call.get("output") or "").startswith("חשבונית #"))


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


def _send_turn_and_approve_receipt(
    chat_id: str, text: str, id_prefix: str, date_answer: str = "היום"
) -> Tuple[Tuple[Optional[str], Optional[AIResponse]], Tuple[Optional[str], Optional[AIResponse]]]:
    """Like `_send_turn_and_approve`, but for any request that may trigger
    create_receipt - whose `payment_date` is now mandatory (2026-08-12,
    bugfix-028 A3): a request that doesn't already state a date may get an
    open question back instead of a pending-approval prompt (almost always
    for the missing date), which a plain single "כן" doesn't answer. Handles
    both legitimate shapes: if the ASK turn's reply already contains the
    standard "לאישור" pending-approval marker, the model settled on a date
    itself (visible in the approval prompt for the user to confirm/correct) -
    only the final "כן" is sent, unchanged from `_send_turn_and_approve`. If
    not, one extra turn answers `date_answer` ("today" by default - a
    genuinely common, acceptable answer for this phrasing, per the
    constitution's own guidance) before the final "כן". Either way, only the
    LAST "כן" may ever actually execute create_receipt.

    Returns the same ((ask_response, ask_ai_response), (approve_response,
    approve_ai_response)) shape as `_send_turn_and_approve`, so existing
    call sites need only rename the function."""
    ask_response, ask_ai_response = _send_turn(chat_id, text, id_prefix=f"{id_prefix}_ASK")
    assert not _calls_for(ask_ai_response, "create_receipt"), (
        f"create_receipt executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    pre_approve_response, pre_approve_ai_response = ask_response, ask_ai_response
    if not pre_approve_response or "לאישור" not in pre_approve_response:
        pre_approve_response, pre_approve_ai_response = _send_turn(
            chat_id, date_answer, id_prefix=f"{id_prefix}_DATE"
        )
        assert not _calls_for(pre_approve_ai_response, "create_receipt"), (
            f"create_receipt executed before the separate approval turn: "
            f"{pre_approve_ai_response.mcp_calls if pre_approve_ai_response else None!r}"
        )

    approve_result = _send_turn(chat_id, "כן", id_prefix=f"{id_prefix}_APPROVE")
    return (ask_response, ask_ai_response), approve_result


def _fresh_nonexistent_client_name(chat_id: str, id_prefix: str, max_attempts: int = 5) -> str:
    """Return a client name from `_unique_client_name()`'s real-name pool
    that is CONFIRMED not to already exist as a real Morning client -
    needed by any test whose premise is "this client doesn't exist yet"
    (feature 027's not-found/refusal flows).

    `_unique_client_name()`'s pool (565x591 = ~334K combinations) is
    "unique enough" for tests that don't care whether the name happens to
    coincide with a real pre-existing client (harmless collision before
    feature 027 - every create_invoice call succeeded regardless of
    whether the client existed). Feature 027 makes a collision visible: if
    the randomly-picked name happens to already be a real client (the
    sandbox accumulates real clients across every E2E run, growing over
    time), a "client doesn't exist yet" test's whole premise silently
    doesn't hold, and its actual outcome is indistinguishable from success
    on a fresh flow (a real, observed 2026-08-07 failure). This checks via
    a real, read-only get_client_details turn (no approval needed) before
    returning, and retries with a new name on a genuine collision.

    The acceptance check itself (only a literal "not found" counts as
    fresh) is still correct post-bugfix-039 and must stay strict - a
    NON-exact match (get_client_details discloses a similar real client's
    details instead of saying "not found") means create_invoice's identical
    resolve_client_by_name would likely ALSO hit that same non-exact match
    and refuse with a confirmation question rather than genuinely treating
    the client as not-found, which would silently invalidate the calling
    test's whole premise.

    NOTE (2026-08-12): a real run exhausted all 5 attempts here without
    landing on a genuinely clean draw, plausibly because bugfix-039's
    per-word discovery surfaces a plausible non-exact candidate far more
    readily than the old whole-string-only search did, against a sandbox
    pool that's been drawn from heavily across many E2E runs. Raising
    max_attempts to paper over this was proposed and explicitly REJECTED
    ("25 means there is a bug!") - kept at 5, unresolved, needs a real
    decision (bigger name pool vs. a redefined freshness check vs.
    something else) rather than a bigger retry budget. Each attempt is one
    real (cheap, billed-tier) OpenAI turn.
    """
    for _ in range(max_attempts):
        candidate = _unique_client_name()
        response, _ = _send_turn(
            chat_id=chat_id,
            text=f"פרטים על הלקוח {candidate}",
            id_prefix=f"{id_prefix}_FRESHCHECK",
        )
        if response and ("לא נמצא" in response or "אין" in response):
            return candidate
        logger.warning(f"Name collision picking a fresh nonexistent client name: {candidate!r} already exists")
    raise RuntimeError(f"Could not find a genuinely nonexistent client name after {max_attempts} attempts")


def _seed_client_via_conversation(
    chat_id: str,
    client_name: str,
    id_prefix: str,
    email: Optional[str] = None,
    phone: str = _SEED_PHONE,
) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Seed a real Morning client via the real, two-turn `add_client`
    conversational flow (Feature 026, approval-gated) and return the
    APPROVE turn's (response, ai_response).

    Feature 027 (mandatory client reference for document creation): every
    create_invoice/create_transaction_account/create_combo_document call
    now resolves its client_name against a real client record and refuses
    if none exists - any test that needs "a client that already exists"
    MUST seed it this way first. This is the ONLY way to create a client
    from this E2E layer (the app-wall forbids importing morning-mcp-app's
    MorningClient directly - see this module's own docstring) - there is no
    faster raw-API shortcut available here, unlike the sandbox-level
    integration tests in apps/morning-mcp-app.

    Asserts the seed itself actually succeeded (fails loudly, not silently)
    - a downstream test failure caused by a failed seed would otherwise be
    misleading about what actually broke. Sleeps 3s afterward (search-index
    lag, research.md Decision 8 - a cost-free local wait, cheaper than
    retrying a whole billed conversational turn) before returning, so the
    client is reliably resolvable by the very next turn.
    """
    seed_email = email or _random_seed_email()
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=chat_id,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {phone}",
        id_prefix=f"{id_prefix}_SEEDCLIENT",
    )
    add_calls = _calls_for(ai_response, "add_client")
    assert add_calls and add_calls[0]["error"] is None, (
        f"Failed to seed client {client_name!r} via add_client - cannot "
        f"proceed with the rest of this test: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    time.sleep(3)
    return response, ai_response


def _seed_fresh_client(
    chat_id: str,
    id_prefix: str,
    max_attempts: int = 5,
    name_factory: Callable[[], str] = _unique_client_name,
) -> Tuple[str, Optional[str], Optional[AIResponse]]:
    """Seed a brand-new client under a freshly-drawn name, retrying with a
    new draw if this particular name collides with an existing real sandbox
    client (a real, growing risk as the sandbox accumulates clients across
    many billed runs - see bugfix-028 handoff, 2026-08-12).

    `name_factory` defaults to `_unique_client_name` (a fully random
    first+family pair) but can be overridden for a test that needs some
    control over the drawn name's shape (e.g. a fixed spelling variant paired
    with a random family name) while still getting the same collision-retry
    safety - see callers passing a custom factory for examples.

    `resolve_client_name` has no fuzzy leniency at all - a collision here
    means it is doing exactly its designed job of flagging a non-exact or
    exact match. Per the 2026-08-12 constitution fix, what happens next
    depends on which kind of match it found:
    - EXACT match ("שם הלקוח המדויק במורנינג") → a real pre-existing
      duplicate. The only thing on offer is updating THAT existing client -
      never blindly say "כן" here, since that would silently mutate an
      unrelated real sandbox client's email/phone. Draw a new name instead.
    - Non-exact (a "did you mean X, or create a new one?" question, or a
      candidates list) → creation is still on the table; one extra "כן" is
      needed to say "the new one", landing on the ordinary pending-approval
      prompt every add_client goes through (Feature 022) - then one more
      "כן" to actually approve it. A genuinely fresh name with no match at
      all only needs that last "כן" (the ordinary one-turn approval flow).

    Unlike `_seed_client_via_conversation`, never asserts on a single
    attempt's outcome - only on running out of attempts entirely. Returns
    the (client_name, response, ai_response) actually used, since it may
    differ from any name the caller had in mind."""
    for attempt in range(1, max_attempts + 1):
        candidate = name_factory()
        seed_email = _random_seed_email()
        response, ai_response = _send_turn(
            chat_id=chat_id,
            text=f"תוסיף לקוח חדש בשם {candidate}, מייל {seed_email}, טלפון {_SEED_PHONE}",
            id_prefix=f"{id_prefix}_SEEDCLIENT_A{attempt}",
        )
        resolve_calls = _calls_for(ai_response, "resolve_client_name")
        resolve_output = (resolve_calls[0]["output"] or "") if resolve_calls else ""
        if resolve_output.startswith("שם הלקוח המדויק במורנינג"):
            logger.warning(
                f"_seed_fresh_client: attempt {attempt} name {candidate!r} is an EXACT "
                f"match for a real existing client - retrying with a new name "
                f"(never approving an update to an unrelated client)."
            )
            continue

        for _ in range(2):
            add_calls = _calls_for(ai_response, "add_client")
            if add_calls and add_calls[0]["error"] is None:
                time.sleep(3)
                return candidate, response, ai_response
            response, ai_response = _send_turn(
                chat_id=chat_id, text="כן", id_prefix=f"{id_prefix}_SEEDCLIENT_A{attempt}_YES"
            )

        add_calls = _calls_for(ai_response, "add_client")
        if add_calls and add_calls[0]["error"] is None:
            time.sleep(3)
            return candidate, response, ai_response
        logger.warning(
            f"_seed_fresh_client: attempt {attempt} name {candidate!r} did not "
            f"cleanly create a new client after confirmation - retrying with a "
            f"new name. Bot reply: {response!r}"
        )
    raise RuntimeError(f"Could not seed a genuinely fresh client after {max_attempts} attempts")


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
