# User Stories: Dev/Prod Environment Separation

**Feature Branch**: `019-env-separation`
**Related Spec**: `spec.md` (same directory)

---

### User Story 1 - Run all four instances side by side on one machine (Priority: P1)

As the operator, I want denidin-app-dev, denidin-app-prod, morning-mcp-app-dev, and morning-mcp-app-prod all runnable as containers on the same machine, each fully isolated in config/data/logs/ports, so environment separation is real infrastructure isolation rather than a config toggle. (Caveat, see Clarifications: because there is only one real Green API instance shared by dev/prod denidin-app, "simultaneous" for the two denidin-app containers is a container/process-isolation guarantee, not a guarantee that both may safely poll real WhatsApp traffic at the same moment — that remains a manual, one-at-a-time operator rule. The two morning-mcp-app containers, and morning-mcp-app alongside either denidin-app container, have no such restriction.)

**Why this priority**: This is the core requirement — without simultaneous operation, "environment separation" is just a config toggle, not real isolation.

**Independent Test**: Start all four containers. Verify via `docker compose ... ps` (across both compose files) that 4 distinct containers are running, each with distinct config/data/log/port bindings, with no conflicts.

**Acceptance Scenarios**:

1. **Given** prod denidin-app and prod morning-mcp-app are already running, **When** the operator starts dev morning-mcp-app (and, if dev denidin-app is also needed, first stops prod denidin-app), **Then** all desired containers run without any container refusing to start due to port or volume-mount conflicts with the other environment.
2. **Given** all four containers are running, **When** the operator inspects each app's config/data/log paths, **Then** each instance reads/writes only its own environment's files.
3. **Given** dev denidin-app is running for live manual testing, **When** the operator wants to resume real prod traffic, **Then** the documented hand-off procedure (stop dev denidin-app, start/confirm prod denidin-app) restores prod polling with no message loss beyond the hand-off window itself.

---

### User Story 2 - Dev and prod never cross-wire their MCP tool call (Priority: P1)

As the operator, I want dev denidin-app's OpenAI MCP tool call to reach only dev morning-mcp-app (via a dev-only ngrok tunnel and dev-only Morning sandbox credentials), and prod denidin-app to reach only prod morning-mcp-app (via a prod-only ngrok tunnel and real Morning credentials), so a mistake in dev can never touch real invoices/clients in Green Invoice production.

**Why this priority**: This is the safety-critical requirement driving the whole feature — crossing this boundary means dev testing could create/modify real financial records.

**Independent Test**: With both environments running, issue an invoice-related request as a godfather user to dev denidin-app; confirm (via Morning sandbox dashboard / mocked sandbox data) the call landed in the sandbox account, never in the real Green Invoice account, and confirm the reverse for a prod request.

**Acceptance Scenarios**:

1. **Given** dev denidin-app is configured with dev morning-mcp-app's tunnel URL, **When** a godfather sends an invoice command, **Then** the MCP call is routed through the dev ngrok tunnel to dev morning-mcp-app, which uses Morning **sandbox** credentials.
2. **Given** prod denidin-app is configured with prod morning-mcp-app's tunnel URL, **When** a godfather sends an invoice command, **Then** the MCP call is routed through the prod ngrok tunnel to prod morning-mcp-app, which uses Morning **production** credentials.
3. **Given** dev morning-mcp-app's tunnel goes down, **When** dev denidin-app attempts an MCP call, **Then** it degrades gracefully (existing "not running" status behavior) and prod is entirely unaffected.

---

### User Story 3 - Operator can tell environments apart at a glance (Priority: P2)

As the operator, I want distinct process names/PID files/log files/ports per environment, so I can tell at a glance (via `ps`, log tail, or `docker ps`) which environment a given running process or log line belongs to, without cross-referencing config files.

**Why this priority**: Operational safety net — reduces the chance of an operator accidentally sending a stop/restart/deploy command to the wrong environment.

**Independent Test**: Run `ps aux | grep denidin` / `docker ps` and confirm environment is identifiable from the process/container name alone; tail each log file and confirm no ambiguity about which environment produced a given line.

**Acceptance Scenarios**:

1. **Given** both dev and prod denidin-app are running, **When** the operator runs `./stop_denidin.sh dev` (or the dev-specific stop script), **Then** only the dev instance is stopped; prod is untouched.
2. **Given** both dev and prod morning-mcp-app are running, **When** the operator checks each app's status file, **Then** each status file is environment-scoped (distinct file per env) and reflects only that environment's tunnel state.

