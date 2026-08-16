# Research: Support Multiple Clients (Godfathers) — Multi-Tenancy

**Feature**: `055-multiple-clients-godfathers` · Phase 0 output of `speckit.plan`
**Purpose**: Resolve the architecture questions `spec.md`'s `speckit.clarify` pass deliberately
left open, per METHODOLOGY.md §IV Phase 0.

---

## 1. Hosting model

**Decision**: Shared, multi-tenant-native services. No container-per-tenant.

- **denidin-app**: one running process/container (per environment, see §3) serves every
  tenant. `SessionManager`/`MemoryManager`/`ledger_event_manager` data roots become
  `tenant_id`-partitioned on disk (`{data_root}/{tenant_id}/sessions|memory|events`) instead of
  one data root per process. `UserManager` RBAC resolution becomes tenant-scoped — a phone
  number's role is looked up within the tenant that owns the Green API instance the inbound
  message arrived on (see §2).
- **Messaging gateway (Green API capability)**: one shared service holds credentials for, and
  runs a concurrent listener/poller for, every tenant's Green API instance within a single
  process. Each inbound message is tagged with its `tenant_id` before entering the shared
  conversation pipeline. Outbound sends are routed back out through the correct tenant's Green
  API instance by `tenant_id`. Confirmed feasible at the expected scale directly by the user:
  "I can listen to hundreds of GreenAPI instances at once, no problem."
- **Invoicing capability (morning-mcp-app)**: one shared server, one shared ngrok tunnel (see
  §4) — not one per tenant.

**Rejected alternative — container-per-tenant** (the original recommendation this research
session opened with, explicitly rejected by the user): each tenant gets its own denidin-app +
morning-mcp-app container pair, generalizing today's per-environment Docker pattern.
- *Why rejected*: "I definitely don't want to maintain and monitor 2N containers and processes —
  that's not scalable." The isolation this buys is real but unnecessary — REQ-TENANT-001–003
  already mandate per-tenant *credential* isolation regardless of hosting model, and credential
  isolation doesn't require process isolation to achieve.
- *What was underweighted*: ops/monitoring burden scales linearly with tenant count under this
  model; the user has already reasoned through the alternative (shared listener process handling
  many tenants) and confirmed it's technically sound for at least the messaging and invoicing
  capabilities.

**Rejected alternative — fully split microservices per capability** (a stronger version the user
considered and set aside): SessionManager/AIHandler/MemoryManager each becoming their own
independently-scalable shared service, not bundled into one denidin-app process.
- *Why rejected (for now)*: the user's own answer selected the more conservative shape — one
  shared denidin-app process for the core pipeline, with only the external-integration
  capabilities (messaging, invoicing) built as separately-shared, multi-tenant-native services.
  Splitting the core pipeline further is a larger rewrite than the tenant-isolation problem
  requires today; nothing in this design blocks doing so later (the capability-interface pattern
  in §5 generalizes to it).

**Escape hatch, explicitly not built now**: a tenant that later needs genuine process-level
isolation (regulatory reasons, extreme scale) is not a first-class supported mode of this
feature. The capability/tenant-registry design (§5) doesn't preclude giving one tenant a
dedicated deployment later — it would just be a deliberate one-off decision at that time, not
something this feature needs to design for today.

## 2. Tenant identity & data partitioning

**Decision**: `tenant_id` (internal UUID, see spec.md Terminology Glossary) becomes the
partition key threaded through every request and data path in the shared services, in place of
the process/container boundary a container-per-tenant design would have relied on for
isolation.

