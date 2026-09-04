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
`_unique_client_name`/`_seed_client` below, the default fresh-per-run
pattern) - see GROUND_TRUTH_CLIENTS.md in this same directory for the full
registry, why each one exists, and what to do if the sandbox is ever wiped.
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Tuple

from whatsapp_chatbot_python import Notification

logger = logging.getLogger(__name__)

DENIDIN_APP_DIR = Path(__file__).resolve().parents[2]

# Feature 075: single source of truth in tests/e2e_helpers.py; re-exported here
# so tests/billed/conftest.py and the MCP e2e modules can import it from their
# usual helper module.
from tests.e2e_helpers import sanity_worker_data_root  # noqa: E402,F401


class NoMorningTunnelError(Exception):
    """Raised when the shared status file reports no live Morning MCP tunnel.

    This means the test environment is not up (Morning server/ngrok tunnel not
    running) - the fix is to start apps/morning-mcp-app (./run_morning_mcp.sh),
    not to retry or mock around it.
    """


class ClientAlreadyExistsError(Exception):
    """Raised by `_seed_client` (specific-name variant) when the name it was
    asked to create turns out to be a genuine EXACT match for a real,
    pre-existing sandbox client (2026-08-12, user decision, following the removal of the
    constitution's old "offer to update instead" behavior for this exact
    case - the app itself now just refuses and stops, so a test-side helper
    trying to CREATE a new client must treat this as a real, distinguishable
    failure too, never silently proceed or approve an update to the
    unrelated existing client). Callers that draw a random name may choose
    to catch this and retry with a new one; callers using a specific,
    already-established name (already referenced in prior conversation
    turns) generally cannot recover mid-flow and should let it fail loudly.
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


def build_button_tap_webhook(
    chat_id: str, sender_name: str, selected_id: str, stanza_id: str, message_id: str
) -> dict:
    """Build a real Green API incomingMessageReceived webhook event dict for an
    interactiveButtonsResponse (a WhatsApp interactive-button tap, Feature 047) -
    shape matches the real payload captured live during Gate Zero
    (specs/.../047-whatsapp-interactive-approval-buttons/research.md /
    gate-zero-captured-notifications.json), trimmed to the fields
    denidin.py's handle_button_tap and WhatsAppMessage.from_notification
    actually read."""
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
            'senderName': sender_name,
            'senderContactName': sender_name,
        },
        'messageData': {
            'typeMessage': 'interactiveButtonsResponse',
            'interactiveButtonsResponse': {
                'stanzaId': stanza_id,
                'selectedIndex': 0,
                'selectedId': selected_id,
                'selectedDisplayText': 'כן' if selected_id == 'denidin_approve' else 'לא',
            },
        }
    }


def create_real_notification(event_dict: dict) -> Notification:
    """Create a real SDK Notification object (no mocking), tracking answer() and
    answer_with_interactive_buttons() calls.

    Feature 047: `answer_with_interactive_buttons` needs `self.api` internally
    (`chat = self.get_chat(); return self.api.sending.sendInteractiveButtons(...)`),
    which this bare `Notification.__new__` construction never sets (real
    `__init__` is deliberately skipped, same as before this feature) - a real
    Green API send would be as undesirable here as `.answer()`'s real send
    always was (this is a fake test chat_id, nothing should actually be
    delivered anywhere). So this is captured the same way `.answer()` already
    is, rather than routed through a real `self.api` - additive, not a change
    to the existing `.answer()` capture pattern. `body` is ALSO appended to
    `_test_sent_messages` (dual-write) so every existing helper reading
    `get_response()`/`_test_sent_messages[0]` keeps seeing exactly what a real
    user would read on screen, regardless of whether it arrived as plain text
    or as an interactive-buttons body - the same content either way, per
    spec.md Scope ("buttons change how the answer arrives, never what the
    question contains")."""
    notification = Notification.__new__(Notification)
    notification.event = event_dict
    notification._test_sent_messages = []
    notification._test_button_sends = []

    def track_answer(message):
        notification._test_sent_messages.append(message)
        logger.info(f"Would send to user: {message}")

    _next_id = [0]

    def track_answer_with_interactive_buttons(body, buttons, header=None, footer=None):
        _next_id[0] += 1
        id_message = f"TEST_BUTTONS_{event_dict.get('idMessage', 'noid')}_{_next_id[0]}"
        notification._test_button_sends.append({
            'body': body, 'buttons': buttons, 'header': header, 'footer': footer,
            'idMessage': id_message,
        })
        notification._test_sent_messages.append(body)
        logger.info(
            f"Would send interactive buttons to user: body={body!r} buttons={buttons!r} "
            f"idMessage={id_message}"
        )
        return SimpleNamespace(code=200, data={'idMessage': id_message}, error=None)

    notification.answer = track_answer
    notification.answer_with_interactive_buttons = track_answer_with_interactive_buttons
    return notification


def get_response(notification: Notification) -> Optional[str]:
    return notification._test_sent_messages[0] if notification._test_sent_messages else None


def get_button_send(notification: Notification) -> Optional[dict]:
    """Feature 047: the captured `answer_with_interactive_buttons` call this
    notification's turn made, if any - {'body', 'buttons', 'header', 'footer',
    'idMessage'}. None if this turn sent plain text instead (no pending
    approval was created) or sent nothing at all."""
    sends = notification._test_button_sends
    return sends[0] if sends else None


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


# --------------------------------------------------------------------------- #
# Feature 059 item 5: pick an already-existing sandbox client instead of       #
# seeding a throwaway one.                                                     #
#                                                                             #
# Most Morning-MCP billed/expensive tests just need *a* valid client to exist  #
# - client freshness buys them nothing (only a fresh *document* matters, and   #
# those tests seed that separately). Historically each still paid 2-3 billed   #
# OpenAI turns + a `time.sleep(3)` to seed a client through the conversational #
# `add_client` flow. `tests/fixtures/morning_sandbox_clients.json` is a        #
# committed, occasionally-refreshed snapshot of real sandbox clients whose     #
# names are safe to pick blindly (two clean Hebrew words, unambiguous first    #
# word, nothing else asserts anything specific about them - see the pull       #
# script apps/morning-mcp-app/scripts/pull_sandbox_clients.py and              #
# GROUND_TRUTH_CLIENTS.md). Group 2 tests `pick_existing_client()` from it -   #
# no OpenAI, no seeding turn, no sleep.                                        #
# --------------------------------------------------------------------------- #
_SANDBOX_CLIENTS_FIXTURE = (
    DENIDIN_APP_DIR / "tests" / "fixtures" / "morning_sandbox_clients.json"
)
_sandbox_clients_cache: Optional[List[dict]] = None


def _load_sandbox_clients() -> List[dict]:
    global _sandbox_clients_cache
    if _sandbox_clients_cache is None:
        payload = json.loads(_SANDBOX_CLIENTS_FIXTURE.read_text(encoding="utf-8"))
        clients = payload.get("clients") or []
        if not clients:
            raise RuntimeError(
                f"{_SANDBOX_CLIENTS_FIXTURE} has no clients - regenerate it with "
                f"apps/morning-mcp-app/scripts/pull_sandbox_clients.py"
            )
        _sandbox_clients_cache = clients
    return _sandbox_clients_cache


def pick_existing_client(predicate: Optional[Callable[[dict], bool]] = None) -> dict:
    """Return a random real sandbox client row (dict with
    ``name``/``id``/``email``/``phone``/``tax_id``) from the committed
    ``morning_sandbox_clients.json`` fixture - for any Group 2 test that needs
    *a* client to exist but does not depend on it being brand-new.

    No OpenAI call, no seeding conversation, no ``time.sleep`` - the client is
    already indexed in Morning, so it resolves on the very next turn.

    `predicate`, if given, filters the pool first (e.g.
    ``pick_existing_client(lambda c: c["email"])`` for a test that needs the
    client to carry an email it can assert round-trips). Raises if nothing
    matches - a signal to refresh the fixture, never something to paper over.
    """
    pool = _load_sandbox_clients()
    if predicate is not None:
        pool = [c for c in pool if predicate(c)]
    if not pool:
        raise RuntimeError(
            "pick_existing_client: no sandbox client matches the given predicate - "
            "regenerate tests/fixtures/morning_sandbox_clients.json "
            "(apps/morning-mcp-app/scripts/pull_sandbox_clients.py) or loosen the predicate"
        )
    return random.choice(pool)

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


def _seeded_email_from(ai_response: Optional[AIResponse]) -> str:
    """Extract the email `_seed_client` actually used, from the add_client
    call already captured in its returned `ai_response`.

    `_seed_client` draws its own random email internally
    (`_random_seed_email()`) unless one is passed in, and never returns it
    directly - most callers only care about the resulting `client_name`. A
    caller that DOES need the exact seeded email later (e.g. to assert it
    round-trips unchanged through get_client_details/update_client) must
    extract it from here, never track a separately-drawn `seed_email` of its
    own - that stray variable is exactly what caused a real, pre-existing
    `NameError` in 3 separate tests in
    test_denidin_morning_client_management_e2e.py (found live, 2026-08-12)."""
    add_calls = _calls_for(ai_response, "add_client")
    if not add_calls:
        raise ValueError(
            f"No add_client call found - is this really _seed_client's own "
            f"returned ai_response? mcp_calls: {ai_response.mcp_calls if ai_response else None!r}"
        )
    return json.loads(add_calls[0]["arguments"])["email"]


# --------------------------------------------------------------------------- #
# resolve_client_name's FOUR outcomes - the ONE place this suite classifies    #
# them and drives an identity-resolution question to a conclusion.             #
#                                                                             #
# The production resolve_client_name MCP tool returns exactly one of four      #
# fixed-prefix Hebrew strings (morning-mcp-app/…/formatters.py), and the       #
# model very often echoes that same string near-verbatim in its plain-text    #
# reply when it answers a resolution question without a fresh tool call - so   #
# `_classify` reads the marker from the tool output OR the reply text,         #
# whichever carries one:                                                       #
#   EXACT            format_client_name_resolved            - the client       #
#                    exists in Morning exactly as queried (the ONLY outcome    #
#                    that means "exists as queried")                           #
#   SINGLE_CANDIDATE format_client_name_confirmation_question - one similar     #
#                    but non-exact client; a bare "כן" confirms it             #
#   MULTI_CANDIDATE  format_ambiguous_clients_message         - 2+ similar     #
#                    clients; "כן" can NOT disambiguate - an exact name must   #
#                    be supplied                                               #
#   NONE             format_client_not_found / nothing looked the client up   #
#                    and nothing named an outcome - zero confirmed matches     #
#                                                                             #
# There is NO fifth "errored"/"not attempted" bucket. A resolve_client_name    #
# call that Morning rejected, or one whose output matches none of the four     #
# markers, is a hard failure - `_classify` RAISES ``ResolveClientNameError``   #
# (identity resolution must never error; in a test any unintended error is a   #
# failure, not a state to recover from). Only a turn with no resolve call at   #
# all and no marker in the reply is benign - that is a plain-text clarifying   #
# question, classified NONE (nothing has confirmed the client exists).         #
#                                                                             #
# NOTHING else in this suite may read those markers, re-derive "does this      #
# client exist", or decide what to reply to a resolution question - it all     #
# goes through `_resolve_client_name` below. Inline copies of this exact       #
# check drifted and broke the suite twice in 2026-08 (once in the old          #
# `_fresh_nonexistent_client_name` helper, then again via a second ad-hoc      #
# copy in test_create_document_for_new_client_declines_client_creation). One   #
# classifier, one driver, one place - so it can only ever be wrong in one.     #
# --------------------------------------------------------------------------- #
_EXACT_CLIENT_MATCH_MARKER = 'שם הלקוח המדויק במורנינג: "'
_SINGLE_CANDIDATE_MARKER = 'מצאתי לקוח בשם "'
_MULTI_CANDIDATE_MARKER = "נמצאו כמה לקוחות בשם דומה"
_CLIENT_NOT_FOUND_MARKER = "לא נמצא לקוח בשם הזה"


class ResolveClientNameError(AssertionError):
    """A resolve_client_name call errored, or returned an output shape that
    matches none of the four known markers. Identity resolution must never
    error - in this suite that is a hard failure, never a state to recover
    from (user, 2026-09-02: "error or junk is NOT NONE - it is an error that
    should be raised ... any error is a failure unless we intended for it to
    happen"). A test that deliberately provokes such an error catches this."""


class ResolveOutcome(Enum):
    """Exactly which of resolve_client_name's four outcomes a turn produced.
    There is no "errored"/"not attempted" member - see
    ``ResolveClientNameError`` and the comment block above:

    * ``EXACT``            - the client exists in Morning exactly as queried
      (the ONLY outcome for which ``.exists`` is True).
    * ``SINGLE_CANDIDATE`` - one similar but non-exact client; a bare "כן"
      confirms it.
    * ``MULTI_CANDIDATE``  - 2+ similar clients; an exact name is needed to
      disambiguate.
    * ``NONE``             - zero confirmed matches: either the not-found
      marker, or nothing looked the client up and the reply named no outcome
      (a plain-text clarifying question).
    """

    NONE = "none"
    EXACT = "exact"
    SINGLE_CANDIDATE = "single_candidate"
    MULTI_CANDIDATE = "multi_candidate"


@dataclass
class ResolveResult:
    """Outcome of classifying (and optionally driving to a conclusion) a
    resolve_client_name interaction.

    * ``outcome``       - classification of the FIRST turn examined (what the
                          model's initial resolve_client_name call returned).
                          ``.exists`` reflects THIS.
    * ``final_outcome`` - classification of the LAST turn, after any driving.
    * ``resolved_name`` - the exact / confirmed-candidate client name when one
                          is determinable (EXACT, or a SINGLE_CANDIDATE's
                          quoted name); ``None`` for MULTI_CANDIDATE / NONE.
    * ``reply`` / ``ai_response`` - the final turn's reply text and
                          ``AIResponse`` (so a caller can assert on what the
                          model did once identity was settled - a follow-up
                          get_client_details call, a mutation-approval prompt,
                          etc.).
    """

    outcome: ResolveOutcome
    final_outcome: ResolveOutcome
    resolved_name: Optional[str]
    reply: Optional[str]
    ai_response: Optional[AIResponse]

    @property
    def exists(self) -> bool:
        """True iff the client exists in Morning exactly as first queried -
        i.e. the FIRST resolve_client_name call was a genuine EXACT match.
        Every other outcome (zero / single-non-exact / ambiguous) means "not
        as queried" (user, 2026-08-12: "WHEN AN AMBIGUOUS REPLY RETURNS IT
        MEANS THE CLIENT AS REQUESTED DOES NOT EXIST")."""
        return self.outcome is ResolveOutcome.EXACT


def _resolve_client_name(
    chat_id: Optional[str] = None,
    name: Optional[str] = None,
    id_prefix: Optional[str] = None,
    *,
    initial_result: Optional[Tuple[Optional[str], Optional[AIResponse]]] = None,
    disambiguator: Optional[str] = None,
    drive: bool = True,
    max_rounds: int = 4,
) -> ResolveResult:
    """THE one place this suite understands resolve_client_name's four
    outcomes. Nothing else classifies a resolve_client_name output, checks the
    EXACT marker, or answers an identity-resolution question.

    Two modes:

    * **classify only** (``drive=False``) - pass an already-captured turn as
      ``initial_result=(reply, ai_response)``; returns its ``ResolveResult``
      with no further turns sent. ``chat_id`` / ``name`` / ``id_prefix`` are
      then unused (pass ``initial_result=(None, ai_response)`` when only the
      ``AIResponse`` is on hand).

    * **classify and drive** (``drive=True``, default) - classify the first
      turn (either ``initial_result``, or a fresh ``"פרטים על הלקוח {name}"``
      probe when ``initial_result`` is omitted), then drive it to a definitive
      state, up to ``max_rounds`` reply turns:
        - EXACT / NONE                           -> terminal, return as-is
        - a real mutation-approval prompt reached -> terminal (identity is
          settled; the model has moved on to the approval gate)
        - SINGLE_CANDIDATE -> reply "כן", re-classify
        - MULTI_CANDIDATE  -> reply ``disambiguator`` (an exact name; REQUIRED
          for this outcome), re-classify
        - NONE, but the model is still asking something (a plain-text
          clarifying question, not the not-found terminal) -> nudge with
          ``disambiguator`` if one was given, else terminal
      Any tool error on a driven turn - or a resolve_client_name call that
      errored / returned junk on any turn - raises (identity resolution must
      never error). ``.outcome`` always reports what the FIRST turn was;
      ``.reply`` / ``.ai_response`` / ``.resolved_name`` reflect the final
      state.
    """
    def _match_marker(text: str) -> Optional[Tuple[ResolveOutcome, Optional[str]]]:
        """Read one of the four fixed markers out of `text` (a tool output OR a
        reply). ``None`` if the text carries none of them."""
        if _EXACT_CLIENT_MATCH_MARKER in text:
            after = text.split(_EXACT_CLIENT_MATCH_MARKER, 1)[1]
            return ResolveOutcome.EXACT, (after.split('"')[0] or None)
        if _SINGLE_CANDIDATE_MARKER in text:
            after = text.split(_SINGLE_CANDIDATE_MARKER, 1)[1]
            return ResolveOutcome.SINGLE_CANDIDATE, (after.split('"')[0] or None)
        if _MULTI_CANDIDATE_MARKER in text:
            return ResolveOutcome.MULTI_CANDIDATE, None
        if _CLIENT_NOT_FOUND_MARKER in text:
            return ResolveOutcome.NONE, None
        return None

    def _classify(
        turn_ai: Optional[AIResponse], turn_reply: Optional[str] = None
    ) -> Tuple[ResolveOutcome, Optional[str]]:
        """One turn -> exactly one of the four ``ResolveOutcome`` values. The
        marker is read from the turn's LAST resolve_client_name output if it
        made a call, otherwise from the reply text (the model routinely quotes
        the same fixed string when it answers in plain text). A resolve call
        that errored, or one whose output matches no marker, RAISES
        ``ResolveClientNameError``. A turn with no resolve call and no marker
        in the reply is NONE - a benign plain-text clarifying question,
        nothing has confirmed the client exists. The ONLY place any of the
        four markers is read."""
        calls = _calls_for(turn_ai, "resolve_client_name")
        if calls:
            last = calls[-1]
            if last.get("error") is not None:
                raise ResolveClientNameError(
                    f"resolve_client_name errored - identity resolution must "
                    f"never error: {last!r}"
                )
            matched = _match_marker(last.get("output") or "")
            if matched is None:
                raise ResolveClientNameError(
                    f"resolve_client_name returned an output matching none of "
                    f"the four known markers: {last.get('output')!r}"
                )
            return matched
        matched = _match_marker(turn_reply or "")
        if matched is not None:
            return matched
        return ResolveOutcome.NONE, None

    if initial_result is not None:
        reply, ai_response = initial_result
    else:
        assert chat_id and name and id_prefix, (
            "_resolve_client_name: chat_id/name/id_prefix are required when no "
            "initial_result is given"
        )
        reply, ai_response = _send_turn(
            chat_id, f"פרטים על הלקוח {name}", id_prefix=f"{id_prefix}_RESOLVE_PROBE"
        )

    first_outcome, resolved_name = _classify(ai_response, reply)
    outcome, current_name = first_outcome, resolved_name

    if drive:
        assert chat_id and id_prefix, (
            "_resolve_client_name(drive=True): chat_id/id_prefix are required to "
            "send resolution replies"
        )
        for round_num in range(1, max_rounds + 1):
            if _is_real_approval_prompt(reply):
                break
            if outcome is ResolveOutcome.EXACT:
                break
            if outcome is ResolveOutcome.SINGLE_CANDIDATE:
                answer = "כן"
            elif outcome is ResolveOutcome.MULTI_CANDIDATE:
                assert disambiguator, (
                    "_resolve_client_name: resolve_client_name returned multiple "
                    "candidates but no `disambiguator` (exact name) was supplied "
                    "to answer with - a bare 'כן' cannot disambiguate a "
                    "multi-candidate list"
                )
                answer = disambiguator
            else:  # NONE - the confirmed not-found terminal, or the model
                # asked a plain-text clarifying question (no resolve call, no
                # marker). With an exact name in hand, nudge with it (it
                # resolves a plain-text question and corrects a spurious
                # not-found alike); without one, NONE is terminal.
                if not disambiguator:
                    break
                answer = disambiguator
            reply, ai_response = _send_turn(
                chat_id, answer, id_prefix=f"{id_prefix}_RESOLVE_R{round_num}"
            )
            for call in (ai_response.mcp_calls if ai_response else []):
                assert call.get("error") is None, (
                    f"_resolve_client_name: a tool call errored while resolving "
                    f"identity (round {round_num}): {call!r}"
                )
            outcome, round_name = _classify(ai_response, reply)
            if round_name:
                current_name = round_name

    return ResolveResult(
        outcome=first_outcome,
        final_outcome=outcome,
        resolved_name=current_name,
        reply=reply,
        ai_response=ai_response,
    )


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


def _is_real_approval_prompt(text: Optional[str]) -> bool:
    """Whether `text` is the REAL mutation-approval gate ("...לאישור...
    אישור — כן/לא?"), as opposed to an identity-resolution question
    ("did you mean X, or create new Y?", or a "pick 1 or 2" multi-choice) -
    found live 2026-08-13: a bare "כן" only correctly answers the former: it
    isn't a valid answer to either shape of the latter, and a test blindly
    sending "כן" every round can stall forever against one. The real
    approval gate is reliably identifiable by its own fixed shape - it
    always contains all three of "לאישור", "כן", and "לא" together."""
    return bool(text and "לאישור" in text and "כן" in text and "לא" in text)


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
    create_combo_document_as_reference - Feature 022), then send a second turn with a
    Hebrew affirmative to approve it.

    Returns ((ask_response, ask_ai_response), (approve_response, approve_ai_response))
    - callers typically assert on the ASK turn that nothing executed yet, and
    on the APPROVE turn (the one carrying the real mcp_call) for the actual
    outcome.
    """
    ask_result = _send_turn(chat_id, text, id_prefix=f"{id_prefix}_ASK")
    approve_result = _send_turn(chat_id, approval_text, id_prefix=f"{id_prefix}_APPROVE")
    return ask_result, approve_result


def _send_button_tap(
    chat_id: str, selected_id: str, id_prefix: str, stanza_id: Optional[str] = None
) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Feature 047: send one real WhatsApp interactive-button tap through the
    real router handler (handle_button_tap), same shape _send_turn uses for
    text. Returns (reply text, AIResponse) for inspection - a stale/no-op tap
    (resolve_button_tap returned None) means both are None, since nothing at
    all gets sent in that case (spec.md Clarifications: silent).

    `stanza_id` defaults to chat_id's CURRENT pending approval's
    `sent_message_id` - the same thing a real device would be tapping (the
    button actually rendered on screen), read via the same
    PendingApprovalManager.attach_sent_message_id wiring denidin.py's real
    turn-processing path uses (see create_real_notification's
    answer_with_interactive_buttons stub - it returns a real idMessage-shaped
    Response, so this wiring fires exactly as it does in production). Pass an
    explicit stanza_id to deliberately simulate a stale tap (e.g. a
    previous turn's idMessage, after a newer pending approval has replaced
    it)."""
    import denidin

    if stanza_id is None:
        pending = denidin.denidin_app.ai_handler.pending_approval_manager.get(chat_id)
        assert pending is not None and pending.sent_message_id, (
            f"No pending approval with a sent_message_id for chat={chat_id!r} - "
            f"nothing to tap. pending={pending!r}"
        )
        stanza_id = pending.sent_message_id

    notification = create_real_notification(build_button_tap_webhook(
        chat_id=chat_id,
        sender_name="E2E Godfather",
        selected_id=selected_id,
        stanza_id=stanza_id,
        message_id=f"{id_prefix}_{int(datetime.now(timezone.utc).timestamp())}"
    ))
    denidin.handle_button_tap(notification)
    response = get_response(notification)

    ai_response = denidin.denidin_app.ai_handler.last_response

    if ai_response is not None:
        for call in ai_response.mcp_calls:
            logger.info(
                f"mcp_call: name={call['name']} error={call['error']!r} "
                f"arguments={call['arguments']!r} output={call['output']!r}"
            )
    logger.info(f"Bot response (button tap): {response}")

    return response, ai_response


