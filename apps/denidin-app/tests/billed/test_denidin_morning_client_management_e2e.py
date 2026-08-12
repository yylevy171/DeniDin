"""E2E Tests (Feature 026): client management - list_clients, get_client_details,
update_client, fuzzy name matching, RBAC denial - real webhook, real OpenAI
Responses API, real Morning MCP server, real Morning sandbox.

Split (2026-08-04, Feature 038, human-approved T012/T013) from the former
single test_denidin_morning_mcp_e2e.py - see
test_denidin_morning_invoice_creation_e2e.py's module docstring for the full
split rationale and shared-fixture/helper locations (this directory's
conftest.py for fixtures, denidin_mcp_e2e_helpers.py for helpers/constants).

list_clients/get_client_details are read-only, no approval wait
(NO_APPROVAL_MCP_TOOLS). update_client mutates a client record, so it
requires explicit approval (APPROVAL_REQUIRED_MCP_TOOLS, Feature 026) -
see `_send_turn_and_approve`/`_send_turn_and_decline`.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run,
can be run freely - no per-run approval, no one-at-a-time restriction (see
CLAUDE.md/CONSTITUTION §VII).
"""
from __future__ import annotations

import random
import re
import time

import pytest

from .denidin_mcp_e2e_helpers import (
    BLOCKED_ROLE_CHAT_ID,
    CLIENT_ROLE_CHAT_ID,
    GODFATHER_CHAT_ID,
    _HEBREW_FAMILY_NAMES,
    _HEBREW_FIRST_NAMES,
    _HEBREW_NAME_SPELLING_VARIANTS,
    _SEED_PHONE,
    _calls_for,
    _complete_add_client_flow,
    _normalize_hebrew_geresh,
    _random_seed_email,
    _seed_fresh_client,
    _seeded_email_from,
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_decline,
)

def _single_word_first_name() -> str:
    """A first name from the pool guaranteed not to itself contain a space -
    a handful of real entries are two words (e.g. "בת שבע", "יעקב יוסף") -
    needed by tests that build a prefix out of "the first name" specifically,
    where a compound entry would make that operation meaningless."""
    name = random.choice(_HEBREW_FIRST_NAMES)
    while " " in name:
        name = random.choice(_HEBREW_FIRST_NAMES)
    return name


