# User Stories: Support Multiple Clients (Godfathers) — Multi-Tenancy

**Feature**: `055-multiple-clients-godfathers`
**Format**: Given-When-Then, prioritized P1 (MVP-critical) → P3 (nice-to-have-for-this-feature)

---

### User Story 1 — Tenant infrastructure isolation (Priority: P1)

As the platform owner, I want each tenant's WhatsApp/Green API traffic, Morning invoicing
account, and OpenAI usage fully separated from every other tenant's, so that no tenant can see,
affect, or be billed for another tenant's activity.

**Why this priority**: This is the foundational guarantee the whole feature exists to provide —
without it, "multi-tenant" is just a UI label on a still-shared backend. Every other story
depends on tenant identity existing and being isolating.

**Independent Test**: Configure two tenants (A, B), each with its own Green API instance/number
and Morning account. Send a WhatsApp message to tenant A's number; confirm the resulting
session, memory writes, ledger events, and Morning MCP calls all resolve against tenant A's own
resources only, with zero reads/writes touching tenant B's.

**Acceptance Scenarios**:

1. **Given** tenants A and B are both configured and running, **When** a client messages
   tenant A's WhatsApp number, **Then** the message is processed using only tenant A's Green
   API credentials, data root (sessions/memory/events), and Morning account — nothing is read
   from or written to tenant B's resources.
2. **Given** tenant A's godfather asks DeniDin to create an invoice, **When** the Morning MCP
   tool call executes, **Then** it hits tenant A's Morning account, never tenant B's.
3. **Given** the working assumption that OpenAI credentials are also per-tenant, **When**
   tenant A and tenant B each send a message at the same time, **Then** each call uses its own
   tenant's OpenAI credential.

---

### User Story 2 — Multi-godfather per tenant (Priority: P1)

As a tenant business, I want to designate more than one person as godfather for my tenant, so
multiple people at my business can manage clients and invoicing.

**Why this priority**: Explicitly named as a real business need ("some businesses may want more
than 1 godfather") — without it, tenants are artificially limited to single-operator use even
though the underlying godfather role already supports concurrent users today.

**Independent Test**: Configure a tenant with two distinct phone numbers as `Role.GODFATHER`.
Message DeniDin from each number within that tenant; confirm both are resolved as godfather
with full godfather-level token limits and tool access (including Morning MCP).

**Acceptance Scenarios**:

1. **Given** a tenant configured with two godfather phone numbers, **When** either number
   messages DeniDin, **Then** that sender is resolved with `Role.GODFATHER` permissions for
   that tenant.
2. **Given** a tenant's two godfathers, **When** one godfather sets up a ledger event or
   invoice, **Then** the other godfather (same tenant) can see/manage it exactly as if they had
   created it themselves (shared tenant-level state, not per-godfather-siloed).

---

### User Story 3 — Super-admin oversight across all tenants (Priority: P1)

As ylevy (the platform owner), I want my phone number to resolve as admin in every tenant, so I
retain full oversight and control regardless of which tenant's WhatsApp number I'm messaging.

**Why this priority**: Without cross-tenant admin access, operating/debugging/supporting
multiple tenants in production has no built-in path — this is required from day one of running
more than one tenant.

**Independent Test**: Configure ylevy's phone number as `Role.ADMIN` in two different tenants'
configs. Message each tenant's WhatsApp number from that phone number; confirm admin-level
resolution and permissions in both, independently.

**Acceptance Scenarios**:

1. **Given** ylevy's phone number is listed as admin in tenant A's and tenant B's configs
   independently, **When** ylevy messages tenant A's number, **Then** DeniDin resolves
   `Role.ADMIN` for that turn, scoped to tenant A.
2. **Given** the same setup, **When** ylevy asks either tenant's DeniDin "what version are you
   running?", **Then** it answers using that tenant's own running version (admin capability
   already exists today, ungated by RBAC — confirmed still works per-tenant).
