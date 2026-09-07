# Tasks: Client-name resolution architecture fix

## Status as of 2026-08-12, end of overnight session

Phases 1–7 implemented, unit/integration-tested, and — where sandbox-dependent — verified against the
real Morning sandbox. **Nothing in this diff is committed** — the user has not reviewed any of it yet;
per the standing "never commit/push without approval" rule, this all awaits explicit review, same as
everything else on this branch.

- **Phases 1–6**: fully done. `resolve_client_name` built and sandbox-verified; the shared
  `_require_resolved_client` gate built; all six tools (`get_client_details`, `update_client`,
  `list_invoices`, `create_invoice`, `create_transaction_account`, `create_combo_document`) migrated,
  each with rewritten unit tests (morning-mcp-app: 267 passing) and rewritten/added real-sandbox
  integration tests (all touched files individually confirmed green — see the sandbox note below); dead
  code (`_resolve_client_for_document_creation`/`ClientResolution`) deleted, zero remaining references.
  denidin-app's `ai_handler.py` `NO_APPROVAL_MCP_TOOLS` updated (adds `resolve_client_name`) and its own
  unit (764) + integration (29) suites re-confirmed green.
- **Sandbox note**: the full 90-test integration run tripped the sandbox's `/api/v1/account/token`
  rate limit partway through (a burst of multiple test files each minting their own fresh token in
  quick succession, not a volume-over-time issue — confirmed by testing: a bundled 4-file retry failed
  *faster* and *worse* than the original 90-test run, while every affected file passed cleanly when run
  **individually**). All originally-failing tests were re-run solo and are green. **Nobody has re-run
  the complete 90-file suite in one single green pass** — if that's wanted as a final check, expect to
  need the same one-file-at-a-time pacing, or a lighter concurrent MorningClient token cache, to avoid
  retripping the limit.
