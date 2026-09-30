# Phase 0 Research: Morning Client-Name Cache

## Decision 1: Where the cache intercepts

**Decision**: The cache is checked inside `resolve_client_name` (`tools.py`), as a fast
path *before* `resolve_client_by_name`'s Step 0 exact-match Morning call — not inside
`MorningClient.search_clients` (the raw HTTP layer) and not as a separate MCP tool.

**Rationale**: `resolve_client_by_name`'s full algorithm (word-prefix growth, Levenshtein
ordering) exists specifically for the *fuzzy/ambiguous* case, which by definition can't be
served from a name→id cache — the whole point of that algorithm is resolving a name the
caller does *not* already know exactly. The case worth caching is exactly the opposite: an
exact, previously-seen name, which is Step 0's fast path today (one Morning call). Caching
that specific fast path is what turns it into zero Morning calls, while the fuzzy fallback
(cache miss) is untouched and behaves byte-identically to today. This also keeps the
change small and contained to one call site, with no change to the resolution algorithm
itself, the tools consuming its output (`_require_resolved_client`), or any MCP tool
schema — `denidin-app` sees no difference at all (per the spec's clarified scope boundary).

**Alternatives considered**:
- Cache inside `MorningClient.search_clients`: rejected — would need to cache raw Morning
  API pages keyed by prefix, not resolved client identities; doesn't map to "known client
  name → id" at all, and would still leave `_grow_word`'s multi-call fuzzy path fully
  exercised for a name that's actually already exact.
- A new `get_all_clients`/context-injection tool (the spec's own "Future Optimization
  Research" section): explicitly out of scope for this feature — a parallel research track
  the spec calls out as an add-on, not a replacement, and not part of the MVP.

## Decision 2: Cache store — SQLite

**Decision**: A new SQLite database, `data/client_cache.db`, inside `morning-mcp-app`'s
own container, one file per environment (dev/prod have separate Morning accounts and
therefore separate caches — 2026-08-03 asymmetry decision applies here too).

**Rationale**: Matches `denidin-app`'s `reminders.db` precedent (a small, mutable, local
SQLite store) rather than the immutable-JSON-per-record pattern `ledger_event_manager.py`
uses (clients are mutable — renamed, deleted — and queried by exact key, not appended
append-only). In-memory-only was rejected because it loses the cache on every container
restart (this app restarts routinely — code changes, `run_morning_mcp.sh` rebuilds), which
would tank the hit rate right after every deploy. A plain JSON file was rejected for the
same reason SQLite already won that argument for `reminders.db`: no built-in
concurrency-safe partial update, and this project already has an established SQLite
pattern to follow instead of inventing a second one.

**Alternatives considered**: in-memory-only (rebuilt from `list_clients` on start) — loses
persistence across restarts; plain JSON file — no transactional partial writes.

## Decision 3: Invalidation — event-driven + periodic TTL sweep

**Decision**: Two mechanisms, combined:
1. **Event-driven, immediate**: on `add_client` success, write-through the new client
   into the cache immediately. On any write tool receiving Morning's "Invalid Client ID"
   error, evict that one client_id from the cache immediately (spec's existing "Handling
   Stale Data" requirement).
2. **Periodic TTL sweep**: a background refresh (interval config-driven, e.g. every N
   minutes) that calls `list_clients` and reconciles the full cache against Morning's
   current roster — catching renames/deletes made directly in Morning's own UI, which no
   in-app event can ever observe.

**Rationale**: Event-driven alone can't detect out-of-band Morning changes (a rename in
the Morning web UI generates no event this app ever sees). TTL-only forces every cache
entry to wait up to a full interval before becoming available, degrading the fast path
during that window and making the 85% hit-rate KPI harder to hold right after a restart.
The combination gets both: fast entries for changes DeniDin causes, periodic correction
for changes it doesn't.

## Decision 4: A cache hit is trusted as resolution on its own

**Decision**: `resolve_client_name` returning a cache-hit result is exactly equivalent, to
every caller, to a fresh Morning-confirmed exact match — no synchronous re-verification
against live Morning on a hit.

**Rationale**: Re-verifying every hit against Morning would defeat the entire purpose of
caching (the KPI is savings on the common path). Trust is instead earned structurally: the
periodic TTL sweep (Decision 3) keeps entries reconciled, and the write-tool eviction path
(Decision 3, point 1) catches the one case that actually matters operationally — a stale
id used in a real write — synchronously, at the moment it would otherwise cause harm.

## Decision 5: `denidin-app` is unaffected

**Decision**: This feature makes zero changes to `apps/denidin-app` code, config, or the
MCP tool contract. The cache is entirely internal to `apps/morning-mcp-app`; every
existing `resolve_client_name`/`list_clients`/`add_client` caller (including Feature 069's
post-turn recognition call) continues to work unmodified and unaware.

**Rationale**: Clarified explicitly by the operator during `speckit.clarify` — `denidin-app`
never calls Morning directly and this feature must not introduce an exception to that. See
spec.md's `## Clarifications` and the corrected `## Scope Notes` section.

## Decision 6: Feature flag

**Decision**: `config.feature_flags.morning_cache_enabled` (default `false`), matching the
existing `enable_mcp_server` flag's shape in `config/config.schema.json`. When `false`,
`resolve_client_name`'s code path is byte-for-byte identical to pre-feature behavior — no
cache lookup, no write-through, no background sweep started.

**Rationale**: CONSTITUTION.md §VI (Feature Flags for Safe Deployment) requires new
behavior to be flag-gated, default off, with the disabled path unchanged. This also gives
the Phase 1.a/1.b acceptance tests a clean on/off toggle to measure against, as approved.
