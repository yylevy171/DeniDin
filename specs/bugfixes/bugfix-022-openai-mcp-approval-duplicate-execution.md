# Bugfix Spec: OpenAI can execute an approved MCP tool call more than once for a single approval

## Bug ID
bugfix-022-openai-mcp-approval-duplicate-execution

## Title
Resolving a document-creating MCP approval (Feature 022) can result in the already-approved tool call executing **more than once** against the real Morning API — risking duplicate real-world financial documents (e.g. two invoices for one approved action) from a single user approval.

## Priority
P0 — a document-creating tool executing twice against a real, live invoicing system is a financial-integrity/compliance risk, not just a UX bug (reporter: duplicate invoices are a real legal exposure).

## Status
**Open — interim fail-safe mitigation deployed and accepted; true prevention deferred.** Human explicitly reviewed and accepted the current "detect and refuse" behavior as sufficient for now (2026-08-03): *"For now I am fine with the existing fail behavior. If this is the only type of failure we get, I am good."* No further work planned unless duplication recurs or its rate/impact changes.

## Date Opened
2026-08-03

## Reported By
yaronlev171 (discovered during Feature 033's billed-test sweeps of `apps/denidin-app`)

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` — `_call_openai_approval_api`, `_resolve_pending_approval` (the Feature 022 approval-resolution path for every document-creating Morning MCP tool: `create_invoice`, `create_receipt`, `create_credit_note`, `create_transaction_account`, `create_combo_document`, `add_client`, `update_client`, `close_transaction_account`)
- Likely true-fix location (not yet touched): `apps/morning-mcp-app` — the code that makes the actual real call to the Green Invoice (Morning) API is the only place that can guarantee a document is created at most once, regardless of how many times OpenAI dispatches the approved tool call

## Description
During real, billed E2E test sweeps (`tests/billed/test_denidin_morning_mcp_e2e.py`), a single user approval (one `"כן"` in response to one pending-approval prompt) resulted in the approved tool executing **twice** server-side, confirmed twice today via direct log evidence:

**Incident 1** (`test_godfather_marks_invoice_paid_via_whatsapp`'s seed step, `_seed_fresh_invoice`): the approval-resolution call to OpenAI's Responses API returned `HTTP 429 Too Many Requests`, the OpenAI Python SDK auto-retried the same call (same idempotency key), and the eventual successful response contained **two `mcp_call` entries** for `create_invoice` with identical arguments — two real invoices (`#51207`, `#51208`) were created in the Morning sandbox for one approval.

**Incident 2** (same test, different run, same day, **after** the interim mitigation below was deployed and the client-side SDK retry disabled): the exact same symptom recurred — two `mcp_call` entries for `create_invoice` in one approval-resolution response — with **no 429 and no client-side retry involved this time**. This proves the duplication is not solely caused by our own SDK-level retry behavior; something on OpenAI's side of the Responses API / remote MCP round-trip can independently dispatch an already-approved tool call more than once, outside our observation and control.

## Root Cause
Not fully determined — and, per the accepted decision below, not being pursued further right now. What is confirmed:
- The duplication happens **before** `denidin-app` ever sees the response: by the time `_call_openai_approval_api` returns, any real-world side effect (e.g. a Morning document) from every `mcp_call` in the response has already happened server-side. Nothing in `denidin-app`'s own code can prevent or undo it after the fact — only detect and report on it.
- Ruled out: our own SDK auto-retry as the *sole* cause (Incident 2 recurred with `max_retries=0` on this call).
- Not yet investigated: whether this is a known OpenAI Responses-API/MCP-tool-execution behavior, a transient infra issue on OpenAI's side, or something about the specific remote MCP server (ngrok tunnel latency/reconnect?) that increases the odds of a duplicate dispatch.

## Steps to Reproduce
Not reliably reproducible on demand. Observed empirically twice across roughly 40-50 real approval-flow executions in billed E2E sweeps run today (2026-08-03) against real OpenAI + the real Morning sandbox API. No known trigger condition beyond "approving a document-creating tool call."

## Interim Mitigation (implemented and deployed, 2026-08-03, as part of `feature/033-ledger-event-persistence`)
1. **`_call_openai_approval_api`** now calls the OpenAI client with `max_retries=0` for this specific request — a failed attempt (429/5xx/timeout) surfaces immediately as an exception instead of being silently retried by the SDK, ruling out our own retry behavior as a duplication source going forward. `_resolve_pending_approval` catches this and returns a clean "try again" error (`APPROVAL_FAILED_TRY_AGAIN`), leaving the pending approval in place so the user's next `"כן"` is a fresh, single attempt.
2. **`_resolve_pending_approval`** inspects the approval-resolution response's `output` for `mcp_call` items after a successful call, counting executions of **the specific approved tool** (`pending.tool_name`) - not the total `mcp_call` count. If the approved tool itself appears more than once, it does **not** report success: it clears the pending approval (so a naive retry from the user can't compound the problem), logs the full raw call detail at ERROR level for manual reconciliation against Morning, and returns a friendly Hebrew error (`APPROVAL_POSSIBLY_DUPLICATED`) explicitly telling the user to check manually in the system and not approve again in the meantime.

