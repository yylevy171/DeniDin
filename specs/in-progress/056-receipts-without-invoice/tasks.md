# Tasks: Receipts Without Invoice (+ Transaction Account Cancellation) — Feature 056

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **User stories**: `./user-stories.md` ·
**Research**: `./research.md` · **Data model**: `./data-model.md` · **Contracts**: `./contracts/`
**Apps**: `apps/morning-mcp-app/` (primary — both changes live here) + `apps/denidin-app/`
(one RBAC-list addition + a `billed` test for US2 only; US1 needs no `denidin-app` change at
all, since `create_receipt` is already in `APPROVAL_REQUIRED_MCP_TOOLS`)
**Branch**: `feature/056-receipts-without-invoice`

## Conventions

- Task ID `T###`. `[P]` = parallelizable (different files, no dependency on an incomplete task).
- **"TDD" (METHODOLOGY §VI, redefined 2026-08-18)** now means specifically Phase 3's
  `billed`/`expensive` acceptance test(s) below — defined now, but not run until Phases 1 and 2
  are both fully GREEN, then run once as this feature's real, user-perspective proof it works.
- **Unit/integration test discipline (METHODOLOGY §VI.b, unchanged)**: within Phases 1-2, every
  test task (`a`) is written first, must **fail** (RED), and needs **explicit human approval**
  before its implementation task (`b`). Approved tests are **immutable** (CONSTITUTION §VIII)
  unless explicitly re-approved. This is the same RED→GREEN discipline as before the TDD
  redefinition — only the term "TDD" itself moved to Phase 3.
