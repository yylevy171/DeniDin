# Bugfix Spec: `list_reminders` spuriously invoked during an unrelated Morning-invoice turn, and a second orphaned function call breaks the whole reply

## Bug ID
bugfix-042-reminders-invading-unrelated-turns

## Title
On a GODFATHER turn asking Morning (invoice) list_invoices question with an explicit
"give me everything, no filtering" phrasing, the model called `list_reminders` (Feature 054, a
tool with nothing to do with invoicing) *in addition to* the correct `resolve_client_name` +
`list_invoices` MCP calls, in the same turn. The turn's `response.output` carried **two**
`function_call` items, but the app's follow-up-call machinery only resolves the first
`list_reminders` call id it finds and submits output only for that one — leaving the second
function call's id with no submitted output. The next OpenAI Responses API round-trip then
rejects the whole turn with `400 Bad Request: "No tool output found for function call
<id>"`, and the turn ends with `should_reply=True` but zero characters of reply text, so the
user gets a generic `"Sorry, I encountered an unexpected error. Please try again."` even
though the real invoice data (8 invoices, correctly resolved) was already sitting in the same
response, fully computed and discarded.

## Priority
P1 — reproduces reliably in a billed acceptance test (not a one-off flake), **and confirmed live
in production the previous morning** (see "Production Sighting" below) at a second, independent
call site (`_call_openai_ledger_followup_api`, Feature 024/033's ledger-event follow-up — not
just `_handle_list_reminders`). In production the effect was worse than the test's generic error
message: a real client-facing chat was interrupted mid-invoicing-flow with an **unsolicited
reminder-approval prompt** the user never asked for and had to explicitly decline before the
conversation could proceed. A tool-bearing feature (reminders) reaching into turns it has no
business in — and, via the same underlying orphaned-function-call defect, either silently
discarding a correct answer (test case) or interrupting a real user with an unwanted approval
request (production case) — is a real information-loss/reliability/UX bug on the money-facing
path, confirmed at two independent sites — same severity class as bugfix-041 (also
reminders/tool-boundary related, also found the same day).

## Status
Open — root cause investigated via a real billed test failure AND a real production incident
(see "Reproduction" and "Production Sighting" below); no fix designed or implemented yet. Per
Bug-Driven Development (METHODOLOGY.md §VII), next step is human approval of this root cause
before test-gap analysis or fix design begins.

## Date Opened
2026-08-24

## Reported By
yaronlev171 — surfaced by a genuine `billed`-tier acceptance-test failure during Feature 025's
12-test post-merge sweep, and independently corroborated live in production: "I also saw this in
production" — confirmed by reading `denidin-app-prod` logs for 2026-08-23 06:05–06:10 IL time
(see "Production Sighting").