**Correction (2026-08-03, same day):** the guard originally counted *any* `mcp_call` entries in the response, not specifically the approved tool. This produced a real false positive: a legitimate `create_invoice` call followed by its natural `download_invoice_pdf` follow-up (required by the constitution - every `create_invoice` confirmation must include a download link) was wrongly flagged as a duplicate and blocked a good response. Narrowed to count only executions of `pending.tool_name` specifically. **Incident 1 (the original, first-observed case) remains confirmed genuine** independent of this correction - verified via two actual, distinct invoice documents (`#51207`, `#51208`) both present in the Morning sandbox for the same client/amount, not just via the mcp_call count. Incidents reported later the same day, before this correction, cannot be retroactively confirmed as genuine vs. false-positive from the (truncated) logs alone - the guard's own detection message did not originally distinguish same-tool repeats from multi-tool sequences.

**This does not prevent the duplicate document from existing in Morning** — both calls have already reached the real API by the time this code runs. It only guarantees `denidin-app` never silently reports false success when this happens, and gives a human an unambiguous signal to go check and correct the real system.

## Fix Options Considered (for true prevention — not yet approved/implemented)

**A. Idempotency at the Morning-API-call layer (`apps/morning-mcp-app`).** `pending.approval_request_id` is already unique per approval and available to pass through as a tool argument. The Morning-side tool implementation could check "have I already created a document for this exact key?" before calling the real Green Invoice API, and return the existing result on a repeat instead of creating a new one. This is the only place that can *guarantee* single execution, since it's the one place that actually talks to the real financial system, regardless of how many times OpenAI dispatches the call. Open question, not yet researched: whether Green Invoice's own API supports a native idempotency key, or whether a local dedup cache would need to be built in `apps/morning-mcp-app` itself.

**B. Accept the interim mitigation as sufficient for now.** No further code changes; rely on "detect duplication, refuse to report false success, alert for manual check" as the standing behavior.

### Decision (2026-08-03)
**Option B**, explicitly approved by the human reporter. Option A remains documented above as the known path to true prevention, to be picked up if/when duplication recurs at a rate or in a context that makes the interim mitigation insufficient.

## Test Gap Analysis
No existing automated test reproduces the duplicate-execution condition itself (it depends on non-deterministic OpenAI/infra behavior, not something we can trigger on demand). The interim mitigation's own logic (max_retries=0 wiring, the `>1 mcp_call` detection and fallback response) has **not yet** been given dedicated unit test coverage — it was verified only by observing it correctly fire against the real duplication in Incident 2's billed test run. Adding unit tests for `_resolve_pending_approval`'s duplicate-detection branch (mocking a `response.output` with 2+ `mcp_call` items) is a reasonable, low-cost follow-up, not yet done.

## Acceptance Criteria
- [x] Root cause investigated with real evidence (log-confirmed, twice)
- [x] Interim mitigation approved by human and implemented
- [x] Interim mitigation verified against a real recurrence (Incident 2, live billed sweep)
- [ ] Unit test coverage for the duplicate-detection branch itself (not yet written)
- [ ] True prevention (Option A, Morning-side idempotency) — explicitly deferred, not started
- [x] Human sign-off to leave as-is for now (2026-08-03)

## References
- `apps/denidin-app/src/handlers/ai_handler.py` (`_call_openai_approval_api`, `_resolve_pending_approval`)
- `apps/denidin-app/src/constants/error_messages.py` (`APPROVAL_FAILED_TRY_AGAIN`, `APPROVAL_POSSIBLY_DUPLICATED`)
- Feature 022 (`specs/done/022-explicit-approval-for-document-creation/`) — the approval-gating mechanism this bug occurs within
- `feature/033-ledger-event-persistence` branch — where both incidents were observed and the interim mitigation was built
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
