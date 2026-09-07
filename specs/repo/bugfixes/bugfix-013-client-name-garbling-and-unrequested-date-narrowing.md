# Bugfix Spec: Client-name garbling and unrequested date-range narrowing in Morning tool calls

## Bug ID
bugfix-013-client-name-garbling-and-unrequested-date-narrowing

## Title
The AI mis-transcribes a client name into tool-call arguments, and separately narrows date ranges the user didn't ask for, without disclosing either

## Status
Closed — not reproducible at the app level (2026-07-21). Two independent root causes identified for the two sub-issues (see "Investigation Findings" below):

1. **Date-range narrowing**: fixed and merged to `master` (PR #116, commit `978b20d`) — `runtime_constitution.md` lines 173-174 now explicitly instruct: if no date is mentioned at all, omit `from_date`/`to_date` entirely, do not default to the current month. Two E2E regression tests added (`test_zehavit_client_name_transcribed_exactly`, `test_no_date_mentioned_omits_date_range`).
2. **Client-name garbling**: closed as **not reproducible / not fixable at this repo's level** — human decision (2026-07-21), see "Resolution" below. No app-level cause was found across the full WhatsApp-receipt-to-tool-call path; the garbling is consistent with a known token-fidelity weak point of the underlying model (gpt-4o-mini) for uncommon Hebrew tokens, not a bug in this codebase's code or prompts. Filed under `specs/not_reproducible/bugfixes/` rather than `specs/done/bugfixes/` since nothing was actually fixed for this half — it's accepted as an inherent model-generation risk, to be revisited only if it recurs with new evidence or a pattern emerges.

## Resolution (name-garbling half)
Accepted as residual risk, per human decision 2026-07-21. No follow-up feature spec opened at this time (an entity-verification/confirmation step was considered and explicitly declined for now — can be revisited later if this recurs). If it resurfaces with clearer evidence (e.g. reproduces consistently for other uncommon Hebrew names, or a genuine app-level trigger is found), re-open a new bugfix spec referencing this one rather than reopening this file.

## Date Opened
2026-07-20

## Reported By
yylevy171 (found via manual prod-environment testing, same live session as bugfix-012/014)

## Affected Area
- The AI's tool-call argument construction when invoking `list_invoices`/other Morning tools (`AIHandler`'s Responses API call, `apps/denidin-app/data/constitution/runtime_constitution.md`'s invoice-management guidance) — this is a prompt/behavior issue, not a `morning-mcp-app` code bug (the tool itself receives whatever arguments the model sends and executes them correctly)

## Description
Two related, observed defects in the same live testing session, both in how the model constructs Morning tool-call arguments from a casual user request — not in the tools themselves.

### 1. Client name garbling
User asked (real WhatsApp, prod): "לקוחה בשם זהבית - בדוק לי כמה שילמה ומתי, תן לי הכל" (client named Zehavit - check how much she paid and when, give me everything).

- 1st tool call: `client_name: "זבית"` (missing the ה) — "no matching invoices" returned.
- User asked again, giving just a date ("10.7.2026"): 2nd tool call: `client_name: "זבת"` — now missing **two** letters (ה and י) — "no matching invoices" again.

The correct name, "זהבית", was never used in either tool call, despite being typed correctly by the user both times (the name doesn't even appear misspelled in the user's own messages). This is a reproducible, worsening transcription error, not a one-off token glitch — confirmed not universal, however: a later request for a different client ("אריאן רגב") in the same session transcribed the name correctly in every call.

### 2. Unrequested, undisclosed date-range narrowing
Both Zehavit tool calls also silently restricted the search to `from_date: "2026-07-01", to_date: "2026-07-31"` (the current month) even though the user explicitly said "תן לי הכל" (give me everything) — no date range was requested, and the model never disclosed that it was applying one. This is the same *shape* of issue later confirmed for `status` filtering in bugfix-014 (an unrequested restrictive filter silently narrows a "give me everything"-type request), just manifesting as a date filter here instead of a status filter.

This directly conflicts with the runtime constitution's own rule: *"Be transparent about anything you filled in yourself... If your confidence in a filled-in value is low... ask instead of guessing silently."* Defaulting silently to "this month" when the user said "everything" is exactly the case that rule is meant to prevent.

## Evidence (from this session's real logs)

```
20:11:41 - MCP calls: [{'name': 'list_invoices', 'arguments':
  '{"status":"paid","from_date":"2026-07-01","to_date":"2026-07-31","client_name":"זבית"}',
  'output': 'לא נמצאו חשבוניות התואמות את החיפוש.'}]

20:12:34 - MCP calls: [{'name': 'list_invoices', 'arguments':
  '{"status":"paid","from_date":"2026-07-01","to_date":"2026-07-31","client_name":"זבת"}',
  'output': 'לא נמצאו חשבוניות התואמות את החיפוש.'}]
```

(Compare with the correctly-transcribed, appropriately-wide `"אריאן רגב"` calls documented in bugfix-014, which used a `2026-01-01`–`2026-07-20` range instead of narrowing to one month — inconsistent behavior even across the two sessions' worth of date-scoping choices.)

## Suspected Root Cause (unconfirmed)

Not yet investigated at the code/prompt level. Candidate directions:
- **Name garbling**: possibly a model-generation-level issue (token-level substitution/dropping when producing Hebrew text inside a JSON tool-call argument) rather than anything fixable in this repo's code — would need to check whether this reproduces consistently for other uncommon Hebrew names, or is closer to random noise. Not clearly addressable via a constitution-prompt change the way bugfix-011/012's tool-usage gaps were, since it's about token generation fidelity, not decision-making guidance.
- **Date-range narrowing**: more likely addressable via `runtime_constitution.md` — similar in spirit to bugfix-011's fix (which addressed the AI declining instead of composing an analytical answer). A new/extended rule could instruct: when a request has no date qualifier at all ("everything", "all", or simply no date mentioned), do not silently inject a date range — omit `from_date`/`to_date` entirely (both are `Optional` on `list_invoices`, per `tools.py:201-206`) unless a scope is genuinely needed to keep results manageable, and if one is applied, disclose it in the reply.

## Investigation Findings (read-only, 2026-07-21)

**Scope of this pass**: code/config/log/documentation review only, plus general web research on the underlying model family's known behavior. No code was changed, no tests were run, no deployment was touched, per explicit instruction. Findings below are root-cause analysis for approval, not fixes.

### 2. Date-range narrowing — root cause found: existing rule was violated, not missing

`apps/denidin-app/data/constitution/runtime_constitution.md` (lines 169–172) **already contains** the rule this bug's initial hypothesis assumed was missing:

> "Otherwise call `list_invoices`, using only what the CURRENT request gives you. Filter by client name; add a `from_date`/`to_date`/`status` only if this request itself states one. Never carry a date or status over from an earlier, unrelated lookup — an ungrounded filter is worse than none."

The user's first Zehavit message ("בדוק לי כמה שילמה ומתי, תן לי הכל") contains **no date reference of any kind** — yet the model's tool call added `from_date: "2026-07-01", to_date: "2026-07-31"` anyway. This is not a gap in the constitution's guidance; it's the model failing to follow an instruction that already directly covers this exact case. The separate date-normalization rule (lines 189–199, "a reasonable default when part of a date is left out") does not apply here either — it's scoped to filling in the *missing piece* of a *partially given* date ("7 ביולי" with no year), not inventing an entire date range when literally none was mentioned.

This reclassifies the fix direction from "write a new rule" (the spec's original suggestion) to "the existing rule needs to be strengthened, made more prominent, or reinforced with an explicit contrastive example" (e.g. adding a line like *"if no date is mentioned at all, omit `from_date`/`to_date` entirely — do not default to the current month"*) — recognizing this may reduce but not fully eliminate recurrence, since it's fundamentally a case of an instruction-following lapse by the underlying model (gpt-4o-mini, per `config.dev/prod.example.json`'s `ai_model`), not a decision the guidance failed to address at all.

### 1. Client-name garbling — root cause: no app-level cause found; consistent with a model tokenization issue

Traced the full path from WhatsApp message receipt to tool-call argument with no app-level transformation step found that could explain letter-dropping:
- `apps/denidin-app/src/handlers/whatsapp_handler.py` does no text encoding/decoding/mutation of message content — it only validates message *type* (`textMessage`/`extendedTextMessage`).
- `apps/denidin-app/src/handlers/ai_handler.py` (~line 458-469) logs `item.arguments` directly off the OpenAI Responses API's `mcp_call` item — the app does not construct, sanitize, re-encode, or truncate this JSON itself; whatever string the model generated is what gets sent to the MCP tool and logged verbatim.
- This rules out an app-side bug (e.g. a lossy encode/decode round-trip, a buffer/length truncation, a regex-based sanitizer eating characters) as the mechanism — the garbling is already present in what the model itself generated, before this app ever touches the string.
- This is consistent with the bug spec's own suspicion and with general, documented weak points of the GPT-4/4o tokenizer family for non-English/uncommon-token text: the o200k_base tokenizer's subword segmentation is known to behave unevenly outside high-frequency English text, and per community-reported and academic discussion (see Sources below), token-boundary effects are a recognized source of degraded fidelity for less-common non-English strings — Hebrew personal names being exactly this kind of low-frequency token sequence. "זהבית" is a less common name than "אריאן רגב" (which transcribed correctly in the same session), which fits a token-frequency-driven explanation better than an app-level bug that would be expected to affect all Hebrew text somewhat uniformly.
- **Practical implication**: this looks like it sits outside what a constitution/prompt change or app-code fix can reliably guarantee — it's a property of the underlying model's generation fidelity for a specific class of input, not a decision the model is making incorrectly. A mitigation worth considering (not a fix, and not evaluated further this pass): a post-hoc verification step where the model's own reply is checked against the original message for named entities before the tool result is trusted — but this is a new behavior, not a bug fix, and would need its own spec/approval if pursued.

**Sources** (general web research, not project-specific):
- [GPT-4 Tokenizer Overview](https://www.emergentmind.com/topics/gpt-4-s-tokenizer)
- [Large Language Model Tokenizer Bias: A Case Study and Solution on GPT-4o](https://arxiv.org/html/2406.11214v2)
- [GPT-4 Abruptly stops any output in Hebrew - OpenAI Developer Community](https://community.openai.com/t/gpt-4-abrubtly-stops-any-output-in-hebrew/310354)

### Recommendation

Treat this as two separately-tracked fixes, not one:
- Date-narrowing: a constitution wording strengthening is a reasonable, low-risk next step, pending approval — same BDD gates as any other constitution-only fix (see bugfix-011 for precedent).
- Name garbling: likely not fixable via this repo's code or prompt in a way that guarantees correctness; recommend either accepting the residual risk (same as any LLM output), or scoping a *separate*, new feature spec (not a bugfix) for an entity-verification/confirmation step, if this is worth pursuing further.

## Steps to Reproduce
1. As GODFATHER/ADMIN, ask about an uncommon/less-common Hebrew client name's payment history, requesting "everything" with no date qualifier, in a single message.
2. Observe whether the `client_name` argument matches what was actually typed, and whether `from_date`/`to_date` get silently populated despite no date being requested.

## Expected Behavior
- Tool-call arguments should faithfully reflect user-provided values (client names transcribed exactly).
- A request for "all"/unqualified data should not have an undisclosed date range silently applied.

## Acceptance Criteria
- [x] Root cause confirmed for the date-narrowing behavior: an existing constitution rule (lines 169-172) was violated by the model, not a documentation gap
- [x] Root cause investigated for name-garbling: no app-level cause found across the WhatsApp-receipt-to-tool-call path; consistent with a known model-tokenization weak point for uncommon Hebrew tokens, not reliably fixable via this repo's code/prompt (see Investigation Findings)
- [x] Root cause explanations approved by human (BDD gate) — approved 2026-07-21
- [x] Failing test/reproduction written (BDD, per METHODOLOGY §VII), to whatever extent testable deterministically — done for date-narrowing (two E2E regression tests, PR #116); not applicable for name-garbling, accepted as non-deterministic model behavior
- [x] Fix proposed, approved, and applied — date-narrowing only (PR #116, merged); name-garbling has no code/prompt fix, accepted as residual risk per human decision 2026-07-21
- [x] Re-verified live against real production data — date-narrowing fix verified via new E2E tests; name-garbling closed without a fix to verify (see Resolution)

## References
- `specs/bugfixes/bugfix-011-ai-declines-analytical-invoice-query.md` — same category of constitution-guidance gap (AI narrowing/declining beyond what was actually asked)
- `specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md` — same live session, related "unrequested restrictive filter" pattern (status instead of date)
- `apps/denidin-app/data/constitution/runtime_constitution.md`
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