## Affected Area
- `apps/denidin-app/config/runtime_constitution.md` — "Invoice Management Context (Morning)"
  already states explicitly (line ~194-197): *"Reminder tools are never in scope here either
  (see 'Reminder Management' below) — if a reply mid-invoicing-flow is ambiguous, resolve it as
  an invoicing question... never as an opening for a reminder or any other unrelated tool."*
  This instance is **not** an ambiguous-reply case — the turn was a first, unambiguous,
  explicit invoice-listing request ("תן לי את כל התשלומים שביצע דורית אשכנזי" — "give me all
  the payments Dorit Ashkenazi made") — so the existing carve-out's wording may not be reaching
  this shape of turn, or the model is simply not reliably following it (a known category of
  model-following risk, distinct from a missing rule).
- `src/handlers/ai_handler.py`:
  - `_handle_list_reminders` (~line 2203) / `extract_function_call_id` — extracts and resolves
    only the **first** matching `list_reminders` function call in `response.output`; has no
    awareness that a second, unrelated `function_call` item can also be present in the same
    `response.output` and needs its own tool-output submission before any follow-up round-trip
    can succeed.
  - `_call_openai_list_reminders_followup_api` (~line 2175) — submits `function_call_output`
    for exactly one `call_id`; the OpenAI Responses API requires an output for **every**
    pending function call in the chain before it will accept a follow-up, not just the one this
    method knows about.
  - This is a structural gap, not specific to `list_reminders` — the same pattern
    (single-call-id assumption) likely affects any turn where the model emits multiple
    `function_call` items of different tools in one response, regardless of which two tools
    they are. **Confirmed** by the production incident below: `_call_openai_ledger_followup_api`
    (~line 2719, Feature 024/033) already loops over *all* `capture_ledger_event` calls in a
    turn (`ledger_calls: List[Dict]` — its own docstring: *"OpenAI rejects the follow-up
    outright if any pending function call from that turn is left without a resolved output, so
    this must supply one `function_call_output` item per call"*) — but that awareness is scoped
    only to calls of its **own** tool family. It has no visibility into a `create_reminder` call
    also present in the same `response.output`, so the same class of orphaned-call 400 happens
    here too, for the exact reason its own docstring already describes as mandatory to avoid.

## Reproduction

Real billed acceptance test failure (Feature 025's post-merge 12-test sweep, run 4/12), fully
reproducible, not a flake:

```
tests/billed/test_denidin_morning_list_invoices_e2e.py::test_client_explicit_everything_request_gets_the_complete_picture
```

Turn: GODFATHER sends `"תן לי את כל התשלומים שביצע דורית אשכנזי"` ("give me all the payments
Dorit Ashkenazi made") — an explicit, standalone Morning invoice-listing request, nothing about
reminders anywhere in the message or (per the test's setup) the conversation so far.

From the app's own log (`ai_handler` — `_finalize_response`):

```
output item types=['mcp_list_tools', 'reasoning', 'mcp_call', 'mcp_call', 'reasoning',
                    'function_call', 'function_call'], output_text=''
```

The two `mcp_call`s are the correct, successful `resolve_client_name` +
`list_invoices` (confirmed via the same log line's `MCP calls for request ...`: both
completed, `list_invoices` returned all 8 real invoices with full detail). But
`response.output` also carries **two** `function_call` items — at least one of them
`list_reminders` (its follow-up handler fired: `_call_openai_list_reminders_followup_api:
call_id='call_r2nIeW6ntw9WBlTaKivXc731'`). The follow-up call it issued failed:

```
ERROR - [054] list_reminders follow-up call failed: Error code: 400 - {'error':
{'message': 'No tool output found for function call call_MEcI5XlUrEhXHwF2BlXJ0S1F.',
'type': 'invalid_request_error', 'param': 'input', 'code': None}}
```

Note the id in the error (`call_MEcI5XlUrEhXHwF2BlXJ0S1F`) is **different** from the id the
follow-up call itself was submitting output for (`call_r2nIeW6ntw9WBlTaKivXc731`) — i.e. a
*second*, still-unresolved function call is what OpenAI is rejecting the request over. The
exception is swallowed (`except Exception: return None`), so `_handle_list_reminders` returns
`None` and processing falls through as if nothing had gone wrong — except the turn now has no
text and `should_reply=True`, tripping `ValueError: AIResponse ... owes the user a reply ...
but carries no text`, caught by the outer handler and turned into the generic
`"Sorry, I encountered an unexpected error. Please try again."` sent to the user — discarding
the correctly-resolved 8-invoice answer entirely.

A secondary, masking bug in the test itself: `_assert_full_picture`'s failure-message
construction accesses `ai_response.mcp_calls` without checking `ai_response is not None`
first, producing `AttributeError: 'NoneType' object has no attribute 'mcp_calls'` on top of the
real assertion failure — noise on top of signal, not itself the bug, but worth fixing
alongside (test code, not production code).

## Production Sighting

Real `denidin-app-prod` logs, 2026-08-23 06:04–06:11 IL time (`docker --context denidin-winprod
compose -f docker/docker-compose.prod.yml logs --since/--until`), chat `120363210094632983@g.us`
("$$ גבייה אילה $$", ADMIN role), a genuine bank-deposit-driven invoicing flow, not a test:

1. `06:04:20`–`06:05:13` — an earlier, unrelated approval (a receipt for אתי אסולין) completes
   cleanly.
2. `06:05:25` (AUDIT-IN) — a real bank SMS/notification forwarded into the chat: an incoming
   transfer of ₪12,272.00 from "מקורות" (Mekorot), reference 3339. The model correctly captures
   this as a ledger event (`[024] capture_ledger_events_from_text` → `ledger_events_captured=1`,
   source `בנק`/`הפקדה`, `client_name='מקורות'`, `amount='₪12,272.00'`, `txn_date='2026-08-21'`).
3. `06:07:00`→`06:07:36` — the ledger-event follow-up correctly finds and reports back the
   matching open transaction account: *"מצאתי חשבון עסקה מתאים של מקורות: מספר מסמך 90188,
   סכום 12,272 ₪..."* ("Found a matching transaction account for Mekorot: document #90188,
   amount 12,272 ₪...").
4. `06:08:09`→`06:08:43` — user confirms; bot verifies the account and asks the one remaining
   real question needed to close it out: *"...כדי להפיק את חשבונית המס־קבלה המקושרת אליו, האם
   הסכום כולל מע״מ?"* ("...to produce the linked tax-invoice/receipt, is the amount VAT
   inclusive?").
5. `06:09:07` (AUDIT-IN) — user replies with a single word: **`"כולל"`** ("inclusive"). Nothing
   about reminders, nothing ambiguous — a direct answer to the VAT question just asked.
6. `06:09:41` — **the same bug, at the ledger-followup call site**:
   ```
   ERROR - Ledger-event follow-up call failed for request req_ba2dafb8da19: Error code: 400
   - {'error': {'message': 'No tool output found for function call
   call_pmrwrwKRyrdEyDqofrdygJLU.', 'type': 'invalid_request_error', 'param': 'input',
   'code': None}}
   ```
   That orphaned call_id (`call_pmrwrwKRyrdEyDqofrdygJLU`) is immediately revealed, one log line
   later, to belong to a **spontaneous, unsolicited `create_reminder` call** the model made in
   the very same turn as its VAT-question follow-up:
   ```
   [054] PendingLocalToolApprovalManager(...).set('120363210094632983@g.us',
   PendingLocalToolApproval(tool_name='create_reminder', ...,
   call_id='call_pmrwrwKRyrdEyDqofrdygJLU', arguments={'message_text':
   'תזכיר לי לבדוק את ההפקדה של מקורות בסך 12,272 ש״ח', 'schedule_type': 'one_time',
   'one_time_due_at': '2026-08-24T09:00:00+03:00', ...}))
   ```
   Unlike the test case, the app did **not** crash the turn here — a separate, unguarded code
   path (reminder-creation-proposal detection) still scans the *original* response for a
   `create_reminder` call regardless of whether the ledger follow-up succeeded, finds it, and
   proceeds to build a real pending approval from it.
7. `06:09:42` (AUDIT-OUT) — the real user is sent an actual WhatsApp interactive-buttons prompt
   they never asked for: *"📋 לאישור — תזכורת חדשה: טקסט: תזכיר לי לבדוק את ההפקדה של מקורות
   בסך 12,272 ש״ח, מועד: חד-פעמי, 24/08/2026 09:00 — אישור — כן/לא?"* ("New reminder for
   approval: 'remind me to check Mekorot's deposit of 12,272 ₪', one-time, 24/08/2026 09:00 —
   approve — yes/no?") — in direct response to the user simply having answered "inclusive" to a
   VAT question. The actual VAT answer/document-creation logic is not visible at all in this
   turn's reply — it was lost the same way as in the test (swallowed by the failed follow-up),
   except here the reminder-approval flow filled the silence instead of a generic error.
8. `06:10:08` — user has to notice this is not what they asked for and explicitly declines via
   the "לא" (no) button; this reads (`_resolve_pending_local_tool_approval`,
   `is_affirmative=False`) as a normal decline, and the app "falls through to a fresh turn."
9. `06:10:21`→`06:10:33` — only on this **next, fresh** turn does the real, originally-requested
   action finally happen: the linked receipt/tax-invoice is created and reported —
   *"התזכורת לא נוצרה. הופקה חשבונית מס/קבלה מספר 112309 למקורות, בסך 12,272 ₪ כולל מע״מ..."*
   ("The reminder was not created. Tax-invoice/receipt #112309 was issued for Mekorot,
   12,272 ₪ including VAT...").

**Net effect on a real client-facing chat**: a straightforward one-word VAT answer, in the
middle of an otherwise perfectly-handled bank-deposit reconciliation flow, was silently derailed
into an unwanted reminder-approval request that the user had to actively notice and reject
before the real, correct action (already fully computed and ready, per step 4-5's own
information) could reach them — roughly a minute of avoidable back-and-forth, in a workflow
whose whole purpose is fast, low-friction bookkeeping.

## Related Work
- `specs/bugfixes/bugfix-041-no-reply-silently-skips-ledger-relevant-content.md` — same day,
  same general class (a tool-bearing feature's boundary with another context not holding up
  under a real turn), opposite direction: 041 is a tool that *should* have fired and didn't,
  042 is a tool that *shouldn't* have fired but did anyway (and then broke the turn that should
  have succeeded cleanly).
- CLAUDE.md's "EVERY NEW TOOL-BEARING FEATURE NEEDS EXPLICIT CONSTITUTION BOUNDARIES" banner —
  the constitution boundary for this exact scenario (reminders vs. invoicing) is **already
  present** (unlike the gap that banner was originally written about), so this is evidence the
  gap can persist even with an explicit cross-reference in place — either the wording needs to
  be stronger/reach this phrasing, or the fix needs to be structural (code-level defense against
  multiple simultaneous function calls of different tools), or both.

## Next Steps (per Bug-Driven Development, METHODOLOGY.md §VII)
1. Human approval of this root cause (this document).
2. Test-gap analysis — this was caught by an existing acceptance test (good), but there is no
   dedicated regression test yet asserting the code's behavior when a response carries function
   calls for two *different* local/tool-families in one turn; needs one. Should cover **both**
   confirmed call sites (`_handle_list_reminders` and `_call_openai_ledger_followup_api`), since
   the production sighting proves the defect isn't confined to one follow-up handler.
3. Design a fix — open questions, not yet decided:
   - Should the constitution's existing carve-out be strengthened (e.g. explicit anti-example
     covering this exact "give me everything" phrasing), reducing how often the model reaches
     for `list_reminders` at all?
   - Should the code defensively submit `function_call_output` for **every** unresolved
     function call in `response.output` before any follow-up round-trip is attempted, not just
     the one call the current handler happens to be looking for — this looks like the more
     durable, structural fix, independent of which specific tool intrudes.
   - Should a turn producing multiple unrelated tool calls at all be treated as an anomaly
     worth logging/flagging distinctly, given RBAC/tool-attachment already scopes which tools
     are even available per turn?
4. Failing test written, approved, minimal fix implemented, verified.
