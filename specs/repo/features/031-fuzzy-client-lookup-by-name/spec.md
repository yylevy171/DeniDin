# Feature Spec: Fuzzy Client Lookup by Name

**Feature ID**: 031-fuzzy-client-lookup-by-name
**Priority**: P2
**Status**: Done - Merged to master (PR #148)
**Created**: July 30, 2026

---

## Problem Statement

`list_invoices`' `client_name` filter (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py:404-442`,
`_map_list_invoices_filters` at line 347) passes the value straight through to
Morning's real `/documents/search` endpoint as a `clientName` query param —
there is no client-side matching logic today, and no test in
`tests/integration/` documents what match semantics the Morning API itself
applies server-side (exact string, prefix, substring, or none at all beyond
what its own UI's client-search/autocomplete field does). In practice, a
godfather asking about "Yossi" when the client is filed as "Yossi Cohen Ltd"
— or a slightly misspelled/transliterated Hebrew name — may get an empty
result even though the client exists, with no fallback.

**Goal**: support fuzzy/partial name lookup for clients, consistent with
whatever matching behavior Morning's own web UI exposes for its client field
(the user's framing: "based on what morning's list functionality allows, and
according to how the UI works there is something there") — i.e. investigate
before building a redundant client-side layer.

## Clarifications

### Session 2026-07-30

- Q: Should this spec cover write paths too (`create_invoice`'s
  `client_name` auto-resolve/create), or stay scoped to the read path
  (`list_invoices`) as originally framed? → A: Read-only, `list_invoices`
  only. `create_invoice`'s auto-create-on-new-name behavior is Morning's own
  intentional "try and fail" design, already confirmed acceptable for
  `add_client` by Feature 026 Decision 10 — not treated as a bug here.
- Q: Feature 026 (merged 2026-07-30, same day this spec was drafted) already
  confirmed Morning's dedicated `POST /clients/search` endpoint does real
  token-prefix matching (`_resolve_client_by_name`,
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py:848`), and a
  pre-existing prompt-level fix (`runtime_constitution.md:364-371`, added
  2026-07-24, predates this spec) already tells the model to treat
  `list_invoices`' `client_name` as fuzzy and cross-check with amount/date
  hints. Given that, what should this spec's core deliverable be? → A:
  Sandbox-test first, then decide. Add a real integration test against
  `/documents/search` with a partial/substring client name to finally
  confirm what Open Question 1 has left unconfirmed since this spec was
  written. If Morning already partial-matches server-side there, this spec
  may close with no code change — confirmed already-working behavior — as
  the outcome, rather than assuming new code is required up front.
- Q: If `list_invoices` ends up resolving `client_name` via
  `search_clients` and that resolves to multiple candidate clients (e.g.
  two clients both matching "Cohen"), what should it do? → A: Refuse and
  ask the user to disambiguate first — do not search across all matches.
  Consistent with `get_client_details`/`update_client`'s existing "never
  guess on an ambiguous match" rule (Feature 026, REQ-CLIENT-003/007), even
  though `list_invoices` itself is read-only/no-approval-required.

## Open Questions (resolved by Feature 026 / pre-existing constitution guidance)

- ~~Is there a dedicated client-list/client-search Morning API endpoint,
  separate from `/documents/search`?~~ **Resolved**: yes —
  `POST /clients/search`, wrapped as `MorningClient.search_clients`
  (`apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py:102`),
  confirmed live to be a token-prefix match (Feature 026).
- ~~Where does client-side fuzzy matching live — inside `list_invoices`, or
  a new dedicated find/search tool?~~ **Resolved**: option (b), a dedicated
  tool. Feature 026 built `list_clients`/`get_client_details` plus the
  shared `_resolve_client_by_name` helper (`tools.py:848`) — this spec's
  implementation phase reuses that infrastructure rather than building a
  new one.
- ~~Ambiguous match handling.~~ **Resolved** — see Clarifications above:
  surface candidates and ask, never guess or merge.
- ~~Does this apply only to `list_invoices`, or also to `create_invoice`/
  `add_client`?~~ **Resolved** — see Clarifications above: `list_invoices`
  only; write paths out of scope.

## Open Questions — resolved (2026-07-30, live sandbox investigation)

- **What does Morning's `/documents/search` `clientName` param actually do
  server-side?** **Resolved**: case-insensitive full-text substring
  matching across the whole client name (not prefix-only, not exact-only) —
  confirmed live against the real sandbox; see `research.md` Decision 1 for
  the probe methodology and results. This means **no code change to
  `list_invoices` is needed** — the only remaining work is a permanent
  regression test locking in this confirmed behavior. See `plan.md`.

## References

- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`list_invoices`,
  `_map_list_invoices_filters`, lines 347-442) — current pass-through filter
  logic.
- `apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py` — current
  set of wrapped Morning endpoints; a dedicated client-search endpoint, if one
  exists, would be added here.
- `apps/morning-mcp-app/tests/integration/test_morning_sandbox_*.py` — real
  sandbox tests that would need to confirm actual API matching behavior
  before any implementation (per this repo's zero-mocking policy for
  external services).
