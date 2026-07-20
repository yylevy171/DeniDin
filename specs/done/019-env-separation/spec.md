# Feature Specification: Dev/Prod Environment Separation

**Feature Branch**: `019-env-separation`
**Created**: 2026-07-20
**Status**: Draft
**Input**: User description: "Separate dev and prod environments for denidin-app and morning-mcp-app, running all four instances simultaneously on one machine with fully isolated config, data, ngrok tunnels, and MCP wiring, while sharing a single production OpenAI API key across both envs and using Morning sandbox for dev / Morning production for prod."

---

## Clarifications

### Session 2026-07-20

- Q: Should pytest's ephemeral test fixtures share the renamed `dev_data/` root with the persistent dev environment, or get their own root? → A: Split — `config.test.json` gets its own separate ephemeral root; `config.dev.json` owns `dev_data/` independently. Pytest runs never touch dev's persistent state.
- Q: How should run/stop tooling select dev vs. prod? → A: Positional arg (`./run_denidin.sh dev` / `./run_denidin.sh prod`), one script per app.
- Q: One docker-compose file with 4 services, or split dev/prod compose files? → A: Split — `docker-compose.dev.yml` (denidin-dev + morning-dev) and `docker-compose.prod.yml` (denidin-prod + morning-prod).
- Q: Do the run/stop scripts manage local (non-containerized) long-lived processes, or containers? → A: Containers only — no long-lived process ever runs on the host outside Docker. `run_denidin.sh dev`/`prod` and `run_morning_mcp.sh dev`/`prod` become thin wrappers around `docker compose -f docker-compose.<env>.yml up -d <service>` (stop scripts wrap `stop`/`down`). Consequence: today's PID-file/nohup single-instance-enforcement logic is retired, not ported — Docker itself prevents/no-ops a duplicate `up` of a running service. Consequence: ngrok can no longer run as a host process launched by the run script — it must run *inside* the morning-mcp-app container (binary present in the image, launched alongside the server process, using that environment's own authtoken from its config file).
- Q: How should status-file exchange between each environment's two containers work? → A: Per-environment bind-mounted shared directory (`./shared/mcp-status-dev`, `./shared/mcp-status-prod`), each mounted into exactly its own environment's two containers and never the other's — see FR-009 and `contracts/status-file-contract.md`.

### Session 2026-07-20 (WhatsApp number & role mapping)

- Q: There is one paid WhatsApp Business number and no plan to get a second. Green API instances are 1:1 with a linked WhatsApp number. How does dev denidin-app receive traffic? → A: **Manual instance hand-off.** Dev and prod denidin-app share the same real Green API instance credentials (`green_api_instance_id`/`green_api_token`) in their respective configs — there is no second instance. The operator manually ensures only one of `denidin-app-dev`/`denidin-app-prod` is actually running at a time whenever real WhatsApp traffic could arrive (stop prod, then start dev to test live; stop dev, restart prod afterward). **Important correction to Success Criteria**: `GreenAPIBot` **polls** Green API for notifications (not a pushed webhook) — if both containers ran concurrently against the same instance, they would race to consume the same notification queue and messages would be nondeterministically split between them. SC-001 ("all four run concurrently with zero conflicts") therefore holds for containers/process-level isolation, but real WhatsApp message delivery is only safe to one denidin-app environment at a time; this is a documented operational rule, not a bug the software prevents.
- Q: With a single real tester and no second number, how are godfather (AH in prod) and admin (ylevy in prod) roles distinguished in dev? → A: **Operator-switchable single role**, no synthetic/fake numbers. Real phone numbers: AH = `972506205541`, ylevy = `972522968679`. Prod is fixed: `godfather_phone` = `972506205541` (AH), `admin_phones` = `["972522968679"]` (ylevy). Dev has no fixed mapping for ylevy's number — instead, `config.dev.json` is edited by the operator to place `972522968679` in *either* `godfather_phone` *or* `admin_phones` (never both at once), and `denidin-app-dev` is restarted to pick up the change, whenever the operator wants to switch which role they're testing as. Mutual exclusivity (only one role active for that number at a time) is an operator discipline, not software-enforced — see FR-015.

