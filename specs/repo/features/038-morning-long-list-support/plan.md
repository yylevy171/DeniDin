# Implementation Plan: Morning Long List Support — Feature 038

**Feature**: 038-morning-long-list-support
**Branch**: `feature/038-morning-long-list-support`
**Spec**: `./spec.md` · **User Stories**: `./user-stories.md` · **Research**: `./research.md`
**Status**: Ready for Task Generation
**Estimated Duration**: 1 day (single-function fetch-loop port + one new formatter helper + test suite)
**Updated**: August 4, 2026

**Compliance**: CONSTITUTION.md (§I no env vars — N/A, no config touched; §III git workflow —
feature branch created before any work; §IV type hints/docstrings on all touched functions; §V
real-sandbox integration tests / zero mocking of external services — all new/changed tests hit the
real Morning sandbox, no `unittest.mock`; §VIII test immutability — one existing test requires
human-approved rewrite, flagged explicitly, not silently changed; §XVII no monkey-patching — plain
function edits, no runtime patching) and METHODOLOGY.md (§I spec-first with mandatory
`user-stories.md`, §VI TDD with human approval gates, §VII Integration Contracts). No new feature
flag: this is a bug fix to an existing tool's fetch/format behavior behind an existing, unconditional
code path — CONSTITUTION §I's feature-flag rule applies to *new* behavior being added alongside old
behavior; here there is no old behavior worth preserving (the old behavior is the bug), so this
follows Bug-Driven-Development-adjacent reasoning even though it's filed as a feature spec (the user
opted to file it as `spec.md`/`backlog/` rather than `bugfixes/`, per the transcript's request).

---

## Summary

Phase 0 research (`research.md`) confirmed `/documents/search` (wrapped by
`MorningClient.list_invoices()`) returns the identical `total`/`page`/`pages`/`items`
pagination shape already proven for `/clients/search` — so `list_invoices` can
reuse `list_clients`' exact real-pagination pattern (`tools.py:942-955`,
Feature 026) with no new API-shape handling. Additionally, a live sandbox
measurement (research.md Decision 5, added 2026-08-04 after user review of
the test plan) confirmed a second, independent truncation concern is real
and common: a fully-fetched, in-cap result set can still be far too large
to send as one MCP tool call reply (~280 tokens/invoice block; an 81-item
real result formats to ~22,695 tokens). After a second round of test-plan
review (research.md Decision 6), the token budget was (mistakenly)
permanently lowered to 800; a third round (research.md Decision 7,
user-corrected) reverted this — **2500 is the real, unmodified practical
limit the user observed on MCP tool call output in practice, not a
self-imposed margin to lower**, and it may need to be raised later. The
budget is now a `MorningMCPConfig` field (`list_invoices_token_budget`,
default 2500), not a hardcoded constant, so future changes are config
edits, not code changes - exactly one test in this feature overrides it
to a lower value, via the same config-value dependency-injection path
every other config value already uses.

**Deliverable**: `list_invoices` (`tools.py:411-449`) is rewritten to (1) read
the real `total` from Morning's first page, (2) if `total` is within the
raised fetch cap (`_LIST_INVOICES_MAX_ITEMS`, 10 → 100), loop every remaining
page and status-filter the complete set; (3) if `total` exceeds the cap,
fetch nothing further and return a new refusal message stating the real
total; (4) for the in-cap success path, estimate the formatted reply's
token size (`tiktoken`, `o200k_base`) against the config-driven
`list_invoices_token_budget` (default 2500, `_LIST_INVOICES_TOKEN_BUDGET`
in `tools.py` is the matching Python-level default for direct calls)
and, if it would exceed that, include only the largest prefix that fits,
with an honest shown/total count and a "too long, narrow your search"
closing note. `format_invoice_list` loses its now-dead `has_more` parameter
and gains the count line (now shown-vs-total aware). A new
`format_too_many_invoices_message(total)` formatter is added, mirroring
`format_too_many_clients_message`. All test fixtures use real,
already-existing sandbox data (no new invoices seeded) — three date ranges
found via research.md Decision 4/6 (81 items, 103 items, 13 items).
Three new `billed` tests land in `apps/denidin-app`'s billed test suite,
which — per user direction — is also being split from one 2094-line file
into per-topic files as part of this feature (see Project Structure below).

## Technical Context

