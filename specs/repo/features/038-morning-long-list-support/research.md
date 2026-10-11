# Phase 0 Research: Morning Long List Support — Feature 038

**Feature**: 038-morning-long-list-support
**Date**: August 4, 2026

## Decision 1: Does `/documents/search` expose the same pagination shape as `/clients/search`?

**Question**: `list_clients`' real-pagination pattern (`tools.py:942-955`) reads
`total`/`page`/`pages`/`items` off `search_clients()`'s response. `list_invoices`
today never reads any of those fields from `MorningClient.list_invoices()`'s
response (`_extract_items`, `tools.py:375-381`, only reads `items`/`data`). Before
porting the pattern, confirm live whether `/documents/search` actually returns
the same pagination fields, and what the real page size is.

**Method**: Live sandbox probe (this app's own `config/config.test.json`
sandbox credentials — real API call, no mocking per CONSTITUTION §V),
`MorningClient.list_invoices(params={})` with no filters, inspecting the raw
response shape.

**Result** (confirmed live, 2026-08-04):

```text
keys: ['pageSize', 'page', 'total', 'from', 'to', 'pages', 'items', 'aggregations']
total = 2038
page = 1
pages = 82
items = 25   (i.e. pageSize = 25 items per page)
```

**Findings**:
- `/documents/search` returns the exact same `total`/`page`/`pages`/`items`
  field names as `/clients/search` — the `list_clients` pagination pattern
  ports directly, no field-name translation needed.
- Real page size is **25** items per page (`pageSize`), not the 10-item
  client-side cap this app currently imposes — i.e. today's code already
  discards 15 of the 25 items on page 1 alone, before even considering
  the missing-further-pages bug.
- This app's own real sandbox account already has **2038** real invoices
  (82 pages) — comfortably over the clarified fetch cap of 100. This means
  the "too many, ask user to narrow" path (US2) can be exercised with a
  real, already-existing, unfiltered `list_invoices(client=...)` call in an
  integration test — no need to seed >100 throwaway invoices to test that
  branch.
- Conversely, US1 (complete fetch within cap) still requires a **narrowing
  filter** (e.g. a unique `client_name` marker, as the existing tests
  already do) to get a real total in the "more than 10, at or under 100"
  range without depending on the sandbox's fluctuating unfiltered volume.

**Decision**: Port `list_clients`' pattern (`tools.py:942-955`) to
`list_invoices` unchanged in structure — read `total`/`page`/`pages` from
the first `client.list_invoices(params)` response, compare `total` against
the (raised) fetch cap, then either loop remaining pages or refuse.

## Decision 2: Where does the local status filter fit relative to the fetch-cap decision?

**Question**: `list_invoices` applies `_matches_status` client-side, after
fetching. `list_clients` has no equivalent second filter. Does the status
filter change where the cap-vs-total comparison should happen?

**Finding**: No — the fetch **cost** (how many Morning pages must be
requested) is determined entirely by the raw, pre-status-filter `total`,
since every raw page must be fetched and downloaded regardless of how many
of its items will later be discarded by the status filter. The status
filter only affects what's counted/displayed in the *final* reply, not
how many pages are fetched.

**Decision**: Compare `total` (raw, from Morning) against the fetch cap
first. If under cap, fetch all pages, *then* apply `_matches_status` to the
complete raw set, then count and format the (possibly smaller)
post-filter set. Documented as an accepted trade-off in `spec.md` Edge
Cases: a status-narrowed query can theoretically still be refused for
exceeding the raw-total cap.

## Decision 3: `format_invoice_list`'s `has_more` parameter

**Question**: Today `format_invoice_list(invoices, has_more)` appends a
generic "more results exist" note when `has_more` is true. Does this
still have a purpose after this feature?

**Finding**: No. Once `list_invoices` only ever calls
`format_invoice_list` on a *complete* fetched-and-filtered set (the
over-cap case now returns a dedicated refusal message instead, never
reaching this formatter), `has_more` can never legitimately be `True`
again from this call site — it would always be a stale/impossible
signal, not real information.

