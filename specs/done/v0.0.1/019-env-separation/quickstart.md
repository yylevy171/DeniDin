# Quickstart: Dev/Prod Environment Separation

## Prerequisites

- Docker + Docker Compose v2 installed.
- Two ngrok accounts (free tier is fine), each with its own authtoken — one for dev, one for prod.
- `apps/denidin-app/config/config.dev.json` and `config.prod.json` populated from the new `config.dev.example.json`/`config.prod.example.json` (Green API creds, OpenAI key — same key in both — Morning MCP shared secret matching the corresponding morning-mcp-app config).
- `apps/morning-mcp-app/config/config.dev.json` (Morning **sandbox** creds, dev ngrok authtoken) and `config.prod.json` (Morning **production** creds, prod ngrok authtoken) populated from their `.example.json` counterparts.

## Start morning-mcp-app for both environments (always safe to run together)

```bash
cd apps/morning-mcp-app && ./run_morning_mcp.sh dev
cd apps/morning-mcp-app && ./run_morning_mcp.sh prod
```

Verify: `docker compose -f docker-compose.dev.yml ps` shows `morning-mcp-app-dev` running, `docker compose -f docker-compose.prod.yml ps` shows `morning-mcp-app-prod` running; `./shared/mcp-status-dev/morning_mcp_status.dev.json` and `./shared/mcp-status-prod/morning_mcp_status.prod.json` each show `"status": "running"` with their own distinct live ngrok URL.

## Start denidin-app — ⚠️ one environment at a time only

**Both `config.dev.json` and `config.prod.json` carry the same real Green API instance credentials** (one paid WhatsApp Business number, no second instance available). `GreenAPIBot` polls Green API for notifications — running `denidin-app-dev` and `denidin-app-prod` concurrently would make both race to consume the same real-message queue and split traffic between them nondeterministically. **Never run both at the same time.** Normal operation is prod always up; dev is a deliberate, temporary hand-off:

```bash
# Normal state: prod is the one live to real WhatsApp traffic
cd apps/denidin-app && ./run_denidin.sh prod

# To test dev with real WhatsApp messages: hand off from prod to dev
cd apps/denidin-app && ./stop_denidin.sh prod
cd apps/denidin-app && ./run_denidin.sh dev

# ...test as needed (see "Verify isolation" below)...

# Hand back to prod when done
cd apps/denidin-app && ./stop_denidin.sh dev
cd apps/denidin-app && ./run_denidin.sh prod
```

Verify at each step: `docker compose -f docker-compose.<env>.yml ps` shows exactly one of `denidin-app-dev`/`denidin-app-prod` `Up` at any given time, never both.

## Verify isolation (the actual point of this feature)

1. With `denidin-app-prod` the one actively running, send a WhatsApp invoice command from AH's real number (prod's godfather); confirm the resulting invoice/client appears in Morning **production** only.
2. Hand off to dev (stop prod's denidin-app, start dev's, per above). Send the same command from ylevy's real number (dev's currently-configured role — godfather or admin, per `config.dev.json`); confirm it lands in the Morning **sandbox** only, never production.
3. Hand back to prod; confirm prod resumes cleanly and morning-mcp-app-prod's tunnel/status file were unaffected by the denidin-app hand-off the whole time (morning-mcp-app containers for both environments were never stopped).

## Run the test suite (unaffected by any of the above)

```bash
cd apps/denidin-app
python3 -m pytest tests/ -v --tb=short
```

Uses `config.test.json`'s own ephemeral data root — never touches `dev_data/`, so this can be run at any time regardless of whether the dev container is up.