## User Stories Reference

**NOTE**: Complete user stories are defined in **`user-stories.md`** (same directory). This spec's Requirements section is the authoritative source for FR identifiers; `user-stories.md` is the authoritative source for Given-When-Then acceptance criteria.

## Terminology Glossary

- **Environment (env)**: One of `dev` or `prod`. An environment is a fully independent runtime identity for an app — its own config file, data root, Docker container, port(s), log file, and (for morning-mcp-app) in-container ngrok tunnel + status file.
- **denidin-app instance**: One running copy of denidin-app scoped to a single environment (`denidin-app-dev` or `denidin-app-prod`).
- **morning-mcp-app instance**: One running copy of morning-mcp-app scoped to a single environment (`morning-mcp-app-dev` or `morning-mcp-app-prod`).
- **Env pairing**: The rule that a denidin-app instance's MCP tool must resolve, at runtime, to the morning-mcp-app instance of the *same* environment — never the other one.
- **Morning sandbox**: Green Invoice's non-production API host (`sandbox.d.greeninvoice.co.il`) — used only by the dev environment.
- **Morning production**: Green Invoice's real API host — used only by the prod environment.

## Technology Choices

- **Ngrok account separation**: Two distinct ngrok accounts/authtokens (one per environment), each on the free tier, each running exactly one tunnel at a time — chosen over a single-account multi-tunnel setup because the free tier only supports one online tunnel per account, and separate accounts also give hard fault isolation (a dev tunnel/quota issue cannot affect prod).
- **Config selection**: Environment-specific config files (`config.dev.json` / `config.prod.json`) per app — no environment variables, per CONSTITUTION.md's no-env-var rule.
- **Data root reuse**: denidin-app's existing `test_data/` directory is renamed to `dev_data/` and repurposed as the persistent dev-environment data root. Pytest gets its own separate ephemeral data root (not `dev_data/`), so test runs can never disturb dev's live session/memory state.
- **Execution model**: Containers only. No app process (denidin-app, morning-mcp-app, or ngrok) ever runs directly on the host outside Docker; run/stop scripts are thin wrappers around `docker compose` for the relevant environment's compose file.

## User Scenarios & Testing *(mandatory)*

See `user-stories.md` for the five prioritized user stories (P1: simultaneous operation, P1: MCP env-pairing/no-cross-boundary, P2: at-a-glance operator distinguishability, P2: shared OpenAI key / split Morning credentials, P2: operator-switchable role testing in dev) and their edge cases.

### Edge Cases

