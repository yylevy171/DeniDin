# Tasks: Mandatory Reference to an Existing Client for Invoice Creation — Feature 027

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **User stories**: `./user-stories.md`
**Apps**: `apps/morning-mcp-app/` (primary — all 6 tools + formatters) + `apps/denidin-app/`
(`runtime_constitution.md` guidance addition + new expensive E2E scenarios only — no source code
change, since every target tool is already in `AIHandler.APPROVAL_REQUIRED_MCP_TOOLS`)
**Branch**: `feature/027-mandatory-client-reference-invoicing`

## Correction (2026-08-07, during implementation)

Every `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py` reference below is
**stale** — that file was split by topic into several files under `apps/denidin-app/tests/billed/`
(Feature 038, before this feature started): `test_denidin_morning_document_creation_e2e.py`,
`test_denidin_morning_invoice_creation_e2e.py`, `test_denidin_morning_invoice_lifecycle_e2e.py`,
`test_denidin_morning_list_invoices_e2e.py`, `test_denidin_morning_client_management_e2e.py`
(shared fixtures/helpers in `denidin_mcp_e2e_helpers.py`). These are **`billed`**, not
`expensive` — real, text-only OpenAI calls, freely runnable with no per-run approval gate and no
one-at-a-time restriction (CLAUDE.md/pytest.ini). Every "T00Xb: needs explicit human approval to
run" note below for a denidin-app E2E task is therefore **also stale** for this feature — no
approval gate applies to `billed` tests. Reuse `denidin_mcp_e2e_helpers.py`'s existing
`_unique_client_name()` (a real Hebrew first+family name generator, 565×591 combinations,
deliberately never digits/hex/operation-words - shaped by several real prior billed-test
failures) for any new client name these tests need - it already fully supersedes tasks.md's
generic "seed a client" language and morning-mcp-app's own `_unique_marker`, which is
sandbox-test-specific.

This same E2E layer also has the same "assumes a client can be created for a never-before-seen
name" exposure the sandbox integration tests had - discovered but **not yet fixed/extended** as
of this correction; tracked as remaining work under Phases 2/3/4/6 below.

## Conventions

- Task ID `T###`. `[P]` = parallelizable (different files, no dependency on an incomplete task).
- **TDD gate (METHODOLOGY §VI)**: the test task (`a`) is written first, must **fail** (RED), and
  needs **explicit human approval** before the implementation task (`b`). Approved tests are
  **immutable** (CONSTITUTION §VIII) unless explicitly re-approved.