- **Language/Version**: Python 3.11 (unchanged).
- **Primary Dependencies**: `tiktoken>=0.5.0` (NEW, added to
  `apps/morning-mcp-app/requirements.txt`) — for token-budget estimation
  (`o200k_base` encoding, matching `apps/denidin-app`'s existing usage for
  consistency). Otherwise none new — reuses existing `pytest`,
  `MorningClient`, `pydantic` `Invoice` model, and the real-sandbox
  integration test pattern already established by
  `test_morning_sandbox_list_invoices_tool.py`.
- **Storage**: N/A.
- **Testing**: `apps/morning-mcp-app/tests/integration/test_morning_sandbox_list_invoices_tool.py`
  (real sandbox, no mocks — CONSTITUTION §V) — new tests for US1/US2
  against real, already-existing sandbox date ranges (research.md Decision
  4 — no new invoices seeded); the old `test_list_invoices_tool_caps_results_at_ten_items`
  is deleted (human-approved, T011 — folded into the new US2 test's
  coverage rather than rewritten in place).
  `apps/morning-mcp-app/tests/unit/` gains coverage for the new formatter
  functions (`format_invoice_list`'s count line, `format_too_many_invoices_message`)
  and the fetch-loop/cap-boundary/token-budget logic, isolated from the
  network. `apps/denidin-app/tests/billed/` gains three new
  `@pytest.mark.billed` tests (US1/US2 real-total accuracy + US3 partial-
  truncation, one each) exercising three real sandbox date ranges
  end-to-end (real webhook → real Responses API → real MCP round trip
  against the already-running `morning-mcp-app-dev` container), confirming
  the model relays the tool's precomputed counts/messages faithfully
  rather than inferring its own — directly addressing the user's observed
  model-imprecision concern. Per user direction, these land in a new
  `test_denidin_morning_list_invoices_e2e.py`, itself part of a full
  section-by-section split of the pre-existing
  `test_denidin_morning_mcp_e2e.py` (2094 lines, ~40 tests) into 4 files —
  see Project Structure below.
- **Target Platform**: N/A — no runtime/container change; `apps/morning-mcp-app`'s
  existing Docker container picks this up on its next rebuild+redeploy (per
  CLAUDE.md's "merging does not redeploy" rule — out of scope for this plan,
  handled at `/haleluya` time).
- **Constraints**: Fetch cap of 100 raw items (Morning pages of 25 → up to 4
  page requests per in-cap call, confirmed via research.md Decision 1);
  display token budget config-driven, default 2500 (research.md Decision 7).
- **Scale/Scope**: One function rewritten (`list_invoices`), one formatter
  function changed (`format_invoice_list`), one formatter function added
  (`format_too_many_invoices_message`), one constant changed
  (`_LIST_INVOICES_MAX_ITEMS`), one new config field
  (`MorningMCPConfig.list_invoices_token_budget`), test files
  updated/added in `apps/morning-mcp-app/tests/unit/` and `tests/integration/`,
  plus a 4-way file split + 3 new tests in `apps/denidin-app/tests/billed/`.

## Constitution Check (pre-Phase 0)

- **No env vars** — PASS: the fetch cap stays a module constant like
  `_LIST_CLIENTS_MAX_ITEMS` (not config-driven today, unchanged by this
  feature), but the NEW token budget is added as a genuine
  `MorningMCPConfig`/`config.json` field (`list_invoices_token_budget`,
  research.md Decision 7) — config-driven from the start, per §I, not a
  hardcoded constant needing a code change to adjust.
- **UTC** — N/A: no new timestamp handling.
- **Feature branch** — PASS: `feature/038-morning-long-list-support`.
- **Feature flags** — N/A (see Compliance note above): fixes broken behavior
  on an existing, always-on code path; no old behavior worth preserving
  behind a flag.
- **New dependency (`tiktoken`)** — PASS: already an approved, in-use
  choice elsewhere in this monorepo (`apps/denidin-app`); no new
  technology class introduced, just a second app depending on an
  already-vetted library.
- **Real-sandbox tests / ZERO-MOCKING** — PASS (by construction): all new/
  changed tests hit the real Morning sandbox exactly like existing sibling
  tests in the same file; no `unittest.mock`.
- **No monkey-patching** — PASS: plain function bodies edited in place; no
  runtime attribute/method replacement.
- **Test immutability (§VIII)** — ONE FLAGGED EXCEPTION:
  `test_list_invoices_tool_caps_results_at_ten_items` asserts a cap value
  this feature deliberately changes, and is deleted outright (per explicit
  user direction, T011) rather than rewritten — its coverage intent (a cap
  exists and is enforced) is superseded by the new US2 test. Requires
  explicit human approval at the TDD test-plan gate (`tasks.md`), not
  silently removed.
- **File split (`test_denidin_morning_mcp_e2e.py` → 4 files)** — PASS: a
  pure move/reorganization of existing test *content* (no test logic
  changed), plus this feature's 3 new tests landing directly in the
  resulting file for their topic. Existing tests remain byte-for-byte
  identical in behavior; only their file location and any necessarily-
  shared fixtures/helpers move.
- **Friendly errors (§X)** — PASS: the new refusal message follows the
  existing Hebrew, no-jargon, actionable-next-step pattern already used by
  `format_too_many_clients_message`.

*Re-checked post-Phase-1 design: unchanged — no new violations introduced by
the data model / contracts review below.*

## Integration Contracts (METHODOLOGY §VII)

### `list_invoices` (tool) ↔ `MorningClient.list_invoices()` (client) Contract

**`list_invoices` (tool) MUST**:
- Call `client.list_invoices(params)` at least once (page 1) for every
  invocation, using the existing `_map_list_invoices_filters` output
  unchanged (REQ-INVOICE-005 — no new/changed request params).
- Read `total`, `page`, `pages` from that first response before deciding
  whether to fetch further (mirrors `list_clients`, `tools.py:944,950-951`).
- Pass `{**params, "page": page_num}` for every subsequent page request,
  identical to `list_clients`' `{**payload, "page": page_num}` pattern.
- Stop fetching once `len(items) >= total` or `page_num >= pages` — same
  loop-termination logic as `list_clients` (`tools.py:952`), including its
  defensive `page`/`pages` defaulting to `1` when absent (REQ-INVOICE-007).

**`MorningClient.list_invoices()` PROVIDES** (confirmed live, research.md
Decision 1):
- A dict response with `items` (list, up to `pageSize`=25 per page),
  `total` (int, full match count for the query, ignoring this app's local
  `status` filter), `page` (int, 1-indexed current page), `pages` (int,
  total page count) — identical field names to `search_clients()`.
- No server-side `status` filtering (unconfirmed param name — unchanged
  from today, `_matches_status` still applies locally after all pages are
  fetched).

**`MorningClient.list_invoices()` EXPECTS**:
- `params: dict` — unchanged shape (`fromDate`/`toDate`/`clientName`,
  optionally `page` for subsequent requests).

### `list_invoices` (tool) ↔ `format_invoice_list` / `format_too_many_invoices_message` (formatters) Contract

**`list_invoices` MUST**:
- Call `format_invoice_list(invoices, total_matched)` (signature changed:
  `has_more` removed per research.md Decision 3, `total_matched` added per
  Decision 5) only when the complete, status-filtered set was successfully
  fetched (i.e. `total` was within the cap) — `invoices` here is the
  possibly-token-budget-truncated list, `total_matched` is always the true
  post-status-filter count (equal to `len(invoices)` when untruncated).
- Call `format_too_many_invoices_message(total)` instead, without calling
  `format_invoice_list` at all, when `total` exceeds the item cap.

**`format_invoice_list` PROVIDES**:
- Given a non-empty `invoices` where `len(invoices) == total_matched`: a
  Hebrew string whose first line states the exact count, followed by one
  block per invoice (unchanged `format_invoice_confirmation` per-item
  rendering) — REQ-INVOICE-004.
- Given a non-empty `invoices` where `len(invoices) < total_matched`
  (token-budget truncation occurred): a Hebrew string whose first line
  states "showing X of Y", the same per-item blocks for the included
  subset, and a closing note that more results exist but were omitted for
  length, asking the user to narrow the search — REQ-INVOICE-009.
- Given an empty list: the existing unchanged "no results" message
  (REQ-INVOICE-006).

**`format_too_many_invoices_message` PROVIDES**:
- A Hebrew string stating the real `total` and asking the user to narrow
  by date range, client, or status — no itemized content, mirroring
  `format_too_many_clients_message`'s structure and tone.

### `list_invoices` (tool) ↔ token-budget truncation logic Contract

**`list_invoices` MUST** (only in the in-cap success path, after fetching
and status-filtering the complete set):
- Accept `token_budget: int = _LIST_INVOICES_TOKEN_BUDGET` as a parameter
  (DI endpoint for the config-driven value — `server.py` always passes
  `config.list_invoices_token_budget`; direct callers/tests may pass their
  own value or rely on the default, which matches the config default).
- Format each invoice via `format_invoice_confirmation` and measure it with
  `tiktoken.get_encoding("o200k_base")`, accumulating a running total.
- Reserve a fixed headroom in the 100-150 token range (exact value
  finalized at implementation — research.md Decision 7 confirmed the real
  13-item fixture's expected outcome, 8 of 13 shown, is identical anywhere
  in that range) out of `token_budget` for the count line and any
  truncation note, so the *item-block* budget is budget-minus-reserve, not
  the full amount.
- Stop including further invoice blocks once the next one would exceed
  the remaining item-block budget.
- Call `format_invoice_list` with both the (possibly truncated) list of
  invoices AND the true total matched count, so the formatter can render
  an honest "shown X of Y" line whenever `X < Y`.

**Token-budget logic PROVIDES**:
- A boolean-equivalent signal (shown count < true total) that
  `format_invoice_list` uses to decide whether to render the simple count
  line (REQ-INVOICE-004, untruncated) or the shown/total + narrow-your-
  search variant (REQ-INVOICE-009, truncated) — no separate formatter
  function needed for this, unlike the over-cap case, since both variants
  share the same itemized-block rendering, just with a different opening
  line and an optional closing note.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/038-morning-long-list-support/
├── spec.md            # done — Terminology Glossary, Clarifications (2026-08-04), Requirements, Edge Cases
├── user-stories.md    # done — US1 (P1), US2 (P2), Given-When-Then
├── research.md         # done — Phase 0: pagination-shape probe, status-filter/cap ordering, has_more removal
├── plan.md             # this file
├── data-model.md       # Phase 1 — no new entities (Invoice model unchanged)
├── contracts/           # Phase 1 — list_invoices tool contract (input unchanged; documents output-shape addendum)
├── quickstart.md        # Phase 1 — manual verification steps against the real sandbox
└── tasks.md             # Phase 2 output — /speckit.tasks, not produced by this command
```

### Source Code

```text
apps/morning-mcp-app/
├── requirements.txt                                                  (tiktoken>=0.5.0 added)
├── config/config.schema.json, config.example.json                    (list_invoices_token_budget added, default 2500)
├── src/denidin_mcp_morning/
│   ├── config.py                                                     (MorningMCPConfig.list_invoices_token_budget added)
│   ├── server.py                                                     (create_server threads config value into list_invoices)
│   ├── tools.py
│   │   ├── _LIST_INVOICES_MAX_ITEMS = 10 → 100                       (constant change)
│   │   ├── _LIST_INVOICES_TOKEN_BUDGET = 2500 (Python-level default, matches config default)
│   │   └── list_invoices(..., token_budget=_LIST_INVOICES_TOKEN_BUDGET)  (rewritten: fetch loop + cap branch + token-budget truncation)
│   └── formatters.py
│       ├── format_invoice_list(invoices, has_more=False)
│       │     → format_invoice_list(invoices, total_matched)           (has_more removed, shown/total-aware count line added)
│       └── format_too_many_invoices_message(total)                    (new, mirrors format_too_many_clients_message)
└── tests/
    ├── unit/
    │   ├── test_formatters.py                        # updated: count-line cases, format_too_many_invoices_message
    │   └── test_tools_list_invoices.py (new)          # fetch-loop cap boundary + token-budget boundary, fake-client fixtures
    └── integration/test_morning_sandbox_list_invoices_tool.py
        ├── test_list_invoices_tool_caps_results_at_ten_items      (DELETED — human-approved, T011, see Constitution Check)
        ├── (new) US1 real test: fromDate=2026-07-19/toDate=2026-07-21 (81 real invoices,
        │     research.md Decision 4) — asserts the tool's internally-known total is accurate (81),
        │     proving the fetch itself is complete regardless of display truncation
        └── (new) US2 real test: fromDate=2026-07-13/toDate=2026-07-15 (103 real invoices,
              research.md Decision 4) — asserts refusal message with real total, no itemized content

apps/denidin-app/tests/billed/
├── test_denidin_morning_mcp_e2e.py (SPLIT — see below, human-approved per user direction)
├── test_denidin_morning_invoice_creation_e2e.py (new)        # create_invoice approval flow + add_client (former lines ~404-729)
├── test_denidin_morning_client_management_e2e.py (new)       # list/get/update_client + fuzzy matching + RBAC denial (former ~730-1265)
├── test_denidin_morning_list_invoices_e2e.py (new)           # list_invoices + analytical questions + bugfix-013/014 (former ~1266-1630)
│   ├── (existing, moved verbatim) test_godfather_lists_invoices_via_whatsapp, analytical-question tests,
│   │     bugfix-013 client-name-garbling tests, bugfix-014 all-payments tests
│   ├── (new) test_godfather_asks_for_large_in_cap_invoice_range: 81-item real range — asserts the
│   │     model states the accurate real total (81) even though most are truncated from display
│   ├── (new) test_godfather_asks_for_over_cap_invoice_range: 103-item real range — asserts the
│   │     model relays the refusal/narrow-search message, no fabricated itemized list
│   └── (new) test_godfather_receives_partial_list_within_token_budget: 13-item real range —
│         asserts the model states a genuine partial "showing 2 of 13" (or equivalent), not an
│         invented count — the direct test of the user's original model-imprecision concern
└── test_denidin_morning_invoice_lifecycle_e2e.py (new)       # get_invoice_details + mark-paid/cancel + transaction accounts (former ~1631-2094)

(a shared conftest.py/helpers module carries forward whatever fixtures/helpers the original file
defined inline that more than one of the 4 new files needs — exact extraction finalized during
T014, see tasks.md)
```

**Structure Decision**: Production changes stay inside `apps/morning-mcp-app`
(the MCP tool's name, registration, and input contract are unchanged,
REQ-INVOICE-005). `apps/denidin-app` gets three new **test-only** additions
(no production code changes there) to verify the fix end-to-end through the
real Responses API/MCP round-trip, landing in a new file created by fully
splitting the pre-existing 2094-line billed test file by topic — both per
explicit user direction ("this is denidin functionality, not morning" for
where the tests belong; "full split by section" for the file
reorganization). These tests call the already-unchanged MCP tool through
the real API surface, so nothing about the tool's registration/contract
needs to change for `denidin-app` to exercise it this way.

## Phased Execution

### Phase 0 — Research (complete, see research.md)
Live sandbox probe of `/documents/search` pagination shape; status-filter/cap
ordering decision; `has_more` removal decision; real sandbox fixture-range
search (Decision 4); token-budget measurement (Decision 5), a mistaken
permanent-lowering revision (Decision 6), and its correction to a real,
config-driven 2500 default (Decision 7). **Checkpoint**: all seven decisions
resolved, no unknowns block Phase 1 design.

### Phase 1 — Design (this plan + data-model.md + contracts/ + quickstart.md)
Integration Contracts above define the exact fetch-loop and formatter
behavior. **Checkpoint**: plan reviewed, ready for `/speckit.tasks`.

### Phase 2 — Task Generation (tasks.md, `/speckit.tasks`)
Split into Task A (tests, including the one flagged deletion) / Task B
(implementation), per METHODOLOGY §VI. **Checkpoint**: tasks.md approved.

### Phase 3 — TDD Implementation (apps/morning-mcp-app)
1. **RED**: write/update all tests in `tests/unit/` and
   `tests/integration/test_morning_sandbox_list_invoices_tool.py`; confirm
   they fail against current code (human approval gate before this step,
   per METHODOLOGY §VI Step 1-2).
2. **Human approval gate — tests** (§VI Step 3-4), including explicit
   sign-off on the one existing-test deletion (§VIII).
3. **GREEN**: implement `list_invoices`, `format_invoice_list`,
   `format_too_many_invoices_message`, `_LIST_INVOICES_MAX_ITEMS`/
   `_LIST_INVOICES_TOKEN_BUDGET` constants; run tests until green.
4. **REFACTOR**: clean up while keeping tests green.
**Checkpoint**: full `apps/morning-mcp-app` test suite passes (unit +
integration, excluding billed/expensive which are unaffected by this
feature).

### Phase 4 — Billed E2E split + new tests (apps/denidin-app)
1. Split `test_denidin_morning_mcp_e2e.py` into the 4 files listed in
   Project Structure, moving existing tests verbatim (no logic changes —
   pure reorganization, human-approved as part of the test-plan gate since
   it touches existing, already-approved test files).
2. **RED**: write the 3 new billed tests against the finished Phase 3
   implementation (these are confirmatory E2E tests of already-implemented
   behavior, not TDD-driving tests — they should pass once written, given
   Phase 3 is complete first).
3. Run the split + new tests (billed tier — no per-run approval needed,
   CLAUDE.md/CONSTITUTION §VII) and confirm all pass.
**Checkpoint**: `apps/denidin-app`'s billed suite, across all 4 split
files, passes in full.

### Phase 5 — Close out
Move spec folder to `specs/done/` per Folder Movement Rules once merged
(handled at `/haleluya` time, not part of this plan).

## Complexity Tracking

No Constitution Check violations requiring justification — this feature
ports an already-proven pattern (`list_clients`) to a sibling tool, changes
one constant, and adds one small formatter function. No new dependencies,
no new infrastructure, no new abstractions beyond what the existing
`list_clients` precedent already established.
