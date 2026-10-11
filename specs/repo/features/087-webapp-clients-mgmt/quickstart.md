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
   about, reconciled against whatever ledger events exist under the dev
   `denidin_data_root` (read-only mount).
3. Edit a comment inline (UAT-2) — confirm it persists to
   `{webapp_data_root}/clients/client_comments.json` (a separate, webapp-owned
   writable root — never under `denidin_data_root`, which stays read-only; a single,
   non-env-namespaced folder, not a per-env split — corrected 2026-09-24) and
   survives a refresh. Seeded once from Rapaport's real live analyst files, not
   started empty (corrected 2026-09-23).
4. Use the alias-mapping UI on an unmatched name (UAT-3) — confirm
   `{webapp_data_root}/clients/client_mapping.json` updates and the next
   `GET /api/clients` resolves it.

## Tests

```bash
cd apps/webapp/backend && python3 -m pytest tests/ -v --tb=short
cd apps/webapp/e2e && npx playwright test clients.spec.ts
```
