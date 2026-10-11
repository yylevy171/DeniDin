# User Stories: Monitoring & Alerting

**Feature ID**: 028-monitoring-and-alerting
**Created**: July 30, 2026

Per METHODOLOGY.md §I, these stories trace complete end-to-end flows from an
external entry point (a human running a script, or the watchdog's own
periodic loop) through system behavior to an observable result.

---

## US1 (P1): `run_all.sh` fails loudly when morning-mcp-app doesn't actually come up healthy

**Given** a human runs `./scripts/run_all.sh dev` (or `prod`) to start both apps
**When** `morning-mcp-app-<env>`'s container starts, but its tunnel never reports "running", or its internal `/health` reports a different environment than the one just started (e.g. a stale/wrong-environment container)
**Then** `run_all.sh` detects this via the same health-check logic `watchdog.py` uses internally (not a separate re-implementation) — polling the status file for up to a bounded window to absorb the tunnel's known startup lag
**And** if the check does not pass within that window, `run_all.sh` prints a clear failure message naming which check failed and exits non-zero
**And** the overall start is treated as failed, not as "containers are up so we're done"

**Acceptance Criteria**:
- The check logic invoked by `run_all.sh` is the same function(s) `watchdog.py` calls, imported from one shared module — not a duplicate implementation
- A genuinely healthy start (tunnel reports "running", internal + external `/health` both report the started environment) exits 0 with a clear success message
- A failed start (tunnel never comes up, or reports the wrong environment) exits non-zero with a message identifying which check failed

---

## US2 (P1): `run_all.sh` fails loudly when denidin-app's declared environment doesn't match what was just started

**Given** a human runs `./scripts/run_all.sh dev` (or `prod`)
**When** `denidin-app-<env>`'s container starts, but its own config's `environment` field doesn't match `shared/active_env.json` (or the environment just requested)
**Then** `run_all.sh` detects this via the same check `denidin-app`'s `watchdog.py` uses internally
**And** exits non-zero with a clear message, rather than reporting success

**Acceptance Criteria**:
- Uses the same shared function `watchdog.py` (denidin-app) calls - not a separate re-implementation
- `denidin-app` has no HTTP health endpoint (it's a polling bot, not a webhook receiver) - this check is explicitly limited to environment-consistency, not a functional liveness probe, per spec.md's clarification

---

## US3 (P2): `watchdog.py` (both apps) keeps working exactly as before, now backed by the shared module

**Given** either app's container is running normally
**When** its `watchdog.py` performs its periodic (30s) environment-mismatch check
**Then** behavior is unchanged from before this feature (same logging, same teardown-on-mismatch policy, same no-auto-restart) - the only change is that the check functions it calls now live in a shared, importable module instead of being defined inline in `watchdog.py` itself

**Acceptance Criteria**:
- No behavior change to `watchdog.py`'s own loop, logging levels, or teardown policy
- `watchdog.py` (morning-mcp-app) no longer defines its own copies of `_fetch_health_environment`/`_resolve_status_path`/`_external_tunnel_health_environment` - it imports them
- `watchdog.py` (denidin-app) no longer defines its own copies of `_read_own_environment`/`_read_active_environment`/the inline mismatch comparison - it imports them
- Existing + new unit tests for both shared modules pass; no regression in either app's existing test suite

---

## Out of Scope (per spec.md)

- Real-time alerting/paging to a human or external channel - no notification channel exists in this codebase to hook into
- Adding an HTTP health endpoint to denidin-app
- Any change to watchdog.py's teardown policy itself
- A new continuous/periodic monitor beyond watchdog.py's existing 30s loop
