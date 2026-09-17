# Quickstart: Clients Management UI in Webapp

## Local dev (no Docker)

```bash
cd apps/webapp
./run_webapp.sh host   # backend :8100, frontend :5173, live-reload
```

Open http://localhost:5173, log in, and the two tabs — "ארועים" and "לקוחות" — should
appear in the header nav. Switching tabs must not trigger a full page reload.

## Verifying the Clients tab end-to-end

1. Ensure `apps/webapp/backend/config/config.dev.json` has its own real Morning
   sandbox credentials (`api_key_id`/`api_key_secret`/`api_url`) filled in — the
   Clients tab talks to Morning directly and does **not** need `morning-mcp-app`
   running at all.
2. Load the "לקוחות" tab — it should show the same clients Morning's dev sandbox knows
   about, reconciled against whatever ledger events exist under the dev `data_root`.
3. Edit a comment inline (UAT-2) — confirm it persists to
   `apps/denidin-app/dev_data/clients/client_comments.json` (or the equivalent
   env-scoped path the config points at) and survives a refresh.
4. Use the alias-mapping UI on an unmatched name (UAT-3) — confirm
   `client_mapping.json` updates and the next `GET /api/clients` resolves it.

## Tests

```bash
cd apps/webapp/backend && python3 -m pytest tests/ -v --tb=short
cd apps/webapp/e2e && npx playwright test clients.spec.ts
```
