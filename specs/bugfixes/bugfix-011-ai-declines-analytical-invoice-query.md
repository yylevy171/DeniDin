# Bugfix Spec: AI Declines Analytical/Aggregate Invoice Questions Instead of Composing an Answer

## Bug ID
bugfix-011-ai-declines-analytical-invoice-query

## Title
Godfather asks an analytical invoicing question ("who owes me the most?") and the model falsely claims it lacks access, instead of calling `list_invoices` and computing the answer itself

## Status
Fixed - pending merge

## Date Opened
2026-07-20

## Reported By
yylevy171 (found via manual dev-environment testing, same session as bugfix-010)

## Affected Area
- `apps/denidin-app/data/constitution/runtime_constitution.md` ("Invoice Management Context" section)
- Real-time behavior of the OpenAI Responses API call in `AIHandler` when the Morning MCP tool is attached

## Description
With the Morning MCP tool correctly attached (role=GODFATHER, confirmed via
logs — this is NOT a recurrence of bugfix-010) and a real invoicing question
asked, the model replied that it needs access to the invoice system instead
of calling any tool:

> User: "תן לי שמות של ה-3 שחייבים לי הכי הרבה, וכמה כל אחד חייב" (give me the
> names of the 3 who owe me the most, and how much each owes)
>
> Model: "אני זקוק לגישה למערכת ניהול החשבוניות שלך כדי לספק את המידע הזה..."
> (I need access to your invoice management system to provide this
> information...)

No `list_invoices`/`get_financial_summary`/any tool call appears in that
turn's `mcp_calls` log — the model didn't attempt anything, it just declined.

Confirmed live in the same session: when the user explicitly told the bot
"יש לך את כל הגישה שצריך. אם צריך לשלוף את הרשימה ואז לפלטר - תעשה את זה" (you
have all the access you need; if you need to fetch the list and then filter,
do it), the **same model, same tools, same role** immediately called
`list_invoices` with `status=unpaid` and a sensible date range, and produced a
real, correct answer. This proves the tools and RBAC path are fully
functional — the gap is purely in what the model is told it's allowed/expected
to do.

## Root Cause Analysis
`runtime_constitution.md`'s "Invoice Management Context" section has detailed,
well-tested guidance for single-invoice resolution (`list_invoices` filtered
by client/date to find *one* invoice), creation, status changes, and
cancellation — but **no guidance at all for analytical/aggregate questions**
(ranking, totals-per-client, "how many/who/which clients..."). None of the 7
Morning tools (`create_invoice`, `list_invoices`, `get_invoice_details`,
`update_invoice_status`, `add_client`, `get_financial_summary`,
`download_invoice_pdf`) returns a "top N debtors" shape directly —
`get_financial_summary` only returns aggregate totals, not per-client
breakdowns. Answering this class of question correctly requires the model to:
1. Call `list_invoices` (filtered by `status=unpaid` and a reasonable date
   range) to get the raw per-invoice data, then
2. Group/sum/rank/filter that data **itself** in its own response reasoning.

With no rule telling it this composition pattern is expected and encouraged,
the model defaulted to a bugfix-010-shaped failure mode of its own: assuming
"no single tool returns this, therefore I lack access" rather than "I have
raw data available, I can compute this."

## Steps to Reproduce
1. As a confirmed GODFATHER/ADMIN user with the Morning MCP tool attached and
   a live tunnel, ask an analytical question that requires per-client
   aggregation/ranking and isn't satisfied by a single tool call verbatim
   (e.g. "who owes me the most and how much?", "which 3 clients still haven't
   paid this month?").
2. Observe: the model declines / claims it lacks access, with zero tool calls
   in that turn.

## Expected Behavior
The model recognizes it has the raw data access needed (via `list_invoices`,
optionally combined with its own filtering/grouping/ranking) to answer
analytical questions, and does so — composing a checklist of steps
internally when a query needs more than one call or requires post-processing
tool output, rather than declining.

## Impact
- Any analytical/aggregate invoicing question a godfather/admin asks
  (rankings, per-client totals, "who hasn't paid", "top N by amount") gets a
  false "no access" decline instead of a real answer — a significant gap in
  the core value proposition of the Morning MCP integration, since these are
  exactly the kind of question a business owner asks most.

## Acceptance Criteria
- [x] A new `@pytest.mark.expensive` E2E test in
      `tests/expensive/test_denidin_morning_mcp_e2e.py`
      (`test_godfather_asks_analytical_debtor_question_via_whatsapp`)
      reproduces this exact scenario (real webhook → real OpenAI Responses
      API → real Morning MCP tool, real sandbox). Note: initial confirmation
      runs hit an unrelated infra issue first (auth-token mismatch between
      `config.test.json` and the 019-env-separation dev container's own
      `config.dev.json` — fixed by aligning the dev container's token to the
      one `config.test.json` already expects); once that was resolved the
      test passed even before the constitution fix on one run, so "confirmed
      failing" rests on the two live, real-WhatsApp reproductions in dev
      earlier in this session (see Evidence) rather than a deterministic
      failing pytest run — LLM sampling makes this bug probabilistic, not
      100% reproducible on every call.
- [x] Root cause confirmed (this document).
- [x] Fix: added "Analytical/aggregate questions" guidance to
      `runtime_constitution.md`'s Invoice Management Context, instructing the
      model that it has full access to compose an answer from raw tool data
      (call `list_invoices` with appropriate filters, then group/sum/rank/filter
      itself) whenever no single tool returns the requested shape directly,
      and that it must never claim to lack access when a tool that can supply
      the underlying data is actually available.
- [x] The test passes after the fix (verified once, single explicit-approval run).
- [x] No regression in the existing `test_denidin_morning_mcp_e2e.py` suite —
      re-ran all 5 existing tests individually (create/list/details/mark-paid/
      cancel), each with separate explicit approval, none as a batch: all pass.
- [ ] Re-verified live in the dev environment against a real WhatsApp message
      with the same phrasing that originally triggered the bug.

## References
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
- `specs/bugfixes/bugfix-010-rbac-phone-jid-mismatch.md` (found in the same
  testing session; unrelated root cause, but establishes this was a real
  manual-testing pass, not a one-off fluke)
- `apps/denidin-app/data/constitution/runtime_constitution.md`
- `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`

## Cost/Approval Note
Verifying this bug (and its fix) requires running a real, billed OpenAI +
Morning-sandbox E2E test. Per CLAUDE.md/CONSTITUTION §VII: explicit human
approval is required before every single run, one test at a time, never a
batch — this applies to both the failing-state run and the passing-state run
after the fix.
