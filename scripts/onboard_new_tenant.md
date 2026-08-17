# New Tenant Onboarding Checklist

**Status**: Manual checklist. Describes the target workflow once Feature 055
(`specs/in-progress/055-multiple-clients-godfathers/`) is implemented — not yet operational
today (single-tenant codebase as of this writing). Per that feature's spec (Assumptions: "no
tenant-onboarding tooling built by this feature"), this stays a manual, human-followed
checklist for the first real tenant onboarded; it's meant to evolve into
`scripts/onboard_new_tenant.sh` once onboarding volume actually justifies automating it — keep
this checklist and the future script in sync (or retire the checklist) rather than letting them
drift apart.

Cross-references `specs/in-progress/055-multiple-clients-godfathers/data-model.md` (exact field
shapes) and `quickstart.md` (the fully-live two-tenant verification scenarios) — if either
changes, check this file for drift.

**Reminder, not optional**: every "restart"/"start a container" step below is still subject to
this repo's standing "never start an environment without explicit approval, every single time"
rule (`CLAUDE.md`) — this checklist tells you *what* to do, it doesn't pre-authorize *doing* it.

---

## Phase A — Acquire the new tenant's external accounts

- [ ] Green API instance + a paid WhatsApp Business number, dedicated to this tenant.
- [ ] Morning (Green Invoice) account — sandbox credentials for dev, real production account
      credentials for prod (mirrors today's existing single-tenant dev/prod split).
- [ ] OpenAI API key — a distinct key for this tenant (REQ-TENANT-003: per-tenant credential,
      not necessarily a separate OpenAI *account*).

## Phase B — Decide the tenant's identity

- [ ] Generate `tenant_id` (a fresh UUID — internal, never reused, never edited later).
- [ ] Choose `account_name` (external slug, e.g. `"jabaloola-inc"`) — must be unique within
      `tenants.json`.
- [ ] Choose `bot_name` (the persona customers talk to, e.g. `"Jabaloola"`) — feeds the
      constitution's Core Identity line and every tenant-scoped log line (`tenant=<bot_name>`).
- [ ] Collect the tenant's godfather phone number(s) — one or more.
- [ ] **Do not forget**: add ylevy's admin phone number to this tenant's `admins` list too.
      There is no break-glass fallback (REQ-ROLE-005) — an omission here means no admin access
      to this tenant until the config is fixed and it's restarted.
- [ ] Decide `capability_selection` (defaults: `messaging_provider: green_api`,
      `invoicing_provider: morning` — override only if this tenant genuinely needs a different
      provider).
- [ ] Write the tenant's constitution supplement as its own `.md` file (REQ-CONST-003 — never
      inline config text) — an empty file is fine for launch if there's nothing tenant-specific
      yet.
- [ ] Generate a fresh, unique `mcp_auth_token` **per environment** (dev and prod each need
      their own, even for the same tenant).

## Phase C — Add to config (dev environment first)

Per `data-model.md`'s split — identity is environment-agnostic, credentials are not:

- [ ] Add an entry to `apps/denidin-app/config/tenants.json` (identity: `tenant_id`,
      `account_name`, `bot_name`, `godfathers`, `admins`, `constitution_supplement_file`,
      `capability_selection`).
- [ ] Create `apps/denidin-app/config/tenants/<account_name>/constitution_supplement.md` and
      point `constitution_supplement_file` at it (relative path).
- [ ] Add a `tenant_credentials` entry (keyed by `tenant_id`) to
      `apps/denidin-app/config/config.dev.json` — `green_api`, `openai`, `mcp_auth_token`.
- [ ] Add the matching `tenant_credentials` entry to
      `apps/morning-mcp-app/config/config.dev.json` — `mcp_auth_token` (must match the value
      above exactly), `api_key_id`/`api_key_secret`/`api_url`.
- [ ] Double-check: `mcp_auth_token` is unique across every tenant already configured in this
      environment, in both apps' config files.

## Phase D — Restart & verify in dev

- [ ] Get explicit approval, then restart `denidin-app-dev` + `morning-mcp-app-dev`
      (`scripts/run_all.sh dev`) so both apps pick up the new tenant.
- [ ] Confirm the new tenant's messaging listener started — check logs for
      `tenant=<bot_name>` lines with no errors.
- [ ] Message the new tenant's WhatsApp number as its godfather — confirm a reply, and confirm
      it's using the right persona/`bot_name`.
- [ ] Message as ylevy — confirm admin resolution (e.g. "what version are you running?").
- [ ] Trigger a test invoice/ledger event — confirm it lands in this tenant's own Morning
      account, and that `audit.py`'s log line records the correct `tenant_id`.
- [ ] Confirm session/memory/ledger data landed under `dev_data/{tenant_id}/...` and nowhere
      else.

## Phase E — Promote to prod

Separate, explicit approval required — this is its own environment-start decision, not implied
by dev having gone well.

- [ ] Add the same `tenant_credentials` entries to `apps/denidin-app/config/config.prod.json`
      and `apps/morning-mcp-app/config/config.prod.json` (real production Green API/Morning/
      OpenAI credentials this time, not sandbox/dev ones). `tenants.json` itself doesn't need
      touching again — it's already shared across dev and prod.
- [ ] Get explicit approval, then restart `denidin-app-prod` + `morning-mcp-app-prod`.
- [ ] Repeat Phase D's verification steps against prod.

## Phase F — Housekeeping

- [ ] Record the new tenant somewhere durable outside this checklist (an internal roster/
      spreadsheet — not a system this project currently defines).
- [ ] Confirm whatever backup/monitoring exists for `dev_data`/`data` also covers the new
      tenant's subdirectory (it should, automatically, if it already backs up the parent — but
      verify once rather than assume).