- **Two-tier unit/integration testing** (mirrors Feature 027's pattern): fast **unit** tests with
  a fake `MorningClient` double for pure logic (allowed per CONSTITUTION §I/§V — mocking an
  *external* service boundary, not an internal component), plus real **Morning-sandbox
  integration** tests (no mocks) proving the actual wire contract. Phase 3 adds the real-API
  **`billed`** acceptance test(s) on top of these, once both are done.
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
  shape as the "unchanged" regression check rather than writing it from scratch; (4) on a
  successful standalone creation, `log_mutation` is called with the resolved client's id/name
  (spy/capture the call, same technique already used for `create_receipt`'s existing audit
  coverage if present, otherwise a simple call-recording fake) — REQ-INV-024's audit-logging
  requirement, previously untested by any task in this feature.
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
  the opposite direction); (5) on the real-cancellation path (case 1), `log_mutation` is called
  with `client_id`/`client_name` extracted from the fetched original (same pattern as
  `create_receipt`'s existing linked-original `log_mutation` call) — REQ-INV-024, previously
  untested by any task in this feature; on the type-300-rejection path (case 4), `log_refusal`
  is called instead.
- [ ] **T004b** [US2] Implement `cancel_transaction_account(client,
  original_internal_morning_id: str) -> str` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`: fetch via `client.get_invoice`;
  raise `ValueError` if `type != _TRANSACTION_ACCOUNT_DOCUMENT_TYPE`; if `status != 0`, return
  the no-op confirmation (T005b's formatter) without calling `close_invoice`; otherwise call
  `client.close_invoice`, then `log_mutation` with `client_id`/`client_name` extracted from the
  already-fetched original (same pattern `create_receipt`'s existing linked path already uses —
  REQ-INV-024), and return T005b's confirmation (BLOCKED until T004a approved).
- [ ] **T005a** [P] [US2] Write unit tests for a new formatter (working name
  `format_transaction_account_cancelled(...)`) in
  `apps/morning-mcp-app/tests/unit/test_formatters.py`: asserts the confirmation text never
  contains "שולם" or any other paid/payment wording — this is the direct regression test for
  research.md Finding 2 (`get_invoice_details`'s existing formatter does say "שולם" for a
  status-2 document, which is exactly the bug this new formatter must not repeat). If the
  formatter includes any date/timestamp, it MUST come from `now_local()`
  (`apps/morning-mcp-app/src/denidin_mcp_morning/utils/time_utils.py`) — never a bare
  `datetime.now()` — per CLAUDE.md's Israel-local-time rule; assert this explicitly if a date
  ends up in scope.
- [ ] **T005b** [US2] Implement `format_transaction_account_cancelled(...)` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` (BLOCKED until T005a approved).
- [ ] **T006** [US2] Register `cancel_transaction_account` as a new MCP tool in
  `apps/morning-mcp-app/server.py`, mirroring how the existing `create_*`/
  `create_combo_document_as_reference` tools are registered (Feature 021's pattern) — no test
  task on its own; exercised end-to-end by T007a (sandbox integration) here, and by Phase 3's
  `billed` acceptance test once this phase and Phase 1 are both done.
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
  its own — a one-line addition to an existing tuple, verified by Phase 3's `billed` acceptance
  test rather than a dedicated unit test.

**Checkpoint**: User Story 2's unit/integration work is complete — `cancel_transaction_account`
is registered, idempotent, RBAC-wired, and its real-sandbox behavior is fully verified. RBAC/
approval-gate wiring itself is proven end-to-end in Phase 3 (§VI.a), not here.

---

## Phase 3 — Acceptance: TDD (`billed`/`expensive`, user-perspective, run once) (§VI.a)

**Goal**: prove the feature actually works for a real user, end to end, through the real
webhook/router/handler/AI pipeline — not just that its internal pieces pass their own tests.
Per METHODOLOGY §VI.a, "TDD" now means specifically this: a **user-experience description**
written now (T009 — no test code), with the actual test code written AND run together, once,
only after Phase 1 AND Phase 2 are both fully GREEN (T010).

- [ ] **T009** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** Describe (in `tasks.md`
  here, no test file, no code) the `billed`-tier acceptance scenario for US2: a godfather sends
  DeniDin a natural Hebrew message asking to cancel a transaction account → DeniDin asks for
  approval (never executes on the ASK turn) → the godfather replies "כן" → DeniDin confirms the
  cancellation, and the confirmation text never says the account was "paid" — validates
  REQ-INV-023 (RBAC/approval-gate wiring) and REQ-INV-026 (non-"paid" wording) from the real
  user's perspective, not just T005a's unit-level formatter check. This description is the
  target; nothing here is executable yet.
- [ ] **T010** **[TDD — WRITE + RUN, ONCE Phases 1 and 2 are both GREEN]** Turn T009's
  description into a real `billed` test in `apps/denidin-app/tests/billed/` (an existing
  Morning-tool RBAC/approval file if one already covers this shape, otherwise a new
  `test_cancel_transaction_account_billed.py` following the existing
  `tests/billed/test_denidin_morning_*_e2e.py` pattern) and run it immediately, for real — the
  writing and the first run happen together, at this point, not before. Needs `denidin-app` dev
  running with Morning MCP attached — its own separate, explicit environment-start approval, not
  implied by anything earlier in this task list. On failure: fix forward (this is real
  acceptance validation against completed code, not a RED-phase check — a failure here means the
  feature doesn't actually work yet, not that a test needs approval).
- [ ] **T011** 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s full scenario set (both US1 and
  US2) for real, alongside or after T010 — needs its own explicit approval to start the dev
  environment if not already running from T010.

**Checkpoint**: the whole feature — both user stories — is proven to work end-to-end from a real
user's perspective. This is the feature's actual "done."

---

## Dependencies

- Within Phase 1: T001b depends on T001a; T002b depends on T002a AND T001b (needs the builder to
  call); T003a can be written in parallel with T001a/T002a (`[P]`, different file), but T003b
  (verify GREEN) depends on T001b + T002b + T003a-approved.
- Within Phase 2: T004b depends on T004a; T005b depends on T005a; T006 depends on T004b + T005b
  (needs both to register a working tool); T007a can be written in parallel (`[P]`), but T007b
  depends on T004b + T005b + T006 + T007a-approved; T008 has no code dependency on T004-T007 but
  is naturally done alongside them.
- **Phase 1 and Phase 2 are fully independent of each other** — no shared new code, no shared
  test files, no ordering constraint between them (per plan.md's Constitution Check and
  data-model.md, confirmed no overlap). Either phase can be implemented and merged first.
- **Phase 3 depends on BOTH Phase 1 and Phase 2 being fully complete** (T003b and T007b/T008
  all done) — T009 (the user-experience description, no code) can be written early/in parallel
  with either phase since the scenario is already fully known, but T010 (write the actual test
  code AND run it) and T011 (manual gate) cannot start until every earlier phase is GREEN, per
  §VI.a's "describe now, implement and run together at the end" rule.

## Parallel Execution

- T001a, T002a, T003a can all be drafted in parallel (three different files/functions, no
  interdependency in the RED phase) — but T002a's fixtures should wait for T001a's approved
  shape if the same fake-payload assertions are reused between them, to avoid rework.
- T004a, T005a, T007a can similarly be drafted in parallel.
- Phase 1 and Phase 2 as a whole can be worked on in parallel by two different sessions/people,
  since they touch disjoint functions (`create_receipt` vs. a brand-new
  `cancel_transaction_account`) and disjoint test files.
- T009 (Phase 3's user-experience description — no code) can be written in parallel with either
  phase's work, since what US2 should do end-to-end is already fully known from spec.md/
  contracts/ — its actual test code, and running it (both T010), are gated together on both
  phases being GREEN.

## Implementation Strategy

**MVP = Phase 1 (User Story 1)** — the more common, P1 real-world need (deposits/loan
repayments/advance payments), independently mergeable and deployable on its own. Phase 2 (P2,
transaction-account cancellation) is a smaller, independent increment that can follow in the
same PR or a separate one — spec.md's Success Criteria (SC1/SC2) are each satisfied by their own
phase alone, so partial delivery (Phase 1 only, for a while) is a legitimate, real MVP, not just
a task-list convenience. Phase 3 (the actual "TDD" per §VI.a) is the whole feature's final
acceptance pass — it only makes sense to run once both phases being shipped together are GREEN;
if Phase 1 ships alone first, Phase 3's `billed` test (US2-specific) waits until Phase 2 lands.
