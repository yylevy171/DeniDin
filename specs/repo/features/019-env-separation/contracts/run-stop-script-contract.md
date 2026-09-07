# Contract: Run/Stop Script CLI Surface

**Scope**: `apps/denidin-app/{run_denidin.sh,stop_denidin.sh}`, `apps/morning-mcp-app/{run_morning_mcp.sh,stop_morning_mcp.sh}`

## Invocation

```bash
./run_denidin.sh dev|prod
./stop_denidin.sh dev|prod
./run_morning_mcp.sh dev|prod
./stop_morning_mcp.sh dev|prod
```

- Missing or invalid environment argument → print usage and exit non-zero. No default environment (an operator must always be explicit about which environment they're touching, per User Story 3's "tell environments apart" requirement).

## Behavior

- `run_*.sh <env>` → `docker compose -f docker-compose.<env>.yml up -d <service-name>` for that app's service in that environment's compose file, then reports the resulting container status.
- `stop_*.sh <env>` → `docker compose -f docker-compose.<env>.yml stop <service-name>` (or `down`, scoped to just that service — never `down` the whole compose file, since the paired app's service lives in the same file and must be unaffected).
- Neither script starts, forks, or manages any local (non-containerized) process under any circumstance — no `nohup`, no PID file, no local `python3 -m ...` invocation. All prior host-process logic (single-instance PID-file check, host ngrok launch) is removed, not conditionally bypassed.

## Out of scope

- These scripts do not build images (`docker compose up -d` will build on first run if needed, per standard Compose behavior, but no explicit `docker compose build` step is added beyond that).
- Cross-environment orchestration (e.g. "start both dev and prod") is not a single-command feature — operator runs each script twice, once per environment, which is an intentional consequence of environment isolation being the point of this feature.
