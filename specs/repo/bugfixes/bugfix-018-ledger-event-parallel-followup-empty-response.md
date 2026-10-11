# Bugfix Spec: Ledger-Event Follow-Up Call Fails on Redundant Parallel Tool Calls, Leaving a Silent/Empty Reply

## Bug ID
bugfix-018-ledger-event-parallel-followup-empty-response

## Priority: P1

## Title
When the model spuriously calls `capture_ledger_event` multiple times in parallel within one turn, the follow-up API call that submits those tool outputs back to OpenAI can fail with a 400 error, leaving the user with a completely empty (0-char) WhatsApp reply despite tokens already being billed

## Status
Done - Merged to master (PR #179). Root cause confirmed via log inspection
(no new billed calls needed): 17 near-identical parallel `capture_ledger_event`
calls exceeded `max_output_tokens`, truncating the last call's arguments into
unparseable JSON; the follow-up submission silently dropped that call_id,
which OpenAI's real API rejected with 400, leaving a silently empty reply.
Fixed by treating any turn with more than one `capture_ledger_event` call, or
one with unparseable arguments, as an explicit protocol violation (rejected,
nothing persisted, every call_id resolved in the follow-up) plus a generic
fallback message for any other follow-up failure.

## Date Opened
2026-07-30

## Reported By
yaronlev171 (found while running Feature 026's deferred expensive-test batch — see
`specs/in-progress/026-client-management/`)

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` — the ledger-event follow-up submission path
  (log tag `"Ledger-event follow-up call failed for request ..."`)
- The `capture_ledger_event` local function tool and its parallel-call handling
- Any conversation turn where the model calls `capture_ledger_event` more than once in the same
  turn (not specific to client-management requests, though first observed there)

## Description
While running Feature 026's deferred expensive-test batch, `test_godfather_finds_client_via_hebrew_vowel_variant`
failed on its first run: the godfather's message was a plain client-detail lookup
("פרטים על הלקוח דוד גרוזדוביץ'"), but the model additionally called the unrelated
`capture_ledger_event` tool **three times in parallel** within the same turn — each of the three
calls came back **self-annotated by the model itself** as a mistake:

```json
{"status": "captured", ..., "notes": "הודעה זו היא בקשה להצגת פרטי לקוח, ולא הצהרה על הסכם שכר
טרחה; אין ללכוד כאירוע — אין להשתמש בקריאה זו.", ...}
```
("This message is a request to show client details, not a fee-agreement declaration; this should
not be captured as an event — do not use this call.")

So the model correctly recognized each of the three calls was wrong — but made them anyway. When
`ai_handler.py` then tried to submit all three parallel tool outputs back to OpenAI in a follow-up
API call (to get the model's real final answer), that follow-up itself failed:

```
ERROR - Ledger-event follow-up call failed for request req_0f4656c9bd90:
Error code: 400 - {'error': {'message': 'No tool output found for function call
call_iDc4AW9VIWlxgQu9wNRFI5vN.', 'type': 'invalid_request_error', 'param': 'input', 'code': None}}
```

OpenAI rejected the follow-up because one of the three parallel function calls' outputs wasn't
correctly matched/included in the submission. The exception was caught and logged, but the
resulting `response_text` was left completely empty:

```
INFO - AI response generated for request req_0f4656c9bd90: 14634 tokens, 0 chars
```

The user received a blank WhatsApp message — 14,634 tokens were already billed with nothing to
show for it, and no fallback/error message was substituted.

A second run of the exact same test (different random input - a different Hebrew name pair from
the test's name pool, no code changes) **passed cleanly** - the model simply didn't call
`capture_ledger_event` at all that time, so the buggy follow-up-submission path was never
exercised. This is inherent LLM nondeterminism, not a flaky test - the underlying bug is real and
would recur under the same trigger (redundant parallel ledger-event calls).

## Root Cause Analysis
Confirmed via `logs/test_logs/test_denidin_morning_mcp_e2e.log` (no additional billed runs needed
to diagnose):

1. The model, for reasons not yet fully understood (possibly the "Ledger Event Recognition"
   guidance in `runtime_constitution.md` over-triggering on a message that merely *mentions* a
   client name), called `capture_ledger_event` three times in parallel for a message that was not
   actually a fee-agreement/ledger event.
2. `ai_handler.py`'s ledger-event follow-up mechanism (submits captured-event tool outputs back to
   OpenAI to get the model's real final text) does not correctly handle **multiple parallel**
   `capture_ledger_event` calls in the same turn - the follow-up submission omitted or mismatched
   at least one of the three calls' outputs, causing OpenAI to reject the entire follow-up request
   with an HTTP 400.
3. The follow-up failure was caught (logged as an `ERROR`), but no fallback text was substituted -
   `response_text` remained empty, and the empty string was sent to the user as-is.

**Not yet confirmed**: the exact reason the model called `capture_ledger_event` three times in
parallel in the first place (vs. the more common single call or zero calls). This may be a
separate, prompt-level over-triggering issue worth its own investigation, distinct from the
follow-up-submission bug itself.

## Steps to Reproduce
Not reliably reproducible on demand - depends on the model spontaneously making redundant parallel
`capture_ledger_event` calls, which is nondeterministic. Observed once in:
```
python3 -m pytest tests/expensive/test_denidin_morning_mcp_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant -v -m expensive
```
(requires fresh explicit approval per CLAUDE.md before any re-run attempt).

## Expected Behavior
- `capture_ledger_event` should not fire at all for a plain client-lookup request with no
  fee-agreement/payment content (separate, lower-priority concern - see "Not yet confirmed" above).
- Regardless of how many parallel `capture_ledger_event` calls occur in a turn, the follow-up
  submission to OpenAI must succeed (correctly matching every parallel call's output), OR, if the
  follow-up call fails for any reason, the user must never receive a silently empty reply - a
  friendly fallback message must be substituted, matching the existing pattern already used for
  the "model produced no narrating text alongside a pending approval" case
  (`_build_pending_approval_fallback_text`, added this same session for a related gap).

## Impact
- A real user could receive a completely blank WhatsApp reply after a real turn that consumed
  real tokens/billing, with no indication anything went wrong.
- Not specific to client-management requests - any turn where the model redundantly/parallel-calls
  `capture_ledger_event` is at risk, regardless of what the user actually asked about.

## Acceptance Criteria
- [ ] Root-cause the parallel-call follow-up submission bug precisely (which call's output is
      dropped/mismatched, and why) in `ai_handler.py`'s ledger-event follow-up code path.
- [ ] Fix the follow-up submission to correctly handle N parallel `capture_ledger_event` calls in
      one turn, not just the single-call case.
- [ ] Add a safety-net fallback (mirroring `_build_pending_approval_fallback_text`'s pattern): if
      the ledger-event follow-up call fails for any reason, substitute a friendly message instead
      of leaving `response_text` empty - never send a silently blank reply.
- [ ] Separately investigate (may become its own follow-up item, not necessarily blocking this
      bug's fix) why the model called `capture_ledger_event` three times in parallel for a message
      that wasn't a ledger event at all, despite each call's own output correctly flagging itself
      as a mistake.
- [ ] Verify the fix with a fresh, explicitly-approved expensive test run once a reliable
      reproduction or targeted unit test is available.
- [ ] No regression to the existing, working single-call `capture_ledger_event` follow-up path.

## References
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
- `apps/denidin-app/src/handlers/ai_handler.py` (ledger-event follow-up submission, and
  `_build_pending_approval_fallback_text` as the sibling pattern to mirror for a fallback)
- `apps/denidin-app/logs/test_logs/test_denidin_morning_mcp_e2e.log` (lines ~7684-7817, request
  `req_0f4656c9bd90`, 2026-07-30 14:21) - full captured evidence of the failure
- `specs/in-progress/026-client-management/research.md` Decision 13 (the related, already-fixed
  pending-approval fallback gap found in the same testing session)
- Discovered while running Feature 026's deferred expensive-test batch
  (`apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant`)

## Cost/Approval Note
The only run that reproduced this bug was already billed (14,634 tokens, req_0f4656c9bd90). Since
the bug is not reliably reproducible on demand, further diagnosis should rely on log inspection and
code review rather than repeated billed runs. Any future run of this or a related test requires
fresh explicit human approval per CLAUDE.md, same as every expensive test.
