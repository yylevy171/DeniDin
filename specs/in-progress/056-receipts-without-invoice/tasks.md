# Tasks: Receipts Without Invoice (+ Transaction Account Cancellation) — Feature 056

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **User stories**: `./user-stories.md` ·
**Research**: `./research.md` · **Data model**: `./data-model.md` · **Contracts**: `./contracts/`
**Apps**: `apps/morning-mcp-app/` (primary — both changes live here) + `apps/denidin-app/`
(one RBAC-list addition + a `billed` test for US2 only; US1 needs no `denidin-app` change at
all, since `create_receipt` is already in `APPROVAL_REQUIRED_MCP_TOOLS`)
**Branch**: `feature/056-receipts-without-invoice`

## Conventions

- Task ID `T###`. `[P]` = parallelizable (different files, no dependency on an incomplete task).
- **TDD gate (METHODOLOGY §VI)**: the test task (`a`) is written first, must **fail** (RED), and
  needs **explicit human approval** before the implementation task (`b`). Approved tests are
  **immutable** (CONSTITUTION §VIII) unless explicitly re-approved.
- **Two-tier testing** (mirrors Feature 027's pattern): fast **unit** tests with a fake
  `MorningClient` double for pure logic (allowed per CONSTITUTION §I/§V — mocking an *external*
  service boundary, not an internal component), plus real **Morning-sandbox integration** tests
  (no mocks) proving the actual wire contract, plus a real-API **`billed`** test
  (`apps/denidin-app`, `@pytest.mark.billed` — text-only, no per-run approval gate, unlike
  `expensive`) for the RBAC/approval-gate wiring only.
- **No Foundation phase**: unlike Feature 027, neither user story here introduces new *shared*
  helper code — US1 reuses `resolve_client_name`/`_require_resolved_client` (already existing);
  US2 reuses `MorningClient.close_invoice`/`open_invoice` (already existing). Each story's tasks
  go straight into its own phase.
- **Sandbox test naming**: client names in integration tests use the existing
  `f"Test Client {marker}"` convention (`marker = f"DENIDIN_056_{label}_{int(now_local().timestamp())}"`),
  matching every other `apps/morning-mcp-app/tests/integration/test_morning_sandbox_*.py` file —
  never a fixed literal name, never `quickstart.md`'s narrative persona names.
- **Sandbox timing quirks (research.md Finding 4)**: any new sandbox-integration test that calls
  `create_transaction_account` and then immediately `close_invoice`/`cancel_transaction_account`
  on the result must tolerate the same short propagation-lag retry this session's own research
  script needed (a few seconds, a handful of retries) — a single unretried failure right after
  creation is a known sandbox characteristic, not a real bug, per `research.md`.
- **Environment-start discipline (CLAUDE.md)**: the `billed` test task still needs `denidin-app`
  dev running with Morning MCP attached — starting that environment needs its own separate,
  explicit approval, never implied by approval of the test task itself.
- Paths relative to `apps/morning-mcp-app/` or `apps/denidin-app/` as stated per task.

---

## Phase 1 — User Story 1: Standalone receipt for a deposit, loan repayment, or advance payment (Priority: P1) 🎯 MVP

**Goal**: `create_receipt` accepts a call with no `original_internal_morning_id`, resolving the
client via the standard `resolve_client_name`/`name_resolved=True` contract and creating a
standalone type-400 receipt (no VAT/income line, no `linkedDocumentIds`) — while the existing
linked-original path stays byte-for-byte unchanged (REQ-INV-014 through REQ-INV-019).

**Independent Test**: `create_receipt(client, client_name=..., name_resolved=True, amount=...,
description=..., payment_date=...)` (no `original_internal_morning_id`) against the real Morning
sandbox creates a real type-400 document with `linkedDocumentIds == []` and no `income` key —
independently verifiable with no dependency on Phase 2.

- [ ] **T001a** [P] [US1] Write unit tests for a new payload builder
  `_build_standalone_receipt_payload(client_id, amount, description, payment_date)` in
  `apps/morning-mcp-app/tests/unit/test_tools_document_creation.py` (alongside the existing
  `test_build_receipt_payload_defaults_and_override`, which covers the linked-original builder
  `_build_payment_receipt_payload`): asserts `type == 400`, no `"income"`/`"vatType"` key
  present at all, `"linkedDocumentIds" not in payload or payload["linkedDocumentIds"] == []`,
  `client == {"self": False, "id": client_id}`, and `payment == [{"type": 1, "price": amount,
  "date": <validated payment_date>}]` (reusing `_validate_payment_date`, same as every other
  payment-carrying builder). This is data-model.md's standalone-receipt shape's RED phase.
- [ ] **T001b** [US1] Implement `_build_standalone_receipt_payload` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`, next to
  `_build_payment_receipt_payload` (BLOCKED until T001a approved).
- [ ] **T002a** [P] [US1] Write unit tests for `create_receipt`'s new branch in the same
  `test_tools_document_creation.py`, alongside the existing `test_create_receipt_*` functions
  (around line 441+): (1) `original_internal_morning_id=None`, `name_resolved=True`, a resolved
  fake client → calls `_build_standalone_receipt_payload` (T001a), not
  `_build_payment_receipt_payload`, and never calls `client.get_invoice` at all (there is no
  original to fetch) — REQ-INV-014/015; (2) `original_internal_morning_id=None`,
  `name_resolved=False` (or omitted) → refuses immediately via the same
  `_require_resolved_client` contract violation `create_invoice` already uses, no Morning call
  attempted at all; (3) `original_internal_morning_id` given (existing path) → behavior and
  Morning calls are byte-for-byte identical to before this task (REQ-INV-016) — reuse/extend the
  existing `test_create_receipt_happy_path_uses_original_and_allows_override` test's fixture
  shape as the "unchanged" regression check rather than writing it from scratch.
- [ ] **T002b** [US1] Implement the branch in `create_receipt()`
  (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`): make
  `original_internal_morning_id: Optional[str] = None`; add `client_name`, `name_resolved:
  bool = False` parameters; when `original_internal_morning_id is None`, resolve via
  `_require_resolved_client` (same call signature `create_invoice` uses), build via T001b, call
  `client.create_invoice`, `log_mutation`, and return a Hebrew confirmation (reuse the existing
  `"הופקה קבלה מספר {receipt_number}..."` shape, dropping the `"עבור חשבונית מספר {original}"`
  clause since there is no original to name — REQ-INV-018's free-text `description` carries the
  reason instead). When given, existing code path is untouched (BLOCKED until T002a approved).