- What happens if the operator starts two instances of the *same* environment for the *same* app twice? → Docker itself prevents a true duplicate (a second `up` recreates/no-ops the existing container rather than running two).
- What happens if dev's ngrok free-tier tunnel URL rotates on restart? → dev denidin-app must re-discover the new URL via status-file polling, independently of prod.
- What happens if the dev morning-mcp-app's ngrok account/authtoken is invalid or exhausted? → dev denidin-app's MCP tool degrades gracefully; prod is unaffected (separate ngrok account, separate container).
- What happens if someone edits dev config and accidentally points it at the production Morning `api_url` or a prod ngrok tunnel? → out of scope for automated prevention; config examples/docs must make the sandbox-vs-prod distinction unmistakable.
- What happens if both `denidin-app-dev` and `denidin-app-prod` are started at the same time while both hold the same real Green API credentials? → Software does not prevent this (both containers can start fine), but it is operationally unsafe: `GreenAPIBot` polls for notifications, so both would race to consume the same real-message queue and split traffic nondeterministically. This is documented as an operator rule (see Clarifications, WhatsApp session 2026-07-20), not enforced in code.
- How is admin role tested in dev when the operator has only one real WhatsApp number? → The operator edits `config.dev.json` to move `972522968679` (ylevy) into `admin_phones` (out of `godfather_phone`) and restarts `denidin-app-dev`; real WhatsApp messages from that number then resolve to ADMIN until the operator switches it back.
- What happens if the operator forgets to remove `972522968679` from the field it's leaving and it ends up in both `godfather_phone` and `admin_phones` simultaneously? → Not software-prevented; `UserManager`'s existing ADMIN > GODFATHER precedence means it resolves to ADMIN. The operator is expected not to do this (single source of truth for "current test role"), per FR-015.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each app (denidin-app, morning-mcp-app) MUST support two independent runtime environments, `dev` and `prod`, each with its own config file (`config.dev.json` / `config.prod.json`), never sharing a config file between environments.
- **FR-002**: Both environments of both apps MUST be startable and runnable simultaneously on the same machine, each as its own Docker container, without port or data conflicts between environments. (Exception: `denidin-app-dev`/`denidin-app-prod` specifically — see FR-014's one-at-a-time real-traffic rule, which overrides "simultaneous" for that pair only.)
- **FR-003**: Duplicate-start prevention is handled by Docker itself (`docker compose up` on an already-running service is a no-op/recreate, never a second concurrent instance) — no host-level PID-file mechanism is needed or should be built for this feature; the existing PID-file logic in `run_denidin.sh`/`run_morning_mcp.sh` is retired as part of this change, not ported into the containers.
- **FR-004**: Each environment's container MUST write to its own log file(s) (via its own mounted `logs/` volume), distinguishable by filename/path, so an operator can identify an environment from its logs alone without reading config.
- **FR-005**: denidin-app's dev environment MUST use `dev_data/` (renamed from the current `test_data/`) as its `data_root`, mounted into the dev container as a persistent volume; denidin-app's prod environment MUST use the current production `data/` data_root. Pytest continues to run outside these containers (as today) but MUST be repointed at its own separate ephemeral data root distinct from `dev_data/`, so test runs can never disturb the persistent dev environment's live state.
- **FR-006**: morning-mcp-app's dev environment MUST use Morning **sandbox** API credentials and the sandbox `api_url`; morning-mcp-app's prod environment MUST use Morning **production** API credentials and the production `api_url`, each from its own environment-specific config file.
- **FR-007**: Both denidin-app environments (dev and prod) MUST use the same production OpenAI API key and model configuration — no OpenAI sandbox exists, so no separation is required for OpenAI-related fields.
- **FR-008**: Each morning-mcp-app environment's container MUST run its own ngrok tunnel **inside the container** (ngrok binary present in the image, launched alongside the server process), under its own, separate ngrok account/authtoken (two accounts total, provisioned by the operator and supplied via that environment's config file), so dev and prod tunnels never depend on shared ngrok quota, credentials, or a host-level ngrok process.
- **FR-009**: Each morning-mcp-app environment MUST publish its live tunnel URL to its own environment-scoped status file (e.g. `morning_mcp_status.dev.json` / `morning_mcp_status.prod.json`). This file MUST be exchanged between the two same-environment containers via an environment-scoped shared bind-mounted directory (e.g. `./shared/mcp-status-dev` mounted into both `morning-dev` and `denidin-dev`; `./shared/mcp-status-prod` mounted into both `morning-prod` and `denidin-prod`, at the same in-container path each side) — extending the existing single shared `./shared/mcp-status` mount pattern from today's `docker-compose.yml` into one such directory per environment. A dev-scoped shared directory MUST NOT be mounted into any prod container, and vice versa, so cross-environment status-file access is structurally impossible, not just discouraged by config.
- **FR-010**: Each denidin-app environment MUST be configured to read only the status file (and therefore only the tunnel/MCP endpoint) belonging to its own environment's morning-mcp-app instance — a dev denidin-app instance MUST NOT be able to resolve or call a prod morning-mcp-app instance's MCP endpoint, and vice versa.
- **FR-011**: `run_denidin.sh`/`stop_denidin.sh` and `run_morning_mcp.sh`/`stop_morning_mcp.sh` MUST take the environment as a positional argument (`dev` or `prod`) and act as thin wrappers around the corresponding `docker compose -f docker-compose.<env>.yml` command for that app's service — they MUST NOT start a local (non-containerized) long-lived process under any circumstance.
- **FR-012**: Docker Compose configuration MUST be split into `docker-compose.dev.yml` (denidin-dev + morning-dev services) and `docker-compose.prod.yml` (denidin-prod + morning-prod services), so each environment can be built/deployed/restarted as a unit fully independently of the other.
- **FR-013**: Config example files (`config.example.json`) MUST be updated or duplicated (e.g. `config.dev.example.json` / `config.prod.example.json`) so the sandbox-vs-production distinction for Morning credentials is unmistakable to anyone provisioning a new environment.
- **FR-014**: Unlike Morning credentials, `green_api_instance_id`/`green_api_token` MUST be identical (the same real value) in `config.dev.json` and `config.prod.json` — there is one paid WhatsApp Business number and one Green API instance, shared by both environments. Documentation (config examples, README) MUST state explicitly that only one of `denidin-app-dev`/`denidin-app-prod` should be actively running whenever real WhatsApp traffic could arrive, since `GreenAPIBot` polls for notifications and concurrent polling against the same instance would nondeterministically split real messages between the two environments.
- **FR-015**: Role-to-phone mapping MUST support independent role testing in dev without a second WhatsApp number, using only real numbers (no synthetic/placeholder phone strings): prod's `godfather_phone` MUST be `972506205541` (AH) and prod's `admin_phones` MUST include `972522968679` (ylevy) — this mapping is fixed and does not change. Dev's config MUST place `972522968679` (ylevy) in *exactly one* of `godfather_phone` or `admin_phones` at any given time (never both simultaneously) — which one is an operator-editable choice, switched by editing `config.dev.json` and restarting `denidin-app-dev`, whenever the operator wants to test as the other role. Enforcing "never both at once" is an operator discipline documented in config comments/README, not a software-enforced constraint (no new validation code is required — `UserManager`'s existing precedence logic would simply resolve to ADMIN if both were ever set, per its existing ADMIN > GODFATHER precedence).