- **Two-tier testing** (mirrors Feature 026's own pattern): fast **unit** tests with a fake
  `MorningClient` double for pure logic (the shared resolution/extraction helpers — allowed per
  CONSTITUTION §I/§V, which permits mocking *external* services, not internal components), plus
  slower **real Morning-sandbox integration** tests (no mocks) proving the actual wire contract,
  plus real-API **expensive** E2E tests (`apps/denidin-app`, `@pytest.mark.expensive`) through the
  real Green API webhook router for the full WhatsApp-turn flows.
- **Test naming (research.md Decision 8)**: every test's client names MUST use the existing
  `_unique_marker(label)` → `f"Test Client {marker}"` mechanism already used throughout
  `apps/morning-mcp-app/tests/integration/*.py` — never a literal fixed name, and never the
  narrative persona names ("Danny Cohen" etc.) from `user-stories.md`/`quickstart.md`.
- **Expensive-test discipline (CLAUDE.md)**: human approval before **every** run of anything under
  `apps/denidin-app/tests/expensive/`, one at a time, never a bare `-m expensive` sweep, read
  `logs/test_logs/` before re-running.
- **Environment-start discipline (CLAUDE.md)**: any manual-approval-gate task that needs a running
  dev environment requires separate, explicit approval to start it — never assumed from a prior
  approval in this task list.
- **Group B no-id fixture (research.md Outstanding item)**: any test exercising REQ-INV-013's
  refusal path must seed its "pre-feature" original via a **raw `MorningClient.create_invoice`**
  call using the old `{"name": ...}`-only `client` payload shape directly — bypassing the tool
  layer entirely, since none of this feature's own (fixed) tools can produce that shape anymore.
- Paths relative to `apps/morning-mcp-app/` or `apps/denidin-app/` as stated per task.

---

## Phase 1 — Foundation (shared building blocks, no user-facing behavior yet)

- [x] **T001a** [P] Write unit tests (fake `MorningClient`) for a new shared helper
  `_resolve_client_for_document_creation(client, client_name)` in
  `apps/morning-mcp-app/tests/unit/test_tools_client_resolution.py`: 0 matches → not-found
  sentinel; 1 exact match → resolved `(client_id, disclosure=None)`; 1 non-exact match → resolved
  `(client_id, disclosure=<matched name>)`; >1 matches → ambiguous sentinel carrying candidates.
  Reuses Feature 026's `_resolve_client_by_name`/`_is_exact_name_match` internally — tests assert
  on the new helper's combined output, not on re-deriving those two directly.
- [x] **T001b** Implement `_resolve_client_for_document_creation` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`, used by all 3 Group A tools (BLOCKED
  until T001a approved).
- [x] **T002a** [P] Write unit tests for a new formatter `format_original_not_linked_to_client()`
  in `apps/morning-mcp-app/tests/unit/test_formatters_client_reference.py` — friendly Hebrew
  refusal text, constitution-compliant shape ("[emoji] [what happened]. [what to do next].",
  CONSTITUTION §X), never implies a remediation path that doesn't exist (research.md Decision 7).
- [x] **T002b** Implement `format_original_not_linked_to_client()` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` (BLOCKED until T002a approved).
- [x] **T003a** [P] Write unit tests for a new shared helper
  `_extract_linked_client_id(original: dict) -> Optional[str]` in the same
  `test_tools_client_resolution.py`: returns the `id` when `original["client"]` has one; returns
  `None` when it doesn't (or `client` is missing entirely).
- [x] **T003b** Implement `_extract_linked_client_id` in `tools.py`, used by all 3 Group B payload
  builders (BLOCKED until T003a approved).

**Checkpoint**: shared resolution/extraction/formatting helpers exist and are unit-tested. No
tool's actual behavior has changed yet — `create_invoice` etc. still build the old bare-name
payload until their own story's implementation task.

---

## Phase 2 — User Story 1: Document created for an existing, unambiguous client (Priority: P1) 🎯 MVP

**Goal**: `create_invoice` resolves `client_name` to a real client and attaches by `id`, disclosing
non-exact matches; refuses (creates nothing) on zero or multiple matches.

**Independent Test**: seed one sandbox client, request an invoice for it by name, approve, assert
(via `MorningClient.get_invoice`) the created document's `client.id` equals the seeded client's
real `client_id`.

- [x] **T004a** [US1] Write real-sandbox integration test
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_create_invoice_client_resolution.py`:
  (1) exact single match → payload's `client` is `{"id": ...}`, no `name`; created document's
  `client.id` verified against the sandbox equal to the seeded client's real id; (2) non-exact
  single match (seed `f"Test Client {marker}"`, query a shortened prefix) → same attachment, AND
  the tool's returned confirmation text discloses the real matched name; (3) zero matches → no
  document created, friendly not-found message (reusing `format_client_not_found`); (4) >1 matches
  (seed two clients sharing a marker prefix) → no document created, disambiguation message listing
  both. This is `create_invoice`'s full REQ-INV-001/002/003/005/011 RED phase.
- [x] **T004b** [US1] Implement `create_invoice`'s full resolution behavior in `tools.py` — call
  `_resolve_client_for_document_creation` (T001b) before building the payload; branch per T004a's
  4 cases; `_build_create_invoice_payload` changes to take a resolved `client_id` instead of a raw
  `client_name` (BLOCKED until T004a approved).
- [ ] **T005a** [US1] Write real-API E2E test in
  `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`: godfather asks for an
  invoice for a seeded client by name → `create_invoice` approval fires (existing gate, unchanged)
  → approve → confirmation reply → verify via `MorningClient.get_invoice` that `client.id` matches
  the real seeded client, not just that a document exists.
- [ ] **T005b** [US1] Verify GREEN — run the new expensive E2E test (needs its own explicit human
  approval to run, per CLAUDE.md — not implied by this task; needs the dev environment running,
  which also needs separate explicit approval to start).
- [ ] **T006** [US1] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US1 scenario for real
  (needs explicit approval to start the dev environment and to run the expensive E2E test).

**Checkpoint**: User Story 1 fully functional and independently deployable (MVP) — `create_invoice`
never attaches a bare-name document again.

---

## Phase 3 — User Story 2: Document creation blocked on an unknown client, then created after inline client creation (Priority: P1)

**Goal**: on a not-found response (already implemented by T004b), the model asks for missing
client details, calls `add_client`, and retries — two separate, already-existing approval turns.

**Independent Test**: request an invoice for a nonexistent client → assert no document + not-found
reply → provide details → approve `add_client` → retry → approve `create_invoice` → verify the
final document's `client.id` matches the newly-created client.

- [ ] **T007** [US2] Add guidance to `apps/denidin-app/config/runtime_constitution.md`: on a
  Group A tool's "client not found" reply, ask the godfather for phone/email and call
  `add_client`, then retry the original document-creation request — mirrors the existing
  invoice_id-resolution guidance pattern (Feature 026). Docs-only; hot-reloaded by mtime, no
  rebuild needed (no test task — this is prompt content, verified via the E2E test below).
- [ ] **T008a** [US2] Write real-API E2E test in `test_denidin_morning_mcp_e2e.py`: full multi-turn
  flow — request invoice for nonexistent client → not-found reply, zero documents → provide
  phone/email → `add_client` approval → approve → retry (model-initiated or user re-sends) →
  `create_invoice` approval → approve → verify the created document's `client.id` matches the
  just-created client's real `client_id`. Also asserts the two approvals are **separate**
  `mcp_approval_request`/response exchanges (REQ-INV-007), not one combined confirmation.
- [ ] **T008b** [US2] Verify GREEN (same approval discipline as T005b).
- [ ] **T009** [US2] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US2 scenario for real.

**Checkpoint**: User Story 2 fully functional — the "not found → create client inline → retry"
flow works end-to-end with zero new application code beyond the constitution guidance.

---

## Phase 4 — User Story 6: Group B tools preserve the original's real client, or refuse if it has none (Priority: P1)

**Goal**: `create_credit_note`, `create_receipt`, `close_transaction_account` preserve
`original.client.id` when present (REQ-INV-012); refuse and create nothing when absent
(REQ-INV-013) — no fallback to bare-name attachment.

**Independent Test**: (a) seed a real client + an invoice with real attachment → request a linked
document → verify the new document's `client.id` matches the original's; (b) seed an original
with no `client.id` (raw `MorningClient` call, old payload shape) → request a linked document →
assert zero new documents + friendly refusal.

- [x] **T010a** [P] [US6] Write real-sandbox integration test
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_group_b_client_preservation.py::test_create_credit_note_*`:
  preserve path (original has `client.id` → new credit note's `client.id` matches it, verified via
  `MorningClient.get_invoice` on both documents) and refuse path (original has no `client.id`,
  seeded raw → zero new documents, `format_original_not_linked_to_client()` message returned).
- [x] **T010b** [US6] Implement `create_credit_note`/`_build_cancellation_payload` changes in
  `tools.py`: call `_extract_linked_client_id` (T003b) on the fetched original; present → build
  `{"id": ...}`; absent → the calling tool returns T002b's refusal message before ever calling the
  builder or `client.create_invoice` (BLOCKED until T010a approved).
- [x] **T011a** [P] [US6] Write real-sandbox integration test in the same file,
  `test_create_receipt_*`: identical preserve/refuse pattern for `create_receipt`.
- [x] **T011b** [US6] Implement `create_receipt`/`_build_payment_receipt_payload` changes,
  mirroring T010b (BLOCKED until T011a approved).
- [x] **T012a** [P] [US6] Write real-sandbox integration test in the same file,
  `test_close_transaction_account_*`: identical preserve/refuse pattern for
  `close_transaction_account` (the 6th tool, added to scope 2026-08-06).
- [x] **T012b** [US6] Implement `close_transaction_account`/`_build_combo_closing_payload`
  changes, mirroring T010b (BLOCKED until T012a approved).
- [ ] **T013a** [US6] Write real-API E2E test in `test_denidin_morning_mcp_e2e.py`: godfather asks
  for a credit note against a seeded, real-attached invoice → approve → verify `client.id`
  preserved; separately, against a seeded no-id original → approve (or note the tool refuses
  before any approval-worthy action occurs, if refusal happens pre-approval) → verify zero new
  documents and a friendly reply, not a crash.
- [ ] **T013b** [US6] Verify GREEN (same approval discipline as T005b).
- [ ] **T014** [US6] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US6 scenario for real.

**Checkpoint**: User Story 6 fully functional — all 3 Group B tools preserve real attachment or
refuse, with zero silent bare-name fallback anywhere in the feature.

---

## Phase 5 — User Story 3: Document creation blocked on an ambiguous client name (Priority: P2)

**Goal**: dedicated verification that `create_invoice`'s already-implemented (T004b) ambiguous
branch behaves correctly end-to-end, including the disambiguate-and-retry flow.

**Independent Test**: seed two clients sharing a marker prefix (simulating "same first name"),
request an invoice by the shared prefix, assert no document + both candidates listed; disambiguate
and retry, assert success.

- [ ] **T015** [P] [US3] Write real-sandbox integration test
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_create_invoice_client_resolution.py::test_ambiguous_then_disambiguated_retry_succeeds`:
  extends T004a's ambiguous case with a full disambiguate-and-retry round-trip within the same
  test (no separate implementation task — T004b already implements this branch).
- [ ] **T016a** [US3] Write real-API E2E test in `test_denidin_morning_mcp_e2e.py`: godfather
  requests an invoice for an ambiguous shared-prefix name → disambiguation reply listing both real
  candidates (verified against the sandbox) → godfather clarifies → approve → verify the document
  attaches to the correctly-resolved client.
- [ ] **T016b** [US3] Verify GREEN (same approval discipline as T005b).
- [ ] **T017** [US3] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US3 scenario for real.

**Checkpoint**: User Story 3 fully verified — no separate production code beyond what US1 already
built.

---

## Phase 6 — User Story 4: Uniform behavior across the remaining 2 Group A tools (Priority: P2)

**Goal**: `create_transaction_account` and `create_combo_document` get the identical resolution
behavior `create_invoice` has, via the same shared helper — no special-casing.

**Independent Test**: for each tool, seed a client, request that document type by name, approve,
verify `client.id` matches the real client.

- [ ] **T018a** [P] [US4] Write real-sandbox integration test
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_group_a_uniformity.py::test_create_transaction_account_*`:
  same 4-case coverage as T004a (exact/non-exact/not-found/ambiguous), scoped to
  `create_transaction_account`.
- [ ] **T018b** [US4] Implement `create_transaction_account`'s resolution using
  `_resolve_client_for_document_creation` (T001b), mirroring T004b (BLOCKED until T018a approved).
- [ ] **T019a** [P] [US4] Write real-sandbox integration test in the same file,
  `test_create_combo_document_*`: same 4-case coverage, scoped to `create_combo_document`.
- [ ] **T019b** [US4] Implement `create_combo_document`'s resolution, mirroring T004b (BLOCKED
  until T019a approved).