3. **Given** a brand-new tenant is configured without explicitly adding ylevy's number, **When**
   ylevy messages that tenant's number, **Then** ylevy is resolved with whatever role that
   number would otherwise get (e.g. `Role.CLIENT` or unrecognized) — there is no automatic
   break-glass admin fallback; access is restored only by editing that tenant's config to add
   the admin number and restarting (resolved via `speckit.clarify`).

---

### User Story 4 — Pluggable capability abstraction (Priority: P2)

As the platform maintainer, I want each external integration (messaging, invoicing) expressed
as a capability with a well-defined interface, so a new provider (e.g. a future "ypay") can be
added and assigned per tenant without changing core application logic.

**Why this priority**: Not required for a first tenant to go live (Green API + Morning already
work), but is the enabling groundwork for the stated future need ("more MCPs like ypay are
expected") and for genuinely independent per-tenant provider choice. P2 because US1–US3 can
ship against the existing hardcoded Green API/Morning integrations first, with capability
abstraction as a refactor underneath.

**Independent Test**: Define the "messaging provider" and "invoicing provider" capability
interfaces with Green API and Morning as their sole implementations respectively. Confirm
`AIHandler`/`denidin.py`/`WhatsAppHandler` call only the interface, not the concrete class
directly, and that a tenant's config determines which implementation is constructed at startup.

**Acceptance Scenarios**:

1. **Given** the "invoicing provider" capability interface exists with Morning as its
   implementation, **When** a tenant's config specifies `invoicing_provider: morning`, **Then**
   `AIHandler`'s Morning MCP wiring is constructed via the capability interface, not a direct
   Morning-specific reference.
2. **Given** a hypothetical second "invoicing provider" implementation existed (e.g. "ypay"),
   **When** a tenant's config specifies `invoicing_provider: ypay` instead, **Then** no changes
   to `AIHandler` or `denidin.py` are needed — only the new implementation's registration.
3. **Given** the capability interfaces are in place, **When** reviewing `AIHandler`/
   `WhatsAppHandler` code, **Then** there is no direct, capability-bypassing reference to
   Green API's or Morning's concrete client classes from core dispatch logic.

---

### User Story 5 — Per-tenant constitution supplement (Priority: P2)

As a tenant business, I want some AI behavior/policy customized to my business while still
sharing DeniDin's common baseline rules, so my tenant's assistant behaves appropriately for my
business without duplicating the entire constitution per tenant.

**Why this priority**: Named as a real anticipated need ("each tenant might require a bit
different business logic"), but not blocking for a first tenant (which can run on the common
constitution alone, with an empty tenant supplement). P2 because it extends the existing
constitution-loading mechanism rather than introducing new infrastructure.

**Independent Test**: Configure two tenants with different constitution supplements. Send the
same ambiguous message to both; confirm each tenant's `AIHandler`-built `instructions` includes
the common section plus only that tenant's own supplement, and that the common section remains
byte-identical across both (preserving prompt-cache eligibility).

**Acceptance Scenarios**:

1. **Given** a common constitution and tenant A's supplement, **When** `AIHandler` builds
   `instructions` for a message in tenant A, **Then** the result is common text + tenant A's
   supplement, in that order, with tenant B's supplement absent.
2. **Given** the same common constitution reused across tenants A and B, **When** comparing the
   byte content of the common section across both tenants' built `instructions`, **Then** it is
   identical (preserving OpenAI's longest-common-prefix caching benefit).

---

### Edge Cases (cross-story)

- Tenant config missing a required capability implementation (US4) — resolved: tenant starts,
  missing capability's tools just aren't attached. See `spec.md` Clarifications.
- New tenant provisioned without ylevy's admin number present (US3) — resolved: no break-glass,
  config is sole source of truth. See `spec.md` Clarifications.
- Migrating the existing single-tenant deployment's data into "tenant #1" (US1) — resolved: an
  explicit migration script/step, not implicit reuse. Exact mechanics still deferred to
  `speckit.plan`. See `spec.md` Clarifications.