---

### User Story 4 - Shared OpenAI key, split Morning credentials (Priority: P2)

As the operator, I want both dev and prod denidin-app to use the same production OpenAI API key (since OpenAI has no sandbox), while each morning-mcp-app instance uses environment-appropriate Morning API credentials (sandbox for dev, production for prod), so I don't need to provision or pay for an OpenAI sandbox that doesn't exist, while still keeping financial-data risk contained to prod only.

**Why this priority**: Directly dictated by external constraints (OpenAI has one tier); getting this wrong either wastes effort building a nonexistent OpenAI sandbox path or (worse) accidentally uses sandbox Morning creds in prod.

**Independent Test**: Inspect dev and prod denidin-app configs; confirm identical `ai_api_key` value; inspect dev and prod morning-mcp-app configs; confirm distinct `api_key_id`/`api_key_secret`/`api_url` values (sandbox vs. production).

**Acceptance Scenarios**:

1. **Given** dev and prod denidin-app configs, **When** compared, **Then** `ai_api_key` (and other OpenAI model fields) are identical across both.
2. **Given** dev and prod morning-mcp-app configs, **When** compared, **Then** Morning credentials and `api_url` differ, with dev pointing at the sandbox host and prod at the production host.

---

### User Story 5 - Operator-switchable role testing in dev without a second WhatsApp number (Priority: P2)

As the operator, I want to be able to exercise both godfather and admin behavior in dev by editing config and restarting, using my one real WhatsApp number, so role-gated features (e.g. Morning MCP invoicing, currently godfather/admin-only) can be validated in dev before trusting them in prod — without ever needing a second real tester or a fake/synthetic phone number.

**Why this priority**: Directly blocks meaningful dev testing of any role-gated feature otherwise — without this, dev could only ever be exercised as whichever single role the operator's real number resolves to.

**Independent Test**: Inspect `config.prod.json` — confirm `godfather_phone` = `972506205541` (AH) and `admin_phones` includes `972522968679` (ylevy), fixed. Inspect `config.dev.json` — confirm `972522968679` appears in exactly one of `godfather_phone`/`admin_phones`. Edit it to the other field, restart `denidin-app-dev`, and confirm the resolved role for that number flips accordingly.

**Acceptance Scenarios**:

1. **Given** `config.prod.json`, **When** inspected, **Then** `godfather_phone` is `972506205541` (AH) and `admin_phones` includes `972522968679` (ylevy) — this never changes.
2. **Given** `config.dev.json` with `972522968679` currently in `godfather_phone`, **When** the operator texts `denidin-app-dev` from that number, **Then** it resolves to GODFATHER.
3. **Given** the operator edits `config.dev.json` to move `972522968679` from `godfather_phone` into `admin_phones` and restarts `denidin-app-dev`, **When** the operator texts from that same number again, **Then** it now resolves to ADMIN.
4. **Given** `972522968679` is present in only one of the two fields at any time, **When** the operator inspects `config.dev.json`, **Then** it is never present in both simultaneously (operator discipline, not software-enforced).

### Edge Cases

- What happens if the operator starts two instances of the *same* environment for the *same* app twice (e.g., dev denidin-app started twice)? → Docker itself prevents a true duplicate (see FR-003).
- What happens if dev's ngrok free-tier tunnel URL rotates on restart? → dev denidin-app must re-discover the new URL the same way prod already does today (status-file polling), independently of prod's tunnel state.
- What happens if the dev morning-mcp-app's ngrok account/authtoken is invalid or exhausted (free-tier limits)? → dev denidin-app's MCP tool degrades gracefully; prod is unaffected since it uses a separate ngrok account.
- What happens if someone edits dev config and accidentally points it at the production Morning `api_url` or a prod ngrok tunnel? → out of scope for automated prevention in this feature (config review is a human process), but config examples/docs must make the sandbox-vs-prod distinction unmistakable.
- What happens if both `denidin-app-dev` and `denidin-app-prod` are left running concurrently with real WhatsApp traffic incoming? → Not prevented by software; `GreenAPIBot` polling means both would race for the same notifications and traffic would be nondeterministically split. Documented operator rule: stop the other one first (see FR-014, User Story 1's caveat).
- What happens if `972522968679` ends up in both `godfather_phone` and `admin_phones` in `config.dev.json` at once (operator forgot to remove it from the old field)? → Not software-prevented; `UserManager`'s existing ADMIN > GODFATHER precedence resolves it to ADMIN. Operator is expected to keep it in exactly one field.