- [ ] **T020a** [US4] Write real-API E2E test in `test_denidin_morning_mcp_e2e.py` covering both
  remaining Group A tools' happy path (real client attachment) in one or two turns.
- [ ] **T020b** [US4] Verify GREEN (same approval discipline as T005b).
- [ ] **T021** [US4] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US4 scenario for real.

**Checkpoint**: all 3 Group A tools behave identically — REQ-INV-008 satisfied.

---

## Phase 7 — User Story 5: RBAC unaffected (verification only, no new code expected)

**Goal**: confirm this feature introduces no new RBAC surface — client/blocked-role senders still
get none of the 6 tools attached.

- [ ] **T022** [US5] Verify (via a targeted read of `ai_handler.py`'s existing RBAC/tool-attachment
  logic, plus re-running any already-existing client-role E2E scenario covering Morning tool
  non-attachment) that no change in this feature affects RBAC gating. If no existing test directly
  covers "client role + any of these 6 tool names," add one minimal assertion to
  `test_denidin_morning_mcp_e2e.py` rather than skipping verification entirely.

---

## Phase 8 — Polish & Cross-Cutting Verification

- [ ] **T023** Full spec-to-test traceability pass: confirm every REQ-INV-001 through REQ-INV-013
  and every SC-001 through SC-008 has at least one asserting test (unit, integration, or E2E) —
  produce a simple mapping table in this section or a scratch note, not necessarily committed.