def _single_word_family_name() -> str:
    """Same as `_single_word_first_name`, for family names (e.g. "אבו ליל",
    "אבו רוקן" are real two-word pool entries)."""
    name = random.choice(_HEBREW_FAMILY_NAMES)
    while " " in name:
        name = random.choice(_HEBREW_FAMILY_NAMES)
    return name


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
    # _seed_fresh_client already sleeps for the search-index lag (research.md
    # Decision 8) on a successful seed - no need to sleep again here.
    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="E2E_LIST_CLIENTS_SEED")

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
    # _seed_fresh_client already sleeps for the search-index lag (research.md
    # Decision 8) on a successful seed - no need to sleep again here.
    client_name, _, seed_ai_response = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="E2E_CLIENT_DETAILS_SEED")
    seed_email = _seeded_email_from(seed_ai_response)

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
    # _seed_fresh_client already sleeps for the search-index lag (research.md
    # Decision 8) on a successful seed - no need to sleep again here.
    client_name, _, seed_ai_response = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="E2E_UPDATE_CLIENT_SEED")
    seed_email = _seeded_email_from(seed_ai_response)

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
    # _seed_fresh_client already sleeps for the search-index lag (research.md
    # Decision 8) on a successful seed - no need to sleep again here.
    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="E2E_UPDATE_DECLINE_SEED")

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

    # _complete_add_client_flow drives each seed through to a real add_client
    # success regardless of how many turns that takes - a plain approval, or
    # a forced "create new" turn if this literal name non-exactly collides
    # with an unrelated real sandbox client (found live, 2026-08-12: name_a
    # collided with a real "נעים צרפתי" and the old raw 2-turn seed here had
    # no way to answer that disambiguation question).
    email_a = _random_seed_email()
    email_b = _random_seed_email()
    seed_a_response, seed_a_ai_response = _complete_add_client_flow(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {name_a}, מייל {email_a}, טלפון {_SEED_PHONE}",
        client_name=name_a,
        id_prefix="E2E_UPDATE_AMBIG_SEED_A",
        email=email_a,
        phone=_SEED_PHONE,
    )
    seed_b_response, seed_b_ai_response = _complete_add_client_flow(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {name_b}, מייל {email_b}, טלפון {_SEED_PHONE}",
        client_name=name_b,
        id_prefix="E2E_UPDATE_AMBIG_SEED_B",
        email=email_b,
        phone=_SEED_PHONE,
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
    # _seed_fresh_client draws the family name itself (via name_factory) and
    # retries with a new one if a particular draw collides with an existing
    # real sandbox client - never asserts on the seeding turn itself, only
    # on the end state. male_spelling is fixed (needed for the test's own
    # spelling-variant premise); only the family name is redrawn on retry.
    seed_name, _, _ = _seed_fresh_client(
        GODFATHER_CHAT_ID,
        id_prefix="E2E_HEBREW_VARIANT_SEED",
        name_factory=lambda: f"{male_spelling} {random.choice(_HEBREW_FAMILY_NAMES)}",
    )
    family_name = seed_name.split()[-1]
    query_name = f"{chaser_spelling} {family_name}"

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
def test_godfather_get_client_details_resolves_ambiguous_first_name_prefix_after_confirmation(denidin_app):
    """client-name-resolution architecture fix (2026-08-12): get_client_details
    itself never resolves a partial/prefix reference anymore (superseding the
    old test of the same shape, which asserted the OLD architecture's
    single-turn disclosure - obsolete, since get_client_details now requires
    an already-exact name and does zero matching of its own). The real flow
    is two turns: (1) a partial first-name reference is one missing piece of
    information - the exact client identity - so the model must call
    resolve_client_name, get a non-exact single match, and relay its
    confirmation question rather than silently proceeding or guessing; (2)
    once the godfather confirms, the model must actually resolve and THEN
    retrieve the real details - proven by the seeded email appearing in the
    final reply, not just the name being echoed back."""
    # _seed_fresh_client draws its own fresh first+family name pair and
    # retries with a new one if a particular draw collides with an existing
    # real sandbox client - never asserts on the seeding turn itself, only
    # on the end state (a fresh client genuinely exists before the real test
    # begins). A custom name_factory keeps the first name single-word (a
    # handful of pool entries are themselves two words, e.g. "בת שבע") - this
    # test's whole premise is truncating THE first name to build a prefix,
    # which only means something for a single-word first name.
    full_name, _, seed_ai_response = _seed_fresh_client(
        GODFATHER_CHAT_ID,
        id_prefix="E2E_RESOLVE_FIRSTNAME_SEED",
        name_factory=lambda: f"{_single_word_first_name()} {random.choice(_HEBREW_FAMILY_NAMES)}",
    )
    seed_email = _seeded_email_from(seed_ai_response)
    first_name = full_name.split(maxsplit=1)[0]
    # Only a prefix of the first name, alone - Morning's phrase-prefix search
    # only allows the LAST word of a query to be partial (confirmed live),
    # so a truncated first name followed by the full family name would not
    # match at all; querying with just the truncated first name (a single,
    # standalone word) does.
    first_name_prefix = first_name[: max(2, len(first_name) - 2)]

    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {first_name_prefix}",
        id_prefix="E2E_RESOLVE_FIRSTNAME_ASK",
    )

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ask_ai_response, "get_client_details"), (
        f"get_client_details executed on the ambiguous ASK turn, before the "
        f"godfather confirmed which client was meant: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    # Morning geresh-normalizes any apostrophe in a stored name (e.g. "ריצ'רד"
    # -> "ריצ׳רד") - resolve_client_name's confirmation question quotes
    # Morning's own normalized form, not our raw generated full_name.
    assert _normalize_hebrew_geresh(full_name) in ask_response, (
        f"Expected resolve_client_name's confirmation question to name the "
        f"full resolved client {full_name!r} (not just echo the prefix "
        f"{first_name_prefix!r} the user typed) - got: {ask_response!r}"
    )

    confirm_response, confirm_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_RESOLVE_FIRSTNAME_CONFIRM",
    )

    assert confirm_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert _calls_for(confirm_ai_response, "get_client_details"), (
        f"Model never actually retrieved the client's details once the "
        f"identity was confirmed: "
        f"{confirm_ai_response.mcp_calls if confirm_ai_response else None!r}"
    )
    assert seed_email in confirm_response, (
        f"Expected the client's own seeded email {seed_email!r} in the final "
        f"reply - proof of a genuine detail retrieval after confirmation, "
        f"not just the name echoed back: {confirm_response!r}"
    )


