# Implementation Plan: Receipts Without Invoice (+ Transaction Account Cancellation) — Feature 056

**Feature**: 056-receipts-without-invoice
**Branch**: `feature/056-receipts-without-invoice`
**Spec**: `./spec.md` · **User Stories**: `./user-stories.md` · **Research**: `./research.md`
**Status**: TASKED — `tasks.md` complete (T001-T010), ready for `speckit.implement`
**Updated**: 2026-08-18

**Compliance**: CONSTITUTION.md (§I no env vars — N/A, no config touched; all-Israel-local-time —
N/A, no new datetime handling beyond the already-shared `_validate_payment_date`; §III git
workflow — on `feature/056-receipts-without-invoice`, off `master`; §V zero-mocking — new tests
hit the real Morning sandbox exactly like every existing `create_receipt`/
`create_combo_document_as_reference` test; §XVII no monkey-patching — both changes are plain new
code paths, no runtime patching). No feature flag: both changes are purely additive/extending
(an optional parameter becoming valid, and a brand-new tool) — `create_receipt`'s existing
required-original path is byte-for-byte unchanged when a caller still supplies
`original_internal_morning_id`, satisfying the "default behavior unchanged" bar without needing
a toggle.

---

## Summary

Two related Morning-tool changes, per spec.md's two user stories:

1. **US1 (P1)**: relax `create_receipt` so `original_internal_morning_id` is optional. When
   omitted, the call takes `client_name`/`name_resolved=True`/`amount`/`description`/
   `payment_date` directly (the same resolved-client contract every other `create_*` tool
   already uses) and creates a standalone type-400 receipt with no VAT/income line and no
   `linkedDocumentIds` — for deposits, loan repayments, or advance payments that have no
   invoice behind them. When an original IS supplied, every existing behavior is unchanged.
2. **US2 (P2)**: a new tool, `cancel_transaction_account`, cancels a type-300 transaction
   account with **zero documents created** — confirmed live (`research.md`) to be
   `MorningClient.close_invoice` (already existing), with an app-side idempotency guard
   (Morning's raw API isn't idempotent on a redundant close) and its own confirmation wording
   (never reusing `get_invoice_details`'s "paid" formatting, confirmed live to be misleading
   here).

Both changes are godfather/admin-gated and approval-required, matching every other
document-mutating Morning tool. Both are audit-logged via `audit.py`'s existing pattern.

## Technical Context

- **Language/Version**: Python 3.11 (unchanged).
- **Primary Dependencies**: none new — `MorningClient.close_invoice`/`open_invoice` already
  exist; the standalone-receipt path reuses `resolve_client_name`/`_require_resolved_client`,
  already used by `create_invoice`/`create_transaction_account`/`create_combo_document`.