- [ ] **T024** Re-read `apps/denidin-app/.github/ARCHITECTURE.md` and this repo's root
  `CLAUDE.md` "Morning MCP integration" section for any statement that's now stale (e.g. anything
  implying document-creation tools pass a bare client name) and update if needed.
- [ ] **T025** Run this feature's full non-expensive test suite (unit + integration, both apps)
  once GREEN across all phases, to confirm no regression elsewhere (`billed` tests may be run
  freely per CLAUDE.md; `expensive` tests are NOT re-run here — already covered by each phase's
  own explicit approval gate).

---

## Dependencies & Execution Order

- **Phase 1 (Foundation) blocks everything** — all 3 helpers (T001b/T002b/T003b) are used by
  multiple later phases.
- **Phase 2 (US1) blocks Phase 3 (US2) and Phase 5 (US3)** — both reuse `create_invoice`'s
  resolution behavior implemented in T004b; they add tests/guidance/E2E coverage, not new
  production logic.
- **Phase 4 (US6) is independent of Phases 2/3/5** — Group B's fix doesn't depend on Group A's
  implementation, only on Phase 1's T002b/T003b. Could be implemented in parallel with Phase 2 by
  a different session/task if desired.
- **Phase 6 (US4) depends only on Phase 1 (T001b)**, not on Phase 2 — could also run in parallel
  with Phase 2, though sequencing after US1 (as ordered above) lets US4 directly mirror an
  already-proven pattern.
- **Phase 7 (US5) and Phase 8 (Polish)** run last, after all behavior-changing phases are GREEN.

## Suggested MVP Scope

**Phase 1 + Phase 2 (US1) only** — `create_invoice` resolves and attaches by real `client_id` on
an unambiguous match. This alone fixes the motivating problem (no email delivery, no per-client
accounting) for the single most-used document-creation tool, independently deployable and
independently valuable per METHODOLOGY's "each story is a viable increment" principle.
