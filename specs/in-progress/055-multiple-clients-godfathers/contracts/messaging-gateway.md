# Integration Contracts: Messaging Gateway (Green API capability)

**Feature**: 055-multiple-clients-godfathers · Per METHODOLOGY.md §VII format.

**SUPERSEDED 2026-08-17**, discovered during `speckit.implement`: there is no separate
"gateway"/routing component. `WhatsAppHandler` never holds its own `bot` reference — every
reply goes through `notification.answer(...)`, and Green API's `Notification` object is
intrinsically tied to whichever `Bot` instance received it. Combined with the "one full stack
per tenant" design (`contracts/tenant-scoped-data-managers.md`), this means **outbound routing
is automatically correct by construction** — no dispatch table, no `tenant_id`-keyed lookup.
Each `Tenant` (see `src/models/tenant.py`) owns its own `Bot`, registers its own 9 message-type
handlers as bound methods on that bot's router, and runs its own listener thread — a complete,
self-contained messaging endpoint, not a client of a shared gateway. `DeniDin` (the App) just
calls `tenant.start()` for each configured tenant. Kept below for historical record, not the
implemented design.

---

---

### Messaging Gateway ↔ Core Conversation Pipeline Contract

**Messaging Gateway (new component, `messaging_provider` capability implementation for Green
API) MUST**:
- Hold credentials for, and run one concurrent listener/poller per, every tenant's Green API
  instance within a single shared process (`research.md` §1).
- Tag every inbound message with the `tenant_id` of the Green API instance it arrived on, before
  handing it to the core conversation pipeline — the pipeline itself never infers `tenant_id`
  from message content.
- Route an outbound send back out through the correct tenant's Green API instance, keyed by the
  `tenant_id` the core pipeline supplies with the send request.
- Never let one tenant's Green API instance failure (auth error, rate limit, disconnect) affect
  another tenant's listener — one listener's fault MUST NOT crash or block the shared process's
  other listeners.

**Core Conversation Pipeline PROVIDES**:
- A single entry point (exact function signature: `speckit.tasks` decision) accepting
  `(tenant_id, WhatsAppMessage)` — the existing `denidin.py` router handlers extend to require
  `tenant_id`, not remove/replace their existing per-message-type dispatch structure.
- Deterministic behavior when `tenant_id` is unresolvable (should not happen if the gateway
  contract above is honored, but the pipeline MUST fail loudly/log rather than silently
  processing under a wrong or default tenant).

**Core Conversation Pipeline EXPECTS**:
- `tenant_id` is always present and always correct on every message the gateway hands it — the
  pipeline does not re-validate which Green API instance a message "really" came from.
- Every downstream call the pipeline makes (`UserManager.get_user`, `SessionManager.get_session`,
  `MemoryManager.recall`, `ledger_event_manager` writes, `AIHandler` construction) receives this
  same `tenant_id` explicitly — never a global/thread-local (CONSTITUTION §XVII).

---

### Messaging Gateway ↔ Tenant Config Contract

**Messaging Gateway MUST**:
- Load every tenant's Green API credentials from that environment's tenant list at startup, and
  MUST support the gateway process being restarted to pick up a newly-onboarded tenant (no
  requirement for hot-add without restart — manual onboarding, per spec.md Assumptions, already
  implies a restart is acceptable).
- Treat a tenant missing from the messaging-provider capability's config as simply absent — no
  listener started for it, no error blocking the other tenants' listeners.

**Tenant Config PROVIDES**:
- One `green_api` credential set per tenant (`data-model.md`'s `Tenant.green_api`), keyed by
  `tenant_id`.

**Tenant Config EXPECTS**:
- Nothing from the gateway beyond read access — this is a one-directional read at startup, not a
  live subscription (config is static per-process-lifetime, consistent with "config is code").
