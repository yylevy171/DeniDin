# Feature Spec: Support Multiple Clients (Godfathers) — Multi-Tenancy

**Feature ID**: 055-multiple-clients-godfathers
**Priority**: TBD
**Status**: In progress — `speckit.specify` drafted 2026-08-16 from user clarification;
`speckit.clarify` completed 2026-08-16 (5 questions asked/answered). Not yet run through
`speckit.plan`.
**Created**: 2026-08-16

---

## Problem Statement

DeniDin today is architected as a single-tenant deployment: one Green API instance/WhatsApp
number, one Morning (Green Invoice) account, one `runtime_constitution.md`, one RBAC table
(`UserManager`), all shared globally. There is exactly one "business" behind any given running
instance of DeniDin.

The business goal is to operate DeniDin as a **white-label, multi-tenant product**: multiple
independent paying businesses ("tenants"), each fully isolated from every other tenant at the
application level — their own WhatsApp number/Green API instance, their own Morning account,
and (for now) their own OpenAI account — all served by one DeniDin deployment/codebase, rather
than one bespoke deployment per customer.

Within a tenant, the existing RBAC concepts mostly still apply — a tenant is run by one or more
**godfather**s, who interact with **client**s (WhatsApp numbers/entities) — but today's RBAC
model has no notion of a godfather or client belonging to a specific tenant, no notion of a
tenant at all, and no mechanism for a single operator (the platform owner) to retain
administrative oversight across every tenant at once.

Separately, but motivated by the same tenant-isolation need: DeniDin's integrations with
external services (Green API for messaging, Morning for invoicing) are not currently expressed
as swappable abstractions — each is called directly by name from application code. Supporting
per-tenant choice of provider (e.g. a future "ypay" as an alternative to Morning) requires first
defining these integrations as pluggable **capabilities** with a well-defined interface, so a
tenant's configuration can select an implementation per capability without core application code
changes.

This feature is the specify-phase output for that combined scope. Given its size, `speckit.plan`
may find it necessary to split delivery into sub-phases or even sibling features (e.g. tenant
core model first, capability-abstraction refactor second) — this spec captures the full intended
shape so that split can be made deliberately, not because the requirements themselves are
optional.

## Clarifications

### Session 2026-08-16

- Q: What's the underlying business motivation? → A: **White-label / multi-tenant use.**
  DeniDin gets operated on behalf of multiple independent businesses, each with their own
  godfather(s) and clients, fully isolated from one another at the application level.
- Q: What is a "client" in this feature — the existing `Role.CLIENT`, or a new concept? → A:
  Neither exactly as originally framed. The real new concept introduced by this feature is
  **tenant** (= account), the paying business-level entity. "Client" stays what it is today — a
  WhatsApp number/entity a godfather interacts with, presently just an RBAC role
  (`Role.CLIENT`) with no dedicated data entity — but a client now implicitly belongs to
  whichever tenant its godfather(s) belong to. No new client entity/data model is introduced by
  this feature.
- Q: Can one godfather serve multiple clients, or one-per-client? → A: Not the relevant axis.
  Godfather-to-client cardinality is unchanged (a godfather already serves many clients). The
  new axis this feature introduces is **tenant-to-godfather**: a tenant may have more than one
  godfather (some businesses want two+ people with godfather-level access), and each godfather
  belongs to exactly one tenant (no cross-tenant godfathers).
- Q: Does memory/ledger events/Morning MCP/group resolution need to become client-scoped? → A:
  Reframed as tenant-scoped, not client-scoped (see above). Each tenant needs its own isolated
  memory store, its own ledger events, and its own Morning MCP/Green Invoice account — this is
  infrastructure-level isolation, not a filter applied on top of shared infrastructure. Group
  membership resolution (`GroupMembershipResolver`) is unaffected in mechanism (still resolves
  the most-permissive role among a group's real members) but now operates within one tenant's
  scope; a WhatsApp group spanning two tenants' phone numbers is not a supported scenario (a
  WhatsApp group lives on exactly one WhatsApp Business number, hence exactly one tenant).