**Decision**: Remove the `has_more` parameter from `format_invoice_list`
entirely (it has exactly one caller, `list_invoices`) rather than keep a
parameter that can never again carry a real value — simpler than leaving
dead optionality behind. Add the new precomputed count line here as well
(REQ-INVOICE-004).

## Decision 4: Real sandbox date ranges for test fixtures (2026-08-04, user-directed)

**Question**: Rather than seeding new throwaway invoices, find real, already-
existing sandbox date ranges that naturally produce (a) a result set well
over the old 10-item cap but comfortably under the new 100-item cap
(≥80 items), and (b) a result set just over the new 100-item cap
(102-105 items) — both to be used as stable test fixtures, and re-probed if
the sandbox's data ever changes enough to invalidate them.

**Method**: Live sandbox probes (`MorningClient.list_invoices(params={"fromDate":..., "toDate":...})`,
reading `total` only, no full fetch) across 2026's months, then narrowed to
day-level ranges within July 2026 (the month with by far the most volume).

**Result** (confirmed live, 2026-08-04):

| Range (`fromDate` → `toDate`) | Real `total` | Use |
|---|---|---|
| `2026-07-19` → `2026-07-21` | **81** | ≥80-item fixture (US1 token-budget scenario, see Decision 5) |
| `2026-07-13` → `2026-07-15` | **103** | 102-105-item fixture (US2 over-cap scenario) |

Both ranges were re-verified stable at the point of writing (no other test
in this repo creates invoices dated in July 2026 — all existing seed-based
tests use `datetime.now(timezone.utc)` for their invoice dates, i.e.
August 2026 at the time of writing, so these historical July ranges are not
at risk of being mutated by other tests running concurrently or later).
**If a future full-suite run changes these totals** (e.g. sandbox data is
reset/reseeded), the fixture ranges must be re-probed with the same method
and this table updated — the exact bounds (81, 103) are a snapshot of real
data, not a guaranteed-permanent constant like `_LIST_INVOICES_MAX_ITEMS`.

**Decision**: Use `2026-07-19`→`2026-07-21` (81 real invoices) for the
in-cap/large-reply integration and billed tests, and `2026-07-13`→`2026-07-15`
(103 real invoices) for the over-cap refusal integration and billed tests —
no new invoices seeded for either scenario.

## Decision 5: Token-budget truncation (2026-08-04, user-directed)

**Question**: The user reports (from direct observation, not independently
re-derived here) that an MCP tool call's output is subject to an
approximately **2500-token** practical limit before the calling model's
context handling degrades ("output token limit"). An in-cap (≤100), fully-
fetched result set (US1) could still individually be large enough in
*formatted text* to approach or exceed this — does that actually happen
with real data, and if so, by how much?

**Method**: Fetched Decision 4's 81-item range (`2026-07-19`→`2026-07-21`)
in full, formatted every item with the existing (unchanged)
`format_invoice_confirmation`, and measured the resulting text with
`tiktoken`'s `o200k_base` encoding (same encoding already used elsewhere in
this monorepo for token accounting, per `apps/denidin-app/src/handlers/ai_handler.py`
— chosen here for consistency, not because Morning/MCP output size is known
to use this exact tokenizer).

**Result** (confirmed live, 2026-08-04):
- 81 formatted invoice blocks = **22,695 tokens** total (`o200k_base`).
- Average **~280 tokens per invoice block**.
- At a 2500-token budget, only the first **~8-9** of 81 items fit.

**Findings**: The token-budget problem is real and severe for this
fixture — nowhere close to a rare edge case. It is also **orthogonal** to
the item-count fetch cap (REQ-INVOICE-002): a query can be well under the
100-item cap (guaranteeing a *complete fetch*) and still need truncation
for *display*, because formatted text size scales with content (Hebrew
descriptions, client names), not just item count.

