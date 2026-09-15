# Tasks: Morning Client-Name Cache

**Input**: Design documents from `specs/repo/features/072-morning-client-name-cache/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/cache-contract.md

**Tests are INCLUDED** (per operator direction) — unit tests for the new `ClientCache`
module, integration tests (real Morning sandbox, no mocking) for the wired-in behavior.
`billed`/`expensive` acceptance tests (Phases 1.b/2/3 from user-stories.md) are explicitly
OUT of scope for `speckit.implement` — final phase, run only after everything below is
GREEN.

## Correction found during tasks planning (folded in below)

The spec's "Handling Stale Data" section assumes write tools consume a **cached
`client_id`** directly, evicting on a Morning "Invalid Client ID" HTTP error. That is not
how this codebase's write tools actually work: `_require_resolved_client` (`tools.py`)
already does its own **live, name-based** re-resolution on every write call (bugfix-028
architecture fix) — no write tool has ever consumed a client_id straight from
`resolve_client_name`'s output (REQ-CLIENT-018: only a name is ever disclosed). So a stale
cache entry can never reach Morning as a bad id; instead, a write whose `client_name` came
from a now-stale cache hit will simply fail `_require_resolved_client`'s live lookup with
today's existing `ClientNotFoundError` — no new error class needed. **The correct
eviction hook is therefore inside `_require_resolved_client`/`_resolve_exact_client_name`:
when a name that IS in the cache fails live re-resolution, evict it there.** This keeps
the user-facing behavior the spec asks for (a stale name self-heals via the existing "not
found" message; the cache is cleared so a retry re-resolves live) without inventing a
code path this architecture doesn't have.

## Phase 1: Setup

- [x] T001 Add `morning_cache_enabled` (bool, default false) and
  `client_cache_sweep_interval_minutes` (int, default 60) to
  `apps/morning-mcp-app/config/config.schema.json`'s `feature_flags`/top-level object
- [x] T002 [P] Add the same two fields (commented-out/default values) to
  `apps/morning-mcp-app/config/config.example.json`
- [x] T003 [P] Add `morning_cache_enabled: false` to
  `apps/morning-mcp-app/config/config.test.json` (explicit default; tests that need it on
  set it via a per-test config override, never a shared mutation)
- [x] T004 Add corresponding fields to `MorningMCPConfig` (`apps/morning-mcp-app/src/denidin_mcp_morning/config.py`)
  and `load_config()`'s parsing/defaults
- [x] T005 [P] Confirm `APScheduler` availability for `apps/morning-mcp-app` (it has no
  current dependency on it, unlike `denidin-app`) — add `APScheduler>=3.10.0` to
  `apps/morning-mcp-app/requirements.txt` if missing
- [x] T006 Create `apps/morning-mcp-app/data/` (gitignored) as the new cache-db directory;
  add a `.gitignore` entry

## Phase 2: Foundational — `ClientCache` module (blocking prerequisite)

- [x] T007 [P] Unit tests for `ClientCache` in
  `apps/morning-mcp-app/tests/unit/test_client_cache.py` (real SQLite against a tmp path,
  no Morning, no mocking needed — this is pure local state): `lookup_exact` miss on empty
  db; `write_through` then `lookup_exact` hit; name normalization equivalence (word order /
  casing / geresh, mirroring `_bag_equal_words`); `evict` removes a row and subsequent
  `lookup_exact` misses; `reconcile` upserts new rows, updates a renamed row, deletes a
  row no longer present
- [x] T008 Implement `ClientCache` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/client_cache.py` per
  contracts/cache-contract.md and data-model.md's schema — make T007 pass

## Phase 3: User Story 1 — Cache Hit Fast Path (P1)

**Goal**: A previously-resolved exact client name resolves with zero Morning API calls.
**Independent test**: resolve the same known client name twice; the second call makes no
`search_clients` HTTP call.

