# Integration Contracts: Tenant-Scoped Data Managers

**Feature**: 055-multiple-clients-godfathers · Per METHODOLOGY.md §VII format.

**Rewritten 2026-08-17 (implementation discovery)**: the original version of this contract
assumed `SessionManager`/`MemoryManager`/`ledger_event_manager` methods would need a `tenant_id`
parameter threaded through every call. Reading the actual code during `speckit.implement`
showed this is unnecessary — `SessionManager`, `MemoryManager`, and `LedgerEventManager` are
already **constructor-scoped** (storage directory, and for `MemoryManager` the OpenAI client
too, are passed once at construction, not per call), and `AIHandler.__init__` already builds
exactly one of each from a single `config`/`ai_client`. The correct multi-tenant design is
**one full stack per tenant** — one `AIHandler` per tenant, each internally holding its own
`UserManager`/`SessionManager`/`MemoryManager`/`LedgerEventManager`/`GroupMembershipResolver`,
constructed from that tenant's own `Tenant` object — not per-call `tenant_id` threading. This
also **fully supersedes `contracts/group-resolution-tenant-scoping.md`** (finding G1): one
`GroupMembershipResolver` instance per tenant means its cache is isolated by construction, no
`(tenant_id, chat_id)` re-keying needed.

**REQ-PARITY-001, strengthened**: `SessionManager`, `MemoryManager`, `LedgerEventManager`,
`UserManager`, and `GroupMembershipResolver` need **zero internal code changes**. Any caller
that constructs one of these directly (including `tests/billed/`/`tests/expensive/`, untouched
during this implementation) is unaffected — not by a default-parameter fallback, but because
the classes themselves are literally unmodified.

---

### `TenantAIHandlerFactory` (new) ↔ `Tenant` Contract

**`TenantAIHandlerFactory.build(tenant: Tenant, base_config: AppConfiguration) -> AIHandler`
MUST**:
- Construct exactly one `AIHandler` for `tenant`, internally building its own
  `UserManager(godfather_phones=tenant.godfathers, admin_phones=tenant.admins, ...)`,
  `SessionManager(storage_dir=tenant.data_root / "sessions", ...)`,
  `MemoryManager(storage_dir=tenant.data_root / "memory", ai_client=<built from
  tenant.openai>, ...)`, `LedgerEventManager(storage_dir=tenant.data_root / "events")` — mirrors
  `AIHandler.__init__`'s existing single-tenant construction exactly, just sourcing values from
  `tenant` instead of a single global `config`.
- Reuse `base_config` only for values that are genuinely environment-wide, not per-tenant (e.g.
  `ai_embedding_model`, `feature_flags`) — never for anything `Tenant` itself provides.
- Not mutate or replace any *existing* single-tenant construction path (`AIHandler.__init__`,
  `denidin.py`'s `initialize_app`) — this factory is additive, called once per tenant from a new
  multi-tenant bootstrap path.

**`Tenant` PROVIDES** (already implemented, `src/models/tenant.py`): `data_root` (derived
`Path`), `openai`/`green_api` credentials, `godfathers`/`admins`, `capability_selection`.

---

### Messaging Gateway ↔ Per-Tenant `AIHandler` Registry Contract

**Messaging Gateway MUST**:
- Hold a `Dict[tenant_id, AIHandler]` (built via `TenantAIHandlerFactory`, one entry per active
  tenant) and route each inbound message to the matching tenant's `AIHandler` — never a shared
  `AIHandler` instance handling more than one tenant.
- For the migrated ("tenant #1") case specifically: the existing single-tenant `initialize_app`
  path continues to work completely unchanged for direct callers (tests, `__main__`) — the
  multi-tenant registry is a parallel bootstrap path, not a replacement, until
  `denidin.py`'s entry point itself is switched over (a later task, not Phase 3's concern).

**Per-Tenant `AIHandler` Registry EXPECTS**: nothing beyond what `AIHandler.__init__` already
requires today (a valid `ai_client`, a valid `config`-shaped object) — no new requirements
placed on `AIHandler` itself.

---

### `UserManager` — multi-godfather extension (the one real, necessary code change here)

Unlike the managers above, `UserManager` needs one small, additive, backward-compatible change
— today's `godfather_phone: Optional[str] = None` constructor parameter is genuinely singular
(a real limitation, not a multi-tenancy artifact), and REQ-ROLE-001 needs a tenant to support
*more than one* godfather.

**`UserManager.__init__` MUST**:
- Gain a new optional `godfather_phones: Optional[List[str]] = None` parameter, checked
  *in addition to* the existing singular `godfather_phone` (both may resolve `Role.GODFATHER`;
  the two are additive, not either/or).
- Existing callers passing only `godfather_phone` (a single string) — including
  `tests/billed/`/`tests/expensive/`, untouched — MUST see zero behavior change.
- Per-tenant construction (via `TenantAIHandlerFactory`) passes `tenant.godfathers` (already a
  list) as `godfather_phones`, leaving `godfather_phone` unset.