- [ ] **T003a** [P] [US1] Write real-sandbox integration test
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_standalone_receipt.py`, mirroring
  `test_morning_sandbox_invoice_status_tools.py`'s structure: (1) happy path — seed a real
  client, call `create_receipt` with no original, verify via `client.get_invoice` on the
  returned id that `type == 400`, `linkedDocumentIds == []`, no `income` key; (2) a later,
  separate `create_invoice` call for the "same" transaction is NOT required to reference the
  standalone receipt and succeeds independently — REQ-INV-019; (3) an unresolved/ambiguous
  `client_name` refuses exactly like `create_invoice`'s existing non-exact-match tests, zero
  documents created; (4) the EXISTING linked-original `create_receipt` flow (seed an invoice,
  pay it via the original path) still behaves identically — regression check for REQ-INV-016,
  can reuse `test_morning_sandbox_invoice_status_tools.py`'s existing fixtures/pattern directly
  rather than re-deriving it.
- [ ] **T003b** [US1] Verify GREEN — run the new integration test file (real sandbox, no
  approval gate needed per CLAUDE.md's integration-test rules; `apps/morning-mcp-app` doesn't
  need a running container for this, tests run via host `pytest` directly). Confirm the full
  existing `apps/morning-mcp-app/tests/` suite (unit + integration, real sandbox) still passes
  with zero regressions (BLOCKED until T001b/T002b are both implemented and T003a is approved).

**Checkpoint**: User Story 1 fully functional and independently deployable (MVP) — a godfather
can record a deposit/loan/advance-payment receipt with zero invoice ever created for it, and
every existing `create_receipt` behavior is provably unchanged.

---

## Phase 2 — User Story 2: Cancelling a transaction account creates no document (Priority: P2)

**Goal**: a new `cancel_transaction_account` tool sets a type-300 document's status to
"manually closed" via the already-existing `MorningClient.close_invoice`, creating zero
documents, with an app-side idempotency guard and a confirmation that never says "paid"
(REQ-INV-020 through REQ-INV-026).

**Independent Test**: `cancel_transaction_account(client, original_internal_morning_id=<a real
open type-300 doc>)` against the real sandbox sets `status: 2`, `linkedDocuments` unchanged,
zero new documents for that client — independently verifiable with no dependency on Phase 1.

- [ ] **T004a** [P] [US2] Write unit tests for `cancel_transaction_account`'s idempotency guard
  in `apps/morning-mcp-app/tests/unit/test_mark_invoice_paid.py` (alongside the existing
  `test_already_closed_type_300_is_idempotent_no_op`/`test_already_closed_type_305_is_idempotent_no_op`
  pattern) — extend `_FakeMorningClient` with a `close_invoice(internal_morning_id)` stub
  (tracking calls the same way `create_invoice_calls` already does) since it isn't faked there
  today. Assert: (1) a status-`0` (open) original → `close_invoice` IS called exactly once;
  (2) a status-`2` (already manually closed) original → `close_invoice` is NEVER called, a
  no-op confirmation is returned instead (REQ-INV-021/025); (3) a status-`1` (closed via a
  linked payment document — i.e. already fulfilled) original → same no-op, `close_invoice`
  never called — cancellation must never contradict a real payment document; (4) a non-type-300
  original (e.g. type 305) → raises `ValueError`, `close_invoice` never called (REQ-INV-022,
  mirrors `test_create_receipt_rejects_a_transaction_account_original`'s existing pattern for
  the opposite direction).
- [ ] **T004b** [US2] Implement `cancel_transaction_account(client,
  original_internal_morning_id: str) -> str` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`: fetch via `client.get_invoice`;
  raise `ValueError` if `type != _TRANSACTION_ACCOUNT_DOCUMENT_TYPE`; if `status != 0`, return
  the no-op confirmation (T005b's formatter) without calling `close_invoice`; otherwise call
  `client.close_invoice`, `log_mutation`, return T005b's confirmation (BLOCKED until T004a
  approved).
