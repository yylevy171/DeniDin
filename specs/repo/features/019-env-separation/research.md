# Phase 0 Research: Dev/Prod Environment Separation

No `[NEEDS CLARIFICATION]` markers remain in the Technical Context — all ambiguities were resolved during `/speckit.specify`'s clarification session (see spec.md's Clarifications section). This document records the rationale/alternatives behind the key technical decisions already made, for future maintainers.

## Decision: ngrok runs inside the morning-mcp-app container, not on the host

- **Decision**: Bake the ngrok CLI binary into `apps/morning-mcp-app/Dockerfile`; launch it from the container's entrypoint/CMD alongside the FastMCP server process, using that environment's `mcp.ngrok_authtoken` from its own mounted `config.<env>.json`.
- **Rationale**: The user's explicit requirement is "no long-lived process runs local, only via docker." ngrok today is a host process spawned by `run_morning_mcp.sh`; keeping that would mean a non-containerized long-lived process, violating the requirement and reintroducing a shared-host-process surface between dev and prod (e.g. both writing to `~/.ngrok2/ngrok.yml` if not careful about isolation).
- **Alternatives considered**:
  - *ngrok as a sidecar container* (separate service in compose, sharing a network namespace with morning-mcp-app): rejected as needless extra complexity — one container per environment is simpler to reason about and there's no reuse benefit since each env's ngrok config is entirely different (separate account).
  - *ngrok on host, containers for the rest*: rejected — directly contradicts the explicit containers-only requirement, and doesn't solve dev/prod ngrok-process isolation any better than the in-container approach.

## Decision: Docker Compose split into `docker-compose.dev.yml` / `docker-compose.prod.yml`

- **Decision**: Two compose files, each with 2 services (its app pair), replacing today's single `docker-compose.yml`.
- **Rationale**: User's explicit choice (Q3, option B) — maps directly to "deploy dev" / "deploy prod" as independent units; matches existing app-level independence (each app is separately buildable) at the deploy layer.
- **Alternatives considered**: single compose file with 4 services (rejected — user wants environment-level deploy independence, and this file split makes accidentally running `docker compose up` with no explicit env impossible, since there is no unqualified `docker-compose.yml` anymore).

## Decision: PID-file/single-instance logic is retired, not ported

- **Decision**: `run_denidin.sh`/`run_morning_mcp.sh` drop their nohup+PID-file+`ps` duplicate-detection logic entirely once they become `docker compose` wrappers.
- **Rationale**: Docker Compose already prevents/no-ops concurrent duplicate starts of the same service (a repeated `up` recreates or attaches to the existing container, never runs two). Reimplementing PID-file logic on top of that would be redundant defensive code with no failure mode it actually prevents.
- **Alternatives considered**: Keep PID files as a "belt and suspenders" check inside the container entrypoint — rejected as unnecessary; no evidence Docker's own enforcement is insufficient, and CLAUDE.md/user guidance favor deleting no-longer-needed code over keeping unreachable-in-practice safety nets (precedent: `specs/done/v0.0.1/016-ai-model-selection`'s removal of an unreachable legacy-fallback field).

## Decision: pytest gets its own ephemeral data root, separate from `dev_data/`

- **Decision**: `config.test.json`'s `data_root` moves off the renamed `dev_data/` onto a new, separate ephemeral root (exact name TBD in Phase 1 data-model — e.g. `test_data/` retained as pytest's own root, distinct from the persistent `dev_data/`).
- **Rationale**: User's explicit choice (Q1, option B) — a pytest run must never be able to reset/pollute the dev environment's live session/memory state, and a long-running dev container must never have its persistent data wiped by an unrelated `pytest tests/` invocation on the same machine.
- **Alternatives considered**: Single shared root (option A) — rejected due to the data-corruption risk called out above.

## Decision: OpenAI credentials identical across dev/prod; Morning credentials split sandbox/production

- **Decision**: No change needed — carried straight from the spec's Technology Choices, since OpenAI has no sandbox tier and Morning already has both.
- **Rationale**: Given, not derived — external constraint (only one OpenAI API tier exists).
- **Alternatives considered**: N/A.
