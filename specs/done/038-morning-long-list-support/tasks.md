# Tasks: Morning Long List Support — Feature 038

**Input**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`, `contracts/list_invoices.json`
**Prerequisites**: all of the above complete (this file)

---

**Compliance**: CONSTITUTION.md §I-III (no env vars, UTC N/A, feature branch already created),
METHODOLOGY.md §VI (TDD, human approval gates — EVERY `a` task requires approval before its `b`
task; tests are IMMUTABLE once approved, except the one explicitly flagged deletion below).

**Path Conventions**: paths relative to `apps/morning-mcp-app/` unless prefixed
`apps/denidin-app/` (Phase 6 only).

**Revision history**:
- 2026-08-04 (round 1): after user review of the initial test plan, added User Story 3
  (token-budget truncation, then 2500), switched US1/US2 integration tests to real, already-existing
  sandbox date ranges (research.md Decision 4) instead of seeding, and added 2 billed E2E tests.
- 2026-08-04 (round 2): after further review, revised the token budget to a permanent **800**
  (research.md Decision 6), moved the token-budget proof into a `billed` test instead of a plain
  `apps/morning-mcp-app` integration test, kept all new billed tests inside `apps/denidin-app`
  (explicit user direction — "this is denidin functionality, not morning"), changed T011 from a
  rewrite to an outright deletion, and added a full section-by-section split of
  `apps/denidin-app/tests/billed/test_denidin_morning_mcp_e2e.py` into 4 files.
- 2026-08-04 (round 3, correction): round 2's permanent 800 was wrong — the user corrected that
  2500 is the real, unchanged practical output-token limit (may need to increase later), and the
  actual ask was only to keep ONE specific test cheap. Resolution (research.md Decision 7):
  `list_invoices_token_budget` becomes a `MorningMCPConfig` field (default 2500, config-driven per
  CONSTITUTION §I, not a hardcoded constant); exactly one `apps/morning-mcp-app` unit test
  (T002a) passes an explicitly low override — "testing harnesses can set configs as they like."
  The 3 billed E2E tests (T009a/T010a/T015a) needed no changes — they already used inequality
  assertions against the real default, not a hardcoded exact count.

---

## Phase 1: Setup

- [ ] **T000** [P] `venv/bin/pip install -r requirements.txt` (in
  `apps/morning-mcp-app`) to pick up the new `tiktoken` dependency in the
  dev virtualenv (already verified installable during research.md
  Decision 5's live probe).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The formatter changes both US1/US2/US3 depend on — must land
first since `list_invoices` (Phase 3) calls these formatters.

**⚠️ CRITICAL**: No user-story implementation task may begin until T001a/
T002a are approved and T001b/T002b are complete.

- [ ] **T001a** [P] Write unit tests for formatter changes in
  `tests/unit/test_formatters.py` (existing file — add cases):
  - `format_invoice_list([inv1, inv2], total_matched=2)` starts with a
    count line stating "2" and is followed by exactly 2 invoice blocks,
    with no "shown X of Y" language (REQ-INVOICE-004).
  - `format_invoice_list([inv1], total_matched=5)` (shown < total) starts
    with a "showing 1 of 5" line, is followed by exactly 1 invoice block,
    and ends with a closing note that more results exist but were omitted
    for length, asking to narrow the search (REQ-INVOICE-009).
  - `format_invoice_list([], total_matched=0)` returns the existing
    unchanged "no results" message, with no count line prepended
    (REQ-INVOICE-006).
  - `format_invoice_list` no longer accepts a `has_more` argument; it now
    requires `total_matched` (locks in research.md Decision 3/6).
  - `format_too_many_invoices_message(103)` returns a Hebrew string
    containing "103", asking to narrow the search, with no invoice-detail
    content (no `"חשבונית #"` substring).
  - **Tier**: unit (isolated, no network — pure formatter functions).
- [ ] **T001b** [P] Implement `format_invoice_list`'s new
  `(invoices, total_matched)` signature (shown/total-aware count line +
  closing note) and add `format_too_many_invoices_message`, in
  `src/denidin_mcp_morning/formatters.py` (BLOCKED until T001a approved).

- [ ] **T002a** [P] Write unit tests for the fetch-loop/cap-boundary/
  token-budget logic in `tests/unit/test_tools_list_invoices.py` (new
  file), using a small hand-built fake `MorningClient`-shaped object (NOT
  `unittest.mock` — same real-fake-object pattern already established in
  `tests/unit/test_tools_client_management.py`, which already exposes a
  `.search_clients()` fake for `list_clients`'s equivalent tests):
  - Total ≤ cap (100): loop fetches every page (`page_num < pages` until
    `len(items) >= total`), matching `list_clients`' loop exactly.
  - Total == cap (100) exactly: still fetches everything (boundary is
    `>`, not `>=` — spec.md Edge Cases).
  - Total > cap (101+): fetches only page 1, no second page request is
    made.
  - `page`/`pages` missing from a response: defaults applied (`1`/`1`),
    matching `list_clients`' existing fallback (REQ-INVOICE-007).
  - **Token-budget boundary** (REQ-INVOICE-008/009/010, config-driven
    `list_invoices_token_budget`, real default 2500 — research.md
    Decision 7): with fake invoices whose description text produces
    known, measured token sizes (via the real `tiktoken` encoding — not
    mocked, just controlled *content*), confirm the fetch loop still
    retrieves the complete raw set regardless of display truncation, and
    that the number of blocks passed to `format_invoice_list` stops at
    the right boundary (last block whose cumulative token count, reserving
    the implementation's fixed 100-150 token headroom, stays within
    budget). **This is the ONE test in the whole feature that passes an
    explicitly low `token_budget` override directly to
    `tools.list_invoices()`** — per user direction ("testing harnesses
    can set configs as they like"), computed from real measured block
    sizes rather than hardcoded, so it stays deterministic and cheap
    regardless of the real production default. Every other test in this
    feature (including all 3 billed E2E tests) uses the real,
    unmodified 2500 default — never override it elsewhere.
  - **Tier**: unit.
- [ ] **T002b** [P] Change `_LIST_INVOICES_MAX_ITEMS` 10 → 100; add
  `MorningMCPConfig.list_invoices_token_budget` (default 2500,
  `config/config.schema.json` + `config/config.example.json` updated) and
  thread it from `server.py`'s `create_server` into `tools.list_invoices`
  via dependency injection (`_LIST_INVOICES_TOKEN_BUDGET = 2500` in
  `tools.py` stays only as the matching Python-level default for direct
  calls — the config field is authoritative for the real server, per
  REQ-INVOICE-010); rewrite `list_invoices`'s fetch + token-budget-
  truncation logic in `src/denidin_mcp_morning/tools.py` to mirror
  `list_clients`' loop (fetch stage) plus the new accumulate-until-budget
  logic (display stage)
  (BLOCKED until T002a approved).

**Checkpoint**: formatter + fetch-loop + token-budget unit tests pass in
isolation — ready for the real-sandbox integration tests below.

---

## Phase 3: User Story 1 — Complete fetch within the fetch cap (Priority: P1) 🎯 MVP

**Goal**: A query matching more than 10 but at or under 100 real invoices
is *fetched* completely internally (true total always known) — closes the
observed production bug's root cause. (Full *display* of all of them is
User Story 3's separate, token-budget-governed concern.)

**Independent Test**: Real sandbox range `fromDate=2026-07-19`,
`toDate=2026-07-21` (81 real invoices, research.md Decision 4) — confirm
the tool's internal fetch loop retrieves and status-filters all 81 before
any truncation decision is made (verified via the reply's stated real
total, since the fetch itself has no separately-observable output).

### Implementation for User Story 1 (TDD Pattern)

- [ ] **T003a** [US1] Write real-sandbox integration test
  `test_list_invoices_tool_fetches_complete_set_within_cap` in
  `tests/integration/test_morning_sandbox_list_invoices_tool.py`: call
  `list_invoices(client, from_date="2026-07-19", to_date="2026-07-21")`
  and assert the reply states "81" as the real total (the "of Y" component
  of REQ-INVOICE-009's count line — this range is expected to trigger
  token-budget truncation given real block sizes, so this test asserts
  the *total* reported is accurate, not that all 81 are individually
  displayed). **Tier**: integration (real Morning sandbox, no approval
  gate — CLAUDE.md's billed/expensive gate is OpenAI-specific and does
  not apply here).
- [ ] **T003b** [US1] No new implementation — this test exercises T001b +
  T002b together (BLOCKED until T003a approved AND T001b/T002b complete).

- [ ] **T004** [US1] 👤 **MANUAL APPROVAL GATE**: Run `quickstart.md` §1
  against the real 81-item range and visually confirm the stated real
  total is accurate, as an end-to-end sanity check beyond the automated
  test.

**Checkpoint**: User Story 1's fetch-completeness fix is verified against
real data — the root cause of the production bug (fetch silently limited
to one Morning page) is closed.

---

## Phase 4: User Story 2 — Clear refusal when a query is too broad (Priority: P2)

**Goal**: A query whose real total exceeds the fetch cap returns a clear
Hebrew refusal stating the real total, never a silent partial list.

**Independent Test**: Real sandbox range `fromDate=2026-07-13`,
`toDate=2026-07-15` (103 real invoices, research.md Decision 4) — confirm
the refusal message, not an itemized list, is returned.

### Implementation for User Story 2 (TDD Pattern)

- [ ] **T005a** [US2] Write real-sandbox integration test
  `test_list_invoices_tool_refuses_when_over_cap` in
  `tests/integration/test_morning_sandbox_list_invoices_tool.py`: call
  `list_invoices(client, from_date="2026-07-13", to_date="2026-07-15")`,
  assert the reply contains "103" and contains no `"חשבונית #"`
  substring (no itemized content leaked through), and assert no
  token-budget "showing X of Y" language appears (mutually exclusive with
  US3). **Tier**: integration (real sandbox, no approval gate).
- [ ] **T005b** [US2] No new implementation — exercises T001b + T002b
  together (BLOCKED until T005a approved AND T001b/T002b complete).

- [ ] **T006** [US2] 👤 **MANUAL APPROVAL GATE**: Run `quickstart.md` §2
  against the real 103-item range and visually confirm the refusal
  message's wording and real total.

**Checkpoint**: User Stories 1 AND 2 both work independently against the
real sandbox.

---

## Phase 5: Flagged Existing-Test Deletion (requires explicit human approval — CONSTITUTION §VIII)

- [ ] **T011** 👤 **HUMAN APPROVAL GATE (required before this task starts,
  separate from every gate above)**: Present
  `test_list_invoices_tool_caps_results_at_ten_items`'s current assertion
  (`result.count("חשבונית #") <= 10`) and the proposed action — **delete
  it outright** (explicit user direction, not a rewrite) since its intent
  (a cap exists and is enforced) is already covered by the new US2 test
  (T005a) — for explicit sign-off, per CONSTITUTION §VIII Test
  Immutability.
- [ ] **T011a** Delete the test from
  `tests/integration/test_morning_sandbox_list_invoices_tool.py` (BLOCKED
  until T011 approved).
- [ ] **T011b** No implementation change needed — this is a test-only
  task.

*(Numbered T011 rather than continuing sequentially, preserved from the
prior revision of this file to minimize renumbering churn across review
rounds.)*

---

## Phase 6: Billed E2E Coverage — file split + 3 new tests (apps/denidin-app)

**Purpose**: Per user direction, verify the fix at the layer that actually
matters to the godfather — the model's final WhatsApp reply — using real
webhook → real Responses API → real MCP round trip against the
already-running `morning-mcp-app-dev` container. Directly tests whether
the model relays the tool's precomputed counts/messages faithfully (the
user's original concern about model imprecision) rather than
inferring/hallucinating its own. Also splits the existing 2094-line,
~40-test file into 4 topic files (explicit user direction: "full split by
section").

### Step 1 — Split the existing file (pure reorganization, no logic changes)

- [ ] **T012** 👤 **APPROVAL GATE**: Present the proposed 4-way split
  below for sign-off before moving any code (this touches ~40 existing,
  already-approved tests — CONSTITUTION §VIII discipline applies to the
  *reorganization* itself, even though no test logic changes):
  - `test_denidin_morning_invoice_creation_e2e.py` — `create_invoice`
    approval flow + `add_client` (current lines ~404-729).
  - `test_denidin_morning_client_management_e2e.py` — `list_clients` /
    `get_client_details` / `update_client` + fuzzy-matching + RBAC denial
    (current lines ~730-1265).
  - `test_denidin_morning_list_invoices_e2e.py` — `list_invoices` +
    analytical/aggregate questions (bugfix-011) + bugfix-013
    (client-name garbling) + bugfix-014 (all-payments) (current lines
    ~1266-1630) — **this feature's 3 new tests land here** (Step 2).
  - `test_denidin_morning_invoice_lifecycle_e2e.py` — `get_invoice_details`
    + mark-paid/cancel direct dispatch + transaction-account payment
    marking (current lines ~1631-2094).
  - Shared fixtures/helpers (config loading, `denidin_app` fixture,
    `_calls_for`, `_send_turn_and_approve`, `_unique_client_name`,
    `_random_amount`/`_random_description`, Hebrew name pools, etc.)
    currently defined inline in the one file move to a shared location
    (either the existing `denidin_mcp_e2e_helpers.py` if that's where
    per-file-shared code already lives, or a new `conftest.py` — resolved
    during T014 based on which helpers are genuinely shared vs. only used
    by tests in one resulting file).
- [ ] **T013** [P] Perform the move: create the 4 new files, move each
  existing test function verbatim into its topic file, extract shared
  fixtures/helpers per T012's approved plan, delete the old
  `test_denidin_morning_mcp_e2e.py` (BLOCKED until T012 approved).
- [ ] **T014** Run the full existing billed suite across all 4 new files
  (`pytest apps/denidin-app/tests/billed/ -m billed -v`) and confirm every
  moved test still passes exactly as before the split — this is the
  verification that the reorganization changed no behavior. **Tier**:
  billed (no approval gate per CLAUDE.md, but this is a real-cost run
  across ~40 tests — mention to the human before running as a courtesy
  given the scale, even though not formally gated).

### Step 2 — New tests for Feature 038 (TDD Pattern)

- [ ] **T009a** [P] Write billed E2E test
  `test_godfather_asks_for_large_in_cap_invoice_range` in the new
  `test_denidin_morning_list_invoices_e2e.py`: godfather asks (in Hebrew)
  for invoices between 2026-07-19 and 2026-07-21 (81 real invoices),
  assert `ai_response.mcp_calls` shows a `list_invoices` call, and assert
  the model's final WhatsApp reply states a total consistent with 81 (not
  a smaller number the model might otherwise infer from only seeing the
  truncated display) — direct regression test for "model summarizes
  totals imprecisely." **Tier**: billed (no approval gate, no
  one-at-a-time restriction, per CLAUDE.md).
- [ ] **T009b** No new `apps/denidin-app` implementation needed — exercises
  the already-unchanged MCP tool contract through the already-existing
  Responses API integration (BLOCKED until T009a approved AND Phase 2/3
  implementation complete).

- [ ] **T010a** [P] Write billed E2E test
  `test_godfather_asks_for_over_cap_invoice_range` in the same file:
  godfather asks for invoices between 2026-07-13 and 2026-07-15 (103 real
  invoices), assert the model's final reply reflects a "too many results,
  narrow your search" style answer with a total consistent with 103, and
  assert no fabricated/hallucinated itemized invoice list appears.
  **Tier**: billed.
- [ ] **T010b** No new implementation needed (BLOCKED until T010a approved
  AND Phase 4 implementation complete).

- [ ] **T015a** [P] Write billed E2E test
  `test_godfather_receives_partial_list_within_token_budget` in the same
  file: godfather asks for invoices between 2026-07-21 and 2026-07-22 (13
  real invoices, research.md Decision 4/7), using the real, unmodified
  2500-token production default (no override — this is the E2E proof,
  distinct from T002a's cheap unit-level override). **Explicitly asserts
  on the actual bot `response` text (the final WhatsApp-visible reply the
  user would read), not merely `ai_response.mcp_calls` output** — per user
  direction, this must test the token-cap behavior from the user's
  perspective, i.e. what actually lands in the chat, not just that the
  tool was called correctly:
  - the visible reply states a genuine partial count (shown < 13, shown >
    0 — confirmed live the exact split is 8 of 13 at the real 2500
    default, but assert the inequality rather than the exact number to
    stay decoupled from the implementation's exact reserve value);
  - the visible reply does not claim to have shown all 13;
  - the visible reply reads as a coherent, actionable message (states the
    real total, explains more exist, invites narrowing) — not just a
    substring match, per manual read in T016.
  **Tier**: billed. This is the direct test of the user's original
  concern about model imprecision on counts, verified at the point that
  actually matters: what the user sees.
- [ ] **T015b** No new implementation needed (BLOCKED until T015a approved
  AND Phase 2/3 implementation complete).

- [ ] **T016** 👤 **MANUAL APPROVAL GATE**: Read the actual WhatsApp-style
  replies from T009a/T010a/T015a's runs and confirm they read naturally
  in Hebrew, not just pass their automated assertions.

**Checkpoint**: the fix is verified all the way through the real,
user-facing conversational layer, and the billed test suite is left in a
more maintainable, topic-organized state.

---

## Phase 7: Polish

- [ ] **T017** [P] Run full `apps/morning-mcp-app` test suite
  (`pytest tests/ -v --tb=short`, excluding billed/expensive as already
  configured) — confirm no regression in `create_invoice`,
  `get_invoice_details`, or other `tools.py` functions sharing the edited
  file.
- [ ] **T018** [P] Docstring/comment pass on `list_invoices`,
  `format_invoice_list`, `format_too_many_invoices_message` — confirm
  Google-style docstrings reference `user-stories.md` US1/US2/US3
  (CONSTITUTION §IV, matching this file's existing docstring convention).

---

## Dependencies & Execution Order (TDD-Aware)

- **Phase 1 (Setup)**: `tiktoken` install — no dependencies.
- **Phase 2 (Foundational)**: T001a/T002a can run in parallel; BOTH must be
  approved before T001b/T002b (which can then also run in parallel, since
  they touch different files: `formatters.py` vs `tools.py`). BLOCKS
  Phase 3/4/6.
- **Phase 3 (US1)** and **Phase 4 (US2)**: both depend only on Phase 2
  completion — can be worked in either order or in parallel (different
  test functions in the same file — coordinate to avoid merge conflicts,
  not a logical dependency).
- **Phase 5 (flagged deletion)**: independent of Phase 3/4 ordering, but
  its own approval gate (T011) is separate from — and MUST NOT be bundled
  with — every other gate in this file, per CONSTITUTION §VIII and
  METHODOLOGY §XVIII (no generalizing one approval into another).
- **Phase 6 (Billed E2E)**: Step 1 (split, T012-T014) can happen any time
  (pure reorganization, no dependency on Phase 2-5). Step 2's new tests
  (T009a/T010a/T015a) depend on Step 1 being complete (they're written
  directly into the new file) AND on Phase 2/3/4's implementation being
  complete (T001b/T002b) — these are confirmatory E2E tests of finished
  behavior, not TDD-driving tests for it.
- **Phase 7 (Polish)**: after all of Phase 2-6 are complete and green.

## Notes

- Every `a`/`b` pair above follows METHODOLOGY §VI exactly: tests written
  and approved BEFORE the corresponding implementation; once approved,
  immutable without a fresh, explicit approval (§VIII) — this applies even
  within this single small feature, task by task, not just once at the
  start.
- T011's gate is intentionally called out as separate from every other
  gate in this file — approving any other phase's tests does not carry
  approval for deleting the pre-existing test in Phase 5, and vice versa.
  T012's gate (the file-split plan) is likewise separate from T011's and
  from Phase 2-4's test-plan gates.
- Billed tests (T009a/T010a/T015a, and the full-suite run T014) are
  explicitly exempt from the run-approval and one-at-a-time restrictions
  that apply to `expensive`-tier tests (CLAUDE.md/CONSTITUTION §VII) —
  they still go through the normal TDD test-plan approval gate like any
  other test task, but running them once approved needs no further
  per-run sign-off.