@pytest.mark.billed
def test_godfather_update_client_resolves_ambiguous_family_name_prefix_after_confirmation(denidin_app):
    """Same corrected flow as the get_client_details test above, but for
    update_client - which additionally requires its own mutation approval
    (Feature 022), separate from and after the identity confirmation.

    Real failure (2026-08-13, take 1): this test used to assume exactly one
    identity-confirmation round before approval (ASK, one "כן" as CONFIRM,
    one more "כן" as APPROVE) - but a live run needed TWO confirmation
    rounds: the model's first reply was an open "did you mean X, or create a
    new one named Y?" question, which a bare "כן" cannot correctly answer
    (it isn't a yes/no question). The model correctly recognized this and
    re-asked a real yes/no identity question instead of guessing which
    option "כן" meant - good, cautious behavior, not a bug.

    Real failure (2026-08-13, take 2): answering every pre-approval round
    with a blind "כן" doesn't work either - a second live run's family-name
    prefix collided with a real PRE-EXISTING client sharing the same family
    name (not just the freshly-seeded one), so the model kept asking a
    genuine pick-one-of-N question ("למי התכוונת: X או Y?") that "כן" can
    never answer, no matter how many rounds are allowed. Fixed: every
    pre-approval round now answers with the literal originally-seeded
    `full_name` instead of "כן" - unambiguous for both question shapes (a
    yes/no "did you mean X?" and a "pick one of X/Y" alike), since it's
    always a valid, exact answer to "which client did you mean."

    So a fixed turn count is the wrong shape for this flow: however many
    identity-resolution rounds it takes, only the REAL mutation-approval
    prompt matters, and it's reliably identifiable by its own fixed shape -
    it always contains all three of "לאישור", "כן", and "לא" together (the
    "אישור — כן/לא?" gate a genuine yes/no question always ends with). This
    test keeps answering with the exact client name until a response with
    that shape shows up (capped at MAX_PRE_APPROVAL_ROUNDS rounds - if it
    never arrives, or any tool call along the way errors, or update_client
    fires before the real approval round, that's a genuine failure), then
    sends a final "כן" to actually approve it (the real yes/no gate, where
    "כן" is finally the correct answer) - verified independently via a
    follow-up get_client_details call, not just trusted from the model's
    own claim."""
    # _seed_fresh_client draws its own fresh first+family name pair and
    # retries with a new one if a particular draw collides with an existing
    # real sandbox client - never asserts on the seeding turn itself, only
    # on the end state. A custom name_factory keeps the family name
    # single-word (a handful of pool entries are themselves two words, e.g.
    # "אבו ליל") - this test's whole premise is truncating THE family name
    # to build a prefix, which only means something for a single-word
    # family name.
    full_name, _, _ = _seed_fresh_client(
        GODFATHER_CHAT_ID,
        id_prefix="E2E_RESOLVE_FAMILYNAME_SEED",
        name_factory=lambda: f"{random.choice(_HEBREW_FIRST_NAMES)} {_single_word_family_name()}",
    )
    family_name = full_name.split(maxsplit=1)[1]
    family_name_prefix = family_name[: max(2, len(family_name) - 2)]
    new_phone = "052-9876543"  # deliberately different from _SEED_PHONE, so a
        # real change is actually being requested

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תעדכן את הטלפון של {family_name_prefix} ל-{new_phone}",
        id_prefix="E2E_RESOLVE_FAMILYNAME_ASK",
    )

    MAX_PRE_APPROVAL_ROUNDS = 3
    round_num = 0
    while not (response and "לאישור" in response and "כן" in response and "לא" in response):
        assert response is not None, (
            f"CRITICAL: godfather got NO RESPONSE (silent drop) on "
            f"pre-approval round {round_num}"
        )
        for call in (ai_response.mcp_calls if ai_response else []):
            assert call.get("error") is None, (
                f"Unexpected tool error on pre-approval round {round_num}: {call!r}"
            )
        assert not _calls_for(ai_response, "update_client"), (
            f"update_client executed before the real approval prompt was "
            f"even reached (pre-approval round {round_num}): "
            f"{ai_response.mcp_calls if ai_response else None!r}"
        )
        round_num += 1
        assert round_num <= MAX_PRE_APPROVAL_ROUNDS, (
            f"The real mutation-approval prompt (containing \"לאישור\"/\"כן\"/"
            f"\"לא\" together) never arrived within {MAX_PRE_APPROVAL_ROUNDS} "
            f"pre-approval rounds - last response: {response!r}"
        )
        response, ai_response = _send_turn(
            chat_id=GODFATHER_CHAT_ID,
            text=full_name,  # exact name - unambiguous whether the model
                # asked a yes/no "did you mean X?" or a pick-one-of-N
                # question (a bare "כן" can't answer the latter at all)
            id_prefix=f"E2E_RESOLVE_FAMILYNAME_ROUND{round_num}",
        )

    # `response` now holds the real approval prompt itself - it must name
    # the resolved client, and must still not have executed anything.
    # Morning geresh-normalizes any apostrophe in a stored name - see the
    # matching comment in the get_client_details test above.
    assert _normalize_hebrew_geresh(full_name) in response, (
        f"Expected the real update_client PENDING-APPROVAL prompt to name "
        f"the resolved client {full_name!r} - got: {response!r}"
    )
    assert not _calls_for(ai_response, "update_client"), (
        f"update_client executed before explicit approval of the mutation "
        f"itself: {ai_response.mcp_calls if ai_response else None!r}"
    )

    approve_response, approve_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_RESOLVE_FAMILYNAME_APPROVE",
    )

    assert approve_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    update_calls = _calls_for(approve_ai_response, "update_client")
    assert update_calls and update_calls[0]["error"] is None, (
        f"update_client did not succeed on the APPROVE turn: "
        f"{approve_ai_response.mcp_calls if approve_ai_response else None!r}"
    )

    time.sleep(3)  # search-index lag (research.md Decision 8)

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {full_name}",
        id_prefix="E2E_RESOLVE_FAMILYNAME_VERIFY",
    )

    assert details_ai_response is not None
    assert _SEED_PHONE not in (details_response or ""), (
        f"sanity check: the seed phone {_SEED_PHONE!r} must not still be the "
        f"reported one - got: {details_response!r}"
    )
    assert "052-9876543" in (details_response or ""), (
        f"Expected the updated, normalized phone in the follow-up details "
        f"reply, got: {details_response!r}"
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


