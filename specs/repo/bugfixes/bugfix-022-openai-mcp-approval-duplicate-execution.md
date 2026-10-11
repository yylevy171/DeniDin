# Bugfix Spec: OpenAI can execute an approved MCP tool call more than once for a single approval

## Bug ID
bugfix-022-openai-mcp-approval-duplicate-execution

## Title
Resolving a document-creating MCP approval (Feature 022) can result in the already-approved tool call executing **more than once** against the real Morning API — risking duplicate real-world financial documents (e.g. two invoices for one approved action) from a single user approval.

## Priority
P0 — a document-creating tool executing twice against a real, live invoicing system is a financial-integrity/compliance risk, not just a UX bug (reporter: duplicate invoices are a real legal exposure).

## Status
**Done — merged to master (PR #177), confirmed mechanism closed (2026-08-04).** Detect-and-refuse fail-safe remains as defense-in-depth; true prevention (Option A) still deferred, now for a hypothetical rather than a confirmed second cause. Only **one** real duplication was ever confirmed: Incident 1 (auto-retry-on-429). "Incident 2" (see Description) was re-examined and is now understood to have been a false positive of the original over-broad guard, not a second real duplication - see "Correction" under Interim Mitigation. With no second confirmed mechanism, the fix below (2026-08-04) closes the only mechanism that was ever actually observed. Human accepted the residual, unconfirmed risk (any cause other than an automatic retry) as sufficient to leave as detect-and-refuse only, not pursue Option A (2026-08-03): *"For now I am fine with the existing fail behavior. If this is the only type of failure we get, I am good."*

### Root Cause Update (2026-08-04)
`_call_openai_approval_api` was still wrapped in the same tenacity `@retry(retry_if_exception_type((RateLimitError, APITimeoutError, APIError)), stop_after_attempt(2), ...)` decorator used on the file's other (non-approval) OpenAI calls. The 2026-08-03 mitigation only disabled the OpenAI SDK's own internal retry (`self.client.with_options(max_retries=0)`) - it did not remove this outer tenacity decorator, which transparently re-invokes the whole method (a second real `responses.create()` call, dispatching the already-approved tool a second time) on `RateLimitError`/`APITimeoutError`/`APIError`, independent of the SDK's own retry setting, and does so **silently** (tenacity only logs/raises once every attempt is exhausted) - so a retry via this path could happen without ever producing a visible 429/retry log line. This is exactly Incident 1's mechanism (auto-retry-on-429 -> second real dispatch), just relocated to a layer the 2026-08-03 fix didn't touch. A regression unit test (`tests/unit/test_ai_handler_approval_no_retry.py::test_rate_limit_error_makes_exactly_one_call`) reproduces this: with the decorator in place, `RateLimitError` on the mocked approval-resolution call results in 2 calls, not 1.

### Fix (2026-08-04)
Removed the `@retry(...)` decorator from `_call_openai_approval_api` entirely - this call is now single-attempt at every layer (SDK and our own), with no exceptions, and no automatic-retry code path remains anywhere in this call chain that we control. On `RateLimitError` (429) specifically, `_resolve_pending_approval`'s existing `except` handling now reliably fires after exactly one attempt: it leaves the pending approval in place and returns the existing `APPROVAL_FAILED_TRY_AGAIN` friendly error, asking the user to resend.

**Scope of this guarantee, stated precisely:** this closes Incident 1's mechanism completely - our own code can never again automatically re-dispatch an approved tool call after a 429/timeout/API error, at any layer. It does **not** newly guarantee zero documents from a single, non-retried attempt if OpenAI's own infrastructure could somehow commit a tool call server-side while still returning an error to the client - that was never confirmed to happen (Incident 2, the only evidence for it, is now understood to be a false positive), so there is currently no known live mechanism left for that to occur through. The `>1 mcp_call` detect-and-refuse guard (below) stays in place as defense-in-depth regardless.

## Date Opened
2026-08-03

## Reported By
yaronlev171 (discovered during Feature 033's billed-test sweeps of `apps/denidin-app`)

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` — `_call_openai_approval_api`, `_resolve_pending_approval` (the Feature 022 approval-resolution path for every document-creating Morning MCP tool: `create_invoice`, `create_receipt`, `create_credit_note`, `create_transaction_account`, `create_combo_document`, `add_client`, `update_client`, `close_transaction_account`)
- Likely true-fix location (not yet touched): `apps/morning-mcp-app` — the code that makes the actual real call to the Green Invoice (Morning) API is the only place that can guarantee a document is created at most once, regardless of how many times OpenAI dispatches the approved tool call

## Description
During real, billed E2E test sweeps (`tests/billed/test_denidin_morning_mcp_e2e.py`), a single user approval (one `"כן"` in response to one pending-approval prompt) resulted in the approved tool executing **twice** server-side:

**Incident 1** (`test_godfather_marks_invoice_paid_via_whatsapp`'s seed step, `_seed_fresh_invoice`) — the only confirmed real occurrence: the approval-resolution call to OpenAI's Responses API returned `HTTP 429 Too Many Requests`, the OpenAI Python SDK auto-retried the same call (same idempotency key), and the eventual successful response contained **two `mcp_call` entries** for `create_invoice` with identical arguments — two real invoices (`#51207`, `#51208`) were created in the Morning sandbox for one approval.

**"Incident 2"** (same test, different run, same day, after the interim mitigation below was deployed) was initially logged as a second occurrence of the same symptom, but was re-examined and is now understood to be a **false positive** of the original over-broad guard described in "Correction" below (the two `mcp_call` entries were `create_invoice` + its legitimate `download_invoice_pdf` follow-up, not two executions of the same tool) - not a real second duplication. There is therefore only one confirmed real incident.

## Root Cause
Confirmed for the one real incident: the OpenAI Python SDK's own default auto-retry-on-429 re-issued the approval-resolution call, producing two real dispatches of the approved tool from one client-visible approval. See "Root Cause Update (2026-08-04)" under Status for a second, latent path (a leftover tenacity retry decorator) capable of reproducing the exact same mechanism, found and closed even though it was never proven to have actually fired for real - closing it removes any remaining automatic-retry code path in this call chain.

## Steps to Reproduce
Not reliably reproducible on demand. Observed empirically twice across roughly 40-50 real approval-flow executions in billed E2E sweeps run today (2026-08-03) against real OpenAI + the real Morning sandbox API. No known trigger condition beyond "approving a document-creating tool call."

## Interim Mitigation (implemented and deployed, 2026-08-03, as part of `feature/033-ledger-event-persistence`)
1. **`_call_openai_approval_api`** now calls the OpenAI client with `max_retries=0` for this specific request — a failed attempt (429/5xx/timeout) surfaces immediately as an exception instead of being silently retried by the SDK, ruling out our own retry behavior as a duplication source going forward. `_resolve_pending_approval` catches this and returns a clean "try again" error (`APPROVAL_FAILED_TRY_AGAIN`), leaving the pending approval in place so the user's next `"כן"` is a fresh, single attempt.
2. **`_resolve_pending_approval`** inspects the approval-resolution response's `output` for `mcp_call` items after a successful call, counting executions of **the specific approved tool** (`pending.tool_name`) - not the total `mcp_call` count. If the approved tool itself appears more than once, it does **not** report success: it clears the pending approval (so a naive retry from the user can't compound the problem), logs the full raw call detail at ERROR level for manual reconciliation against Morning, and returns a friendly Hebrew error (`APPROVAL_POSSIBLY_DUPLICATED`) explicitly telling the user to check manually in the system and not approve again in the meantime.

**Correction (2026-08-03, same day):** the guard originally counted *any* `mcp_call` entries in the response, not specifically the approved tool. This produced a real false positive: a legitimate `create_invoice` call followed by its natural `download_invoice_pdf` follow-up (required by the constitution - every `create_invoice` confirmation must include a download link) was wrongly flagged as a duplicate and blocked a good response. Narrowed to count only executions of `pending.tool_name` specifically. **Incident 1 (the original, first-observed case) remains confirmed genuine** independent of this correction - verified via two actual, distinct invoice documents (`#51207`, `#51208`) both present in the Morning sandbox for the same client/amount, not just via the mcp_call count. "Incident 2" was this exact false-positive pattern (`create_invoice` + `download_invoice_pdf`), confirmed on later review - see Description.

**This does not prevent the duplicate document from existing in Morning** — both calls have already reached the real API by the time this code runs. It only guarantees `denidin-app` never silently reports false success when this happens, and gives a human an unambiguous signal to go check and correct the real system.

## Fix Options Considered (for true prevention — not yet approved/implemented)

**A. Idempotency at the Morning-API-call layer (`apps/morning-mcp-app`).** `pending.approval_request_id` is already unique per approval and available to pass through as a tool argument. The Morning-side tool implementation could check "have I already created a document for this exact key?" before calling the real Green Invoice API, and return the existing result on a repeat instead of creating a new one. This is the only place that can *guarantee* single execution, since it's the one place that actually talks to the real financial system, regardless of how many times OpenAI dispatches the call. Open question, not yet researched: whether Green Invoice's own API supports a native idempotency key, or whether a local dedup cache would need to be built in `apps/morning-mcp-app` itself.

**B. Accept the interim mitigation as sufficient for now.** No further code changes; rely on "detect duplication, refuse to report false success, alert for manual check" as the standing behavior.

### Decision (2026-08-03)
**Option B**, explicitly approved by the human reporter. Option A remains documented above as the known path to true prevention, to be picked up if/when duplication recurs at a rate or in a context that makes the interim mitigation insufficient.

## Test Gap Analysis
The confirmed mechanism (auto-retry-on-429 causing a second dispatch) is now covered by a deterministic regression test (`tests/unit/test_ai_handler_approval_no_retry.py`, 2026-08-04) - it mocks the OpenAI client to raise `RateLimitError` and asserts the approval-resolution call is attempted exactly once, proven to fail against the pre-fix code (2 attempts) and pass against the fix (1 attempt). The `>1 mcp_call` detect-and-refuse guard's own logic still has **no** dedicated unit test coverage (mocking a `response.output` with 2+ same-tool `mcp_call` items) - a reasonable, low-cost follow-up, not yet done.

## Acceptance Criteria
- [x] Root cause investigated with real evidence (log-confirmed for the one real incident)
- [x] Interim mitigation approved by human and implemented
- [x] "Incident 2" re-examined and confirmed to be a false positive of the original guard, not a second real duplication (2026-08-04)
- [x] Root cause fully closed: leftover tenacity `@retry` decorator on `_call_openai_approval_api` (capable of silently reproducing Incident 1's mechanism) found and removed (2026-08-04)
- [x] Deterministic unit test proving the fix (`tests/unit/test_ai_handler_approval_no_retry.py`, 2026-08-04) - fails against pre-fix code, passes against the fix
- [ ] Unit test coverage for the `>1 mcp_call` duplicate-detection branch itself (still not written - separate from the above, defense-in-depth only)
- [ ] True prevention (Option A, Morning-side idempotency) — explicitly deferred, not started; no longer needed for the confirmed mechanism (now closed), only for a hypothetical, never-confirmed alternate cause
- [x] Human sign-off to leave Option A as-is for now (2026-08-03)

## References
- `apps/denidin-app/src/handlers/ai_handler.py` (`_call_openai_approval_api`, `_resolve_pending_approval`)
- `apps/denidin-app/src/constants/error_messages.py` (`APPROVAL_FAILED_TRY_AGAIN`, `APPROVAL_POSSIBLY_DUPLICATED`)
- Feature 022 (`specs/done/v0.0.1/022-explicit-approval-for-document-creation/`) — the approval-gating mechanism this bug occurs within
- `feature/033-ledger-event-persistence` branch — where both incidents were observed and the interim mitigation was built
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
