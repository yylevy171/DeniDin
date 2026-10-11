# Implementation Plan: Monitoring & Alerting

**Feature ID**: 028-monitoring-and-alerting

## Approach

Two independent apps, two independent (but structurally identical) shared
modules - consistent with this repo's existing "no cross-app imports"
architecture rule. Each module is stdlib-only (no third-party dependencies)
specifically so its one-shot CLI mode can be invoked from `run_all.sh` on the
host without any venv-activation concerns (CLAUDE.md's clone/venv
confinement rules) - it never needs `jsonschema`, `requests`, `fastmcp`, or
any other installed package, just `json`/`urllib.request`/`pathlib`.

### `apps/morning-mcp-app/src/denidin_mcp_morning/health_check.py` (new)
Moved from `watchdog.py` (unchanged behavior, just relocated + made
importable): `fetch_health_environment(url)`, `resolve_status_path(...)`,
`external_tunnel_health(status_path)` (tri-state: not-attempted /
attempted-and-failed / succeeded, per the 2026-07-30 bugfix). Adds a CLI:
`python3 health_check.py --status-file PATH [--internal-url URL]
--expected-env dev|prod [--wait-seconds N]`. Exits 0 only if every check
that was actually attempted (status file present, `"running"`, has a
`server_url`; internal URL given) succeeded and reported `--expected-env`.

`watchdog.py` imports these three functions instead of defining its own
copies; its `main()` loop logic (ERROR/WARNING levels, mismatch teardown) is
unchanged.

### `apps/denidin-app/health_check.py` (new, top-level - mirrors watchdog.py's own location, not under src/)
Moved from `watchdog.py`: `read_own_environment(config_path)`,
`read_active_environment(active_env_path)`, and a new
`check_environment_consistency(own_env, active_env)` extracted from the
inline comparison that used to live directly in `main()`'s loop body. CLI:
`python3 health_check.py --config PATH --active-env-file PATH
[--expected-env dev|prod]`.

`watchdog.py` imports these instead of defining its own copies; loop
behavior unchanged.

### `scripts/run_all.sh`
After both `run_denidin.sh`/`run_morning_mcp.sh` calls: resolve
morning-mcp-app's actual host-mapped port via `docker compose port
morning-mcp-app-$ENV 8000` (not hardcoded - dev is 8000, prod is 8001 today,
but this asks the running compose project instead of assuming), then invoke
both health-check CLIs. Non-zero exit or failed check from either →
`run_all.sh` prints a clear failure and exits 1.

## Testing

- New `apps/morning-mcp-app/tests/unit/test_health_check.py` (moves the
  watchdog tests already written 2026-07-30 for the tri-state/URL-fix
  behavior, since that logic is relocating there) + one CLI-level test.
- New `apps/denidin-app/tests/unit/test_health_check.py` (no prior coverage
  existed for its watchdog logic either - same gap as morning-mcp-app had).
- `watchdog.py` (both apps) keeps no dedicated test (as before - it's a
  thin `main()` loop around the now-shared, now-tested functions); a quick
  import-and-signature smoke check is enough to confirm the refactor didn't
  break it.
- No expensive/E2E tests needed - this is host/script-level tooling, not a
  change to either app's request-handling code path.