- Q: Who has authority across all tenants? → A: **ylevy (the platform owner) is a super-admin
  over every tenant**, both operationally (controls the production infrastructure that runs
  every tenant's containers) and within the app's own RBAC — resolved by ylevy's phone number
  being registered as `Role.ADMIN` in every tenant's own config, not by a separate
  cross-tenant mechanism. Each tenant's config independently lists ylevy's number as admin.
- Q: Is OpenAI account/credential also isolated per tenant? → A: **Assumption for now: yes,
  separate OpenAI account/credential per tenant** — the user is not fully decided on this and
  may want to manage OpenAI centrally later, but this spec proceeds on "separate per tenant"
  as the working assumption (see Assumptions). This differs from the pre-existing dev/prod
  design note in `apps/denidin-app/CLAUDE.md` ("OpenAI is the only credential/service still
  shared between dev and prod") — that statement is about the dev/prod axis, not the tenant
  axis, and is unaffected by this feature; each *tenant* still gets its own OpenAI credential
  under this assumption, independent of how dev/prod share credentials today.
- Q: How should tenant-specific AI behavior be handled given the constitution's existing
  prompt-caching-friendly design (`runtime_constitution.md` as one byte-identical prefix)? → A:
  Split into a **common** constitution (shared by all tenants, stays the stable cached prefix)
  plus a **per-tenant** supplement (tenant-specific business rules/etiquette), concatenated
  after the common section — deliberately preserving the existing prompt-caching approach
  described in `apps/denidin-app/CLAUDE.md` (constitution text must stay the stable,
  byte-identical *prefix*), since the common portion is still identical across every call for a
  given tenant and per-call-dynamic content (memories, date) already comes after it.
- Q: How should the pluggable "capability" abstraction work mechanically? → A: Per this
  project's constitution (§XVII, no monkey-patching), capability selection is a **compile-time
  strategy/DI pattern** — each capability (e.g. "messaging provider", "invoicing provider") is
  a well-defined interface with one or more concrete implementations (`GreenAPIMessagingProvider`,
  `MorningInvoicingProvider`, etc.), and a tenant's config names which implementation to
  construct at startup/per-request. Not a dynamic plugin-loading system (no runtime code
  loading, no reflection-based discovery) — new implementations are still added as new code,
  just behind the shared interface, and wired in via dependency injection like every other
  component in this codebase.

### Session 2026-08-16 (speckit.clarify)

- Q: How is a tenant expected to be hosted, and roughly how many tenants at once — process-level
  isolation (container set per tenant, extending today's dev/prod pattern) or in-process
  (one shared app instance routing per-tenant by config)? → A: **Not decided — left open for
  `speckit.plan` to evaluate both options** against expected tenant count and effort before
  committing. This spec's requirements (tenant isolation, multi-godfather, super-admin,
  capability abstraction, per-tenant constitution) hold under either hosting model; the choice
  is a planning/architecture decision, not a scoping one.
- Q: Should the OpenAI credential be per-tenant or shared across all tenants? → A: **Per-tenant
  — firm decision, no longer just a working assumption.** Consistent with every other
  integration being fully isolated; gives per-tenant usage/cost visibility and blast-radius
  containment. This supersedes the "Assumptions" section's earlier framing of this as unsettled.
- Q: What should happen if a tenant's config is missing a required capability implementation
  (e.g. no invoicing provider specified)? → A: **Start, but disable the missing capability** —
  a tenant with no invoicing provider still starts and serves messaging normally; invoicing
  tools/Morning MCP simply aren't attached for that tenant's godfathers (degrades gracefully,
  same shape as the existing RBAC-gated tool attachment — godfather/admin only get Morning MCP
  today; this becomes "godfather/admin only, AND only if the tenant has an invoicing provider
  configured"). Messaging provider is implicitly still required to start at all, since without
  it the tenant has no way to receive/send messages in the first place.
- Q: If ylevy's number is accidentally left out of a new tenant's config, is there a break-glass
  path to regain admin access? → A: **No — config is the sole source of truth, no automatic
  fallback.** Consistent with the project's existing "config is code" philosophy; ylevy already
  has full operational/infrastructure control over every tenant's containers regardless, so
  recovery is: edit that tenant's config file to add the admin number, restart — same mechanism
  as onboarding any tenant, not a special-cased override path.
- Q: How should the existing single-tenant deployment's data become "tenant #1"? → A:
  **Explicit migration script/step** — a dedicated migration copies/restructures existing
  `data/sessions`, `data/memory`, `data/events` into the new tenant-scoped layout, rather than
  an in-place/implicit default-tenant assignment. Exact target layout and script mechanics
  belong in `speckit.plan` (depends on the still-open hosting-model decision above), but the
  approach itself — a real, explicit migration step, not implicit reuse — is now decided.
- Q: What identifies a tenant (config, logs, data paths)? → A: **Both** — an internally
  generated UUID (stable, collision-proof primary identifier used in data paths/internal
  references) plus a human-readable external account name/slug (used in config filenames, log
  lines, anywhere a human needs to recognize which tenant is which).
- Q: Can the same phone number hold different roles in different tenants? → A: **Yes — roles
  are fully independent per tenant.** RBAC resolution is always scoped to "which tenant received
  this message"; nothing stops the same real phone number from being a client in tenant A and a
  godfather in tenant B.
- Q: How does multi-tenancy interact with the existing dev/prod environment split — does each
  tenant get its own dev AND prod, or does dev/prod stop being per-tenant? → A: **Not decided —
  left open for `speckit.plan`**, tightly coupled to the still-open hosting-model decision above.
  Flagged as a real open risk: this is a genuinely new axis (environment × tenant) that the
  existing dev/prod isolation/locking machinery (`env_lock.sh`, `shared/active_env.json`,
  per-environment watchdogs) was never designed around, and `speckit.plan` needs to explicitly
  reconcile the two rather than assume today's dev/prod model extends for free.
- Q: Does this feature need to build tenant-onboarding tooling, or is manual config-file
  creation sufficient? → A: **Manual config, no tooling** — same mechanics as today's dev/prod
  setup (copy a template config, fill in credentials, restart). No onboarding script/CLI is
  built as part of this feature; tooling is deferred to a later feature if/when onboarding
  volume justifies it.
- Q: Who can change a tenant's own settings once it exists (constitution supplement, godfather
  list, capability selection)? → A: **ylevy-only, via config files** — consistent with the
  existing "config is code" / no-runtime-admin-UI pattern used everywhere else in this app.
  Godfathers cannot self-serve any tenant-level setting under this feature; a conversational
  self-service flow (if ever wanted) is out of scope here.

## Terminology

- **Tenant (Account)**: The paying business-level entity operating one instance of DeniDin's
  behavior. Identified internally by a generated UUID (stable, used in data paths/internal
  references) and externally by a human-readable account name/slug (used in config filenames,
  logs). Fully isolated from every other tenant: own Green API instance + WhatsApp Business
  number, own Morning (Green Invoice) account, own OpenAI account/credential, own memory store,
  own ledger events, own (common + tenant) constitution. A given phone number's RBAC role is
  resolved independently per tenant — the same number can hold different roles (or no role) in
  different tenants.
- **Godfather**: The existing per-tenant ruling role (`Role.GODFATHER`). A tenant may have one
  or more godfathers; each godfather belongs to exactly one tenant.
- **Super-Admin**: ylevy's role — `Role.ADMIN` recognized in every tenant's own RBAC config by
  phone number, plus real operational control over the infrastructure hosting every tenant.
  Not a new RBAC role/tier; the existing `Role.ADMIN` concept, just present in every tenant's
  config independently.
- **Client**: A WhatsApp number/entity a godfather interacts with, within their tenant. Today,
  purely an RBAC role (`Role.CLIENT`) with no dedicated data entity — unchanged by this feature
  except that a client is now implicitly scoped to its godfather's tenant.
- **Capability**: A well-defined, pluggable interface for an external integration point (e.g. a
  "messaging provider" capability, an "invoicing provider" capability). Each capability has one
  or more concrete implementations (Green API implements messaging provider today; Morning
  implements invoicing provider today; a future "ypay" would be a second invoicing-provider
  implementation). A tenant's configuration selects which implementation to use per capability,
  resolved via dependency injection at startup — not a runtime plugin system.
- **Common constitution / Tenant constitution**: The existing `runtime_constitution.md` splits
  into a common section (identical across all tenants, preserves the existing prompt-caching
  prefix behavior) and a per-tenant supplement (tenant-specific rules), concatenated after the
  common section when `AIHandler` builds `instructions`.

## Assumptions

- Capability abstraction is introduced first for the two integrations that already exist today
  (Green API "messaging provider", Morning "invoicing provider"); it is not scoped to also
  build a second real implementation of either (e.g. an actual "ypay" integration) as part of
  this feature — only the interface + existing implementation behind it, so a future provider
  can be added later without a core refactor.
- No new dedicated "client" data entity/model is introduced by this feature — clients remain an
  RBAC-role-only concept, scoped implicitly via their godfather's tenant.
- No tenant-onboarding tooling (script/CLI/wizard) is built by this feature — onboarding a new
  tenant is manual config-file creation, same effort as today's dev/prod setup.
- No conversational self-service tenant management is built by this feature — all tenant
  settings (constitution supplement, godfather list, capability selection) are edited by ylevy
  directly in config files; godfathers have no self-serve path to change their own tenant's
  settings.

## Technology Choices

- Capability abstraction is implemented as Python interfaces (abstract base classes) with
  concrete implementations selected via dependency injection from each tenant's config at
  startup — no new framework/library, consistent with the existing DI-based construction in
  `denidin.py`'s `initialize_app` and CONSTITUTION §XVII's no-monkey-patching rule.
- No new datastore is introduced — tenant config remains plain JSON files, consistent with the
  "no environment variables / config is code" rule; exact per-tenant config file naming/layout
  is a `speckit.plan` mechanic, not a technology choice.
- Tenant identification uses Python's standard `uuid` module for the internal id — no new
  ID-generation dependency.

## Requirements

**Note**: the hosting model (process-per-tenant vs. one shared process routing per-tenant, see
Clarifications) is still an open decision for `speckit.plan`. The requirements below are written
to hold under either model.

### Tenant isolation
- The system MUST support more than one tenant running from a single DeniDin/morning-mcp-app
  codebase, each with its own Green API instance, WhatsApp Business number, and Morning
  account — no tenant's messaging or invoicing traffic is visible to or shared with another
  tenant.
- The system MUST keep each tenant's memory store (`MemoryManager`/ChromaDB), session data
  (`SessionManager`), and ledger events (`ledger_event_manager.py`) fully separate from every
  other tenant's — the existing dev/prod data-root-per-environment pattern is the closest
  existing precedent, but tenant isolation is a new, orthogonal axis (a single environment,
  e.g. `prod`, hosts multiple tenants at once).
- The system MUST use a separate OpenAI account/credential per tenant (firm decision, see
  Clarifications).

### Multi-godfather per tenant
- A tenant's config MUST support designating more than one phone number as `Role.GODFATHER`
  within that tenant.
- Every godfather designated for a tenant MUST receive full godfather-level permissions/tool
  access (including Morning MCP access) scoped to that tenant only.

### Super-admin across tenants
- ylevy's phone number MUST resolve to `Role.ADMIN` in every tenant's own RBAC config
  independently (each tenant's config lists it, rather than a single cross-tenant override
  mechanism).
- Admin-level capabilities (already existing today, e.g. answering "what version are you
  running?") MUST continue to work per-tenant when ylevy interacts with any given tenant's
  WhatsApp number.
- There MUST NOT be a hardcoded/break-glass admin fallback outside of config — a tenant missing
  the admin phone number in its config has no admin access to that tenant until the config is
  corrected and the tenant restarted (see Clarifications).

### Capability abstraction
- The system MUST define a "messaging provider" capability interface, with Green API as its
  existing implementation, selected per tenant via configuration/dependency injection.
- The system MUST define an "invoicing provider" capability interface, with Morning as its
  existing implementation, selected per tenant via configuration/dependency injection.
- Adding a new capability implementation (e.g. a future "ypay" invoicing provider) MUST NOT
  require changes to core application logic (`AIHandler`, `denidin.py` dispatch, etc.) beyond
  registering the new implementation and referencing it from a tenant's config.
- No dynamic/runtime plugin loading — capability implementations are ordinary code, wired via
  dependency injection, per this project's no-monkey-patching constitutional rule (§XVII).

### Per-tenant constitution
- `runtime_constitution.md` MUST split into a common section (shared, identical across all
  tenants) and a per-tenant supplement, concatenated after the common section when `AIHandler`
  builds `instructions` — preserving the common section as the stable, byte-identical prefix
  needed for OpenAI's automatic prompt caching (per the existing description in
  `apps/denidin-app/CLAUDE.md`).

### Migration
- The existing single-tenant deployment's data (`data/sessions`, `data/memory`, `data/events`)
  MUST be migrated into "tenant #1" via an explicit migration script/step (see Clarifications) —
  not treated as already-compliant in place. Target on-disk layout and script mechanics are
  deferred to `speckit.plan`, pending the hosting-model decision.

### Group membership resolution
- `GroupMembershipResolver`'s existing mechanism (most-permissive member's role governs a group
  turn) is unchanged, but now operates within a single tenant's scope — a WhatsApp group lives
  on exactly one tenant's WhatsApp Business number, so no group can span multiple tenants.

### Key Entities
- **Tenant**: internal UUID, external account name/slug, own Green API instance credentials,
  own WhatsApp number, own Morning account credentials, own OpenAI credential, own data root
  (sessions/memory/events), own constitution supplement, list of godfather(s) + admin phone
  numbers.
- **Capability implementation registry**: per-tenant mapping of capability name (e.g.
  "messaging_provider", "invoicing_provider") to a concrete implementation, resolved at
  startup/per-request via dependency injection.

## Edge Cases

- If a tenant's config omits the invoicing provider, the tenant still starts and serves
  messaging; invoicing tools/Morning MCP just aren't attached for that tenant's godfathers
  (resolved — see Clarifications). Omitting the messaging provider is not a supported
  degraded state — a tenant needs it to start at all.
- If ylevy's phone number is omitted from a new tenant's config, there is no automatic
  break-glass fallback — config is the sole source of truth, recovered by editing that
  tenant's config and restarting (resolved — see Clarifications).
- Migration of the existing single-tenant deployment's data into "tenant #1" happens via an
  explicit migration script/step, not implicit reuse (resolved — see Clarifications); exact
  target layout and script mechanics still deferred to `speckit.plan`.

## Success Criteria

- **SC-001**: A new tenant can be fully configured and brought online (own WhatsApp number,
  Green API, Morning, OpenAI credential) with zero changes to shared application code — only a
  new config file plus the manual onboarding steps.
- **SC-002**: A message sent to one tenant's WhatsApp number never appears in, or affects, any
  other tenant's session, memory, ledger events, or Morning invoicing data — verified end-to-end
  with at least two tenants running concurrently.
- **SC-003**: A tenant configured with two godfather phone numbers grants both full
  godfather-level access within that tenant, with zero cross-tenant leakage of that access.
- **SC-004**: ylevy's phone number resolves as admin in every configured tenant with no manual
  per-message override, confirmed across at least two tenants.
- **SC-005**: Adding a new invoicing-provider capability implementation requires zero changes to
  `AIHandler`/`denidin.py` dispatch logic — only new implementation code plus a tenant config
  reference.
- **SC-006**: The common constitution's byte content is identical across every tenant's built
  `instructions` (prompt-cache prefix preserved), verified by direct comparison.

---

See `user-stories.md` (MANDATORY, Given-When-Then) in this same directory for the full
prioritized user stories backing these requirements. `speckit.plan`, `speckit.tasks`, and
`speckit.analyze` have not yet been run for this feature.
