# Data Model: Support Multiple Clients (Godfathers) — Multi-Tenancy

**Feature**: `055-multiple-clients-godfathers` · Phase 1 output of `speckit.plan`

---

## Tenant

The paying business-level entity, split across two config surfaces (see "Config file
structure" below): environment-agnostic **identity** (`tenants.json`, one file, shared by
dev and prod) and environment-specific **credentials** (inside each of `config.dev.json`/
`config.prod.json`, keyed by `tenant_id`) — see `research.md` §3 for why "environment"
(dev/prod) stays orthogonal and unmultiplied, and why credentials still differ per environment
even though identity doesn't.

### Tenant Identity (`tenants.json`, environment-agnostic)

| Field | Type | Notes |
|---|---|---|
| `tenant_id` | UUID (string) | Internal, stable, generated once at onboarding. Never reused, never edited. Primary key for data paths and every tenant-scoped lookup (`research.md` §2), and the join key into each environment's credential map. |
| `account_name` | string (slug) | External, human-readable. Used in config filenames, log lines. Not guaranteed globally unique the way `tenant_id` is, but MUST be unique within `tenants.json` (operational sanity, not a hard system requirement). |
| `bot_name` | string | The name this tenant's bot goes by in conversation (e.g. "DeniDin", "Jabaloola") — substituted into the common constitution template's "Core Identity" line at render time (REQ-CONST-002), and **required in every tenant-scoped log line** (REQ-LOG-001). Distinct from `account_name`: `account_name` identifies the *business*; `bot_name` identifies the *bot persona* that business's customers talk to. |
| `godfathers` | list of phone numbers | `Role.GODFATHER` within this tenant (REQ-ROLE-001). Zero or more phone numbers may additionally be `Role.ADMIN` — see below. |
| `admins` | list of phone numbers | `Role.ADMIN` within this tenant (REQ-ROLE-003). ylevy's number MUST appear in every tenant's list (operational convention, not system-enforced — REQ-ROLE-005: no break-glass fallback if omitted). |
| `constitution_supplement_file` | relative file path | Points to a standalone `.md` file (e.g. `config/tenants/jabaloola/constitution_supplement.md`), NOT inline config text — expected to grow large, and inline JSON strings are the wrong shape for prose (REQ-CONST-003). Concatenated after the rendered common constitution when `AIHandler` builds `instructions` (REQ-CONST-001). May point to an empty file for a tenant with no tenant-specific rules. |
| `capability_selection` | map | Capability name → implementation id, e.g. `{"messaging_provider": "green_api", "invoicing_provider": "morning"}`. Resolved via DI per-call by `tenant_id` (`research.md` §5), not once at process startup. |
| `data_root` | derived, not stored | `{environment_data_root}/{tenant_id}/` — sessions, memory (ChromaDB), ledger events all live under this path. Never a config field itself; always derived from `tenant_id`, and inherently environment-specific even though identity isn't (dev and prod never share session/memory data for the same tenant). |

### Tenant Credentials (per environment — `config.dev.json`/`config.prod.json`, keyed by `tenant_id`)

| Field | Type | Notes |
|---|---|---|
| `green_api` | credential set | Instance id + API token + WhatsApp Business number for this tenant's messaging-provider capability implementation. **Differs between dev and prod** even for the same tenant (separate Green API instance per environment, consistent with the existing single-tenant dev/prod asymmetry). |
| `openai` | credential | API key for this tenant's AI calls (REQ-TENANT-003 — firm decision, per-tenant). Also differs per environment, same reasoning. |
| `mcp_auth_token` | string | This tenant's bearer token for the shared morning-mcp-app server *in this environment* (`research.md` §4) — doubles as both auth and tenant-selection for that call. Dev and prod each need their own token even for the same tenant, since they're two different server instances. |

