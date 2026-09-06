"""E2E Tests (Feature 018 + bugfix-011/013/014 + Feature 038): list_invoices,
analytical/aggregate questions, client-name transcription/date-range
handling, and the "all payments" completeness regression - real webhook,
real OpenAI Responses API, real Morning MCP server, real Morning sandbox.

Split (2026-08-04, Feature 038, human-approved T012/T013) from the former
single test_denidin_morning_mcp_e2e.py - see
test_denidin_morning_invoice_creation_e2e.py's module docstring for the full
split rationale and shared-fixture/helper locations (this directory's
conftest.py for fixtures, denidin_mcp_e2e_helpers.py for helpers/constants).

list_invoices/get_financial_summary are read-only, no approval wait
(NO_APPROVAL_MCP_TOOLS) - every test below is single-turn.

**Feature 038 additions (2026-08-04)**: list_invoices' fetch/display
behavior changed (10-item display cap -> 100-item fetch cap +
token-budget-aware display truncation, see
specs/in-progress/038-morning-long-list-support/) - the 3 new tests at the
end of this file verify that change end-to-end, at the layer that actually
matters: what the model actually says to the user, not just the raw tool
output (per explicit user direction during that feature's test-plan
review).

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run,
can be run freely - no per-run approval, no one-at-a-time restriction (see
CLAUDE.md/CONSTITUTION §VII).
"""
from __future__ import annotations

import json

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _HEBREW_FIRST_NAMES,
    _calls_for,
    _random_amount,
    _random_description,
    _resolve_client_name,
    ResolveOutcome,
    pick_existing_client,
    _send_turn,
    _send_turn_and_approve,
)

# ============================================================================
# list_invoices
# ============================================================================

# Fixed, genuinely closed historical date in the Morning sandbox (verified
# free, no billing, 2026-07-13): exactly 6 real invoices exist for this date,
# being months in the past it will never gain more invoices (unlike "today").
#
# FEATURE 038 FLAG (2026-08-04): this comment previously said these 6 items
# stay "well under list_invoices' 10-item display cap, so nothing is
# truncated" - true under the OLD (pre-038) behavior, but Feature 038
# replaces that item-count cap with a token-budget-based display truncation
# (_LIST_INVOICES_TOKEN_BUDGET = 800; research.md Decision 6 measured real
# invoice blocks here at ~270 tokens each, so 6 of them - ~1620 tokens -
# will likely NOT all fit once Feature 038 ships). The assertion below
# ("at least 2 of these 2 specific numbers, first and last of the 6") may
# start failing once the morning-mcp-app-dev container this test runs
# against is rebuilt with the Feature 038 fix (not yet done as of this
# comment - the shared dev container still runs pre-038 code, so this
# existing test is UNCHANGED and still expected to pass right now). Flagged
# here for whoever runs this test after that rebuild: if it fails, this is
# the expected reason, and updating this specific assertion for the new
# truncation model needs its own explicit human approval (CONSTITUTION
# §VIII), not a silent fix.
KNOWN_FIXED_DATE = "2026-02-07"
KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE = ("60001", "60006")  # first and last of the 6


@pytest.mark.billed
@pytest.mark.sanity
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

    # Tool correctness: real, known ground truth in the tool's own output
    # (JSON per the 2026-09-04 contract - assert on the parsed fields, not
    # prose markers that no longer exist in the output).
    combined_output = "\n".join(c["output"] or "" for c in list_calls)
    docs = [
        d
        for c in list_calls if c["output"]
        for d in json.loads(c["output"]).get("documents", [])
    ]
    found_numbers = [
        n for n in KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE
        if any(str(d.get("display_number")) == n for d in docs)
    ]
    assert len(found_numbers) >= 2, (
        f"Expected at least 2 known invoice numbers {KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE} "
        f"in the tool output, found {found_numbers}. Tool output: {combined_output!r}"
    )
    assert all(d.get("amount") is not None for d in docs), (
        f"Tool output missing amount field: {combined_output!r}"
    )
    assert all(d.get("internal_morning_id") for d in docs), (
        f"Tool output missing invoice id field: {combined_output!r}"
    )
    assert all(d.get("status_label") for d in docs), (
        f"Tool output missing status field: {combined_output!r}"
    )


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
# The un-polluted real sandbox client. "זהבית" alone is ambiguous - the sandbox
# also holds junk "זהביתDENIDIN_039_T1_<ts> צור" clients from old Feature 039
# runs (that marker-in-name pattern was removed from _unique_client_name on
# 2026-08-03, so this is a fixed pool of pre-existing debris, not a live leak).
# Both tests below therefore drive resolve_client_name's MULTI_CANDIDATE outcome
# to a settled identity with this exact name, via the shared _resolve_client_name
# helper, before asserting anything about list_invoices.
_ZEHAVIT_REAL_CLIENT = "זהבית צור"


