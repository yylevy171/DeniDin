# Quickstart: Morning Client-Name Cache

## Enabling it

1. In `apps/morning-mcp-app/config/config.dev.json` (or `.prod.json`), set:
   ```json
   "feature_flags": { "enable_mcp_server": true, "morning_cache_enabled": true }
   ```
2. Rebuild/restart that environment: `./stop_morning_mcp.sh dev && ./run_morning_mcp.sh dev`
   (per CLAUDE.md — code changes here have no effect on an already-running container).
3. Every `resolve_client_name` call now checks `data/client_cache.db` first. First call for
   any given client is still a live Morning round-trip (cache miss, then write-through);
   every subsequent call for that same exact name is served from the cache.

## Verifying it's working

- `apps/morning-mcp-app`'s own audit log (`audit.py`, bugfix-036 pattern) — a cache-hit
  resolution logs distinctly from a live one (exact log shape decided at
  `speckit.tasks`/implementation).
- Manually: call `resolve_client_name` twice in a row for the same known client via the
  live tunnel (or an integration test) — the second call should complete with no Morning
  API traffic observed.

## Running the acceptance tests (once implemented)

- **Phase 1.a** (`apps/morning-mcp-app/tests/integration/`, no AI, real Morning sandbox):
  `python3 -m pytest tests/integration/test_client_cache_latency.py -v` (exact filename
  TBD at tasks time).
- **Phase 1.b** (`apps/denidin-app/tests/billed/`, real AI): run via
  `scripts/run_single_test.sh "tests/billed/test_client_cache_full_cycle.py::..."` — billed,
  no approval gate needed per CLAUDE.md.
- **Phase 2** (sanity regression): included in `./scripts/run_sanity.sh`'s billed subset
  once added, per the sanity-suite conventions (`@pytest.mark.sanity`).
- **Phase 3** (85% hit-rate proof): run `./scripts/run_sanity.sh` (or
  `run_sanity_parallel.sh`) with `morning_cache_enabled: true` in `config.test.json`, then
  check the hit-rate measurement/log this feature adds against the sanity run.

## Disabling / rollback

Flip `morning_cache_enabled` back to `false` and restart — the code path reverts to
byte-for-byte pre-feature behavior (CONSTITUTION §VI). No data migration needed;
`data/client_cache.db` is simply left unread until re-enabled.
