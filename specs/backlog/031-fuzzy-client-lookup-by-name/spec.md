# Feature Spec: Fuzzy Client Lookup by Name

**Feature ID**: 031-fuzzy-client-lookup-by-name
**Priority**: P2
**Status**: Draft
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

## Open Questions (not yet clarified)

- **What does Morning's `/documents/search` `clientName` param actually do
  server-side?** Needs direct sandbox investigation (partial match already
  handled by Morning? exact only?) before deciding whether DeniDin needs to
  add anything at all. If Morning already does substring/fuzzy matching
  server-side, this may be mostly a documentation/model-prompting fix (making
  sure the model passes a bare name rather than over-qualifying it) rather
  than new code.
- **Is there a dedicated client-list/client-search Morning API endpoint**
  (separate from `/documents/search`), and does *that* endpoint's matching
  behavior differ from the invoice-search `clientName` filter? Morning's own
  UI likely has a client-picker with autocomplete — worth checking whether
  that's backed by a different, more fuzzy-friendly endpoint DeniDin isn't
  using yet (`MorningClient` currently only wraps document/invoice endpoints,
  per `apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py`).
- **If server-side matching is insufficient, where does client-side fuzzy
  matching live?** Options: (a) inside `list_invoices`' tool implementation,
  fetching a broader result set and fuzzy-filtering locally (e.g. a
  `rapidfuzz`-style ratio against `clientName`) before formatting; (b) a new
  dedicated `find_client`/`search_clients` MCP tool the model calls first to
  resolve an ambiguous name to a canonical one, then uses that in
  `list_invoices`/`create_invoice`/etc. (b) is more consistent with this
  project's existing tool-per-concern pattern (11 focused tools rather than
  overloading one).
- **Ambiguous match handling.** If a fuzzy match returns multiple plausible
  clients (e.g. two clients both containing "Cohen"), needs a defined
  behavior — likely surfacing the candidates back to the user for
  disambiguation rather than silently picking the top match, consistent with
  the project's "friendly, no silent guessing" error-message style.
- **Does this apply only to `list_invoices`, or also to `create_invoice`/
  `add_client`/other tools that take a `client_name`/`client` string?** A
  typo on `create_invoice` today likely just creates a new client record
  under the misspelled name (Morning's own dedup behavior, if any, is also
  unconfirmed) rather than matching an existing one — worth scoping whether
  this spec covers lookup-only (read paths) or also write-path
  name-resolution.

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
