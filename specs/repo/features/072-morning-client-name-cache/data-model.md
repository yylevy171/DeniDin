# Phase 1 Data Model: Morning Client-Name Cache

## Store

`apps/morning-mcp-app/data/client_cache.db` — one file per environment (mounted via the
same per-clone `docker/docker-compose.{dev,prod}.local.yml` override pattern
`denidin-app`'s `dev_data`/`data` already use, so the cache is shared across clones the
same way session data is — a cold cache after every clone's own container restart would
otherwise tank the hit rate for whichever clone happens to run dev). SQLite, one table.

## Table: `clients`

**Revised 2026-09-15 (operator design review, post-implementation)**: the table stores
the FULL client record, not just name+id as originally scoped — see cache-contract.md's
revision note for why (zero extra Morning cost, and it's what makes `get_client_details`
genuinely cache-accelerated).

| Column | Type | Notes |
|---|---|---|
| `client_id` | TEXT PRIMARY KEY | Morning's own client id — the authoritative key. |
| `name` | TEXT NOT NULL | The exact name as stored in Morning (what `resolve_client_name` discloses verbatim — REQ-CLIENT-018 in `tools.py`, never the id). |
| `name_normalized` | TEXT NOT NULL | Bag-of-words, casefolded, geresh-normalized form of `name` (same normalization `_bag_equal_words`/`_normalize_hebrew_geresh` already apply) — the lookup key for an exact-match cache hit, so a hit is exactly as forgiving of word order/casing/apostrophe style as today's Step-0 exact match already is, no more and no less. Indexed. |
| `email` | TEXT, nullable | |
| `phone` | TEXT, nullable | |
| `tax_id` | TEXT, nullable | |
| `address` | TEXT, nullable | |
| `updated_at` | TEXT NOT NULL | ISO-8601 Israel-local timestamp (`now_local()`/`local_isoformat()`, per CONSTITUTION §II) of the last write-through or TTL-sweep confirmation for this row. |

Index: `CREATE INDEX idx_clients_name_normalized ON clients(name_normalized)` — **not
unique** (corrected 2026-09-15, found live against the real sandbox's accumulated test
data): Morning does not enforce unique client names, so two different real `client_id`s
can legitimately share the same stored `name`. `lookup_exact` treats more than one row
matching a normalized name as an ambiguous miss (falls through to live resolution) rather
than arbitrarily picking one — the same discipline `resolve_client_by_name`'s own Step 0
exact match already applies (exactly one candidate, or it isn't safe to treat as exact).

## Lifecycle / state transitions

- **Insert**: on `add_client` success (event-driven write-through, including the
  already-exists recovery path — see cache-contract.md), on a successful `update_client`,
  when a periodic TTL sweep (`fetch_all_clients`) discovers a client not yet cached, or
  whenever the cache-first shared gate (`_resolve_exact_client_name`) falls through to a
  live exact match on a miss (so the *next* lookup for that name is a hit, per User Story
  2).
- **Update**: the periodic TTL sweep upserts the full record for every `client_id` it
  finds — this is how a rename or detail change done in Morning's own UI is detected and
  corrected (Decision 3, research.md). `update_client` also upserts immediately on its own
  success, rather than waiting for the next sweep.
- **Delete**: a write tool that receives Morning's real "client doesn't exist" error
  (verified live 2026-09-15: HTTP 400, `errorCode: 2411`) at the actual document-creation
  call evicts that one `client_id` row immediately — see cache-contract.md's "one new
  failure mode" section for why this is where staleness surfaces now, not at the identify
  step. The periodic TTL sweep also deletes any cached `client_id` no longer present in
  Morning's live roster.
- No soft-delete / tombstone — a missing row is simply a cache miss, falling through to
  the existing live-Morning resolution path unchanged.

## Non-goals

- Not a source of truth (spec, "Proposed Direction & Architecture") — Morning's own client
  record is always authoritative; this table only ever mirrors it.
- No relationship to any other entity in this codebase (`LedgerEvent`, `Reminder`, etc.) —
  purely local to `apps/morning-mcp-app`, never read or written by `denidin-app`.
