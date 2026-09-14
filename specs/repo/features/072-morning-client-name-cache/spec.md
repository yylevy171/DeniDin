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
- **Latency** on the common path — an exact match still costs a network hop (creating a 3-5 second delay for the user).

## PM & Business Requirements
**Goal:** Deliver a noticeably faster chat experience by avoiding Morning API network calls for returning clients.
- **Minimum Hit Rate (KPI)**: The implementation MUST guarantee a minimum **85% cache hit rate** against the existing production logs. A 100% hit rate is unrealistic to maintain (new clients happen), and anything below 50% indicates a flawed syncing/caching implementation.
- **Engineering Autonomy**: The specific technical architecture (in-memory vs SQLite, TTL cron vs JIT updating, context-injected vs local tool swap) is left entirely to the engineering team, provided the 85% hit rate and the 3-5 second perceived latency savings are achieved.

## Proposed Direction & Architecture (Decided)

**Architecture Decision**: The cache will be implemented entirely within the `morning-mcp-app` as a **transparent cache**.
- The AI remains completely unaware of the cache. It calls `resolve_client_name` exactly as it does today.
- The MCP server intercepts the call, checks its local cache, and either returns the cached ID instantly or falls back to querying the Morning API.
- Implementation specifics (TTL, population, refresh rates) are left to engineering, provided the 85% hit rate KPI is met.

### Handling Stale Data (Cache Invalidation)
A critical risk of a transparent cache is returning a client ID that was recently deleted or deactivated in Morning. If the AI attempts to use a stale ID (e.g., calling `create_document` with a deleted ID), Morning will throw an error. 
- **Requirement**: The MCP tools that execute writes (like `create_document`) MUST gracefully handle "Invalid Client ID" errors from the Morning API by:
  1. Immediately evicting that specific client from the cache.
  2. Returning a clear error message to the AI (e.g., *"Error: The client ID is no longer valid or was deleted in Morning. The cache has been cleared. Please resolve the client name again."*). 
- This ensures the AI can auto-recover in the next turn without entering a broken loop.
- **Not a source of truth** — Morning stays authoritative; the cache is a read-through
  accelerator, never the place a name is "created."
- **Shared or per-environment** — dev and prod have separate Morning accounts (2026-08-03
  decision), cache partitioning must respect this.

## Alternative Architecture Research: "LLM Context Caching"
The CEO raised an alternative approach: What if we expose a `get_all_clients` MCP tool? The AI could call this tool once (e.g., in the morning or on session start), retrieve the entire list of clients and IDs, and effectively *cache the data in its own context window*.
- **The Theory**: By having the IDs in the prompt/context, the AI would *never* need to call a resolution tool, eliminating the tool-turn entirely (Zero-Turn resolution).
- **The Challenge**: Production environments have hundreds of clients. Injecting 500+ names and IDs into the context window for *every single message* might drastically increase LLM inference cost, inference latency (time-to-first-token), and network payload size, potentially offsetting the tool-call speed gains.
- **The Solution (Provider Context Caching)**: To avoid sending the massive payload on every turn, the engineering team must investigate utilizing the LLM provider's native **Context Caching API** (e.g., Gemini Context Caching). This allows DeniDin to send the massive list of clients to the LLM *once*, receive a tiny `cache_id`, and just pass that `cache_id` on subsequent turns.
- **Engineering Task**: Before finalizing the Transparent MCP Cache (Option A), the engineers MUST research and benchmark this "LLM Context Caching" approach using the provider's Context Caching API. They must prove whether managing an LLM cache is actually faster/cheaper in production than a 50ms MCP tool-call hop.

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