def _send_turn_and_approve_via_button_tap(
    chat_id: str, text: str, id_prefix: str
) -> Tuple[Tuple[Optional[str], Optional[AIResponse]], Tuple[Optional[str], Optional[AIResponse]]]:
    """Like `_send_turn_and_approve`, but approves via a real WhatsApp
    interactive-button tap ("כן"/BUTTON_ID_APPROVE) instead of typing "כן" -
    exercises the Feature 047 button-tap resolution path
    (AIHandler.resolve_button_tap) end to end, real webhook to real reply,
    same as _send_turn_and_approve does for the text path. Returns the same
    ((ask_response, ask_ai_response), (approve_response, approve_ai_response))
    shape, so existing assertions on either half work unchanged."""
    from src.managers.pending_approval_manager import BUTTON_ID_APPROVE

    ask_result = _send_turn(chat_id, text, id_prefix=f"{id_prefix}_ASK")
    approve_result = _send_button_tap(chat_id, BUTTON_ID_APPROVE, id_prefix=f"{id_prefix}_TAP_APPROVE")
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


def _send_turn_and_approve_capturing_approval(
    chat_id: str, text: str, id_prefix: str, tool_name: str, clarify_answer: str = "היום"
) -> Tuple[str, Optional[AIResponse]]:
    """Like `_send_turn_and_approve`/`_send_turn_and_approve_receipt`, but for
    a caller (bugfix-038) that needs the actual TEXT of whichever turn carried
    the real pending-approval prompt (identified via `_is_real_approval_prompt`
    - "לאישור"/"כן"/"לא" together, never a bare identity-resolution question) -
    not just the ASK turn's raw reply, which for `create_receipt` may instead
    be an open clarifying question (payment_date is mandatory - see
    `_send_turn_and_approve_receipt`) rather than the approval itself.

    Generalizes `_send_turn_and_approve_receipt` to any Group A/B tool: sends
    `text`, and if the reply is not yet a real approval prompt, sends one
    `clarify_answer` turn (default "today" - the common answer to a missing-
    date question) before giving up. Asserts `tool_name` never fires before
    the final "כן". Returns (approval_text, approve_ai_response) - callers
    inspect `approval_text` for what the user was actually asked to approve,
    and `approve_ai_response` (via `_calls_for`) for the real outcome."""
    response, ai_response = _send_turn(chat_id, text, id_prefix=f"{id_prefix}_ASK")
    assert not _calls_for(ai_response, tool_name), (
        f"{tool_name} executed before any approval was given: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )

    if not _is_real_approval_prompt(response):
        response, ai_response = _send_turn(chat_id, clarify_answer, id_prefix=f"{id_prefix}_CLARIFY")
        assert not _calls_for(ai_response, tool_name), (
            f"{tool_name} executed before the actual approval turn: "
            f"{ai_response.mcp_calls if ai_response else None!r}"
        )

    assert _is_real_approval_prompt(response), (
        f"expected a real pending-approval prompt (containing 'לאישור') after "
        f"at most one clarifying turn, got: {response!r}"
    )
    approval_text = response

    _, approve_ai_response = _send_turn(chat_id, "כן", id_prefix=f"{id_prefix}_APPROVE")
    return approval_text, approve_ai_response


def _seed_client(
    chat_id: str,
    id_prefix: str,
    *,
    name: Optional[str] = None,
    name_factory: Callable[[], str] = _unique_client_name,
    text: Optional[str] = None,
    email: Optional[str] = None,
    phone: str = _SEED_PHONE,
    create: bool = True,
    ensure_exists: bool = False,
    max_attempts: int = 5,
) -> Tuple[str, Optional[str], Optional[AIResponse]]:
    """The ONE client-seeding flow for this E2E suite - one real
    conversational `add_client` path with a few caller-selected variants.
    Always returns ``(client_name, last_response, last_ai_response)``;
    ``last_response`` / ``last_ai_response`` are ``None`` for the two
    read-only variants that never create anything.

    Variants:

    * **fresh drawn name** (default: ``name=None``) - draws a name from
      ``name_factory`` (default ``_unique_client_name``), seeds it, and on a
      genuine EXACT-match collision with a real pre-existing client redraws
      and retries, up to ``max_attempts``. Never approves an update to the
      colliding client (bugfix-045). Pass a custom ``name_factory`` to
      control the drawn name's shape (e.g. a fixed spelling variant + random
      family name) while keeping the collision-retry safety.

    * **specific name** (``name="..."``, optionally with ``text=``) - seeds
      that exact name. A genuine EXACT-match collision raises
      ``ClientAlreadyExistsError`` (no redraw - the caller established this
      name in earlier turns and cannot silently swap it). ``text``, if
      given, is the first turn sent verbatim (for a caller mid-conversation
      that has already stated the name/fields its own way); otherwise a
      standard "add a client named X, email, phone" turn is sent.

    * ``create=False`` - draws a name (``name_factory``) and returns it only
      once a read-only probe confirms NO client by that literal name exists
      yet; redraws on collision. Creates nothing. For tests whose premise is
      "this client doesn't exist yet" (feature 027's not-found / refusal
      flows) - they take the returned name into a later request and assert
      the app treats it as unknown.

    * ``ensure_exists=True`` (with ``name="..."``) - idempotent: a read-only
      probe first; if the client already exists, returns immediately having
      done nothing; otherwise seeds it. For expensive tests that reuse one
      FIXED payer name across runs and must not pile up duplicates (which
      would make the name ambiguous and fail the test for the wrong reason).

    Existence is decided ONLY by ``_resolve_client_name(...).exists`` (a
    genuine EXACT `resolve_client_name` match) - zero / single-non-exact /
    ambiguous all mean "does not exist as queried", never parsed from the
    model's free text (user, 2026-08-12: "WHEN AN AMBIGUOUS REPLY RETURNS IT
    MEANS THE CLIENT AS REQUESTED DOES NOT EXIST").

    add_client is Feature 026's exception to "always require an exact
    resolved match" (its whole purpose is to create a client that does NOT
    exist yet - runtime_constitution.md's "Exception when the underlying
    request is to ADD a NEW client", tightened bugfix-045). On a non-exact
    resolve during creation with no pending approval yet, one explicit
    "לא, תוסיף לקוח חדש בשם X, מייל ..., טלפון ..." turn forces the
    create-new intent through by name (restating email/phone, which the
    model otherwise re-asks for) rather than guessing whether a bare "כן"
    answers whatever the disambiguation question was. Then up to two "כן"
    turns approve the pending `add_client`. A non-exact candidate that still
    fails to complete `add_client` after that is a REAL failure (raises, never
    silently retried) - that silent retry is what buried the bugfix-045
    regression for weeks. `time.sleep(3)` after a successful create covers
    Morning's search-index lag so the client resolves on the very next turn.
    """
    import denidin

    drawn = name is None
    attempts = max_attempts if drawn else 1

    for attempt in range(1, attempts + 1):
        candidate = name_factory() if drawn else name
        assert candidate

        if not create or ensure_exists:
            _, probe_ai = _send_turn(
                chat_id=chat_id,
                text=f"פרטים על הלקוח {candidate}",
                id_prefix=f"{id_prefix}_PROBE_A{attempt}",
            )
            exists = _resolve_client_name(
                initial_result=(None, probe_ai), drive=False
            ).exists
            if not create:
                if not exists:
                    return candidate, None, None
                logger.warning(
                    f"_seed_client(create=False): {candidate!r} already exists - redrawing"
                )
                continue
            if exists:  # ensure_exists and the client is already there
                return candidate, None, None

        seed_email = email or _random_seed_email()
        first_text = text or (
            f"תוסיף לקוח חדש בשם {candidate}, מייל {seed_email}, טלפון {phone}"
        )
        response, ai_response = _send_turn(
            chat_id=chat_id, text=first_text, id_prefix=f"{id_prefix}_SEED_A{attempt}"
        )

        # Classify the seed turn's resolve_client_name outcome through the ONE
        # shared classifier. A genuine EXACT match is a real collision with a
        # pre-existing client - drawn names redraw, a caller-fixed name raises
        # (never approve an update to an unrelated client - bugfix-045).
        seed_res = _resolve_client_name(
            initial_result=(response, ai_response), drive=False
        )
        if seed_res.exists:
            if drawn:
                logger.warning(
                    f"_seed_client: attempt {attempt} name {candidate!r} is an EXACT "
                    f"match for a real existing client - redrawing (never approving an "
                    f"update to an unrelated client)."
                )
                continue
            raise ClientAlreadyExistsError(
                f"_seed_client: target name {candidate!r} is a real, pre-existing "
                f"exact-match client - refusing to proceed (never approving an update "
                f"to an unrelated client). mcp_calls: "
                f"{ai_response.mcp_calls if ai_response else None!r}"
            )

        # Not an EXACT collision (handled above). The model may have surfaced a
        # SIMILAR client (SINGLE / MULTI), reported not-found, or asked a
        # free-text "which one / create new?" question - in EVERY one of those
        # cases the create-new intent is pushed through the SAME single way:
        # one explicit reply naming the new client and restating email + phone
        # (which the model otherwise re-asks for). That one reply correctly
        # answers a one-candidate confirmation, a multi-candidate list, and a
        # free-text "pick 1/2/3" alike - it rejects every existing candidate BY
        # NAME, so a bare "כן" can never be read as "yes, use that existing
        # client instead" (bugfix-045). Sent whenever nothing has been created
        # and no approval is pending yet - NOT gated on whether a
        # resolve_client_name call fired (the model often disambiguates in
        # plain text with no fresh call; gating on that dead-ended the seed -
        # 2026-09-02).
        add_calls = _calls_for(ai_response, "add_client")
        already_succeeded = bool(add_calls and add_calls[0]["error"] is None)
        pending = denidin.denidin_app.ai_handler.pending_approval_manager.get(chat_id)
        if not already_succeeded and pending is None:
            force_new_text = (
                f"לא, תוסיף לקוח חדש בשם {candidate}, מייל {seed_email}, טלפון {phone}"
            )
            response, ai_response = _send_turn(
                chat_id=chat_id, text=force_new_text,
                id_prefix=f"{id_prefix}_FORCE_NEW_A{attempt}",
            )
            if _resolve_client_name(
                initial_result=(response, ai_response), drive=False
            ).exists:
                if drawn:
                    logger.warning(
                        f"_seed_client: attempt {attempt} name {candidate!r} EXACT match "
                        f"on the force-new turn - redrawing."
                    )
                    continue
                raise ClientAlreadyExistsError(
                    f"_seed_client: target name {candidate!r} is a real, pre-existing "
                    f"exact-match client (seen on the force-new turn). mcp_calls: "
                    f"{ai_response.mcp_calls if ai_response else None!r}"
                )

        for _ in range(3):
            add_calls = _calls_for(ai_response, "add_client")
            if add_calls and add_calls[0]["error"] is None:
                time.sleep(3)
                return candidate, response, ai_response
            if _is_real_approval_prompt(response) or "לאישור" in (response or ""):
                approve_text = "כן"
            else:
                # Still being asked to choose - restate the create-new intent
                # by name rather than sending a bare "כן" that answers nothing.
                approve_text = (
                    f"לא, תוסיף לקוח חדש בשם {candidate}, מייל {seed_email}, "
                    f"טלפון {phone}"
                )
            response, ai_response = _send_turn(
                chat_id=chat_id, text=approve_text,
                id_prefix=f"{id_prefix}_APPROVE_A{attempt}"
            )

        add_calls = _calls_for(ai_response, "add_client")
        if add_calls and add_calls[0]["error"] is None:
            time.sleep(3)
            return candidate, response, ai_response

        raise AssertionError(
            f"_seed_client: name {candidate!r} - add_client did not complete cleanly "
            f"after a create-new reply and approval turns. A real bug, not a name "
            f"collision to retry past: {ai_response.mcp_calls if ai_response else None!r}"
        )

    raise RuntimeError(
        f"_seed_client: could not obtain a "
        f"{'vacant' if not create else 'freshly-seeded'} client name after "
        f"{attempts} attempts (every attempt hit a real EXACT-match collision)"
    )


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
# create_combo_document_as_reference) creates a Morning document when it executes (an
# invoice, a linked Receipt, a linked combo document, or a linked Credit
# Invoice - there is no "status change" that isn't also document creation;
# update_invoice_status, which used to be one more tool in this list, was
# removed entirely by feature 023), so all of them require an explicit
# approval turn before they execute. Tests exercising any of these tools use
# `_send_turn_and_approve`/`_send_turn_and_decline` instead of a bare
# `_send_turn`, and are genuinely two-turn.