### Key Entities

- **Environment config**: Per-app, per-environment config file — same schema as today's `config.json`, differentiated only by values (data root, Morning host/credentials, ngrok authtoken, ports, status-file path).
- **Status file**: Per-environment file published by morning-mcp-app with the live tunnel URL and status (`running` / `not running`), polled by the matching denidin-app environment.
- **Shared status volume**: Per-environment bind-mounted directory (e.g. `./shared/mcp-status-dev`, `./shared/mcp-status-prod`) mounted into exactly the two same-environment containers, carrying the status file between them — the sole channel by which a denidin-app container learns its paired morning-mcp-app container's tunnel URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four instances (denidin-app-dev, denidin-app-prod, morning-mcp-app-dev, morning-mcp-app-prod) can be started concurrently on one machine, each as its own Docker container, with zero port or data conflicts. (Caveat: this covers process/container-level isolation only — per FR-014, `denidin-app-dev` and `denidin-app-prod` share one real Green API instance, so concurrently *polling real WhatsApp traffic* on both is an operator-avoided scenario, not something the containers structurally prevent.)
- **SC-002**: 100% of MCP calls originating from dev denidin-app resolve to dev morning-mcp-app (sandbox Morning), and 100% from prod resolve to prod morning-mcp-app (production Morning) — verified by test/manual audit, with zero observed cross-environment calls.
- **SC-003**: An operator can identify which environment any given running process, log line, or status file belongs to within a few seconds, using only the filename/process name — no need to open config files.
- **SC-004**: Stopping or restarting one environment (e.g. dev) never disrupts the other environment's (prod's) running process, data, or active ngrok tunnel.
