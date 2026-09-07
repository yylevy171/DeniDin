# Feature Specification: Morning Long List Support

**Feature Branch**: `feature/038-morning-long-list-support`
**Feature ID**: 038-morning-long-list-support
**Priority**: P1
**Created**: August 4, 2026
**Status**: Done - Merged to master (PR #189)
**Input**: User description: "list_invoices silently truncates results beyond 10 items (single Morning page only); apply the real-pagination pattern list_clients already uses"

---

**MANDATORY REQUIREMENT MET**: See `user-stories.md` (this directory) for the
complete Given-When-Then user stories with MCP tool dispatch requirements,
per METHODOLOGY.md §I/§II.

**This spec complies with**:
- **CONSTITUTION.md** §I (no env vars, feature-flag discipline where
  applicable), §III (feature branch workflow), §V (integration tests are
  E2E / no mocking of internal components — the existing
  `tests/integration/test_morning_sandbox_list_invoices_tool.py` pattern),
  §VIII (test immutability — see Clarifications/Edge Cases for the one
  existing test this feature must change, with justification).
- **METHODOLOGY.md** §I (user stories mandatory), §II (template structure),
  §VIII (terminology glossary), §IX (technology choices), §X (requirement
  IDs).

---

## Origin

Observed live in prod (2026-08-04): a query for July invoices returned 46 of
62 actual documents, silently dropping the rest — the user caught the
discrepancy manually by cross-checking against the Green Invoice website.

## Terminology Glossary

- **`list_invoices`**: The MCP tool (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py:411`)
  that searches/lists invoices; registered in `server.py`, reached by
  `apps/denidin-app`'s `AIHandler` via the OpenAI Responses API remote-MCP
  tool attachment, RBAC-gated to godfather/admin roles.
- **Morning page**: One response from Morning's real `POST /documents/search`
  endpoint (wrapped by `MorningClient.list_invoices()`), which — like
  `POST /clients/search` — returns `items`/`total`/`page`/`pages` fields
  when the result set spans more than one page.
- **Raw total**: The `total` value Morning's first-page response reports for
  a given `fromDate`/`toDate`/`clientName` query — this reflects Morning's
  own server-side filters only; it does NOT account for this app's
  additional client-side `status` filter (see below).
- **Fetch cap** (`_LIST_INVOICES_MAX_ITEMS`, existing constant, value
  changes from 10 → 100 per this feature): the maximum raw total this app
  will fetch every page for. Above this, the tool refuses to fetch further
  and asks the user to narrow the search — mirroring `list_clients`'
  `_LIST_CLIENTS_MAX_ITEMS` pattern (`tools.py:908`).
- **Local status filter** (`_matches_status`, `tools.py:384`): applied
  client-side, after all raw pages are fetched, because Morning's
  server-side status filter param name is unconfirmed. This means the count
  of invoices actually returned to the user can be lower than the raw
  total the fetch-cap decision was made against.
- **`list_clients` pattern**: The existing real-pagination approach
  (`tools.py:913-958`, Feature 026) this feature ports to `list_invoices`:
  read the real total from page 1, then either fetch every remaining page
  (if under cap) or refuse and report the real total (if over cap) — never
  silently truncate.
- **Token budget** (new, 2026-08-04; corrected 2026-08-04, round 3 — see
  `research.md` Decision 7): a second, independent truncation dimension
  applied only within the in-cap success path, separate from the fetch
  cap. **`list_invoices_token_budget`** — a `MorningMCPConfig` field
  (default **2500**, matching the real practical MCP tool-call output
  limit the user observed in production — this is the real limit, not a
  self-imposed margin below it, and may need to be raised later),
  threaded from config through `server.py` into `tools.list_invoices` by
  dependency injection (`tools._LIST_INVOICES_TOKEN_BUDGET = 2500` is
  just the matching Python-level default for direct calls). Measured via
  `tiktoken`'s `o200k_base` encoding (chosen for consistency with
  `apps/denidin-app`'s existing token accounting, not because this exact
  encoding is confirmed to match OpenAI's own internal MCP-output limit
  measurement).

## Sandbox Fixture Ranges (2026-08-04)

Real, already-existing Morning sandbox date ranges used as test fixtures
(no new invoices seeded) — see `research.md` Decision 4 for probe
methodology and the stability rationale:

- **≥80-item, in-cap range**: `fromDate=2026-07-19`, `toDate=2026-07-21`
  → 81 real invoices (also a fixture that triggers heavy token-budget
  truncation at the real 2500 default: ~22,695 tokens formatted at full
  length, only a handful fit — used to confirm the reported total stays
  accurate even under heavy truncation).
- **Just-over-cap range**: `fromDate=2026-07-13`, `toDate=2026-07-15`
  → 103 real invoices.
- **Small range for a genuine partial-prefix demonstration**:
  `fromDate=2026-07-21`, `toDate=2026-07-22` → 13 real invoices, each
  ~255-292 tokens formatted (research.md Decision 6) — at the real,
  unmodified 2500 default, 8 of 13 are shown, robust to the exact implementation
  reserve chosen (100-150 tokens).

## Clarifications

### Session 2026-08-04

- Q: Should `list_invoices` still cap the number of results it will
  fetch/return in one reply, to avoid a huge WhatsApp message or blown
  token budget on something like "all invoices ever"? → A: Yes — raise the
  fetch cap to 100 (from today's 10), mirroring the `list_clients` pattern:
  fetch every page up to that cap, and if the real total exceeds it, tell
  the user the real total and ask them to narrow the search rather than
  fetching further or truncating silently.
- Q: Does the conversational layer (the AI model reading the tool's Hebrew
  reply) need its own summarization on top of the fully-fetched result set?
  → A: The user has observed the model being unreliable/imprecise at
  counting and summing values itself. Resolution: `list_invoices` will
  prepend a **precomputed, code-computed exact count line** ("נמצאו N
  חשבוניות:") to its reply, so the model relays a deterministic fact
  instead of inferring it from a long list. A monetary total was
  explicitly declined (see next item) — count only.
- Q: Should the precomputed summary line also include a monetary total
  (sum of matched invoices' amounts)? → A: No — count only, no total
  amount. (Rationale volunteered during clarification: summing amounts
  across mixed currencies/partial-payment/credit-note states could produce
  a misleading "total" figure; out of scope for this feature.)

### Session 2026-08-04 (test-plan review)

- Q (user rejected the initially-proposed billed tests, which would have
  seeded new throwaway invoices): should billed/integration tests seed new
  fixture data, or use real, already-existing sandbox data? → A: Use real
  data — search the sandbox for date ranges that already produce the
  needed volumes (≥80 items for the in-cap scenario; 102-105 for the
  just-over-cap scenario) rather than seeding new invoices. Resolved via a
  live sandbox probe — see `research.md` Decision 4 for the exact ranges
  found (81 items: `2026-07-19`→`2026-07-21`; 103 items:
  `2026-07-13`→`2026-07-15`).
- Q: The user additionally flagged that a large-but-in-cap result (≥80
  items) may cross an approximately 2500-token practical output limit on
  an MCP tool call — is this a real concern, and if so what should happen?
  → A: Confirmed real via live measurement (research.md Decision 5): 81
  real invoices format to ~22,695 tokens, ~280 tokens/item — a 2500-token
  budget would only fit ~8-9 items. **New requirement added**
  (REQ-INVOICE-008/009, below): when the fully-fetched, in-cap result
  set's formatted text would exceed the token budget, `list_invoices`
  MUST truncate to a best-effort prefix and tell the user more results
  exist but were omitted because the reply would otherwise be too long —
  never silently return an over-length reply, and never silently drop
  items without saying so (the same "never silently truncate" principle
  as REQ-INVOICE-001/003, applied to a second, independent truncation
  dimension: formatted-text size, not item count).

### Session 2026-08-04 (test-plan review, round 2)

- Q: Should the token-budget behavior (US3) be verified via a `billed`
  (real OpenAI) test rather than a plain tool-level test, and with a much
  lower budget so it doesn't need the large 81-item fixture? → A: Yes to
  billed; the exact budget was revised (see next item) rather than kept
  artificially low, because real invoice blocks here are uniformly
  ~255-292 tokens (live-measured, research.md Decision 6) — a 200-token
  budget would show **zero** items on any real data, not a genuine partial
  list. Resolution: lower the actual **production** token budget itself
  (from 2500 to **800** — see next item) rather than inject a test-only
  override, since that also makes testing trivial against small,
  already-existing real data with no injection mechanism needed.
- Q: Where should this billed test live — a new self-contained
  `apps/morning-mcp-app`-owned billed test (mirroring its existing
  `tests/billed/test_openai_invokes_mcp_e2e.py` pattern), or
  `apps/denidin-app`'s existing billed E2E suite? → A: `apps/denidin-app`
  — "this is denidin functionality, not morning." The
  `apps/morning-mcp-app`-owned pattern was considered (it would allow
  injecting a custom low budget into a private, test-owned server) but
  explicitly rejected in favor of testing the real, unmodified production
  budget against `apps/denidin-app`'s standard shared-dev-container billed
  E2E pattern instead.
- Q: Should `apps/denidin-app/tests/billed/test_denidin_morning_mcp_e2e.py`
  (2094 lines, ~40 tests) be split as part of adding these new tests? → A:
  Yes, fully, by section — see `tasks.md` Phase 6 for the resulting file
  layout. This feature's new tests land directly in the resulting
  `test_denidin_morning_list_invoices_e2e.py`.

### Session 2026-08-04 (test-plan review, round 3 — correction)

- Q: The round-2 resolution above permanently lowered the production
  budget to 800. The user corrected this directly: is 2500 an informal
  guess this feature gets to redefine, or a real, unchanged platform fact?
  → A: **Real and unchanged** — "the output tokens limit is 2500, and
  might actually need an increase the way things are moving." Production
  MUST stay at 2500 (research.md Decision 7 supersedes Decision 6's 800).
  Round 2's actual underlying ask ("lower it... so we don't burn tokens
  for nothing") was about keeping *one specific test* cheap, never about
  changing production behavior — a distinction lost in round 2's
  resolution.
- Q: How should "lower it only for one test" actually be implemented,
  given production must stay at the real 2500? → A: **The budget becomes
  a config value** (`MorningMCPConfig.list_invoices_token_budget`,
  default 2500), not a hardcoded Python constant — "it's a config param
  and that's the only place it should live." Per the user: "testing
  harnesses can set configs as they like, so the specific test that
  needs this lowered can do it for that specific test." Concretely: one
  free, local `apps/morning-mcp-app` unit test passes an explicitly low
  `token_budget` directly to `tools.list_invoices()` (the config value's
  DI endpoint); every other test, including all 3 billed E2E tests, uses
  the real, unmodified default. See research.md Decision 7 for the full
  resolution and REQ-INVOICE-008/010 below for the config-field
  requirement.

## User Stories Reference

**NOTE**: Complete user stories are defined in **`user-stories.md`** (this
directory). Summary:

- **US1 (P1)**: A query whose real Morning total is at or under the fetch
  cap (100) returns the *complete* matching set — the actively-occurring
  production data-loss bug.
- **US2 (P2)**: A query whose real Morning total exceeds the fetch cap
  returns a clear "too many results, narrow your search" message stating
  the real total — never a silent partial list.
- **US3 (P1, new 2026-08-04; corrected 2026-08-04, research.md Decision
  7)**: A complete, in-cap result set whose formatted reply would exceed
  the real, config-driven 2500-token production budget (the user's
  directly-observed platform ceiling — not a self-imposed margin below
  it) is truncated to a best-effort prefix, with an honest "showing X of
  Y, narrow your search" message — confirmed live to be common, not rare
  (even a small 13-item real range only shows 8).

### Edge Cases

- **Boundary at exactly the cap (100)**: treated as "fetch everything" (the
  refusal only triggers when raw total is *strictly greater* than the cap),
  matching `list_clients`' `if total > _LIST_CLIENTS_MAX_ITEMS` boundary
  exactly.
- **Zero matches**: unchanged — existing friendly "no results" Hebrew
  message (`format_invoice_list`'s empty-list branch).
- **Status filter narrows the displayed count below the raw total used for
  the cap decision**: e.g. raw total (date/client-filtered) is 40, but only
  5 of those have `status=unpaid`. The cap/refusal decision is made against
  the **raw** total (pre-status-filter), not the post-filter count, because
  that raw total is what determines how many Morning pages must be fetched
  — the same reasoning `list_clients` uses (it has no local post-filter at
  all, so its total and fetch cost are identical). Accepted trade-off: a
  query could theoretically be refused ("too many, narrow your search") even
  though the *final*, status-filtered result would have been small. This
  matches existing precedent and is not addressed further by this feature.
- **Morning API pagination fields missing/malformed** (`page`/`pages`
  absent or `None` in a page response): defaults to `page=1`/`pages=1`,
  identical fallback behavior to `list_clients` (`tools.py:950-951`) — no
  new handling needed, same code path is reused.
- **Token-budget truncation with a real, large in-cap result** (new,
  2026-08-04): confirmed live via the 81-item sandbox fixture (Sandbox
  Fixture Ranges, above) — this is not a hypothetical, it reproduces with
  real data on the first attempt. See REQ-INVOICE-008/009.
- **Token-budget truncation exactly at the boundary** (0 or 1 items over
  budget): not separately probed live (would require hand-crafting
  borderline data); covered by unit tests against the token-counting logic
  directly rather than a second live sandbox search.
- **Existing test change**: `tests/integration/test_morning_sandbox_list_invoices_tool.py::test_list_invoices_tool_caps_results_at_ten_items`
  currently asserts `result.count("חשבונית #") <= 10`. This assertion is
  **no longer valid** once the cap changes to 100 and full-pagination-within-
  cap becomes the intended behavior; per CONSTITUTION.md §VIII (Test
  Immutability), this existing test requires explicit human approval to
  change — flagged here for that approval during the TDD test-plan gate
  (see `tasks.md`), not changed silently.

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-INVOICE-001**: `list_invoices` MUST, for a query whose real Morning
  total (from the first `/documents/search` page response) is less than or
  equal to the fetch cap, loop through every remaining Morning page and
  return the complete raw result set — not just the first page — before
  applying local status filtering and formatting the reply.
- **REQ-INVOICE-002**: `list_invoices` MUST raise `_LIST_INVOICES_MAX_ITEMS`
  from `10` to `100`, repurposed from "max items returned" to "max raw
  items this tool will fetch pages for," matching `_LIST_CLIENTS_MAX_ITEMS`'s
  role for `list_clients`.
- **REQ-INVOICE-003**: `list_invoices` MUST NOT fetch any Morning page
  beyond the first when the real total exceeds the fetch cap. Instead it
  MUST return a Hebrew message stating the real total and asking the user
  to narrow the search (by date range, client name, or status) — no
  itemized invoice content in that message.
- **REQ-INVOICE-004**: The formatted success reply MUST begin with a
  precomputed, code-computed line stating the exact count of invoices
  being returned (post-status-filter, i.e. the actual number of invoice
  blocks that follow) — not a value inferred by the AI model reading the
  reply.
- **REQ-INVOICE-005**: The existing `status`/`from_date`/`to_date`/
  `client_name` filter parameters, the tool's registered MCP name, and its
  RBAC gating (godfather/admin only) MUST remain unchanged — this feature
  changes only the tool's internal fetch/format behavior, not its contract
  surface.
- **REQ-INVOICE-006**: The zero-match ("no results") reply path MUST remain
  behaviorally unchanged.
- **REQ-INVOICE-007**: Existing pagination-field defensive defaults
  (`page`/`pages` missing → default to `1`) MUST follow the same fallback
  logic already proven in `list_clients` — no new/different defaulting
  behavior introduced for `list_invoices`.
- **REQ-INVOICE-008** (new, 2026-08-04; corrected 2026-08-04, research.md
  Decision 7): After fetching the complete, status-filtered, in-cap
  result set, `list_invoices` MUST estimate the formatted reply's token
  size (`tiktoken`, `o200k_base`) and, if it would exceed the token
  budget (`list_invoices_token_budget`, config-driven, default **2500**
  — the real, unmodified practical limit, not a self-imposed margin below
  it — minus a reserved headroom of 100-150 tokens for the count line and
  truncation note, exact reserve finalized at implementation within that
  range), include only the largest prefix of invoices that fits, rather
  than returning an over-budget reply or silently dropping items with no
  explanation.
- **REQ-INVOICE-009** (new, 2026-08-04): When REQ-INVOICE-008 truncation
  occurs, the reply's count line MUST distinguish the number actually
  shown from the real total matched (e.g. "showing X of Y"), and a closing
  note MUST state that additional matching results exist but were omitted
  because the reply would otherwise be too long, asking the user to narrow
  the search for a complete view. This is mutually exclusive with the
  REQ-INVOICE-003 over-cap refusal — that path never reaches formatting at
  all, so the two truncation messages never appear together.
- **REQ-INVOICE-010** (new, 2026-08-04, research.md Decision 7): The
  token-budget value MUST be a `MorningMCPConfig` field
  (`list_invoices_token_budget`, default 2500, documented in
  `config/config.schema.json` and `config/config.example.json`), threaded
  into `tools.list_invoices` from `server.py` via dependency injection —
  NOT a hardcoded module constant with no config-driven path. Raising or
  lowering the real production value MUST be achievable as a config
  change alone, with no code change required.

### Key Entities

- **Invoice** (`apps/morning-mcp-app/src/denidin_mcp_morning/models.py`):
  unchanged by this feature — same Pydantic model, same fields, same
  validation. This feature changes only how many raw items are fetched and
  passed through `Invoice.model_validate()` before formatting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A real sandbox query matching more than 10 but at or under
  100 invoices returns every matching invoice in one `list_invoices` reply
  (verified by a real-sandbox integration test seeding >10 invoices and
  asserting all are present) — directly closes the production bug (46/62
  observed 2026-08-04).
- **SC-002**: A real sandbox query matching more than 100 invoices returns
  a refusal message stating the real total, with zero fetched pages beyond
  the first (verified in the real sandbox integration test by asserting the
  reply contains the real total and no itemized invoice content).
- **SC-003**: The count stated in the precomputed summary line always
  exactly equals the number of invoice detail blocks in the same reply
  (verified for both a small in-cap result and the zero-match case).
- **SC-004**: All existing `list_invoices`-related tests pass except the
  one explicitly identified as needing a human-approved rewrite (Edge
  Cases, above) — no unrelated regression in `create_invoice`,
  `get_invoice_details`, or other tools sharing `tools.py`.
- **SC-005** (new, 2026-08-04; corrected 2026-08-04, research.md
  Decision 7): A real sandbox query matching 13 invoices (Sandbox Fixture
  Ranges, above) returns a reply, at the real unmodified 2500-token
  budget, showing a genuine partial prefix (8 of 13), whose count line
  explicitly states both the shown count and the real total, with a
  closing note that more results were omitted for length — verified by
  both a unit test (deterministic token math against controlled fake
  data, using an explicitly-lowered `token_budget` — the one test in this
  feature that overrides the config default) and a real `billed` E2E test
  at the real default budget
  (`apps/denidin-app/tests/billed/test_denidin_morning_list_invoices_e2e.py`)
  confirming the model relays this shown/total distinction faithfully in
  its final WhatsApp reply.
- **SC-006** (new, 2026-08-04): The 81-item real sandbox query (which
  triggers heavy truncation — only a few of 81 shown) still reports an
  accurate real total (81) in its count line — proving truncation never
  corrupts the underlying total-count communication, even under the most
  extreme real-data case found.
