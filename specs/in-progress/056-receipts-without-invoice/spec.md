# Feature Specification: Receipts Without Invoice (+ Transaction Account Cancellation)

**Feature Branch**: `feature/056-receipts-without-invoice`
**Created**: 2026-08-17
**Clarified**: 2026-08-18
**Status**: TASKED — clarified and researched 2026-08-18 (direct user decision, three
questions; cancellation mechanism live-confirmed), `plan.md`/`data-model.md`/`contracts/`/
`quickstart.md`/`tasks.md` complete. Ready for `speckit.analyze` and/or `speckit.implement` —
every implementation task in `tasks.md` is a TDD (test-then-implementation) pair; each test
task needs its own explicit human approval before its implementation task may proceed, per
METHODOLOGY §VI, and none of `tasks.md`'s test tasks have been approved/run yet.
**Input**: User description: two related Morning (Green Invoice) accounting-rule logic changes,
captured together as one feature ("open a feature 56 - receipts without invoice ... create a new
feature 56 to encompass the 2 new logic changes required for accounting rules in morning").

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** ("NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"): the exact Morning API mechanism
  for a document-less transaction-account cancellation was NOT assumed — it was confirmed live
  against the real sandbox on 2026-08-18 (see `research.md`), same discipline as every other
  Morning-integration feature in this project.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs (continuing the `REQ-INV-*` series
  started by Feature 027, next available number `REQ-INV-014`).

**Required Files**: `user-stories.md` (present, DRAFT) ✅ · `spec.md` (this file, DRAFT) ·
`research.md` (present — transaction-account cancellation mechanism, live-confirmed 2026-08-18)
✅ · `plan.md` (present, Ready for Task Generation) ✅ · `data-model.md` (present) ✅ ·
`contracts/` (present — `create_receipt.json` updated, `cancel_transaction_account.json` new)
✅ · `quickstart.md` (present) ✅ · `tasks.md` (present — T001-T010 across 2 independent
phases/user stories) ✅.

---

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | Recording a deposit, loan repayment, or advance payment as a receipt with no prior invoice | P1 |
| US2 | Cancelling an open transaction account creates no document | P2 |

## Terminology Glossary

- **Standalone receipt**: A Morning receipt (type 400, "קבלה") created with no prior document
  to reference — as opposed to today's `create_receipt`, which always requires an
  `original_internal_morning_id` pointing at an existing type-305 tax invoice being paid.
- **Transaction account** (חשבון עיסקה, Morning document type 300): a non-tax document already
  creatable via `create_transaction_account` (Feature 021). Today it can only be *fulfilled* —
  closed as paid via `create_combo_document_as_reference` (renamed from `close_transaction_account`
  by bugfix-038), which deliberately creates a linked type-320 combo document. There is currently
  no way to mark one *abandoned/cancelled* instead.
- **Cancellation vs. fulfillment** (transaction accounts only): fulfillment records that the
  underlying deal actually happened and was paid (a real document, type-320, is created).
  Cancellation records that it did *not* happen — no money changed hands for this account, no
  document should exist recording income. This distinction does not apply to tax invoices
  (type 305): Israeli law forbids voiding an issued tax invoice outright, so a tax invoice is
  always "cancelled" via a linked type-330 credit invoice (`create_credit_note`,
  `_build_cancellation_payload`) — that existing, document-producing flow is unchanged and out
  of scope here.
- **Deposit / loan repayment** (פיקדונות / החזרי הלוואה): money received that is not business
  income — e.g. a refundable deposit, a guarantee payment, or a loan repayment. Must be
  documented (a receipt), but is not a taxable event and needs no invoice.
- **Advance payment / timing gap** (פער זמנים / מקדמות): a licensed dealer or company receiving
  payment before the transaction completes or goods are delivered — Israeli law requires a
  receipt to be issued immediately for money received, with the tax invoice following later, on
  completion, per that business's VAT-liability timing.

## Problem Statement

Two related gaps in `apps/morning-mcp-app`'s Morning (Green Invoice) tool coverage, both
accounting-rule logic changes captured together as one feature per explicit user decision:

1. **No way to record a receipt with no prior invoice.** `create_receipt`
   (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`) requires
   `original_internal_morning_id` and rejects any original whose type isn't 305 (tax invoice) —
   there is no way today to create a standalone receipt for a deposit, loan repayment, or advance
   payment that has no invoice behind it at all.
2. **Transaction-account cancellation has no document-less path.** The only existing way to
   change a type-300 transaction account's state is `create_combo_document_as_reference`, which
   always creates a type-320 document (fulfillment). There is no way to mark a transaction
   account cancelled/abandoned — the deal fell through, nothing to record as income — without
   that call incorrectly creating a real financial document for money that never moved.

## Clarifications (2026-08-18, direct user decision)

- **Q1 (tool contract)**: Should a standalone receipt be a new dedicated tool, or a relaxed
  `create_receipt`? → **A: Relax `create_receipt`** — `original_internal_morning_id` becomes
  optional; when omitted, the call is treated as a standalone receipt instead of a
  payment-against-an-invoice receipt. One tool, one contract branches on whether an original was
  given. *(User also reaffirmed, unprompted, that transaction-account cancellation must not
  create any document — only mark the account as handled — matching the original request.)*
- **Q2 (reason tracking)**: Does the system need to record *which* justification applies
  (deposit/loan-repayment vs. advance-payment timing-gap)? → **A: No — free text only.** The
  model composes an appropriate Hebrew description per the runtime constitution's existing
  free-text convention (as it already does for every other document description). No structured
  reason code, enum, or new persisted field.
- **Q3 (advance → later invoice linkage)**: When the real tax invoice is eventually issued for a
  transaction that had an earlier advance-payment receipt, should it reference that receipt? →
  **A: No linkage — independent documents.** The later invoice is created the normal way
  (`create_invoice`), with no `linkedDocumentIds` reference back to the earlier standalone
  receipt. Correlating the two, if ever needed, is a bookkeeping task outside this feature.

## Assumptions (no reasonable-default clarification needed)

- **Client requirement unchanged**: a standalone receipt still requires a real, resolved client
  — same `client_name` + `name_resolved=True` contract every other create tool in this app
  already uses (`create_invoice`, `create_transaction_account`, `create_combo_document`), and
  the same REQ-INV-013 "must be linked to a real client, or refuse" rule `create_receipt`
  already enforces for the original-linked path today. A fully client-less receipt (e.g. a pure
  anonymous guarantee deposit) is out of scope — nothing in the feature request asked for that,
  and every other document-creating tool in this app already assumes a real client.
- **RBAC/approval**: godfather/admin-only (same as every other Morning MCP tool), and
  approval-required before executing — `create_receipt` is already in `ai_handler.py`'s
  `APPROVAL_REQUIRED_MCP_TOOLS`, so the relaxed contract inherits that gate automatically for
  free; the transaction-account cancellation capability must be added to that list explicitly
  (see REQ-INV-023).

## Functional Requirements

- **REQ-INV-014**: `create_receipt` MUST accept being called without
  `original_internal_morning_id`. When omitted, the call creates a standalone receipt not linked
  to any prior document, instead of the existing payment-against-an-invoice behavior.
- **REQ-INV-015**: When creating a standalone receipt (no original given), the tool MUST require
  `client_name` + `name_resolved=True` (the same resolved-client contract `create_invoice`
  already uses), `amount`, `description`, and `payment_date` (already a required field on the
  existing path) — a client-less call MUST be refused, not created with a blank/guessed client.
- **REQ-INV-016**: When `original_internal_morning_id` IS given, every existing behavior of
  `create_receipt` is unchanged byte-for-byte: type-305-only original validation, the
  already-closed idempotent no-op path, and the REQ-INV-013 refusal when the original isn't
  linked to a real client.
- **REQ-INV-017**: A standalone receipt records a pure cash movement (deposit, loan repayment,
  or advance payment) and MUST NOT carry a VAT/income line — consistent with how a type-300
  transaction account already carries no VAT concept. *(Exact Morning payload field shape is a
  planning/research question, not prescribed here — see the CONSTITUTION note above.)*
- **REQ-INV-018**: The model composes the standalone receipt's Hebrew description itself (e.g.
  "פיקדון", "החזר הלוואה", "מקדמה על חשבון...") per the runtime constitution's existing
  free-text description convention. No structured reason code is stored, validated, or exposed
  as a tool parameter (Clarification Q2).
- **REQ-INV-019**: A later tax invoice issued for a transaction that had an earlier
  advance-payment standalone receipt is NOT automatically linked back to that receipt — the two
  remain independent documents in Morning, with no `linkedDocumentIds` correlation added by this
  feature (Clarification Q3).
- **REQ-INV-020**: A new capability cancels an open transaction account (type 300) WITHOUT
  creating any Morning document — distinct from `create_combo_document_as_reference`, which
  deliberately creates a type-320 document to record fulfillment. Cancellation only marks the
  transaction account itself as closed/abandoned internally in Morning; no credit note, no
  combo document, no other linked document is ever produced by this path.
- **REQ-INV-021**: Cancelling an already-cancelled or already-fulfilled (paid) transaction
  account is idempotent — no error, no duplicate mutation — consistent with this app's existing
  idempotency convention for `create_receipt`'s and `create_combo_document_as_reference`'s
  already-closed no-op paths.
- **REQ-INV-022**: Cancellation under this feature is scoped to type-300 transaction accounts
  only. Attempting to cancel any other document type (a tax invoice in particular) is rejected
  with a clear error — tax-invoice cancellation continues to go exclusively through
  `create_credit_note`'s existing, document-producing flow, entirely unchanged by this feature.
- **REQ-INV-023**: Both the standalone-receipt path and the transaction-account-cancellation
  capability are godfather/admin-gated and require explicit user approval before executing
  (`ai_handler.py`'s `APPROVAL_REQUIRED_MCP_TOOLS`) — the relaxed `create_receipt` inherits this
  automatically; the new cancellation capability must be added to that list explicitly as part
  of implementation.
- **REQ-INV-024**: Every standalone receipt creation and every transaction-account cancellation
  (mutations AND refusals) is audit-logged via `audit.py`'s existing mutation/refusal pattern
  (resolved client id/name where applicable, payload sent, response received) — no exception
  carved out for either new capability.

## Resolved via live sandbox research (2026-08-18) — see `research.md`

The Open Questions below were live-confirmed against the real Morning sandbox (plus the
authoritative Green Invoice Postman collection) rather than decided by assumption, per
CONSTITUTION's "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" rule. Full trace, evidence, and the two
new findings below in `research.md`.

- **Exact Morning mechanism for "cancel with no document"**: **CONFIRMED — `close_invoice`**
  (`MorningClient`'s already-existing method, POST `/documents/{id}/close`). Live-verified: sets
  a type-300 transaction account's status `0 → 2`, creates zero documents (`linkedDocuments`
  stays `[]`, the close response's own id equals the original — no new document id), and is
  cleanly reversible via the already-existing `open_invoice`. Morning's status codes 3/"cancelling
  document"/4/"cancelled document" were ruled out: the authoritative Postman collection confirms
  there is no `/cancel` endpoint at all, and 3/4's real Hebrew names describe the two sides of
  the credit-note flow specifically — neither is reachable without creating a document, which is
  exactly what this feature must avoid.
- **New MCP tool vs. extending an existing one**: leaning new dedicated tool (working name
  `cancel_transaction_account`) — `close_invoice`'s contract (an id, nothing else) doesn't fit
  naturally as a branch of any existing `create_*` tool's shape. Final call still belongs to
  `plan.md`.
- **Does `MorningClient` need a new method?**: **No** — `close_invoice`/`open_invoice` already
  exist and are confirmed correct; no new client-level code needed for the Morning API surface
  itself.

### New requirements surfaced by this research (not part of the original placeholder)

- **REQ-INV-025**: The cancellation capability MUST implement its own idempotency guard in
  application code (check current status before calling `close_invoice`; short-circuit as a
  no-op if already closed) — confirmed live that Morning's raw API rejects a redundant
  `close_invoice` call with a 400 error rather than no-op'ing silently, consistent with this
  app's existing idempotency pattern for `create_receipt`/`create_combo_document_as_reference`.
- **REQ-INV-026**: The cancellation capability's confirmation/response text MUST NOT reuse
  `get_invoice_details`'s existing status formatting as-is — confirmed live that it renders a
  cancelled (status-2) transaction account as **"שולם" (paid)**, which is actively misleading
  for money that never moved. A distinct confirmation message (or a formatter branch aware of
  *why* a document was closed) is required.

## Out of Scope

- Structured reason-code tracking/reporting on standalone receipts (Clarification Q2).
- Auto-linking a later invoice back to an earlier advance-payment receipt (Clarification Q3).
- Any change to tax-invoice cancellation (`create_credit_note`) behavior — unchanged.
- Fully client-less standalone receipts (see Assumptions).
- Ledger-event auto-recognition of a standalone receipt as a deposit/loan event in
  `apps/denidin-app`'s `ledger_event_manager.py` (Feature 033) — a plausible, related follow-up
  flagged by the original request but not part of this feature's scope; cross-reference
  `specs/backlog/025-morning-sourced-ledger-events` if picked up later.

## Success Criteria

- **SC1**: A godfather/admin can ask DeniDin, in natural Hebrew, to record a deposit, loan
  repayment, or advance payment as a receipt with no invoice behind it, and receive a correct
  confirmation naming the real client and amount — with no invoice ever created for that
  movement.
- **SC2**: A godfather/admin can ask DeniDin to cancel/abandon an open transaction account, and
  no invoice, receipt, or credit-note document is ever produced as a result — Morning reflects
  the account as no longer open.
- **SC3**: Every existing invoice-payment receipt flow (`create_receipt` against a real type-305
  invoice) behaves identically to today, with zero observable change for any existing test or
  real conversation.

## References

- `specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster/` and
  `specs/done/bugfixes/bugfix-038-group-b-approval-missing-reference-data.md` — the
  client-name-resolution architecture (`resolve_client_name`, `_require_resolved_client`) that
  every create tool including the relaxed `create_receipt` must follow.
- `specs/done/027-mandatory-client-reference-invoicing/` — REQ-INV-001 through REQ-INV-013, the
  "must be linked to a real client, or refuse" rule this feature's standalone path also follows.
- `specs/done/021-flexible-document-creation/` — precedent for type-specific tool decisions and
  the type-300/305/320/330/400 document-type scope this app operates in.
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`create_receipt`,
  `create_combo_document_as_reference`, `_build_payment_receipt_payload`,
  `_build_cancellation_payload`), `morning_client.py` (`close_invoice`/`open_invoice`),
  `models.py` (`_MORNING_STATUS_CODES`).

## Next Steps

1. ~~`speckit.clarify`~~ — DONE 2026-08-18, all Q1-Q3 resolved via direct user decision.
2. `speckit.plan` — `plan.md`, `research.md` (must resolve the Open Questions above against the
   real Morning sandbox), `data-model.md`, `contracts/`, `quickstart.md`.
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
