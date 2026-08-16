# Implementation Plan: Support Multiple Clients (Godfathers) — Multi-Tenancy

**Branch**: `feature/055-multiple-clients-godfathers` | **Date**: 2026-08-16 | **Spec**: `spec.md`
**Input**: Feature specification and `user-stories.md` in this same directory.

---

**Compliance**: NO environment variables (tenant config is more JSON, per CONSTITUTION §I);
Israel local time unaffected; git workflow — this plan continues on the existing feature branch,
no new branch; no monkey-patching — capability/tenant resolution is DI-based throughout (§XVII).

---

## Summary

Turn DeniDin from a single-tenant deployment into a multi-tenant one, without multiplying
infrastructure per tenant. Primary requirement: full data/credential isolation between tenants
(Green API/WhatsApp, Morning, OpenAI, memory, sessions, ledger events), multiple godfathers per
tenant, a cross-tenant super-admin (ylevy), a pluggable capability interface for
messaging/invoicing providers, tenant-configurable bot naming/constitution, tenant-scoped log
attribution, and a defined background-thread policy (unify maintenance work, keep only
inherently-per-tenant connections separate). Technical approach (see `research.md`): **shared,
multi-tenant-native services** — one denidin-app process and one morning-mcp-app
process/tunnel per environment (dev/prod stay exactly 2 environments total, unchanged), each
internally partitioned by `tenant_id` rather than by process/container boundary. This was a
deliberate correction mid-planning from an initially-recommended container-per-tenant model,
rejected by the user for ops-scalability reasons — see `research.md` §1 for the full reasoning
and rejected alternatives.

## Technical Context

