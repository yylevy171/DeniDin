# User Stories: Morning Long List Support

**Feature ID**: 038-morning-long-list-support
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I/§II (MANDATORY)

Every story traces a complete flow from the real external entry point (a
WhatsApp message from a godfather/admin) through routing/dispatch to the
response the user actually sees — not just an internal method call.

---

## User Story 1 - Complete results returned when within the fetch cap (Priority: P1)

A godfather/admin asks DeniDin (in Hebrew, over WhatsApp) for invoices
matching some filter (e.g. "invoices from July") whose real total in Morning
is at or under the fetch cap. Today, only the first Morning page (up to 10
raw items) is ever fetched, so results silently get dropped even though the
true total is well within a reasonable size to fetch and display in full —
this is the exact bug observed live in prod on 2026-08-04 (46 of 62 returned).

**Why this priority**: This is the actual production bug — the deployed
`list_invoices` tool loses financial data (missing invoices) that the user
has no way to detect except by manually cross-checking Green Invoice's
website, which already happened once.

**Independent Test — two complementary levels**:
1. *Fetch completeness* (unit level, deterministic): a small fake result
   set of 15-20 items (well under both the item cap and the token budget)
   proves the fetch loop retrieves every page and the count line states
   the true, complete count — no real-world text-size variance involved.
2. *Real-world confirmation* (integration/billed level): the real sandbox
   range `fromDate=2026-07-19`, `toDate=2026-07-21` (81 real invoices,
   confirmed live 2026-08-04, see `spec.md` Sandbox Fixture Ranges /
   `research.md` Decision 4) proves the fetch itself is complete — the
   tool must internally know the true total is 81 (not silently limited
   to one Morning page) — even though, per User Story 3, most of those 81
   won't fit in the *displayed* reply due to the token budget. The
   regression this closes is specifically that the true total is now
   always known and disclosed; old code never computed or revealed a real
   total at all.

**MCP Tool Dispatch Requirement**: `list_invoices` (already registered as an
MCP tool in `apps/morning-mcp-app/src/denidin_mcp_morning/server.py`, reached
by `apps/denidin-app`'s `AIHandler` via the Responses API remote-MCP
round-trip over the ngrok tunnel — RBAC-gated to godfather/admin) must, for a
single tool invocation, internally loop `MorningClient.list_invoices()`
across every Morning `/documents/search` page needed to retrieve the
complete raw result set whenever that set is within the fetch cap — not just
call it once for page 1. No change to the MCP tool's registration, name, or
input parameters is required; only the tool implementation's fetch behavior
changes.

**Acceptance Scenarios**:

1. **Given** a WhatsApp godfather sends a text message asking to list
   invoices for a date range that matches 23 *small, fake* invoices (unit
   test — small enough that the formatted total stays under the token
   budget, avoiding any interaction with User Story 3), **When** the AI
   handler dispatches the `list_invoices` MCP tool call for that query,
   **Then** the tool fetches every Morning page needed to retrieve all 23
   raw items, applies the existing local status filter, and returns a
   Hebrew reply whose first line states the exact count of matching
   invoices, followed by every matching invoice's details — none omitted.
   (For a real, larger, more verbose result set that does not fit the
   token budget, see User Story 3 — the two behaviors are complementary,
   not contradictory: fetch is always complete, display is truncated only
   when necessary.)
2. **Given** the same scenario, **When** the godfather reads the WhatsApp
   response, **Then** the count stated in the reply's first line matches the
   number of invoice blocks actually listed beneath it (no over/under count).
3. **Given** a query whose real Morning total is exactly at the fetch cap
   (100), **When** `list_invoices` is called, **Then** it still fetches and
   returns the complete set (the cap is a "fetch no further" boundary, not an
   exclusive one — see Requirements for the exact boundary rule).
4. **Given** a query that matches zero invoices, **When** `list_invoices` is
   called, **Then** the existing friendly "no results" Hebrew message is
   returned unchanged (regression: this path must not be affected by the
   pagination change).