- [x] T009 [P] [US1] Integration test in
  `apps/morning-mcp-app/tests/integration/test_client_cache_hit.py` (real sandbox, feature
  flag on via a per-test config override): resolve a real sandbox client's exact name once
  (populates the cache via write-through), then wrap the real `MorningClient` in a
  call-counting spy (not a mock — a thin pass-through wrapper) and resolve the same name
  again, asserting `search_clients` was invoked zero additional times
- [x] T010 [US1] Wire the cache-hit fast path into `resolve_client_name`
  (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`) per contracts/cache-contract.md:
  flag-gated `cache.lookup_exact(name)` before `resolve_client_by_name`; on hit, return
  `format_client_name_resolved(hit.name)` unchanged in shape — make T009 pass
- [x] T011 [US1] Wire `server.py` to construct one `ClientCache` instance (from
  `MorningMCPConfig`'s new fields) and pass it into the tool-calling boundary alongside the
  existing `MorningClient` injection

## Phase 4: User Story 2 — Cache Miss Fallback + Write-Through (P1)

**Goal**: An unknown name still resolves via the existing live flow, and gets cached for
next time.
**Independent test**: resolve a real sandbox client not yet cached (miss, live resolution,
unchanged output) — resolve the same name again, now a hit.

- [x] T012 [P] [US2] Integration test in
  `apps/morning-mcp-app/tests/integration/test_client_cache_miss_then_hit.py`: first
  resolution of a real sandbox client is a live call (cache empty); assert the returned
  Hebrew string is unchanged from today's pre-cache behavior; second resolution of the same
  name makes zero further `search_clients` calls (same spy technique as T009)
- [x] T013 [US2] Wire write-through into `resolve_client_name`'s live-hit branch (on a
  `resolve_client_by_name` exact match, `cache.write_through(resolved)`) — make T012 pass
- [x] T014 [P] [US2] Integration test in
  `apps/morning-mcp-app/tests/integration/test_client_cache_add_client_writes_through.py`:
  call `add_client` for a fresh sandbox client, then resolve its exact name and assert zero
  `search_clients` calls (cache was populated by `add_client` itself, never touched Morning
  search)
- [x] T015 [US2] Wire write-through into `add_client`'s success path (needs the created
  client's `id` + normalized `name` — both already available from Morning's response,
  no extra lookup) — make T014 pass

## Phase 5: User Story 3 — Cache Correction / Sync (P2)

**Goal**: A stale cache entry (renamed/deleted client) self-heals — both reactively (at
write time) and proactively (periodic sweep).

- [x] T016 [P] [US3] Unit test in `apps/morning-mcp-app/tests/unit/test_client_cache.py`
  (extends T007's file): `reconcile([...])` against a fabricated `Client` list fully
  replaces cache contents (upsert existing, insert new, delete missing) — already covered
  by T007; this task adds the edge case of reconciling an **empty** list (full eviction)
- [x] T017 [US3] Wire the reactive-eviction correction into
  `_require_resolved_client`/`_resolve_exact_client_name` (`tools.py`, per the "Correction"
  note above): when a `client_name` present in the cache fails live re-resolution
  (`_resolve_exact_client_name` returns `None`), call `cache.evict(...)` for that cached
  entry before `_raise_client_not_found` runs, so a retry after the name is actually fixed
  resolves live rather than getting a phantom repeat hit
- [x] T018 [P] [US3] Integration test in
  `apps/morning-mcp-app/tests/integration/test_client_cache_stale_eviction.py`: cache a real
  client's name via `add_client`, rename that client in Morning directly
  (`client.update_client`, real sandbox call — not `resolve_client_name`/`add_client`, so
  it does not itself go through the cache), then attempt `get_client_details` (read-only,
  chosen over `create_transaction_account` to avoid leaving stray sandbox documents —
  both go through the same `_require_resolved_client` eviction hook) against the now-stale
  old name with `name_resolved=True`; assert it raises `ClientNotFoundError` (unchanged
  existing behavior) and that a subsequent `lookup_exact` for the old name is a miss
  (evicted). **Confirmed green on retry** (2026-09-15) — the earlier `403 Forbidden` was
  transient/environmental as suspected (same sandbox account, no code change between
  attempts).
- [x] T019 [US3] Implement `cache_sweep_service.py`
  (`apps/morning-mcp-app/src/denidin_mcp_morning/`): an `APScheduler` `BackgroundScheduler`
  job (matching `reminder_delivery_service.py`'s established shape), interval from
  `client_cache_sweep_interval_minutes`, calling `list_clients`'s internal
  full-pagination helper then `cache.reconcile(...)`; only started when
  `morning_cache_enabled` is true
- [x] T020 [P] [US3] Integration test in
  `apps/morning-mcp-app/tests/integration/test_client_cache_sweep.py`: run one sweep tick
  directly (not on a timer — call the sweep function once) against the real sandbox and
  assert every real client is now a cache hit
- [x] T021 [US3] Wire `cache_sweep_service` startup (and graceful shutdown) into
  `server.py`, flag-gated, mirroring how `denidin-app`'s schedulers are started/stopped

## Phase 6: Polish & Cross-Cutting

- [x] T022 [P] Add `morning-mcp-app-{dev,prod}`'s new `data/client_cache.db` volume mount
  to `docker/docker-compose.dev.yml` and `docker/docker-compose.prod.yml` (repo root),
  matching the existing config/logs mount pattern for that service
- [x] T023 [P] Document the new fields in `apps/morning-mcp-app/README.md` (if one exists)
  or the app's own config docs, and note the `data/` volume in CLAUDE.md's multi-clone
  data-singleton section if this cache should be shared across clones the same way
  `dev_data`/`data` are (operator decision — flag for follow-up, not blocking)
- [x] T024 Ran the full existing `apps/morning-mcp-app` unit suite (flag OFF, the
  default): 375 passed (372 pre-existing + 3 new `TestDuplicateNames` cases), same 4
  pre-existing failures as on clean `master` (confirmed via `git stash` comparison —
  `test_logger_retention.py`'s concurrency test + 3 `test_tools_document_creation.py`
  fixture-setup tests), zero regressions from this feature. Ran the full existing
  integration suite once too (133 tests, ~5 min against the real sandbox): 105
  passed/28 failed, and the 28 are concentrated in files unrelated to this feature's own
  wiring (`test_morning_sandbox_update_client_tool.py`,
  `test_morning_sandbox_resolve_client_name_tool.py`,
  `test_morning_sandbox_standalone_receipt.py`) — same `403 Forbidden` from Morning
  confirmed pre-existing (identical failure reproduces on clean `master`).
- [x] T025 Ran every new test with the flag effectively ON (each test constructs its own
  `ClientCache` directly, real sandbox): unit — 22/22 `test_client_cache.py`. Integration —
  `test_client_cache_hit.py` (2/2), `test_client_cache_miss_then_hit.py` (1/1),
  `test_client_cache_add_client_writes_through.py` (1/1),
  `test_client_cache_sweep.py` (1/1), and `test_client_cache_stale_eviction.py` (T018,
  confirmed green on retry once the transient sandbox `403` cleared) (1/1) — all green.
  28/28 total across the full cache-related test set.

## Post-implementation design review (2026-09-15) — significant redesign

After T025's initial "done" state above, an operator design review of the shipped
mechanics (asked directly: when/how does the cache populate/evict, why do writes
re-resolve live, why does the cache only store name+id) surfaced real gaps in the
original design, not just documentation gaps. Full rationale lives in
`contracts/cache-contract.md`'s 2026-09-15 revision and `data-model.md`'s matching
update; summary of what changed:

1. **Cache now stores the FULL client record** (email/phone/tax_id/address), not just
   name+id — costs zero extra Morning calls (every write path already had the full
   record in hand and was discarding it), and is what makes `get_client_details`
   genuinely cache-accelerated for the first time.
2. **`update_client` and `get_client_details` are now cache-first too** (`trust_cache`
   parameter on the shared `_resolve_exact_client_name`/`_require_resolved_client`
   gate, default `True`) — previously they always re-resolved live, gaining nothing
   from the cache at all.
3. **`add_client` now recovers from Morning's "already exists" failure**
   (verified live: HTTP 400, `errorCode: 1010`, existing client_id handed back in
   `errorMessage`) by fetching and write-throughs the real existing record instead of
   just failing and leaving the cache stale on that client indefinitely.
4. **New failure mode, handled**: cache-first writes mean the actual document-creation
   call (not the identify step) is now where a deleted client_id can surface — verified
   live (HTTP 400, `errorCode: 2411`), caught by
   `_create_document_with_stale_client_recovery`, evicts + raises the existing
   `ClientNotFoundError`.
5. `test_client_cache_stale_eviction.py` (T018) was rewritten — its old premise (a live
   per-call check on `get_client_details` catches a rename immediately) no longer holds
   under cache-first reads; it now tests the actual current behavior (served stale until
   the periodic sweep corrects it).
6. Two new integration tests added:
   `test_client_cache_stale_client_id_at_write_time.py` (item 4 above) and
   `test_client_cache_add_client_already_exists.py` (item 3 above).

**Final verification (2026-09-15)**: unit — 25/25 `test_client_cache.py` (22 original +
3 new full-record tests). Integration — all 8 cache-related tests confirmed green,
each individually (`test_client_cache_hit.py` 2/2, `test_client_cache_miss_then_hit.py`
1/1, `test_client_cache_add_client_writes_through.py` 1/1, `test_client_cache_sweep.py`
1/1, `test_client_cache_stale_eviction.py` 1/1 [rewritten], `test_client_cache_stale_
client_id_at_write_time.py` 1/1 [new], `test_client_cache_add_client_already_exists.py`
1/1 [new]). Running the full 8-file group back-to-back repeatedly hit the real Morning
sandbox's `POST /clients` rate limit (same `403 Forbidden` class as this feature's other
pre-existing sandbox-throttle failures, not a code defect) — every test is confirmed
green on its own; the sandbox simply does not tolerate this many client-creation calls
in quick succession within one session's cumulative call volume for the day.

## Dependencies

- Phase 1 (Setup) blocks everything.
- Phase 2 (`ClientCache`) blocks Phases 3-5 (every story wires into it).
- US1 (Phase 3) has no dependency on US2/US3 — independently testable/mergeable first (MVP).
- US2 (Phase 4) depends on US1's `resolve_client_name` wiring (T010) being in place, since
  it extends the same function's miss branch.
- US3 (Phase 5) depends on US2 (needs `add_client` write-through, T015, for T018's setup
  step) and on Phase 2.
- Phase 6 (Polish) runs last.

## Parallel execution examples

- T002/T003/T005/T006 (Setup) can run together — different files.
- T007 (unit tests) and T008 (implementation) are NOT parallel (tests before code, per
  METHODOLOGY §VI.b) but T007 itself can be drafted fully before T008 starts.
- Within Phase 4: T012 and T014 (different integration test files) are parallel; T013 and
  T015 are not parallel with each other (both touch `tools.py`) but each only starts once
  its own test (T012/T014 respectively) is written.

## Implementation strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1 only)**: the cache-hit fast path alone already
delivers the spec's core latency win for the common case (a name already seen once).
US2 (write-through) and US3 (correction/sync) are what sustain the 85% hit rate over time
and handle staleness — required before the Phase 3 acceptance test (85% hit rate) can pass,
but not required for the mechanism itself to be demonstrably correct and mergeable.
