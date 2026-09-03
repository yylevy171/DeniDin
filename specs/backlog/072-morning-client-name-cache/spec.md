# Feature Spec: Morning Client-Name Cache

**Feature ID**: 072-morning-client-name-cache
**Priority**: TBD
**Status**: Draft (definition-only — no `speckit.clarify`/`plan`/`user-stories`/`tasks` yet)
**Created**: 2026-09-01

---

## Origin

Split out of **Feature 069**
(`specs/in-progress/069-mandatory-client-resolution-before-ledger-event/`) on 2026-09-01,
user direction:

> "I dont even understand the question of how a client can have an exact match before
> calling morning (unless some cache implementation. Actually - add a feature spec 72 for
> caching morning client names)"

Feature 069 makes "the ledger event's `client_name` exactly matches a client in Morning"
a precondition for persisting a `הסכם` / `בנק` / `חשבונית` ledger event. To know whether a
name is an exact match, the model must call `resolve_client_name` (a no-approval Morning
MCP read tool) against the live Morning account. Feature 069 accepts one such call per
recognized event, cached only for the lifetime of a single conversation. This feature is
the durable optimization: a cross-conversation cache of Morning client names so a
known-good name doesn't incur a tunnel round-trip every time.

## Problem Statement

Every ledger-event client resolution (Feature 069), and every Morning-document-creation
client resolution (existing "Resolving a client by name" flow), currently reaches Morning
over the ngrok tunnel via `resolve_client_name` / `list_clients`. For a small, slowly
changing client roster this is:

- **Repeated work** — the same handful of names resolved again and again.
- **Tunnel-dependent** — if the Morning MCP tunnel is down, resolution cannot complete at
  all (Feature 069 FR-069, CONSTITUTION §XVIII: no silent degraded write), even for a
  client DeniDin has successfully resolved a hundred times before.
- **Latency** on the common path — an exact match still costs a network hop.

## Proposed Direction (for `speckit.clarify` / `plan`)

A local cache of Morning client identities (name + Morning client id + email/phone as
known), populated from every successful `resolve_client_name` / `list_clients` /
`add_client` result, consulted first on any resolution:

- **Exact-match fast path** — a name that exactly matches a cached entry resolves with no
  Morning call.
- **Staleness / invalidation** — TTL, or an explicit refresh, or invalidate-on-`add_client`;
  decide the model. A cache miss always falls back to a live Morning call.
- **Not a source of truth** — Morning stays authoritative; the cache is a read-through
  accelerator, never the place a name is "created."
- **Shared or per-environment** — dev and prod have separate Morning accounts (2026-08-03
  asymmetry), so the cache is per-environment, same discipline as `shared/mcp-status-<env>/`.

## Scope Notes

- Benefits **both** Feature 069 ledger resolution **and** the existing Morning-doc-creation
  resolution flow — the mechanism is the same `resolve_client_name` call.
- Feature 069 ships **without** this — one `resolve_client_name` call per recognized event,
  conversation-scoped caching only. 072 removes that per-event cost.
- **NEW motivation (2026-09-03, from Feature 069 design review — the user referred to this
  as "feature 74"; same feature, kept as 072):** Feature 069's post-turn recognition call
  determines "client is resolved" **only** from Morning tool evidence in its 1-hour context
  window (a `resolve_client_name` exact match / `add_client` / `create_*` success). If the
  conversational model never calls `resolve_client_name` (it's confident it knows the
  client, or resolved them more than an hour earlier), the recognition call sees no
  evidence → returns `none` → **the `הסכם` / `בנק` event is silently never recorded.**
  Feature 069 accepts this hole (decision: strict MCP-evidence-only, plus a relentless
  constitution rule that every `הסכם`/`בנק` requires an explicit `resolve_client_name`
  call). A durable clients cache **closes the hole**: the recognition call (zero-AI-tunnel,
  text-only) can consult the cache directly to confirm a stated name is an exact known
  Morning client, with no conversational tool call and no live tunnel hop required. This
  makes "the recognition step can read the cache" an explicit capability of this feature,
  not just "the conversational model's resolution is faster."
- Interaction with the Morning-tunnel-down edge case: with a cache, a previously-seen
  client could still resolve while the tunnel is down. Whether Feature 069's "capture
  nothing if resolution can't complete" rule should relax for a cache hit is an open
  question for this feature, not 069.

## Open Questions (for `speckit.clarify`)

- Cache store: SQLite (like `reminders.db`), a JSON file, or in-memory only (rebuilt per
  process start from a `list_clients` sweep)?
- Invalidation strategy — TTL vs. event-driven vs. manual refresh vs. combination.
- Does a cache hit satisfy Feature 069's resolution precondition on its own, or is a
  periodic reconciliation against live Morning required to trust it?
- Should `add_client` write-through immediately, and should a rename in Morning (done
  outside DeniDin) ever be detected?
- **Does the Feature 069 recognition call get direct read access to the cache** (a plain
  in-process lookup, no tool call), or does it stay strictly evidence-from-the-window and
  only the *conversational* model's resolution benefits? The former is what closes 069's
  silent-loss hole; it also means the recognition call trusts the cache as a resolution
  authority, which raises the reconciliation-trust question above.

---

## References

- Feature 069 — `specs/in-progress/069-mandatory-client-resolution-before-ledger-event/`
  (the immediate consumer; ships without this optimization)
- `config/runtime_constitution.md` — "Resolving a client by name"
- `apps/morning-mcp-app` — `resolve_client_name`, `list_clients`, `add_client` MCP tools
