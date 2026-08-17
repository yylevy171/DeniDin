# Integration Contracts: Group Resolution Tenant Scoping

**Feature**: 055-multiple-clients-godfathers · Per METHODOLOGY.md §VII format.

**SUPERSEDED 2026-08-17** by `contracts/tenant-scoped-data-managers.md`'s "one full stack per
tenant" design, discovered during `speckit.implement`: `GroupMembershipResolver.resolve()`
does NOT need an extended `(tenant_id, chat_id)` signature or a runtime client lookup. One
`GroupMembershipResolver` instance per tenant (constructed with that tenant's own
`groups_client`, exactly like today's single-tenant `initialize_app`) means its cache is
isolated by construction — the `(tenant_id, chat_id)` re-keying this document originally
specified is unnecessary; a plain `chat_id`-keyed cache, unchanged, is already correct once
each tenant has its own resolver instance. Kept below for historical record, not the
implemented design.

---

Added during `speckit.analyze` remediation (finding G1): `GroupMembershipResolver`
(Feature 039) was constructor-injected with a single `groups_client` under the single-tenant
model. Under shared multi-tenant services (`research.md` §1), there are N tenants' Green API
clients — the resolver needs the *correct* tenant's client, not just a re-keyed cache
(`data-model.md`'s cache-collision fix alone does not address this).

---

### `denidin.py` ↔ `GroupMembershipResolver` Contract (tenant-scoping extension)

**`denidin.py` (`_resolve_group_user_phone`) MUST**:
- Pass the message's already-resolved `tenant_id` (available from the Messaging Gateway's
  inbound tagging, `contracts/messaging-gateway.md`) into `GroupMembershipResolver.resolve`,
  alongside the existing `chat_id` — never let the resolver guess or default which tenant's
  Green API instance to query.

**`GroupMembershipResolver` PROVIDES**:
- `resolve(tenant_id: str, chat_id: str) -> Optional[GroupResolution]` (signature extended
  from Feature 039's `resolve(chat_id)` — exact parameter order a `speckit.implement` decision,
  but `tenant_id` MUST be required, not optional/defaulted).
- Internally selects that tenant's own Green API `groups_client` (obtained via
  `Messaging Gateway`/`TenantManager`, not a single constructor-injected client as under the
  old single-tenant model) before calling `getGroupData`.
- Cache MUST be keyed `(tenant_id, chat_id)`, not `chat_id` alone (the collision-risk fix
  already specified in `data-model.md`/`research.md` §2) — this contract adds the *client
  selection* correctness on top of that cache-key fix; both are required, neither substitutes
  for the other.

**`GroupMembershipResolver` EXPECTS**:
- Exactly one Green API client available per tenant that has a `messaging_provider` configured
  (REQ-CAP-001) — a tenant with no messaging provider never reaches this path in the first
  place (no listener, no inbound messages, per REQ-CAP-005's "messaging provider required to
  start at all").
- `tenant_id` is always valid and already resolved by the time this is called (same
  expectation as every other tenant-scoped component per `research.md` §2).

---

### `Messaging Gateway` / `TenantManager` ↔ `GroupMembershipResolver` Contract (new)

**`Messaging Gateway`/`TenantManager` PROVIDES**:
- A lookup (`get_groups_client(tenant_id) -> GroupsClient`, or equivalent — exact shape a
  `speckit.implement` decision) returning the specific tenant's Green API groups client,
  mirroring how each tenant's messaging listener already holds its own client
  (`contracts/messaging-gateway.md`).

**`GroupMembershipResolver` MUST**:
- Call this lookup on every `resolve(tenant_id, chat_id)` invocation not already served by
  its per-`(tenant_id, chat_id)` cache — never cache or reuse a *client* across tenants, only
  cache the *resolution result*.
