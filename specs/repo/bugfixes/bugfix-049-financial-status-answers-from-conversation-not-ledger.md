# Bugfix Spec: Financial/agreement-status questions answered from conversation memory instead of a real ledger lookup

## Bug ID
bugfix-049-financial-status-answers-from-conversation-not-ledger

## Title
The model answers questions like "does client X have a fee agreement?" or "what's still unpaid?"
by re-reading its own session/conversation history for a matching mention, instead of calling
`query_ledger_events` (Feature 044) against the actual persisted ledger. When the real answer
exists in the ledger but was never explicitly restated in the current conversation's visible
context, the model confidently reports "no record found" — a false negative the client cannot
tell apart from a genuine absence of data.

## Priority
**P1** — produces a confidently wrong "no such record" answer to a direct financial question,
with no indication to the user that the lookup was incomplete.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-08-30

## Reported By
yaronlev171, during the interactive `needs_clarification.jsonl` review of the Feature 043 player
replay (item 76/86, see `apps/denidin-app/player_data/_review_decisions.jsonl`).

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` — the reply-generation path for financial-status/
  agreement-status questions. Needs investigation to pin down exactly which code path this is:
  whether it's the same general conversational reply path (no tool call made at all for these
  questions), or a dedicated helper that should be calling `query_ledger_events` but isn't being
  invoked for this phrasing of question.
- `config/runtime_constitution.md` — likely needs an explicit instruction that ANY question about
  whether an agreement/payment/invoice exists or its status MUST be answered via a ledger lookup
  tool call, never from memory of the conversation alone, even when the conversation appears to
  already contain the answer.

## Description
Two real instances surfaced in the same player-replay review, both from re-reading conversation
text instead of querying the ledger:

**Instance 1 (item 76/86)** — the client told the assistant directly, in plain words, that a
new-sounding client name was actually an existing one:
```
8/19/26, 07:09 - אילה 🐣: האם יש לליאור חכם הסכם שכר טרחה?
8/19/26, 07:09 - דני דין: לא מצאתי בהקשר הזמין הסכם שכר טרחה עבור ליאור חכם.
8/19/26, 07:11 - אילה 🐣: ליאור חכם זה ליאור - שסטוביץ
8/19/26, 07:11 - דני דין: הבנתי — ליאור חכם הוא ליאור שסטוביץ.
   לפי המידע הזמין לי כרגע, עדיין אין תיעוד של הסכם שכר טרחה עבורו.
8/19/26, 07:12 - אילה 🐣: ליאור שסטוביץ יש הסכם?
8/19/26, 07:12 - דני דין: לפי המידע הזמין לי כרגע, אין תיעוד של הסכם שכר טרחה עבור ליאור שסטוביץ.
```
The assistant told the client **twice** that no fee agreement exists for "ליאור שסטוביץ." A real
one does: event `A27072614470` (agreement_id `0726-ליאור_שסטוביץ-שימוע`, ₪9,000, `שימוע`),
captured earlier in the same ledger. The model never called a ledger-lookup tool for this
question — it answered purely from what it could recall having seen already stated in the
current session's own text, and that specific agreement (captured on an earlier day of the
underlying export, itself replayed in an earlier, separate player run) was never restated inside
the visible conversation window this particular turn was working from.

**Instance 2 (item 37/86)** — the client asked `"מה טרם שולם"` ("what hasn't been paid yet"); the
resume log shows `Morning MCP status file not found` immediately before the model's answer, and
**no tool call of any kind appears in the log for that turn** — no `query_ledger_events`, no
Morning call. The model conflated unpaid fee-agreements with un-invoiced deposits, and only
self-corrected after the client pushed back ("לאאאאאא"). Same root pattern: a financial-status
question answered by summarizing remembered conversation text, not by querying real data.

## Impact
A client asking a direct, closed factual question ("does X have an agreement," "what's unpaid,"
"has this been paid") gets a confident, well-formatted answer that can be **flatly wrong** with
no hedge or caveat — indistinguishable from a correctly-sourced "no" or a correct summary. This
is worse than a visible error: it's silently incorrect, and past reviews already established
(runtime_constitution's ledger-as-cache-not-source-of-truth framing, Feature 044) that a
zero-match result must never be treated as authoritative without a real lookup — this bug shows
the model sometimes never performs that lookup step at all for status/existence questions phrased
this way.

## Next Steps (Bug-Driven Development, METHODOLOGY.md §VII)
1. Root cause: identify exactly why `query_ledger_events` (or the Morning lookup) isn't invoked
   for these question phrasings — is it a constitution-prompting gap (no explicit rule requiring
   a tool call before answering existence/status questions), a tool-selection judgment failure,
   or something else specific to how these questions are worded?
2. Human approval of the root cause.
3. Test-gap analysis — what test coverage exists today for "does client X have an agreement" /
   "what's unpaid" style questions, and why didn't it catch this?
4. Human approval of a failing test.
5. Minimal fix — likely a `runtime_constitution.md` addition making the "always look before
   answering" rule explicit and specific to this question shape, possibly reinforced by making
   the relevant tool available/required for this class of question.
6. Verify against both real instances above.