- **Phase 7**: `runtime_constitution.md` rewritten (the "Resolving a client by name" section, the
  `list_invoices`/"Resolving which invoice" tie-in, and — found necessary during the edit, not
  originally scoped — two more sections that had gone stale for the same reason: `update_client`'s own
  "resolve via get_client_details first" instruction, and the "tool's own reply discloses" claims for
  `get_client_details`/`update_client`, both no longer true post-migration). **NOT verified against a
  real live turn** — that requires denidin-app's billed tests, which require the `morning-mcp-app` dev
  container running TODAY's code, which requires a rebuild/restart. Restarting/rebuilding any
  environment container is a standing, per-instance, never-bundled approval gate in this repo
  (CLAUDE.md's "NEVER START AN ENVIRONMENT... WITHOUT EXPLICIT APPROVAL") — the overnight "finish
  through phase 8" go-ahead does not cover it, so this step was deliberately left undone rather than
  assumed.
- **Phase 8**: **not started**, blocked on the same container-restart approval as Phase 7's
  verification step — billed/expensive E2E tests exercising the real MCP round-trip need the container
  rebuilt with today's `morning-mcp-app` code first, or they'd either silently test stale code or fail
  to reach it at all.

**What a fresh session (or the user directly) needs to do next**: review this diff (all of it, nothing
committed yet); if approved, explicitly authorize a `morning-mcp-app` dev container
stop/rebuild/restart; then resume Phase 7B (live-turn constitution verification) and Phase 8 (the
billed/expensive assertion audit) as originally scoped below.

---

Dependency-ordered, grouped by the 8 phases in `client-name-resolution-plan.md`'s "Step 2". Every
phase's implementation task (B) is blocked until its test task (A) is written AND explicitly approved
by the user, per METHODOLOGY §VII (Bug-Driven Development) — mirrored here per-phase rather than once
for the whole change, given the size/blast-radius (see plan.md's Complexity Tracking). Unit/integration
tests: no per-run approval needed to execute once written, but still need review before being treated
as the basis for implementation (this repo's Test Immutability rule, CONSTITUTION §VIII). Billed test
changes and any `tools.py`/`server.py`/`runtime_constitution.md` content change: checkpointed with the
user, same discipline as the rest of this session.

## Phase 1 — `resolve_client_name` in isolation (fully additive, nothing existing breaks)

- **1A**: Write unit tests for `tools.resolve_client_name` (exact/non-exact/ambiguous/zero-match — new
  test file or new section in `test_tools_client_resolution.py`, reusing existing fixtures) and for the
  two new formatters (`format_client_name_resolved`, `format_name_not_resolved`). Must fail (function/
  formatters don't exist yet).
- **1B** (blocked on 1A approval): Implement `tools.resolve_client_name`, the two new formatters, the
  `server.py` `@mcp.tool()` wrapper, add `"resolve_client_name"` to `NO_APPROVAL_MCP_TOOLS`
  (`ai_handler.py`) and to `EXPECTED_TOOL_NAMES` (`test_mcp_server_e2e.py`). Verify 1A now passes.
- **1C**: One new real-sandbox integration test file, `test_morning_sandbox_resolve_client_name_tool.py`
  (exact/non-exact/ambiguous/zero against the real Morning sandbox — no mocking, per CONSTITUTION §V).

## Phase 2 — Shared gate (`_require_resolved_client`/`_resolve_exact_client_name`/`ResolvedClient`)

- **2A**: Unit tests for the gate in isolation, using a fake `MorningClient` (not yet wired into any of
  the six real tools): `name_resolved=False` → zero `search_clients` calls attempted, correct refusal
  string; `True` + exact → resolved client returned; `True` + non-exact-only/ambiguous/zero →
  `ClientNotFoundError` in every case (exact-only mode collapses all three into one outcome). Must fail
  (gate doesn't exist yet).
- **2B** (blocked on 2A approval): Implement `ResolvedClient`/`_resolve_exact_client_name`/
  `_require_resolved_client`. Verify 2A now passes. Not yet called by any of the six tools.

## Phase 3 — Migrate `get_client_details` and `update_client` (one at a time)

- **3A**: Rewrite/relocate `get_client_details`'s and `update_client`'s existing unit tests per
  `client-name-resolution-data-model.md`'s enumeration (non-exact/ambiguous cases removed — now covered
  by Phase 1's `resolve_client_name` tests; remaining tests gain `name_resolved=True`; add a
  `name_resolved=False` refusal test for each). Present the diff for approval before implementing.
- **3B** (blocked on 3A approval): Migrate `get_client_details` to `_require_resolved_client`, then
  `update_client` separately (two small, individually-verified commits, not one combined change).
  Update the corresponding `server.py` wrappers. Verify 3A now passes.
- **3C**: Rewrite/relocate the corresponding real-sandbox integration tests (`test_morning_sandbox_get_
  client_details_tool.py`, `test_morning_sandbox_update_client_tool.py`) per the same pattern.

## Phase 4 — Migrate `list_invoices`

- **4A**: Rewrite `list_invoices`'s multi-word-`client_name` unit tests (relocate the non-exact
  confirmation case; remaining gain `name_resolved=True`), plus a **new regression test proving the
  single-word substring-search path is untouched** (no `name_resolved` requirement, no behavior
  change) — this is the one phase where "don't break something adjacent" needs its own explicit test,
  since the multi-word/single-word branch split is easy to get wrong.
- **4B** (blocked on 4A approval): Implement. Verify 4A passes, and specifically re-run every existing
  single-word `client_name` test to confirm zero behavior change.
- **4C**: Rewrite the corresponding sandbox integration tests (`test_morning_sandbox_list_invoices_
  tool.py`).

## Phase 5 — Migrate `create_invoice`, `create_transaction_account`, `create_combo_document` (highest blast radius — real document creation, last for a reason)

- **5A**: Rewrite/relocate unit tests for all three (`test_tools_document_creation.py` and any
  `create_invoice`-specific file), including the noted **behavior change** for
  `test_create_combo_document_refuses_when_client_ambiguous` (multi-candidate now collapses to
  `ClientNotFoundError` under exact-only mode — confirm this is still the desired behavior before
  implementing, don't just carry the old assertion's *shape* forward with a new exception type).
- **5B** (blocked on 5A approval): Migrate one tool at a time (`create_invoice` → `create_transaction_
  account` → `create_combo_document`), each its own commit, each re-verified against its own full unit
  suite before moving to the next.
- **5C**: Rewrite the corresponding sandbox integration tests (`test_morning_sandbox_create_invoice_
  client_resolution.py`'s exact/zero-match remnants, `test_morning_sandbox_document_creation_tools.py`).

## Phase 6 — Delete dead code

- **6**: Delete `_resolve_client_for_document_creation`/`ClientResolution` in their own, separately
  reviewable commit, once Phase 5 confirms nothing references them (`grep -rn
  "_resolve_client_for_document_creation\|ClientResolution" apps/morning-mcp-app/src` returns nothing
  outside the definition itself, before deleting).

## Phase 7 — `runtime_constitution.md` rewrite

- **7A**: Draft the replacement "Resolving a client by name" section (text already drafted in
  `client-name-resolution-plan.md`'s "Decided design" — this task is applying it to the real file,
  checking the second constitution copy at `apps/denidin-app/test_data/constitution/runtime_
  constitution.md` for whether it's actually live/referenced anywhere before deciding whether it also
  needs the change).
- **7B** (checkpointed with the user before being treated as final, per CONSTITUTION's "NO UNVERIFIED
  THIRD-PARTY ASSUMPTIONS" rule): apply the edit, then verify against one real live turn (not just
  read back for internal consistency) before moving to Phase 8.

## Phase 8 — `denidin-app` billed/expensive E2E: assertion audit only, NOT flow changes (last — most expensive to iterate, needs the finished constitution text)

**Hard constraint (2026-08-12, explicit user decision)**: these tests are "the beacons of truth" for
real user interaction — their message sequences, prompts, turn counts, and "כן" exchanges are NOT to be
altered by this change. `resolve_client_name` is an internal, same-turn orchestration step (no new
user-visible round-trip), so the human-facing flow doesn't change. The only legitimate edits are to
assertions that inspect `ai_response.mcp_calls` where the tool-call shape genuinely changed (a
`resolve_client_name` call now appears; a "did you mean X?" disclosure that used to live in
`create_invoice`'s own output now lives in `resolve_client_name`'s output instead).

- **8A**: Run each test named in `client-name-resolution-data-model.md`'s billed/expensive section
  for real, AFTER phases 1-7 are implemented, and diff its actual output against pre-change behavior —
  audit which assertions actually broke and why, before touching anything. Do not rewrite
  speculatively.
- **8B** (checkpointed with the user, same as every billed-test edit this session): for each test that
  genuinely needs an assertion fix, make the minimal fix (never touch the message text sent, never add/
  remove/reorder turns) and re-run it for real to confirm both the fix and that the human-facing
  behavior is unchanged. Report per this session's one-at-a-time, stop-on-fail discipline.
- **8C**: Mirror the same audit-and-minimal-fix treatment in `tests/expensive/` where applicable.
