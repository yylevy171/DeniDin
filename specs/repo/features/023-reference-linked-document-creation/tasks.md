# Tasks: Reference-Linked Combo Document Creation

**Feature**: 023-reference-linked-document-creation
**Plan**: `plan.md`

Per METHODOLOGY.md §VI, every implementation task is split into Task A
(write tests, human-approved) and Task B (implement, BLOCKED until Task A
is approved). Tests are IMMUTABLE once approved (§VIII).

## Path Conventions

All paths relative to repo root:
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`
- `apps/morning-mcp-app/src/denidin_mcp_morning/server.py`
- `apps/morning-mcp-app/tests/unit/test_tools_document_creation.py`
- `apps/morning-mcp-app/tests/integration/test_morning_sandbox_document_creation_tools.py`
- `apps/denidin-app/tests/expensive/test_denidin_morning_document_creation_e2e.py`
- `apps/denidin-app/config/runtime_constitution.md`

## Phase 1: Unit tests + implementation (US1, US2, US3)

- **[T001a] [US1/US2/US3]** Write unit tests in
  `test_tools_document_creation.py`:
  - `_build_combo_closing_payload` unchanged when `amount`/`description` are
    omitted (regression guard vs. 020's already-verified-live shape)
  - `_build_combo_closing_payload` with `amount` override → single overridden
    income line, payment price = override
  - `close_transaction_account` happy path, full amount (US1)
  - `close_transaction_account` happy path, partial amount (US2)
  - `close_transaction_account` against a non-300 original → `ValueError`
    naming the type, no `create_invoice` call made (US3)
  - `_mark_invoice_paid`/`update_invoice_status` regression: identical
    payload/behavior to before this feature's signature change
  - 🚨 **HUMAN APPROVAL GATE** — tests reviewed, confirmed failing (no
    implementation yet) before Task B starts.

- **[T001b] [US1/US2/US3] (BLOCKED until T001a approved)** Implement:
  - Extend `_build_combo_closing_payload` with optional `amount`/`description`
  - Add `close_transaction_account` to `tools.py`
  - Register `close_transaction_account` as an `@mcp.tool()` in `server.py`
  - Run T001a's tests — all pass; run full `morning-mcp-app` unit suite —
    no regressions.

**Checkpoint**: Unit-level behavior complete and tested — ready for
integration tests.

## Phase 2: Integration tests (real Morning sandbox)

- **[T002a] [US1/US2/US3]** Write integration tests in
  `test_morning_sandbox_document_creation_tools.py`:
  - Seed a real type-300 document, close it via `close_transaction_account`,
    assert a linked type-320 document exists via `get_invoice_details`
  - Same, with a partial `amount` override — assert the linked document's
    amount matches the override, not the original's full total
  - Attempt against a seeded type-305 original → assert `ValueError`/friendly
    rejection, no new document created in Morning
  - 🚨 **HUMAN APPROVAL GATE** — tests reviewed before running against the
    real sandbox.

- **[T002b] (BLOCKED until T002a approved)** Run against the real Morning
  sandbox; fix any payload-shape mismatches T001b's first draft didn't catch
  (matching 020's own experience — its first-draft combo payload happened to
  be correct on the first try, but this isn't guaranteed to repeat).

**Checkpoint**: Sandbox-verified — ready for E2E.

## Phase 3: Expensive E2E tests (real OpenAI + real Morning, via WhatsApp)

- **[T003a] [US1/US2/US3]** Write E2E tests in
  `test_denidin_morning_document_creation_e2e.py`:
  - Godfather WhatsApp conversation: close an existing חשבון עסקה with a
    combo document, full amount — verify via direct `MorningClient` call,
    not just the bot's reply text
  - Same, partial amount
  - Negative case: ask to close a regular tax invoice this way → friendly
    refusal, no document created
  - 🚨 **HUMAN APPROVAL GATE** — tests reviewed. **Each subsequent run
    requires its own fresh, explicit human approval — one test at a time,
    never a bare `-m expensive` sweep** (CLAUDE.md expensive-test rules).

- **[T003b] (BLOCKED until T003a approved, and until each run is
  individually approved)** Run one at a time; fix issues; re-run only after
  a code change believed to fix the failure (never speculatively).

**Checkpoint**: E2E-verified — ready for constitution docs update.

## Phase 4: Constitution documentation

- **[T004]** Update `runtime_constitution.md` per plan.md's "Constitution
  updates" section: tool list, document-selection guidance,
  `original_invoice_id` resolution note, approval-required list + pending
  phrasing example. No test gate (documentation, not code behavior) — but
  review against the E2E tests' actual observed model behavior from Phase 3
  before finalizing wording.

**Checkpoint**: Feature complete — ready for `speckit.analyze` and haleluya.