def _drive_zehavit_to_list_invoices(id_prefix: str):
    """Send the exact bugfix-013 incident message, resolve the (ambiguous, in the
    polluted sandbox) client identity to `_ZEHAVIT_REAL_CLIENT` via the shared
    `_resolve_client_name` drive loop, and return
    ``(first_turn_ai, resolved_name, list_calls, final_ai, final_reply)`` -
    where `first_turn_ai` is the model's response to the raw incident message
    (for the verbatim-transcription check) and `list_calls` is guaranteed
    non-empty on success."""
    first_reply, first_turn_ai = _send_turn(
        chat_id=GODFATHER_CHAT_ID, text=_ZEHAVIT_MESSAGE, id_prefix=id_prefix
    )
    assert first_reply is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"

    res = _resolve_client_name(
        chat_id=GODFATHER_CHAT_ID,
        id_prefix=id_prefix,
        initial_result=(first_reply, first_turn_ai),
        disambiguator=_ZEHAVIT_REAL_CLIENT,
        drive=True,
    )
    assert res.final_outcome is ResolveOutcome.EXACT, (
        f"client identity never resolved to a single client: "
        f"final_outcome={res.final_outcome}, reply={res.reply!r}"
    )

    final_ai, final_reply = res.ai_response, res.reply
    list_calls = _calls_for(final_ai, "list_invoices")
    if not list_calls:
        # identity settled but the model hasn't listed yet - one more turn on
        # the same (still date-free, still "תן לי הכל") request.
        final_reply, final_ai = _send_turn(
            chat_id=GODFATHER_CHAT_ID, text=_ZEHAVIT_MESSAGE, id_prefix=f"{id_prefix}_LIST"
        )
        list_calls = _calls_for(final_ai, "list_invoices")

    assert list_calls, (
        f"Model never reached list_invoices even after identity resolved to "
        f"{res.resolved_name!r}. mcp_calls: {final_ai.mcp_calls if final_ai else None!r}. "
        f"Final reply: {final_reply!r}"
    )
    return first_turn_ai, res.resolved_name, list_calls, final_ai, final_reply


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
    first_turn_ai, resolved_name, list_calls, final_ai, _ = (
        _drive_zehavit_to_list_invoices("E2E_BUGFIX013_NAME")
    )

    # bugfix-013's garble check: the model transcribes "זהבית" out of the user's
    # free-text sentence into its FIRST structured client reference. Today that
    # is the mandatory resolve_client_name call (Feature 027); pre-027 it was
    # list_invoices directly. That first transcription is what garbled live
    # ("זהבית" -> "זבית", dropped ה) and it must be verbatim.
    first_ref = None
    for call in (first_turn_ai.mcp_calls if first_turn_ai else []):
        try:
            args = json.loads(call["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        first_ref = args.get("name") or args.get("client_name")
        if first_ref:
            break
    assert first_ref == _ZEHAVIT_NAME, (
        f"Client name garbled: the model's first client reference was "
        f"{first_ref!r}, expected {_ZEHAVIT_NAME!r} verbatim "
        f"(mcp_calls: {first_turn_ai.mcp_calls if first_turn_ai else None!r})"
    )

    # And no garble introduced downstream either: the resolved client name must
    # reach list_invoices verbatim too.
    transcribed_names = []
    for call in list_calls:
        try:
            args = json.loads(call["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        transcribed_names.append(args.get("client_name"))
    assert any(name == resolved_name for name in transcribed_names), (
        f"Client name garbled downstream: identity resolved to {resolved_name!r} "
        f"but list_invoices got {transcribed_names!r} "
        f"(mcp_calls: {final_ai.mcp_calls if final_ai else None!r})"
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
    _, _, list_calls, final_ai, _ = _drive_zehavit_to_list_invoices("E2E_BUGFIX013_DATE")

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
            f"(mcp_calls: {final_ai.mcp_calls if final_ai else None!r})"
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
@pytest.mark.sanity
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

    KNOWN FAILURE — BLOCKED ON FEATURE 069 (do not "fix" here). Feature 059
    triage (2026-09-03): the model's answer is correct (full paid+unpaid
    picture), but `ai_handler.py` only harvests `mcp_call` items from the FINAL
    settled response, dropping the `list_invoices` call that ran inside an
    intermediate chained response in the `query_ledger_events` follow-up loop
    (Morning MCP server log proves it ran). So `ai_response.mcp_calls` — and
    this test's tool-call assertion — is incomplete. Feature 069
    (`specs/backlog/069-mandatory-client-resolution-before-ledger-event`)
    reworks this exact ledger/resolution code path; the call-accounting gap is
    expected to close with it. Left red on purpose until then — see
    `specs/done/v0.5.4/059-stabilize-tests-sanity-suite/sanity-failures.md` (S2).
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
# Feature 038 (2026-08-04): real-pagination fetch cap + token-budget display
# truncation, verified end-to-end through the real conversational layer -
# what the model actually tells the user, not just the raw tool output.
#
# REQUIRES the morning-mcp-app-dev container to be rebuilt+restarted with
# the Feature 038 fix before these will pass for real (CLAUDE.md: code
# changes in apps/morning-mcp-app have no effect on an already-running
# container). That rebuild/restart is a separate, explicit
# environment-start action requiring its own human approval - these tests
# are written now (RED, per METHODOLOGY §VI) but must not be run for real
# until that approval is given and the rebuild has happened.
#
# Real, already-existing sandbox date ranges (no invoices seeded) - found
# via a live probe, specs/in-progress/038-morning-long-list-support/research.md
# Decisions 4/6. Re-probe with the same method if the sandbox's data ever
# changes enough that these totals drift from what's asserted below.
# ============================================================================

_038_LARGE_IN_CAP_RANGE_HE = "בין ה-19 ליולי לבין ה-21 ליולי"
_038_LARGE_IN_CAP_TOTAL = 81
_038_OVER_CAP_RANGE_HE = "בין ה-13 ליולי לבין ה-15 ליולי"
_038_OVER_CAP_TOTAL = 103
_038_PARTIAL_PREFIX_RANGE_HE = "בין ה-21 ליולי לבין ה-22 ליולי"
_038_PARTIAL_PREFIX_TOTAL = 13


@pytest.mark.billed
def test_godfather_asks_for_large_in_cap_invoice_range(denidin_app):
    """US1 (spec.md SC-006): a query whose real total (81) is well within
    the 100-item fetch cap must be fetched completely, and the model's
    FINAL WhatsApp reply (not just the raw mcp_call output) must state a
    total consistent with 81 - not a smaller number the model might
    otherwise infer from only seeing the handful of items that fit within
    the 800-token display budget. Direct regression test for "the model is
    bad at counting/summing" (the user's original concern motivating
    REQ-INVOICE-004/008/009)."""
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"כמה חשבוניות יש לי {_038_LARGE_IN_CAP_RANGE_HE}?",
        id_prefix="E2E_038_LARGE_IN_CAP",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"Model never invoked list_invoices for the large in-cap range request. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert str(_038_LARGE_IN_CAP_TOTAL) in response, (
        f"Expected the real total ({_038_LARGE_IN_CAP_TOTAL}) to appear in the model's "
        f"FINAL reply (what the user actually sees), not just the tool output. "
        f"Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_asks_for_over_cap_invoice_range(denidin_app):
    """US2: a query whose real total (103) exceeds the 100-item fetch cap
    must produce a refusal/narrow-your-search reply from the model, not a
    fabricated or partial itemized list - the model must relay the tool's
    refusal faithfully rather than inventing its own summary of results it
    was never given."""
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תראה לי את כל החשבוניות {_038_OVER_CAP_RANGE_HE}",
        id_prefix="E2E_038_OVER_CAP",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"Model never invoked list_invoices for the over-cap range request. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert str(_038_OVER_CAP_TOTAL) in response, (
        f"Expected the real total ({_038_OVER_CAP_TOTAL}) to appear in the model's "
        f"FINAL reply. Full reply: {response!r}"
    )
    assert "חשבונית #" not in response, (
        f"Model's final reply looks like it fabricated/leaked an itemized invoice "
        f"list despite the tool's refusal. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_receives_partial_list_within_token_budget(denidin_app):
    """US3: a query whose real total (13) is well within the fetch cap but
    whose full formatted reply exceeds the 800-token display budget must
    produce a genuine partial count in the model's FINAL reply (shown < 13,
    shown > 0) - not a claim of having shown all 13, and not an invented
    count. This is the direct test of the user's original concern about
    model imprecision on counts, verified at the point that actually
    matters: what the user sees, not `ai_response.mcp_calls` alone (per
    explicit user direction during this feature's test-plan review)."""
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תראה לי את כל החשבוניות {_038_PARTIAL_PREFIX_RANGE_HE}",
        id_prefix="E2E_038_PARTIAL_PREFIX",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"Model never invoked list_invoices for the partial-prefix range request. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert str(_038_PARTIAL_PREFIX_TOTAL) in response, (
        f"Expected the real total ({_038_PARTIAL_PREFIX_TOTAL}) to appear in the "
        f"model's FINAL reply, even though not all of them are individually listed. "
        f"Full reply: {response!r}"
    )
    # The model must not claim completeness it doesn't have - a reply stating
    # "here are all 13" (or listing all 13 individually) would indicate it
    # either fabricated a complete-looking answer or the truncation/shown-vs-
    # total signal never reached it.
    shown_invoice_mentions = response.count("חשבונית #")
    assert shown_invoice_mentions < _038_PARTIAL_PREFIX_TOTAL, (
        f"Expected a genuine partial list in the final reply (fewer than "
        f"{_038_PARTIAL_PREFIX_TOTAL} individually mentioned), got "
        f"{shown_invoice_mentions}. Full reply: {response!r}"
    )




# ============================================================================
# Bugfix (2026-08-07): searching for an invoice by its number alone
# ("חפש לי את חשבונית X") - Morning's real /documents/search endpoint has
# always accepted a `number` filter; it was never wired up in list_invoices,
# so a bare-number reference had no real way to resolve once the sandbox
# grew past the fetch cap. Discovered via feature 027's test work.
# ============================================================================

@pytest.mark.billed
def test_godfather_searches_invoice_by_number_finds_it(denidin_app):
    """Positive case: godfather asks to find an invoice by its real number
    alone (no client name, no date) - the model must resolve it via
    list_invoices' number filter and show the real details, not refuse with
    a 'too many results' narrowing request."""
    amount = _random_amount()
    description = _random_description()
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: only the invoice must be fresh

    _, (seed_response, seed_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_NUMSEARCH_SEED",
    )
    create_calls = _calls_for(seed_ai_response, "create_invoice")
    assert create_calls and create_calls[0]["error"] is None, (
        f"Seed create_invoice failed: {seed_ai_response.mcp_calls if seed_ai_response else None!r}"
    )
    output = create_calls[0]["output"] or ""
    invoice_number = json.loads(output).get("display_number") if output else None
    assert invoice_number, f"Could not find invoice number marker in output: {output!r}"
    invoice_number = str(invoice_number)

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"חפש לי את חשבונית מספר {invoice_number}",
        id_prefix="E2E_NUMSEARCH_FIND",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert list_calls, (
        f"Model never invoked list_invoices for a bare invoice-number search: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    assert "יותר מדי" not in response and "לצמצם" not in response, (
        f"Bot refused to narrow a search that already gave an exact number: {response!r}"
    )
    assert invoice_number in response, (
        f"Bot reply did not surface the found invoice's number {invoice_number!r}: {response!r}"
    )
    assert client_name in response, (
        f"Bot reply did not surface the found invoice's real client name: {response!r}"
    )


@pytest.mark.billed
def test_godfather_searches_invoice_by_number_not_found_is_friendly(denidin_app):
    """Negative case: godfather asks for an invoice number that doesn't
    exist - no crash, no fabricated result, a clear 'not found' reply."""
    bogus_number = "88887777"

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"חפש לי את חשבונית מספר {bogus_number}",
        id_prefix="E2E_NUMSEARCH_NOTFOUND",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert "Traceback" not in response
    assert bogus_number not in response or "לא נמצא" in response or "לא מצאתי" in response, (
        f"Expected a friendly 'not found' reply for a nonexistent invoice number: {response!r}"
    )
