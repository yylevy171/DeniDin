# Feature Spec: Morning Client-Name Cache

**Feature ID**: 072-morning-client-name-cache
**Priority**: TBD
**Status**: Clarified (`speckit.clarify` complete — ready for `speckit.plan`)
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

## Clarifications

### Session 2026-09-15

- Q: Cache store: SQLite (like `reminders.db`), a JSON file, or in-memory only (rebuilt per process start from a `list_clients` sweep)? → A: SQLite, matching `reminders.db`'s pattern — persists across restarts, queried directly.
- Q: Invalidation strategy — TTL vs. event-driven vs. manual refresh vs. combination? → A: Combination — event-driven write-through (on `add_client`/`create_*` success) and eviction (on "Invalid Client ID" errors) as the fast path, plus a periodic TTL sweep to catch out-of-band Morning changes (renames/deletes done outside DeniDin).
- Q: Does a cache hit satisfy Feature 069's resolution precondition on its own, or is a periodic reconciliation against live Morning required to trust it? → A: Yes — a cache hit alone is trusted as resolution, relying on the periodic TTL sweep to keep it reconciled with live Morning.
- Q: Does the Feature 069 recognition call (or any `denidin-app` code) get direct, in-process read access to the cache, bypassing the MCP tunnel? → A: **No.** `denidin-app` never calls Morning directly and never will — every resolution, cached or not, is a real `resolve_client_name` MCP tool call over the tunnel to `morning-mcp-app`. This feature is a **transparent cache inside `morning-mcp-app` only**; `denidin-app` code (including the Feature 069 recognition call) is out of scope and does not change at all. A cache hit still closes Feature 069's silent-loss hole (it's fast enough, and durable enough across conversations, that a stale/no-evidence recognition window is far less likely to occur) — but it does so by making the *existing* tool call cheap and reliable, never by adding a bypass path.

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

**Implementation note (found at `speckit.tasks`, 2026-09-15):** the write tools in this
codebase never actually consume a client id from `resolve_client_name` — they re-resolve
the client **by name, live against Morning** on every write call
(`_require_resolved_client`, bugfix-028), and `resolve_client_name` itself only ever
discloses a *name*, never an id (REQ-CLIENT-018). So the specific "Invalid Client ID HTTP
error" scenario below cannot occur in this codebase as written. The equivalent real
failure mode — a stale cached name that no longer matches any real Morning client — is
instead caught by that same existing live re-resolution failing, and the cache is evicted
there. See tasks.md's "Correction" note and contracts/cache-contract.md for exactly where
this is wired in. The **business requirement** below (auto-recover next turn, no broken
loop, clear message) is still met in full — only the specific mechanics differ from what's
literally written next.

A critical risk of a transparent cache is returning a client ID that was recently deleted or deactivated in Morning. If the AI attempts to use a stale ID (e.g., calling `create_document` with a deleted ID), Morning will throw an error. 
- **Requirement**: The MCP tools that execute writes (like `create_document`) MUST gracefully handle "Invalid Client ID" errors from the Morning API by:
  1. Immediately evicting that specific client from the cache.
  2. Returning a clear error message to the AI (e.g., *"Error: The client ID is no longer valid or was deleted in Morning. The cache has been cleared. Please resolve the client name again."*). 
- This ensures the AI can auto-recover in the next turn without entering a broken loop.
- **Not a source of truth** — Morning stays authoritative; the cache is a read-through
  accelerator, never the place a name is "created."
- **Shared or per-environment** — dev and prod have separate Morning accounts (2026-08-03
  decision), cache partitioning must respect this.

## Future Optimization Research: "LLM Context Caching Add-On"
While the **Transparent MCP Cache** is the core MVP architecture for this feature, the CEO has requested parallel research into an additional optimization layer: "LLM Context Caching". 
- **The Concept**: Expose a `get_all_clients` MCP tool that the AI can call at session start to inject the full client list into its context window, achieving a "Zero-Turn" resolution (the AI wouldn't even need to call `resolve_client_name` because it already knows the IDs).
- **The Challenge**: Injecting 500+ clients into a stateful Responses API thread raises complex questions around Cache Invalidation (how to update the AI's state when a new client is added mid-session) and Token TTL.
- **Engineering Research Task**: The engineers MUST research how other teams handle mutable state and dynamic dataset injection with OpenAI's Responses API & Prompt Caching. 
- **Not a Blocker**: This model-cache is an *add-on optimization*, not a replacement. The Transparent MCP Cache must be built and shipped regardless of this research outcome.

## Scope Notes

- **`denidin-app` is entirely out of scope for this feature (clarified 2026-09-15).**
  `denidin-app` never calls Morning directly — it only ever calls MCP tools over the
  tunnel — and this feature does not change that. Every change this feature makes lives
  inside `apps/morning-mcp-app`. Feature 069's recognition call, and every other
  `denidin-app` caller of `resolve_client_name`/`list_clients`, is unaware this cache
  exists and requires zero code changes; the cache is transparent by construction, not
  just by intent.
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
  call). **Clarified 2026-09-15: this feature does not close that hole via any special
  access path.** `denidin-app` never calls Morning directly, and this feature makes no
  change to `denidin-app` code at all — the recognition call still only sees evidence from
  actual `resolve_client_name` tool calls in its context window, exactly as Feature 069
  defined it. What this feature *does* do is make every such tool call fast and
  tunnel-independent (a transparent cache inside `morning-mcp-app`), which makes it more
  likely the conversational model actually places that call and that it succeeds — but the
  hole itself, and its fix, remain entirely Feature 069's concern.
- Interaction with the Morning-tunnel-down edge case: with a cache, a previously-seen
  client could still resolve while the tunnel is down. Whether Feature 069's "capture
  nothing if resolution can't complete" rule should relax for a cache hit is an open
  question for this feature, not 069.

## Open Questions (for `speckit.clarify`)

None remaining — the two sub-questions originally listed here ("should `add_client`
write-through immediately" and "should a rename in Morning ever be detected") are both
answered by the Q2 clarification above: `add_client` success write-throughs immediately
(event-driven fast path), and the periodic TTL sweep detects renames/deletes done outside
DeniDin.

---

## References

- Feature 069 — `specs/in-progress/069-mandatory-client-resolution-before-ledger-event/`
  (the immediate consumer; ships without this optimization)
- `config/runtime_constitution.md` — "Resolving a client by name"
- `apps/morning-mcp-app` — `resolve_client_name`, `list_clients`, `add_client` MCP tools