- [ ] **T005a** [P] [US2] Write unit tests for a new formatter (working name
  `format_transaction_account_cancelled(...)`) in
  `apps/morning-mcp-app/tests/unit/test_formatters.py`: asserts the confirmation text never
  contains "שולם" or any other paid/payment wording — this is the direct regression test for
  research.md Finding 2 (`get_invoice_details`'s existing formatter does say "שולם" for a
  status-2 document, which is exactly the bug this new formatter must not repeat).
- [ ] **T005b** [US2] Implement `format_transaction_account_cancelled(...)` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` (BLOCKED until T005a approved).
- [ ] **T006** [US2] Register `cancel_transaction_account` as a new MCP tool in
  `apps/morning-mcp-app/server.py`, mirroring how the existing `create_*`/
  `create_combo_document_as_reference` tools are registered (Feature 021's pattern) — no test
  task on its own; exercised end-to-end by T007a/T008a below.
- [ ] **T007a** [P] [US2] Write real-sandbox integration test
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_cancel_transaction_account.py`,
  mirroring `test_morning_sandbox_invoice_status_tools.py`'s structure (with the propagation-lag
  retry tolerance noted in Conventions above): (1) happy path — seed an open type-300 account,
  cancel it, verify `status == 2`, `linkedDocuments` unchanged (still `[]`), close response's
  own id equals the original's id (no new document); (2) idempotency — cancel the same
  already-cancelled account again, verify (via a call-count check on a thin wrapper, or by
  asserting the document's `status`/no new document appears) that no redundant `close_invoice`
  call was made; (3) already-fulfilled — fulfill a second seeded account via
  `create_combo_document_as_reference` first, then attempt cancellation, verify the resulting
  type-320 document is untouched and no new document is created; (4) wrong document type —
  attempt cancellation against a real type-305 invoice id, verify it's rejected and zero
  documents change; (5) reversibility sanity check — `open_invoice` on a cancelled account still
  cleanly returns it to `status: 0` (confirms this feature doesn't accidentally change
  `open_invoice`'s existing behavior).
- [ ] **T007b** [US2] Verify GREEN — run the new integration test file (real sandbox, no
  approval gate needed, same as T003b). Confirm the full existing `apps/morning-mcp-app/tests/`
  suite still passes with zero regressions (BLOCKED until T004b/T005b/T006 are implemented and
  T007a is approved).
- [ ] **T008** [US2] Add `"cancel_transaction_account"` to `APPROVAL_REQUIRED_MCP_TOOLS` in
  `apps/denidin-app/src/handlers/ai_handler.py` (REQ-INV-023). No test-then-impl split needed on
  its own — a one-line addition to an existing tuple, verified by T009a below rather than a
  dedicated unit test.
- [ ] **T009a** [P] [US2] Write a real-API `billed` test in
  `apps/denidin-app/tests/billed/` (an existing Morning-tool RBAC/approval file if one already
  covers this shape, otherwise a new `test_cancel_transaction_account_billed.py` following the
  existing `tests/billed/test_denidin_morning_*_e2e.py` pattern): a godfather asks to cancel a
  transaction account → the tool call comes back as a `mcp_approval_request` (never executes on
  the ASK turn) → an explicit "כן" turn executes it. No per-run approval needed to write/run
  this (billed tier, CLAUDE.md) — but running it does need `denidin-app` dev running with
  Morning MCP attached, which is its own separate, explicit environment-start approval.
- [ ] **T009b** [US2] Verify GREEN (BLOCKED until T008 is implemented, T009a is approved, and
  the dev environment is explicitly approved to start and running).
- [ ] **T010** [US2] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US2 scenario for real
  (needs its own explicit approval to start the dev environment, separate from T009b's).

**Checkpoint**: User Story 2 fully functional — a godfather can cancel an unfulfilled
transaction account with zero documents ever created, cleanly idempotent, RBAC-gated and
approval-required exactly like every other Morning-mutating tool.

---

## Dependencies

- Within Phase 1: T001b depends on T001a; T002b depends on T002a AND T001b (needs the builder to
  call); T003a can be written in parallel with T001a/T002a (`[P]`, different file), but T003b
  (verify GREEN) depends on T001b + T002b + T003a-approved.
- Within Phase 2: T004b depends on T004a; T005b depends on T005a; T006 depends on T004b + T005b
  (needs both to register a working tool); T007a can be written in parallel (`[P]`), but T007b
  depends on T004b + T005b + T006 + T007a-approved; T008 has no code dependency on T004-T007 but
  is naturally done alongside them; T009a/T009b depend on T006 + T008.
- **Phase 1 and Phase 2 are fully independent of each other** — no shared new code, no shared
  test files, no ordering constraint between them (per plan.md's Constitution Check and
  data-model.md, confirmed no overlap). Either phase can be implemented and merged first.

## Parallel Execution

- T001a, T002a, T003a can all be drafted in parallel (three different files/functions, no
  interdependency in the RED phase) — but T002a's fixtures should wait for T001a's approved
  shape if the same fake-payload assertions are reused between them, to avoid rework.
- T004a, T005a, T007a can similarly be drafted in parallel.
- Phase 1 and Phase 2 as a whole can be worked on in parallel by two different sessions/people,
  since they touch disjoint functions (`create_receipt` vs. a brand-new
  `cancel_transaction_account`) and disjoint test files.

## Implementation Strategy

**MVP = Phase 1 (User Story 1)** — the more common, P1 real-world need (deposits/loan
repayments/advance payments), independently mergeable and deployable on its own. Phase 2 (P2,
transaction-account cancellation) is a smaller, independent increment that can follow in the
same PR or a separate one — spec.md's Success Criteria (SC1/SC2) are each satisfied by their own
phase alone, so partial delivery (Phase 1 only, for a while) is a legitimate, real MVP, not just
a task-list convenience.