- An inbound Green API webhook is already received on a specific tenant's Green API instance
  (the messaging gateway holds one listener per tenant's instance) — `tenant_id` is known the
  instant a message arrives, before any routing/RBAC/session logic runs.
- Every downstream call (`UserManager.get_user`, `SessionManager.get_session`,
  `MemoryManager.recall`, `ledger_event_manager` writes, `AIHandler`'s OpenAI call) takes
  `tenant_id` as an explicit parameter (dependency-injected/threaded through the call chain, not
  a global/thread-local) — consistent with CONSTITUTION §XVII's no-monkey-patching,
  no-implicit-global-state rule.
- **Risk flagged explicitly**: this is the one place a shared-process design has to get right
  that a container-per-tenant design would have gotten "for free" from OS-level process
  isolation. Any in-memory cache keyed by something that isn't already globally unique across
  tenants is a cross-tenant leak risk — e.g. `GroupMembershipResolver`'s existing `chat_id`-keyed
  cache MUST be re-keyed to `(tenant_id, chat_id)` once two tenants could theoretically produce
  the same raw Green API `chat_id` pattern. `speckit.tasks`/`speckit.implement` MUST audit every
  existing module-level/in-memory cache in `apps/denidin-app/src/` for this before this feature
  ships, not just the ones already known about.

## 3. Dev/prod × tenant

**Decision**: dev/prod stays exactly 2 environments total, unchanged from today. Tenant is a
data/config dimension *within* an environment, not a multiplier of environments.

- The dev environment's shared services can hold one or more tenant credential sets — in
  practice, at minimum a dedicated "dev tenant" slot used to test changes generically, plus
  optionally a real tenant's non-production credentials if that tenant needs isolated UAT.
- The prod environment's shared services hold every real, live tenant's credential set.
- A new tenant is onboarded by adding its config to the dev environment first (manual, per
  spec.md's Assumptions), verified there, then added to the prod environment's tenant list.
- `env_lock.sh`, `shared/active_env.json`, and the per-environment watchdogs (`watchdog.py`)
  need **no redesign** for a tenant axis — they already operate at the environment level, and
  that's still the only multiplying axis. This directly resolves the risk flagged during
  `speckit.clarify` ("this is a genuinely new axis... never designed around").

**Rejected alternative — dev+prod duplicated per tenant** (2N container-set pairs): superseded
by the hosting-model decision in §1 — once hosting is shared-services rather than
container-per-tenant, there is no longer a per-tenant container to duplicate across
environments in the first place.

## 4. Invoicing capability (Morning / morning-mcp-app) sharing

**Decision**: one shared morning-mcp-app server, one shared ngrok tunnel, per environment (2
total, matching §3) — not one per tenant.

- `BearerTokenMiddleware` (currently one shared secret per environment) extends to one bearer
  token per tenant. The token identifies which tenant's Morning credentials and audit trail
  (`audit.py`) apply to that call — auth and tenant-selection become the same mechanism, not two
  separate lookups.
- Direct user rationale: "there can be a single mcp server with indeed different auth checks,
  but still a single server, and a single ngrok tunnel. This is since the mcp as a functionality
  truly is common for all." The MCP tool surface (`create_invoice`, `list_invoices`, etc.) is
  identical logic for every tenant; only the Morning account credentials and audit attribution
  differ per call.
- `apps/denidin-app`'s existing tunnel-discovery mechanism (`shared/mcp-status-<env>/`) needs no
  new per-tenant status file — one shared status file per environment still describes one
  running server/tunnel, matching §3's "2 environments total."

## 5. Capability abstraction & customization depth

**Decision**: capability implementations remain a DI-resolved interface + implementation
pattern (per spec.md REQ-CAP-001–004), now resolved **per-call by `tenant_id`** (a registry
lookup) rather than once per process at startup — the only mechanical change from the original
spec-level description, needed because one process now serves every tenant instead of one
process per tenant.

**Customization depth — working assumption, explicitly reversible** (per spec.md Assumptions):
config/data-only for now. This was the user's own stated uncertainty ("I'm not sure yet...
tempted to say [config-only] since it's easier, but it might end up as [tenant-specific code]").
The capability-interface pattern already accommodates that pivot without a redesign: a tenant
needing genuinely bespoke logic for one capability gets a one-off implementation class
registered and referenced only from that tenant's config entry — mechanically identical to how
a shared implementation (e.g. Green API) is already selected, just with an implementation used
by exactly one tenant. No new mechanism needs to be built now to keep this option open later.

## 6. Background thread policy

**Decision**: unify by default; only stay per-tenant where a distinct external connection makes
unification impossible.

- **`SessionCleanupThread` + startup cleanup recovery: unified**, single thread/pass iterating
  every tenant's data root in turn. Idempotent maintenance I/O, not latency-sensitive — N
  threads doing the same sweep independently adds thread-count overhead with no real benefit.
- **Messaging listeners: inherently per-tenant**, unchanged from §1 — each tenant holds its own
  live connection to its own Green API instance; there's no way to unify a connection that is,
  by definition, tenant-specific.
- **`watchdog.py`: stays process/environment-level only, unchanged.** Explicitly accepted gap:
  under the shared-process model, one tenant's messaging listener silently dying doesn't fail
  the container's own `/health` check or `active_envs` match, so the watchdog won't catch it —
  narrower blast radius than today's whole-process failures (only that one tenant loses
  connectivity, not everyone), but real. Closing this needs new machinery (a per-tenant
  liveness signal, surfaced somewhere the watchdog or an operator can see) — deliberately not
  built now; flagged as a named follow-up rather than silently accepted as "fine."

## Summary of decisions superseding `spec.md`'s deferred Clarifications

| Question | Decision | Where |
|---|---|---|
| Hosting model | Shared, multi-tenant-native services | §1 |
| Dev/prod × tenant | 2 environments total, unchanged; tenant is data within an environment | §3 |
| Invoicing capability sharing | One shared server + tunnel per environment, tenant via auth token | §4 |
| Customization depth | Config/data-only, reversible without redesign | §5 |
| Background thread policy | Unified where possible; messaging listeners inherently per-tenant; watchdog gap accepted | §6 |