**Decision**: Add a second, independent truncation stage, applied only in
the within-cap (US1) success path, after the complete set is fetched and
status-filtered:
1. Build formatted invoice blocks one at a time, accumulating a running
   `tiktoken` (`o200k_base`) token count, reserving headroom for the count
   line and truncation note (budget applied to the *item blocks only*:
   token budget total minus a fixed reserve, e.g. 100-150 tokens, for that
   surrounding text — exact reserve value finalized during implementation,
   not hardcoded here; see Decision 6 for the final budget value, revised
   after test-plan review).
2. Stop adding blocks once the next one would exceed the reserved budget.
3. If any blocks were omitted this way, the reply's count line must
   distinguish "shown" from "real total matched" (not just restate the
   real total as if everything shown), and a closing note must state that
   more results exist and were omitted because the reply would otherwise
   be too long, asking the user to narrow the search — mirroring the
   over-cap (US2) refusal message's tone but framed as "shown a partial,
   best-effort list" rather than "showed nothing."
4. This is a NEW requirement, not previously in `spec.md` — added as
   REQ-INVOICE-008/009 (see `spec.md` update, 2026-08-04).

## Decision 6: Final token-budget value and test strategy (2026-08-04, user-directed revision)

**Question**: After reviewing the initial test plan (Decision 5's 2500-token
budget, tested via a plain `apps/morning-mcp-app`-level test against the
81-item fixture), the user asked for two changes: (1) the token-budget
behavior should be verified via a **billed** (real OpenAI) test, not just a
plain tool-level test, and (2) the budget used for that test should be
"much lower... like 200" so the test doesn't depend on a large 81-item
fixture. The user also explicitly said the new billed test belongs in
`apps/denidin-app`'s existing billed-test suite ("this is denidin
functionality, not morning"), not a new self-contained
`apps/morning-mcp-app`-owned billed test (morning-mcp-app already has one
such pattern, `tests/billed/test_openai_invokes_mcp_e2e.py`, that was
considered and explicitly rejected for this purpose).

