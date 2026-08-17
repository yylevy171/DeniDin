# Integration Contracts: Tenant-Scoped RBAC

**Feature**: 055-multiple-clients-godfathers · Per METHODOLOGY.md §VII format.

Added during `speckit.analyze` remediation (finding G3) — the underlying work was already
covered by `tasks.md` T015/T018/T019, but METHODOLOGY §VII requires the contract itself to be
written down, not just implied by task descriptions.

---

### `UserManager` ↔ Tenant Config Contract

**Amended 2026-08-17 (REQ-PARITY-001)**: `tenant_id` is an *optional* parameter, defaulting to
the migrated tenant — not a newly-required argument. `tests/billed/`/`tests/expensive/`, not
touched during this implementation, keep calling `get_user(phone)` unchanged and get exactly
today's single-tenant resolution.

**`UserManager.get_user(phone, tenant_id=MIGRATED_TENANT_ID)` (extended signature — was
`get_user(phone)`) MUST**:
- Resolve role by consulting only the named tenant's `godfathers`/`admins` lists
  (`data-model.md`'s Tenant Identity table) — never fall back to another tenant's lists, never
  a global phone→role table.
- Return the same role-precedence result (`Role.ADMIN` > `Role.GODFATHER` > `Role.CLIENT` >
  `Role.BLOCKED`) as today's single-tenant logic, applied within that one tenant's lists.
- Treat a phone number absent from every list in a tenant as `Role.CLIENT` (today's existing
  default-fallback behavior, unchanged) — scoped to that tenant only; the same number may
  resolve differently in a different tenant (spec.md's "same phone number, different roles per
  tenant" decision).

**Tenant Config (via `TenantManager`) PROVIDES**:
- `godfathers`/`admins` phone-number lists per tenant, read-only from `UserManager`'s
  perspective (RBAC never writes back to tenant config — spec.md's "ylevy-only, via config
  files" decision, REQ-TENANT-004/005).

**Tenant Config EXPECTS**:
- `UserManager` never caches a resolved role across tenants — a lookup is always
  `(tenant_id, phone) → role`, never `phone → role` alone (this is the same class of risk
  `research.md` §2 flags for `GroupMembershipResolver`'s cache; `UserManager` must not
  reintroduce it).

---

### `denidin.py`/`AIHandler` ↔ `UserManager` Contract (extension of existing contract)

**Callers MUST**:
- Always supply the message's resolved `tenant_id` (from the Messaging Gateway's inbound
  tagging) alongside the phone/`user_phone` argument — the existing single-argument
  `get_user(phone)` call sites all gain this parameter; there is no valid "unscoped" RBAC
  lookup under this feature.

**`UserManager` PROVIDES** (extended, otherwise unchanged): token-limit/tool-attachment
resolution exactly as today, just computed from the tenant-scoped role above instead of a
global one.