---

## User Story 2 - Clear refusal (not silent truncation) when a query is too broad (Priority: P2)

A godfather/admin asks for a query so broad (e.g. "all invoices ever") that
Morning's real total exceeds the fetch cap. Today this would still silently
truncate to only 10 results with a vague "more results exist" note. Instead,
the tool must refuse to fetch further and clearly tell the user the real
total, asking them to narrow the search — consistent with how `list_clients`
(Feature 026) already handles this same class of problem.

**Why this priority**: Prevents both a runaway fetch (many sequential
Morning API pages in one WhatsApp turn) and a repeat of the exact silent-data-
loss bug from User Story 1 for queries too large even for the raised cap.
Lower priority than US1 because it's a safety/clarity improvement on an edge
case, not a fix to the actively-occurring data-loss bug.

**Independent Test**: Use a real, already-existing sandbox date range with
just over 100 matching invoices — `fromDate=2026-07-13`,
`toDate=2026-07-15` (103 real invoices, confirmed live 2026-08-04, see
`spec.md` Sandbox Fixture Ranges / `research.md` Decision 4) — call
`list_invoices` with that filter, and confirm the reply states the real
total (103) and asks the user to narrow the search — with no itemized
invoice list included.

**MCP Tool Dispatch Requirement**: Same tool (`list_invoices`), same
dispatch path as US1 — this story only changes what the tool does once it
reads a real total from Morning's first-page response that exceeds the cap.

**Acceptance Scenarios**:

1. **Given** a WhatsApp godfather sends a text message asking to list
   invoices for `2026-07-13` to `2026-07-15`, and Morning's real total for
   that query is 103, **When** `list_invoices` is called, **Then** it
   fetches only the first Morning page (to read the real total), fetches
   no further pages, and returns a Hebrew message stating "103" as the
   real total and asking the user to narrow by date range, client, or
   status.
2. **Given** the same scenario, **When** the godfather reads the WhatsApp
   response, **Then** no individual invoice details appear in that message
   (it is a refusal/narrow-your-search message, not a partial list).

---

## User Story 3 - Best-effort truncated reply when a complete, in-cap result is too long to send (Priority: P1)

A query's real total is within the item fetch cap (≤ 100, so the *fetch*
succeeds completely — User Story 1), but the formatted reply for that
complete result set would exceed the token budget
(`list_invoices_token_budget`, a `MorningMCPConfig` field, default **2500**
— research.md Decision 7) — the real, directly-observed practical
output-length limit for MCP tool call output, not a self-imposed margin
below it (correction, 2026-08-04: an earlier revision of this story
mistakenly lowered the *production* value to 800; the user corrected this
— 2500 is real and may need to increase later, and only a specific *test*
should ever use a lower value, via the config field's normal
dependency-injection path, never a permanent production change). Sending
an over-length reply risks the platform itself truncating it
unpredictably (potentially mid-item, corrupting the count line or cutting
off invoice detail mid-sentence) or degrading the calling model's
handling of it. Instead, `list_invoices` must proactively truncate to a
safe prefix and clearly say so.

**Why this priority**: Confirmed live to be a real, easily-triggered
scenario (not a rare edge case) — even a small, 13-real-invoice range
only shows 8 of 13 at the real 2500 default. Without this story, User
Story 1's fix (raising the fetch cap so `list_invoices` no longer
silently limits itself to Morning's first page) would trade one
silent-truncation bug for a different one at the message-length layer —
equally capable of producing confusing or corrupted output with no
explanation. P1 because it is a direct corollary of User Story 1:
shipping US1 without US3 would still leave the underlying "user can't
trust the reply is complete or honest about what's missing" problem
unresolved for any moderately large result.