- **Storage**: N/A — no new persistence in either app; Morning itself is the system of record.
- **Testing**: `apps/morning-mcp-app/tests/unit/` (payload-builder unit tests, pure functions,
  no mocking of internals needed since these are deterministic builders) +
  `apps/morning-mcp-app/tests/integration/` (real sandbox, no mocking — new
  `test_morning_sandbox_standalone_receipt.py` and
  `test_morning_sandbox_cancel_transaction_account.py`, following the existing
  `test_morning_sandbox_invoice_status_tools.py` pattern) + `apps/denidin-app`'s `tests/billed/`
  for the RBAC/approval-gate/tool-attachment wiring (real OpenAI text calls, cheap, no
  per-run approval needed per this app's testing rules).
- **Target Platform**: `apps/morning-mcp-app` (server.py's FastMCP tool registration,
  `tools.py`) and `apps/denidin-app` (`ai_handler.py`'s `APPROVAL_REQUIRED_MCP_TOOLS`) — no
  new runtime/container, but requires the usual rebuild-and-redeploy step once merged (not part
  of this plan; a separate, explicit human decision per CLAUDE.md).
- **Scale/Scope**: one relaxed tool contract (branch inside `create_receipt`), one brand-new
  tool (`cancel_transaction_account`), one new payload-builder function, one new formatter
  function, two `APPROVAL_REQUIRED_MCP_TOOLS`/RBAC wiring additions in `apps/denidin-app`, one
  new `MorningClient` call site (reusing `close_invoice`, no new client method).

## Constitution Check

- **No env vars** — PASS: nothing here touches config-loading.
- **Israel local time** — N/A: no new datetime logic; `payment_date` validation is entirely
  reused from `_validate_payment_date` (already shared by `create_receipt`/
  `create_combo_document`/`create_transaction_account`).
- **Feature branch** — PASS: `feature/056-receipts-without-invoice`, off `master`.
- **Feature flags** — N/A, see Compliance note above (purely additive, default path unchanged).
- **Zero-mocking** — PASS: all new integration tests hit the real Morning sandbox; unit tests
  exercise pure payload-builder functions directly, no internal component is mocked.
- **No monkey-patching** — PASS: new code paths (an `if original_internal_morning_id:` branch,
  a new function, a new tool registration), no runtime method replacement.
- **Test immutability (§VIII)** — PASS: `create_receipt`'s existing tests
  (`test_morning_sandbox_invoice_status_tools.py` and its unit-test counterparts) are untouched;
  the new standalone-receipt path is exercised entirely by new tests.
- **NO UNVERIFIED THIRD-PARTY ASSUMPTIONS** — PASS: the one real unknown (transaction-account
  cancellation mechanism) was live-confirmed against the sandbox before this plan was written
  (`research.md`) rather than assumed.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/056-receipts-without-invoice/
├── spec.md              # done — CLARIFIED (2026-08-18)
├── user-stories.md      # done — CLARIFIED
├── research.md          # done — cancellation mechanism live-confirmed (2026-08-18)
├── plan.md              # this file
├── data-model.md         # this phase
├── contracts/            # this phase — updated create_receipt.json, new
│                          # cancel_transaction_account.json
├── quickstart.md         # this phase
└── tasks.md              # done — T001-T010 (/speckit.tasks)
```

### Source Code

```text
apps/morning-mcp-app/src/denidin_mcp_morning/
├── tools.py
│   # create_receipt(...): original_internal_morning_id becomes Optional[str] = None.
│   #   When None: require client_name + name_resolved=True (via _require_resolved_client,
│   #   same pattern as create_invoice/create_transaction_account), amount, description,
│   #   payment_date (already required) - build a NEW standalone payload (no VAT/income line,
│   #   no linkedDocumentIds) via a new _build_standalone_receipt_payload(...).
│   #   When given: existing behavior, byte-for-byte unchanged (REQ-INV-016).
│   #
│   # NEW: cancel_transaction_account(client, original_internal_morning_id) -> str
│   #   1. client.get_invoice(original_internal_morning_id); refuse (ValueError) if type != 300
│   #      (REQ-INV-022, same pattern as create_receipt's type-305-only guard).
│   #   2. If already status != 0 (not open - already closed/cancelled or fulfilled): idempotent
│   #      no-op, return the current-state confirmation (REQ-INV-021, REQ-INV-025) - NEVER call
│   #      close_invoice on a non-open document (confirmed live: raw API 400s on that).
│   #   3. Otherwise: client.close_invoice(original_internal_morning_id); log_mutation (with
│   #      client_id/client_name extracted from the already-fetched original, same pattern as
│   #      create_receipt's linked path - REQ-INV-024); return a NEW, dedicated Hebrew
│   #      confirmation (REQ-INV-026 - never "שולם"/paid wording).
│   #
│   # NEW: _build_standalone_receipt_payload(client_id, amount, description, payment_date) -> dict
│   #   type 400, no "income"/vatType line (REQ-INV-017), no linkedDocumentIds, a payment[] line
│   #   carrying the real payment_date (mirrors _build_payment_receipt_payload's payment line).
│
├── server.py
│   # Register the new cancel_transaction_account MCP tool (mirrors how the 4 type-specific
│   # create_* tools are registered - feature 021's pattern).
│
├── formatters.py
│   # NEW: format_transaction_account_cancelled(...) or equivalent - the dedicated confirmation
│   #   text for REQ-INV-026, never routing through get_invoice_details's "שולם" wording.
│
└── audit.py
    # No new code needed - cancel_transaction_account's log_mutation/log_refusal calls reuse
    # the existing pattern exactly as every other tool already does.

apps/denidin-app/src/handlers/ai_handler.py
├── APPROVAL_REQUIRED_MCP_TOOLS: add "cancel_transaction_account" (REQ-INV-023).
│   create_receipt is already present - the relaxed contract inherits the gate automatically,
│   no change needed there.

apps/morning-mcp-app/tests/unit/
├── test_tools_document_creation.py
│   # _build_standalone_receipt_payload + create_receipt's new branch: asserts no VAT/income
│   #   line, no linkedDocumentIds, correct payment[] shape (alongside the existing
│   #   _build_payment_receipt_payload/create_receipt coverage already in this file).
├── test_mark_invoice_paid.py
│   # cancel_transaction_account: idempotency guard logic (already-closed/already-fulfilled
│   #   short-circuits without calling client.close_invoice) - extends this file's existing
│   #   _FakeMorningClient with a close_invoice stub, same convention as its existing
│   #   idempotency tests for create_receipt/create_combo_document_as_reference - NOT the same
│   #   as "mocking an external service", which stays real-sandbox-only in integration/.
├── test_formatters.py
│   # format_transaction_account_cancelled: asserts the confirmation never says "שולם"/paid.

apps/morning-mcp-app/tests/integration/
├── test_morning_sandbox_standalone_receipt.py (NEW)
│   # US1's 5 acceptance scenarios, real sandbox, real create_receipt calls.
├── test_morning_sandbox_cancel_transaction_account.py (NEW)
│   # US2's 5 acceptance scenarios, real sandbox, real cancel_transaction_account calls.

apps/denidin-app/tests/billed/
├── (existing file covering Morning-tool RBAC/approval wiring, or a new one)
│   # Real OpenAI text call confirming cancel_transaction_account is attached only for
│   # godfather/admin and requires approval before executing (REQ-INV-023).
```

## Phased Execution

**TDD note (METHODOLOGY §VI, redefined 2026-08-18)**: "Test (TDD)" below, within Phase 1/2,
means §VI.b's unit/integration RED→GREEN discipline (unchanged from before the redefinition).
"TDD" proper — §VI.a's `billed`/`expensive` user-perspective tests — is defined during these
same phases but deliberately not run until Phase 3, after both phases below are GREEN.

### Phase 1 — Standalone receipt (US1, P1)
1. **Test (§VI.b)**: unit test for `_build_standalone_receipt_payload` (RED); integration tests
   in `test_morning_sandbox_standalone_receipt.py` covering US1's 5 acceptance scenarios (RED,
   real sandbox).
2. **Implement**: `_build_standalone_receipt_payload`, relax `create_receipt`'s signature and
   branch on `original_internal_morning_id is None`. Tests go GREEN.
3. **Verify**: full existing `create_receipt` test suite still passes unchanged (REQ-INV-016).

### Phase 2 — Transaction account cancellation (US2, P2)
1. **Test (§VI.b)**: unit test for the idempotency guard logic (RED); integration tests in
   `test_morning_sandbox_cancel_transaction_account.py` covering US2's 5 acceptance scenarios
   (RED, real sandbox — reuses this session's live research.md findings directly).
2. **Implement**: `cancel_transaction_account` in `tools.py`, its dedicated formatter, its
   `server.py` MCP registration. Tests go GREEN.
3. **RBAC wiring**: add to `APPROVAL_REQUIRED_MCP_TOOLS` in `apps/denidin-app`.

### Phase 3 — Acceptance (§VI.a — TDD proper, `billed`/`expensive`, run once)
A `billed`-tier test (written during Phase 2, alongside its other tasks, since the contract is
already known) proves `cancel_transaction_account`'s RBAC/approval-gate wiring end-to-end from a
real user's perspective. It is written early but run only once, here, after Phase 1 AND Phase 2
are both GREEN — this phase is the feature's actual acceptance proof, not a per-story gate.

### Phase 4 — Close out
Move spec to `specs/done/` once merged, per folder movement rules (part of the `haleluya` flow,
not run unprompted).

## Complexity Tracking

No Constitution Check violations requiring justification. The one piece of real complexity —
confirming Morning's real cancellation mechanism rather than guessing — was resolved in
`research.md` before this plan was written, exactly as the zero-assumption rule requires.
