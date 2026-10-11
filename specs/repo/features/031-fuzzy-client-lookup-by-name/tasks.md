# Tasks: Fuzzy Client Lookup by Name — Feature 031

**Input**: `plan.md`, `research.md`, `spec.md` (this directory)
**Prerequisites**: plan.md (done), spec.md (done, Clarified), research.md (done — Decision 1
resolved the only open question via a live sandbox investigation)

---

**Compliance**: CONSTITUTION.md §V (real-sandbox integration tests, zero mocking of external
services) and METHODOLOGY.md §VI (TDD). This feature has **no production code task** — Phase 0
research already confirmed `list_invoices` is correct as built (see `research.md` Decision 1 /
`plan.md` Summary). The only remaining work is a single regression test.

**Tests**: the test *is* the deliverable here, not a preceding gate for implementation code — there
is no Task B to block. It locks in confirmed-correct behavior so a future change in Morning's own
API would be caught, rather than driving new code via RED→GREEN.

---

## Phase 3: User Story 1 — Confirm fuzzy client-name matching for `list_invoices` (Priority: P2)

**Goal**: permanently regression-test that `list_invoices`' `client_name` filter matches on a
substring anywhere in the stored name (not just an exact or prefix match), since this is the
behavior godfathers rely on when asking about a client by a partial/shortened name.

**Independent Test**: run
`apps/morning-mcp-app/tests/integration/test_morning_sandbox_list_invoices_tool.py` against the
real Morning sandbox — the new test passes on its own, independent of any other test in the file.

- [x] T001 [US1] Add
  `test_list_invoices_tool_finds_seeded_invoice_by_non_prefix_substring` to
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_list_invoices_tool.py`: reuse the
  existing `morning_client` fixture (module-scoped, already in this file); seed one real invoice
  for a unique **multi-word** client name (e.g.
  `f"Yossi Cohen DENIDIN_SUBSTRING_TEST_{unique_marker} Ltd"`, following the existing
  `seeded_invoice` fixture's pattern one function up in the same file); then call `list_invoices`
  with a query that is a **middle word of that name, not a prefix of the whole name** (e.g.
  `"Cohen"` or the bare `unique_marker` token) inside the existing up-to-12×1.5s (18s) indexing-wait
  poll loop (mirrors `test_list_invoices_tool_finds_seeded_invoice_by_client_name`'s loop exactly);
  assert the seeded invoice is found. This is new coverage distinct from the existing
  exact-name-match and total-miss tests already in this file.

**Checkpoint**: `pytest tests/integration/test_morning_sandbox_list_invoices_tool.py -v` — all
tests in the file (existing + new) pass against the real sandbox.

---

## Dependencies

- T001 has no dependencies on other tasks in this feature (single task, single file).
- No dependency on any other in-flight feature.

## Parallel Execution

Not applicable — a single task.

## Implementation Strategy

**MVP = the whole feature**: T001 is the entire scope. Once it passes, this feature is complete —
proceed to `/speckit.analyze` (optional, given the small surface area) or directly to closing out
per `plan.md`'s Phase 2 (update `spec.md` Status, move to `specs/done/`).