**Independent Test — two complementary levels**:
1. *Deterministic boundary check* (unit level, `apps/morning-mcp-app`,
   free/local/no-network): hand-built fake invoice blocks whose token
   sizes are computed (not hardcoded) at test time, calling
   `tools.list_invoices(..., token_budget=<explicitly low value>)` — the
   ONE place in this entire feature that overrides the config default,
   per the user's direction that "testing harnesses can set configs as
   they like" for the one test that specifically needs to be cheap and
   deterministic. Verifies the accumulate-until-budget logic stops at the
   right item and the shown/total counts in the resulting message are
   correct.
2. *Real-world confirmation* (`billed` level, per user direction — real,
   OpenAI-driven E2E test, using the real unmodified 2500 default, no
   override): the real sandbox range `fromDate=2026-07-21`,
   `toDate=2026-07-22` (13 real invoices, each ~255-292 tokens formatted)
   — at the real 2500 default, 8 of 13 are shown (confirmed live, robust
   to the exact 100-150-token reserve chosen at implementation). This
   test lives in
   `apps/denidin-app/tests/billed/test_denidin_morning_list_invoices_e2e.py`
   (not a new `apps/morning-mcp-app`-owned billed test — explicitly the
   user's direction, since this is denidin conversational behavior being
   verified, even though the underlying fix lives in
   `apps/morning-mcp-app`) and confirms the *model's own WhatsApp reply*
   states a genuine partial "showing 8 of 13" (or equivalent) message, not
   an invented count.

**MCP Tool Dispatch Requirement**: Same tool, same dispatch path as US1/
US2 — this story only changes what `list_invoices` does with an
already-fully-fetched, in-cap result set immediately before returning it,
so it never issues additional Morning API calls beyond what US1 already
requires.

**Acceptance Scenarios**:

1. **Given** a query's real Morning total is 13 (the
   `2026-07-21`→`2026-07-22` range) and its complete formatted reply would
   exceed the real 2500-token budget, **When** `list_invoices` builds the
   reply, **Then** it includes only the largest prefix of invoice blocks
   that fits within the budget (confirmed live: 8 of 13), states both the
   shown count and the real total (13) in the reply, and appends a
   closing note that more results exist but were omitted because the
   reply would otherwise be too long, asking the user to narrow the
   search.
2. **Given** a query's complete formatted reply fits comfortably within
   the token budget (e.g. the small fake-item fixture from US1's unit
   test), **When** `list_invoices` builds the reply, **Then** no
   truncation occurs and the reply is identical to what US1 alone would
   produce — this story never changes behavior for a reply that already
   fits.
3. **Given** REQ-INVOICE-008 truncation occurs, **When** the godfather
   reads the WhatsApp response, **Then** the message never appears
   alongside the User Story 2 over-cap refusal message in the same reply
   — the two are mutually exclusive (over-cap never reaches formatting;
   token-budget truncation only applies to a result that already passed
   the item-count cap).
4. **Given** the 81-item range (`2026-07-19`→`2026-07-21`, User Story 1's
   real-world fixture) is heavily truncated by this budget (confirmed
   live: only a handful of 81 fit), **When** the godfather reads the
   WhatsApp response, **Then** the stated real total is still exactly 81
   — truncation never corrupts the underlying total-count communication,
   even under the most extreme real-data case found (spec.md SC-006).

---

## Edge Case Coverage (traced to acceptance scenarios above)

- Boundary at exactly the cap (100): US1 Scenario 3.
- Zero-match regression: US1 Scenario 4.
- Status filter narrows the *displayed* count below the raw Morning total
  used for the cap decision (e.g. raw total 40, but only 5 match
  `status=unpaid`): the cap decision is made against Morning's raw
  pre-status-filter total (same fetch-cost reasoning as `list_clients`,
  which has no local post-filter at all) — documented as an accepted
  trade-off in `spec.md` Edge Cases, not a new acceptance scenario, since it
  follows directly from US1's fetch-cap rule.
- Token-budget truncation with real, large data: US3 Scenario 1.
- Token-budget truncation never triggers for a reply that already fits:
  US3 Scenario 2.
- Token-budget truncation and over-cap refusal are mutually exclusive:
  US3 Scenario 3.
