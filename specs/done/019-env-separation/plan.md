# Implementation Plan: Dev/Prod Environment Separation

**Branch**: `019-env-separation` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-env-separation/spec.md`

---

**IMPORTANT**: This plan MUST comply with:
- **CONSTITUTION.md** (§I-III): NO environment variables, UTC timestamps mandatory, Git workflow (feature branches + merge commits)
- **METHODOLOGY.md** (§II, IV, VII): Template structure, Phased planning, Integration Contracts (mandatory for multi-component features)

---

## Summary

Split both `denidin-app` and `morning-mcp-app` into fully isolated `dev` and `prod` runtime environments so all four (app × env) combinations can run concurrently on one machine, exclusively as Docker containers. Each environment gets its own config file, data root, log path, and (for morning-mcp-app) its own ngrok account/tunnel running inside the container. Environment pairing (dev-denidin ↔ dev-morning, prod-denidin ↔ prod-morning) is enforced structurally via per-environment shared bind-mounted status-file volumes — a dev container is never given the mount that would let it see prod's tunnel URL, and vice versa. OpenAI credentials stay identical across environments (no OpenAI sandbox exists); Morning credentials/API host differ (sandbox vs. production). Run/stop tooling becomes a thin `docker compose` wrapper, retiring today's host-level PID-file/nohup process management entirely.

**Known constraint — not symmetric with the above**: `denidin-app-dev` and `denidin-app-prod` are *not* fully independent like the rest of the environment pairs. There is one paid WhatsApp Business number and one Green API instance (no sandbox tier), so `config.dev.json` and `config.prod.json` for denidin-app share the same real `green_api_instance_id`/`green_api_token` (FR-014). Since `GreenAPIBot` polls for notifications rather than receiving pushed webhooks, only one of the two denidin-app containers may be actively running whenever real WhatsApp traffic could arrive — switching between them is a manual operator hand-off (stop one, start the other), not a concurrent-safe operation like every other pairing in this feature. Role mapping (godfather/admin) is correspondingly asymmetric too: prod's mapping is fixed (AH=godfather, ylevy=admin), while dev's is operator-switchable for the single real tester (FR-015). See spec.md's "Session 2026-07-20 (WhatsApp number & role mapping)" Clarifications and `quickstart.md`'s hand-off procedure for full detail.

## Technical Context

**Language/Version**: Python 3.11 (denidin-app), Python 3.10+ (morning-mcp-app) — unchanged, no application code logic changes beyond config plumbing
**Primary Dependencies**: Docker + Docker Compose (v2, `docker compose` CLI), ngrok CLI (now baked into the morning-mcp-app image), existing app dependencies unchanged
**Storage**: Filesystem — per-environment `config.<env>.json`, per-environment data root (`data/` prod, `dev_data/` dev for denidin-app), per-environment log directories, per-environment shared bind-mounted status-file directories
**Testing**: pytest (unchanged; repointed at its own ephemeral data root, decoupled from `dev_data/` per Clarifications). This feature is operational/deployment tooling, not new app behavior — validated primarily via manual verification (start all 4 containers, exercise MCP round-trip per env) plus any existing test suite continuing to pass unmodified against its new ephemeral root.
**Target Platform**: Linux/macOS host running Docker Desktop or Docker Engine, four containers side by side
**Project Type**: Multi-app deployment/ops change — no new source-code project, touches Dockerfiles, compose files, run/stop scripts, and config loading/examples in both existing apps
**Performance Goals**: N/A (operational feature, not a performance-sensitive code path)
**Constraints**: Ngrok free tier: one online tunnel per account → hard requirement for two separate ngrok accounts/authtokens (one per environment), per Technology Choices in spec.md. No environment variables (CONSTITUTION §I) — environment selection is a positional script/compose argument, never `os.getenv`.
**Scale/Scope**: 2 apps × 2 environments = 4 containers; touches `apps/denidin-app/{Dockerfile,config/*,run_denidin.sh,stop_denidin.sh}`, `apps/morning-mcp-app/{Dockerfile,config/*,run_morning_mcp.sh,stop_morning_mcp.sh,src/denidin_mcp_morning/*}`, and repo-root `docker-compose.dev.yml`/`docker-compose.prod.yml` (replacing today's single `docker-compose.yml`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **§I No environment variables**: PASS — environment selection is a `docker compose -f docker-compose.<env>.yml` file choice / positional script arg, resolved to a specific `config.<env>.json` path; no new `os.getenv`/`os.environ` usage anywhere.
- **§I Config via `AppConfiguration`/dependency injection**: PASS — `config.dev.json`/`config.prod.json` load through the existing `AppConfiguration.from_file()` path unchanged; only the file selected differs. Note: for denidin-app specifically, `green_api_instance_id`/`green_api_token` are deliberately *identical* across the two files (FR-014, no config-schema implication, just a shared value) — this is the one field group in this feature that is intentionally not environment-differentiated.
- **§II UTC timestamps**: PASS — no new timestamp-producing code; existing UTC usage in status-file writers is preserved as-is (just repointed at per-env paths).
- **§III Git workflow**: PASS — working on `019-env-separation` feature branch, per-methodology PR flow at merge time.
- **§V Integration tests / no mocking**: PASS — no test behavior changes other than repointing pytest's data root; still zero mocking of internal components; still real sandbox/production Morning endpoints per environment.
- **§VI Feature flags for new behavior**: N/A / not applicable, by the same reasoning as the precedent in `specs/done/016-ai-model-selection` — this is deployment/ops tooling (Dockerfiles, compose files, run scripts, config file selection), not a new runtime code path inside the application that needs a rollback toggle. Nothing here changes byte-for-byte application behavior when "disabled"; there is no disabled state, only "which config/container you started."
- **§VI Error handling/retry**: PASS — no new network call sites introduced; ngrok-in-container startup reuses the existing retry/polling logic already in `run_morning_mcp.sh`, ported into the container entrypoint.
- **METHODOLOGY §VII Integration Contracts**: See below — the shared status-file volume between each environment's two containers is the one cross-component contract this feature introduces, documented explicitly.

**Result**: No violations requiring Complexity Tracking justification.

## Integration Contracts (METHODOLOGY §VII)

**Contract: morning-mcp-app → denidin-app tunnel discovery (per environment)**

- **Producer**: `morning-mcp-app-<env>` container, on ngrok tunnel startup/change, writes `{"status": "running"|"not running", "server_url": "<url>/mcp"|null, "updated_at": "<UTC ISO8601>"}` to the path configured by its own `config.<env>.json` → `mcp.status_file`.
- **Shared channel**: A per-environment bind-mounted host directory (`./shared/mcp-status-dev/` or `./shared/mcp-status-prod/`), mounted at the same in-container path into exactly the two same-environment containers (`morning-mcp-app-<env>` and `denidin-app-<env>`). Never mounted into the other environment's containers.
- **Consumer**: `denidin-app-<env>` container polls the file at the path configured by its own `config.<env>.json` → `mcp.morning_status_file`, exactly as `MorningMcpLocator` does today — no code change to the consumer's read logic, only to the path/mount it resolves against.
- **Failure mode**: If the file is missing/stale/`"not running"`, `denidin-app-<env>` degrades gracefully (existing behavior — Morning MCP tool simply isn't attached for that turn).

## Project Structure

### Documentation (this feature)

```text
specs/019-env-separation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — not created by /speckit.plan)
```

### Source Code (repository root)

```text
docker-compose.dev.yml           # denidin-dev + morning-dev services (NEW, replaces docker-compose.yml)
docker-compose.prod.yml          # denidin-prod + morning-prod services (NEW)
shared/
├── mcp-status-dev/              # bind mount shared by denidin-dev + morning-dev only
└── mcp-status-prod/             # bind mount shared by denidin-prod + morning-prod only

apps/denidin-app/
├── config/
│   ├── config.dev.json          # gitignored, sandbox-adjacent dev secrets, data_root=dev_data
│   ├── config.prod.json         # gitignored, production secrets, data_root=data
│   ├── config.dev.example.json  # NEW, committed
│   ├── config.prod.example.json # NEW, committed (replaces config.example.json)
│   └── config.test.json         # UPDATED: data_root repointed to its own ephemeral root, decoupled from dev_data/
├── dev_data/                     # renamed from test_data/ — persistent dev runtime state
├── logs/
│   ├── dev/                      # NEW: env-scoped, mounted only into denidin-app-dev
│   └── prod/                     # NEW: env-scoped, mounted only into denidin-app-prod
├── run_denidin.sh                # UPDATED: positional `dev`/`prod` arg, docker compose wrapper only
├── stop_denidin.sh               # UPDATED: same
└── Dockerfile                    # unchanged (already env-agnostic; config mounted at runtime)

apps/morning-mcp-app/
├── config/
│   ├── config.dev.json          # gitignored, Morning sandbox creds + dev ngrok authtoken
│   ├── config.prod.json         # gitignored, Morning production creds + prod ngrok authtoken
│   ├── config.dev.example.json  # NEW, committed
│   └── config.prod.example.json # NEW, committed (replaces config.example.json)
├── run_morning_mcp.sh             # UPDATED: positional `dev`/`prod` arg, docker compose wrapper only
├── stop_morning_mcp.sh            # UPDATED: same
├── Dockerfile                     # UPDATED: install ngrok CLI binary into the image
└── docker-entrypoint.sh           # NEW (or updated CMD): launches ngrok (using in-container config) alongside the FastMCP server process, replacing the ngrok-launch block currently in run_morning_mcp.sh
```

**Structure Decision**: No new top-level project — this is a deployment-layer change to the two existing apps plus repo-root compose/shared-volume config. denidin-app and morning-mcp-app remain independently buildable (per CLAUDE.md's existing constraint); the split compose files preserve that independence at the deploy layer too (`docker compose -f docker-compose.dev.yml up denidin-dev` never touches prod).

## Complexity Tracking

*No Constitution Check violations — table not needed.*