`morning` (Morning API key id/secret) is **not** stored in `denidin-app`'s config at all — it
lives only in `morning-mcp-app`'s own per-environment config, keyed the same way by
`tenant_id`. Its absence there → REQ-CAP-005's degraded-start behavior (tenant runs, invoicing
tools not attached for that tenant).

### Config file structure

- **`config/tenants.json`** (new, environment-agnostic, shared by dev and prod): the Tenant
  Identity table above, one entry per tenant. A tenant's business identity, godfathers, and
  constitution supplement don't change based on which environment is asking.
- **`config/config.dev.json`/`config/config.prod.json`** (existing files, extended): gain a new
  `tenant_credentials` map, `tenant_id → Tenant Credentials` (above) — everything
  environment-specific and secret. Everything else in these files (data_root,
  `ai_embedding_model`, feature flags, etc.) is unchanged.
- Same split applies to `apps/morning-mcp-app`'s own config: its own `tenants.json`-equivalent
  (or a shared read of the same file — `speckit.tasks` decision) for `tenant_id`↔bot_name
  mapping if needed for its own logging (REQ-LOG-001 applies there too), and its own
  `config.dev.json`/`config.prod.json` gain a `tenant_credentials` map of `tenant_id → {morning
  api_key_id/secret/api_url, mcp_auth_token}`.
- Rationale for splitting identity from credentials (vs. one combined per-environment tenant
  list, the shape shown to the user before this revision): credential rotation never touches
  tenant identity/business-rules, and vice versa — smaller, more auditable diffs, and a tenant's
  godfathers/constitution supplement is reviewable without ever looking at a file containing
  live secrets.

**Identity rule** (from `speckit.clarify`): a phone number's role is resolved independently per
tenant — the same number can be a `godfathers` entry in one tenant's list and a plain,
unrecognized (or `Role.CLIENT`) number in another's. No global phone-number-to-tenant mapping
exists or is enforced.

**Lifecycle**: created once, manually, by editing that environment's tenant list (no onboarding
tooling — spec.md Assumptions). No supported "delete a tenant" flow in this feature's scope;
deprovisioning is out of scope (not raised during clarification, no default assumed — flag for
`speckit.tasks`/a future feature if it becomes needed).

## Capability

A pluggable interface for an external integration point. Two known instances at spec time.

| Capability name | Interface responsibility | Known implementation(s) |
|---|---|---|
| `messaging_provider` | Send/receive WhatsApp messages for one tenant's number | `green_api` (only one today) |
| `invoicing_provider` | Create/query invoices, clients, financial summaries for one tenant's Morning account | `morning` (only one today; `ypay` is a named future possibility, not built by this feature — spec.md Assumptions) |

Each capability's concrete implementation is resolved by `(tenant_id, capability_name) →
implementation_id` via `Tenant.capability_selection`, then dependency-injected per call —
**not** instantiated once per process at startup (that pattern only worked under the rejected
container-per-tenant hosting model; see `research.md` §1/§5).

## Message (tenant-scoped extension)

Existing `Message` model (`apps/denidin-app/src/models/message.py`) gains no new *stored*
field for tenant identity — `tenant_id` is implicit in *where* a `Message` lives (under
`{data_root}/{tenant_id}/sessions/...`), consistent with how dev/prod already partition data by
directory rather than by a field on every record. `speckit.tasks` should confirm this is
sufficient rather than introducing a redundant `Message.tenant_id` field (mirrors the existing
`sender="AI"` sentinel removal precedent in Feature 039 — don't store what's already implied by
where the record lives).

## Group Membership Resolution Cache (existing component, tenant-risk flagged)

`GroupMembershipResolver`'s existing in-memory cache, currently keyed by `chat_id` alone, MUST
be re-keyed to `(tenant_id, chat_id)` under the shared-process hosting model — flagged as a
concrete, named risk in `research.md` §2, not just a general warning. This is the first of
potentially more such caches; `speckit.tasks` MUST include an explicit audit task for every
existing module-level/in-memory cache in `apps/denidin-app/src/`.