**Language/Version**: Python 3.11 (unchanged — both apps already on this).
**Primary Dependencies**: No new dependencies expected for the core mechanism (DI-based
tenant/capability resolution is plain Python). Green API's client SDK
(`whatsapp_api_client_python`) needs confirmation it supports running N concurrent
instance-listeners inside one process cleanly (asyncio/threading — `speckit.tasks` research
item, not assumed here). FastMCP (morning-mcp-app) already supports custom
middleware/auth (`BearerTokenMiddleware` extension, `contracts/invoicing-capability.md`).
**Storage**: Unchanged — JSON files for config/sessions/events, ChromaDB for memory. New:
`tenant_id`-partitioned directory layout under each environment's existing data root
(`data-model.md`).
**Testing**: pytest, existing tiers (`unit`/`integration`/`billed`/`expensive`) unchanged in
mechanism; new tests need at least two tenant configs to exercise isolation (SC-002) —
`config.test.json` extends to a multi-tenant test fixture shape, exact form a `speckit.tasks`
decision.
**Target Platform**: Docker containers, 2 environments (dev/prod), unchanged from today —
`research.md` §3.
**Project Type**: Existing multi-app monorepo (`apps/denidin-app`, `apps/morning-mcp-app`) —
no new app/service directory introduced; both apps become internally multi-tenant.
**Performance Goals**: Confirmed by the user as non-blocking at expected scale ("hundreds of
GreenAPI instances at once, no problem") — no numeric SLA set beyond that; revisit if real
tenant count approaches that order of magnitude.
**Constraints**: No environment variables; config-is-code (tenant list lives in each
environment's config, gitignored real credentials per existing convention); no monkey-patching
— every tenant/capability resolution is explicit DI, no thread-locals/module globals carrying
`tenant_id` implicitly (`research.md` §2's named cache-leak risk is exactly this constraint
being violated by omission if not audited).
**Scale/Scope**: Low tens of tenants expected (manual onboarding, white-label resale — not
self-serve mass signup).

## Constitution Check

*Gate: must pass before Phase 0 research (it did — see below) and re-checked after Phase 1
design (this document).*

- **No environment variables** (§I): PASS — tenant config is more JSON added to each
  environment's existing config file, no new env-var surface.
- **Israel local time** (§I): PASS — unaffected, no new datetime handling introduced.
- **No monkey-patching, DI/strategy patterns** (§XVII): PASS by design — capability
  implementations and tenant resolution are both explicit DI (`research.md` §5,
  `data-model.md`'s `Capability` section). The named risk (§XVII violation *by omission*, via an
  un-audited in-memory cache implicitly leaking across tenants) is called out explicitly in
  `research.md` §2 and `data-model.md`'s cache section as a mandatory `speckit.tasks` audit item
  — not a violation in the design itself, but a real implementation risk to guard against.
- **Integration tests simulate real external entry points** (§V): PASS, extends — integration
  tests need a second tenant fixture to exercise real cross-tenant isolation, not just a second
  config value; no mocking introduced.
- **Feature flags default false, byte-identical when disabled** (`CLAUDE.md`): applies to how
  this ships incrementally — `speckit.tasks` should gate the shared-multi-tenant code paths
  behind a feature flag until the single existing (migrated) tenant is verified working
  end-to-end, per this project's standing feature-flag convention.
- **No violations requiring Complexity Tracking.**

## Integration Contracts

Per METHODOLOGY.md §VII (mandatory for multi-component features — this one touches
`denidin.py`, `AIHandler`, `UserManager`, `SessionManager`, `MemoryManager`,
`ledger_event_manager`, `GroupMembershipResolver`, and `apps/morning-mcp-app`'s `server.py`/
`BearerTokenMiddleware`/`audit.py`). Full contracts in `contracts/`:

- **`contracts/messaging-gateway.md`** — Messaging Gateway ↔ Core Conversation Pipeline;
  Messaging Gateway ↔ Tenant Config.
- **`contracts/invoicing-capability.md`** — `AIHandler` ↔ morning-mcp-app (shared server,
  extension of the existing MCP contract); `BearerTokenMiddleware` ↔ Tenant Config.
- **`contracts/group-resolution-tenant-scoping.md`** (added at `speckit.analyze` remediation,
  finding G1) — `denidin.py` ↔ `GroupMembershipResolver` (tenant-scoping extension);
  Messaging Gateway/`TenantManager` ↔ `GroupMembershipResolver` (per-tenant Green API client
  lookup, not just the cache-key fix already in `data-model.md`).
- **`contracts/tenant-scoped-rbac.md`** (added at `speckit.analyze` remediation, finding G3) —
  `UserManager` ↔ Tenant Config.
- **`contracts/tenant-scoped-data-managers.md`** (added at `speckit.analyze` remediation,
  finding G3) — `SessionManager`/`MemoryManager`/`ledger_event_manager` ↔ tenant-partitioned
  data root.

All components named in this section's opening paragraph now have a written contract.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/055-multiple-clients-godfathers/
├── spec.md               # speckit.specify + speckit.clarify output
├── user-stories.md       # MANDATORY, Given-When-Then
├── plan.md               # This file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output (messaging-gateway.md, invoicing-capability.md;
│                          # more to follow at speckit.tasks)
└── tasks.md              # Phase 2 output (speckit.tasks — NOT created by this plan)
```

### Source Code (repository root)

No new top-level app/service directory. Changes land inside the existing two apps:

```text
apps/denidin-app/src/
├── managers/
│   ├── tenant_manager.py         # NEW — loads/joins tenants.json + config.<env>.json's
│   │                              # tenant_credentials, exposes tenant_id lookups
│   ├── logging_utils.py          # EXTENDED (or NEW, tasks decision) — tenant bot_name in every
│   │                              # tenant-scoped log line (REQ-LOG-001)
│   ├── user_manager.py           # EXTENDED — RBAC resolution becomes tenant-scoped
│   ├── session_manager.py        # EXTENDED — tenant_id-partitioned data root
│   ├── memory_manager.py         # EXTENDED — tenant_id-partitioned ChromaDB collections
│   ├── ledger_event_manager.py   # EXTENDED — tenant_id-partitioned events
│   └── group_membership_resolver.py  # EXTENDED — cache re-keyed to (tenant_id, chat_id) AND
│                                    # resolve() takes tenant_id, selects that tenant's own
│                                    # groups_client (contracts/group-resolution-tenant-scoping.md)
├── services/
│   └── messaging_gateway.py      # NEW — multi-tenant Green API listener/router (contracts/messaging-gateway.md)
├── capabilities/                 # NEW — capability interfaces + implementations
│   ├── messaging_provider.py     # interface
│   ├── invoicing_provider.py     # interface
│   └── impl/
│       ├── green_api_messaging.py
│       └── morning_invoicing.py
└── handlers/ai_handler.py        # EXTENDED — tenant-scoped OpenAI credential + constitution
                                   # supplement + capability-gated tool attachment

apps/morning-mcp-app/src/denidin_mcp_morning/
├── server.py                     # EXTENDED — BearerTokenMiddleware → per-tenant token map
└── audit.py                      # EXTENDED — tenant_id on every audit line
```

**Structure Decision**: extend both existing apps in place; no new app, no new deployable unit.
`tenant_manager.py` is the one genuinely new core component in `denidin-app`; everything else
is an extension of an existing manager/handler, consistent with `research.md`'s
shared-process decision.

## Complexity Tracking

*No Constitution Check violations — table intentionally omitted (per template: fill only if
violations must be justified).*

---

**Status**: Phase 0 (research.md) and Phase 1 (data-model.md, contracts/, quickstart.md)
complete. `speckit.tasks` complete (`tasks.md`). `speckit.analyze` complete — findings
remediated (2026-08-16): G1 (`GroupMembershipResolver` tenant-scoping), G2 (REQ-CAP-003
verification), G3 (two missing Integration Contracts), C1 (Technology Choices format), I1/I2
(staleness/format nits) — see `spec.md`'s Clarifications for the summary and each artifact's
own updated content for the fix.
