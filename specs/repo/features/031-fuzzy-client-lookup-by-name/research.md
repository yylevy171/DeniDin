# Phase 0 Research: Fuzzy Client Lookup by Name (Feature 031)

## Decision 1: `/documents/search`'s `clientName` param — real server-side matching behavior (confirmed live, 2026-07-30)

- **Question**: the spec's sole remaining open question (Clarifications session
  2026-07-30) — does Morning's real `/documents/search` endpoint do partial/
  substring matching on `clientName`, or exact-string-only? No existing test
  covered this (`test_morning_sandbox_list_invoices_tool.py` only tests an
  exact-name match and a total-miss).
- **Method**: live sandbox investigation (read-only beyond one seed invoice,
  same pattern as the existing `seeded_invoice` fixture in
  `test_morning_sandbox_list_invoices_tool.py`) — created one real invoice for
  a unique four-word client name (`"Yossi Cohen DENIDIN_FUZZY_INVESTIGATION_
  <ts> Ltd"`), waited for the search index (9s, within the existing 18s
  window observed in `test_morning_sandbox_list_invoices_tool.py`), then
  queried `list_invoices` with six different substrings of that name.
- **Finding**: **all six probes matched** — first word ("Yossi"), a *middle*
  word that is not a prefix of the stored name ("Cohen"), the unique marker
  substring alone, a *suffix* word ("Ltd"), and a lowercase variant of the
  first word ("yossi") all found the seeded invoice. Combined with the
  pre-existing `test_list_invoices_tool_returns_readable_string_for_no_matches`
  test (an unrelated random string correctly finds nothing — this isn't a
  match-everything no-op), this confirms Morning's `/documents/search`
  `clientName` param does **case-insensitive full-text substring matching
  across the whole name**, not prefix-only and not exact-only. This is
  strictly *more* permissive than the token-**prefix** match Feature 026
  confirmed for the separate `POST /clients/search` endpoint (`clientName`
  here matches a substring anywhere in the name; `/clients/search`'s `name`
  param only matches from the start of a word).
- **Decision**: **no code change to `list_invoices`/`_map_list_invoices_filters`
  is needed.** The spec's own framing anticipated this outcome ("If Morning
  already does substring/fuzzy matching server-side, this may be mostly a
  documentation/model-prompting fix... rather than new code") — and the
  documentation/model-prompting fix already exists and predates this spec
  (`runtime_constitution.md:364-371`, added 2026-07-24, telling the model to
  treat `list_invoices`' `client_name` as fuzzy and cross-check with amount/
  date hints). That guidance was written without knowing Morning's server-side
  behavior was already this permissive — it's arguably *more* conservative
  than necessary (Morning itself handles substring matching; the model no
  longer needs to lean as hard on amount/date hints to compensate for exact-
  match misses), but loosening it is optional polish, not a correctness gap.
- **Scope-relevant**: this also independently confirms Clarification 2's
  premise (2026-07-30 session) — the "sandbox-test first, then decide"
  answer was the right call here, since it changed the deliverable from
  "likely needs new code" to "confirm and lock in with a regression test."

## Outstanding item for implementation phase

- None blocking. The only remaining work is adding a permanent regression
  test (mirrors `test_list_invoices_tool_finds_seeded_invoice_by_client_name`'s
  structure) that asserts a non-prefix substring match, so a future Morning
  API behavior change would be caught rather than silently assumed. This is
  a test-only addition — no production code changes to
  `apps/morning-mcp-app` or `apps/denidin-app` are required by this spec.