**Constraint discovered**: `apps/denidin-app`'s billed E2E tests
(`test_denidin_morning_mcp_e2e.py` and siblings) run against the
already-running, shared `morning-mcp-app-dev` container reached over its
real ngrok tunnel (per that file's own docstring: "Assumes the test
environment is already up") — unlike morning-mcp-app's own
self-contained-server billed test, there is no way for a single test to
inject a custom, test-only token budget into that shared container without
either changing its live config (forbidden mid-run, and would affect real
usage) or exposing the budget as a new MCP tool parameter (rejected -
expands the tool's contract for no real user-facing benefit, REQ-INVOICE-005).

**Resolution**: rather than making the budget test-injectable, make it a
smaller **permanent production value** - both because a self-imposed
safety margin well under the user's observed ~2500-token platform ceiling
is good design on its own merits (leaves headroom for the platform's own
overhead, keeps WhatsApp replies more scannable), and because it makes
testing straightforward against small, real, already-existing sandbox
data with no injection mechanism needed at all.

**Method**: Measured real invoice block sizes for a small real range
(`fromDate=2026-07-21`, `toDate=2026-07-22`, 13 real invoices) and computed,
for several candidate budgets/reserves, how many blocks would be shown:

```text
sizes (tiktoken o200k_base): [270, 281, 267, 267, 279, 277, 279, 255, 269, 277, 273, 268, 274]
budget=700  reserve=100 -> shown=2 of 13
budget=700  reserve=150 -> shown=1 of 13
budget=800  reserve=100 -> shown=2 of 13
budget=800  reserve=150 -> shown=2 of 13
budget=900  reserve=100 -> shown=2 of 13
budget=900  reserve=150 -> shown=2 of 13
```

**Decision (SUPERSEDED - see Decision 7)**: `_LIST_INVOICES_TOKEN_BUDGET = 800`
was chosen here on the (mistaken) premise that the production value itself
should be permanently lowered. Decision 7 corrects this: the real
production budget stays 2500 (unchanged, may be raised later); only a
specific test overrides it.

## Decision 7: token budget is a config value, not a hardcoded constant - production stays 2500 (2026-08-04, user correction)

**Question**: Decision 6 permanently lowered the production truncation
threshold from 2500 to 800, on the premise that the ~2500-token figure was
just an informal observation worth second-guessing. The user corrected
this directly: **the real, observed practical output-token limit is 2500,
it has not changed, and it may need to increase later** as usage grows -
this is an external, real-world fact about the platform, not a number this
feature gets to redefine downward. Separately, the user's actual ask in
Decision 6 ("much lower... like 200... how else test the token limit")
was about keeping *one specific test* cheap, not about changing production
behavior at all.

**Resolution**:
1. **`_LIST_INVOICES_TOKEN_BUDGET` reverts to `2500`** as the real,
   unmodified production default - matching the observed platform ceiling,
   not an arbitrary self-imposed safety margin below it. If/when the real
   ceiling changes, this is a one-line config change, not a code change
   (see next point).
2. **The budget becomes a genuine config value**, per explicit user
   direction ("it's a config param and that's the only place it should
   live"): `MorningMCPConfig.list_invoices_token_budget` (default `2500`,
   `config/config.schema.json` documents it, `config/config.example.json`
   shows it), threaded through `server.py`'s `create_server` into
   `tools.list_invoices` via dependency injection - the same pattern
   already used for every other config-sourced value in this app (e.g.
   `api_key_id` -> `MorningClient(api_key_id=config.api_key_id)`).
   `tools.list_invoices` keeps a Python-level default
   (`token_budget: int = _LIST_INVOICES_TOKEN_BUDGET`) purely so direct
   calls (tests, `list_clients`-style ad hoc scripts) don't have to thread
   a full config object through - `_LIST_INVOICES_TOKEN_BUDGET` and
   `MorningMCPConfig`'s default are kept in sync at `2500`, but the config
   field is the authoritative source for the real, deployed server.
3. **"Testing harnesses can set configs as they like"**: `MorningMCPConfig`
   is a plain (frozen) dataclass - any test can construct its own instance
   or `dataclasses.replace()` an existing one with a different
   `list_invoices_token_budget`, no special override mechanism needed.
   Concretely, exactly ONE test in this feature actually needs a lowered
   value to stay cheap/deterministic:
   `tests/unit/test_tools_list_invoices.py::test_list_invoices_truncates_to_a_partial_prefix_within_token_budget`
   - a free, local, no-network unit test that passes an explicitly low
   `token_budget` (computed from real measured block sizes, not
   hardcoded) directly into `tools.list_invoices()`. No other test in this
   feature touches this parameter.
4. **Consequence for the 13-item real-sandbox fixture**: at the real,
   unmodified 2500 budget, the same 13-item range
   (`fromDate=2026-07-21`, `toDate=2026-07-22`) already produces a genuine
   partial prefix with no override needed - **shown = 8 of 13**, confirmed
   live and robust across the 100-150 token reserve range (recomputed with
   the same per-block sizes as Decision 6: cumulative sum of the first 8
   blocks is 2175 tokens, within budget-reserve for both 100 and 150;
   the 9th block's cumulative, 2444, exceeds both). The 3 billed E2E tests
   in `apps/denidin-app` (T009a/T010a/T015a, already written) needed **no
   changes** - they already asserted inequalities (`0 < shown < total`),
   never a hardcoded exact count, so they remain correct against the real
   2500 default.
5. **Consequence for the 81-item fixture**: also still produces heavy
   truncation at 2500 (item-block budget ~2350-2400 vs. ~280 tokens/block
   -> roughly 8-9 of 81 shown) - the "total stays accurate under heavy
   truncation" proof (spec.md SC-006) still holds, unchanged.
