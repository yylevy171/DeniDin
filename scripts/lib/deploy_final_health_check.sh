#!/bin/bash
# Shared final-health verification for scripts/deploy_release.sh and
# scripts/deploy_release_single.sh (bugfix-076, 2026-09-07).
#
# Real incident (2026-09-07, live prod): both deploy scripts' per-app "final check" for
# denidin-app used to be `docker logs --tail N | grep "[vVERSION]"` - a log line that prints in
# the first second of denidin.py's startup, long before its health server actually binds (real
# startup work - SessionManager/LedgerEventManager init, then a synchronous, network-bound
# accounting-reconciliation sweep making a real OpenAI+Morning-MCP call - was measured taking
# ~3m23s total before the port opened). That grep passed almost immediately, both deploy scripts
# reported "confirmed live," and denidin-app was actually unreachable (connection refused/reset)
# for several more minutes with nothing watching for it. bugfix-076 also reorders denidin.py's
# own startup to bind the health server FIRST (see denidin.py's __main__ block) - this file is
# the other half of that same fix: replace the log-grep with a REAL /health check, reusing
# scripts/health_monitoring/verify.py, the single source of truth
# scripts/run_all_and_verify_healthy.sh's own post-start polling already uses (status=="ok" in
# the parsed body, not just HTTP 200 - see verify.py's own module docstring). Generous grace
# period (matches run_all_and_verify_healthy.sh's own GRACE_SECONDS=300) since even with the
# startup reorder, a real cold boot's OpenAI/Morning-tunnel/ChromaDB connectivity checks can
# still take real time.
#
# Version confirmation (which app/image actually got deployed) stays a SEPARATE, fast log-grep
# check in both callers, run right after container-up confirmation - this file only replaces the
# HEALTH half of the old combined check, not the version-image half.
#
# Requires REPO_ROOT already set by the caller (both deploy scripts already do this).

# Overridable via env var (test-only seam - scripts/tests/conftest.py's scratch fixtures pass a
# short grace period so tests don't have to wait out the real 300s default; no real caller ever
# needs to set these).
DEPLOY_HEALTH_GRACE_SECONDS="${DEPLOY_HEALTH_GRACE_SECONDS:-300}"
DEPLOY_HEALTH_POLL_INTERVAL="${DEPLOY_HEALTH_POLL_INTERVAL:-10}"

# deploy_final_health_check_local <env> <check_denidin:0|1> <check_morning:0|1>
# Runs verify.py directly, in this checkout - REPO_ROOT already IS the deploy directory for the
# local path (dev, or prod with --local).
deploy_final_health_check_local() {
    local env="$1" check_denidin="$2" check_morning="$3"
    # shellcheck source=/dev/null
    source "$REPO_ROOT/scripts/health_monitoring/prober_paths.sh"
    local args=()
    if [ "$check_denidin" -eq 1 ]; then
        args+=(--denidin-health-url "$(prober_denidin_health_url "$env")")
    fi
    if [ "$check_morning" -eq 1 ]; then
        args+=(--morning-health-url "$(prober_morning_health_url "$env")")
    fi
    local elapsed=0
    echo "== Waiting up to ${DEPLOY_HEALTH_GRACE_SECONDS}s for ${env} to report genuinely healthy (real /health check, local) =="
    while [ "$elapsed" -lt "$DEPLOY_HEALTH_GRACE_SECONDS" ]; do
        if python3 "$REPO_ROOT/scripts/health_monitoring/verify.py" "${args[@]}" --log-file "$(prober_verify_log_file "$env")"; then
            echo "✅ ${env} is genuinely healthy (real /health check passed, took ~${elapsed}s)."
            return 0
        fi
        sleep "$DEPLOY_HEALTH_POLL_INTERVAL"
        elapsed=$((elapsed + DEPLOY_HEALTH_POLL_INTERVAL))
    done
    echo "🚨 ${env} did not report genuinely healthy within ${DEPLOY_HEALTH_GRACE_SECONDS}s (real /health check never passed) - see logs/health_monitoring/${env}/verify.log for the exact per-check failures." >&2
    return 1
}

# deploy_final_health_check_remote <remote_host> <remote_deploy_dir> <env> <check_denidin:0|1> <check_morning:0|1>
# Requires remote_run() already defined by the caller (see scripts/windows_prod/_wsl_ssh.sh) and
# the ops-scripts bundle (which includes verify.py + prober_paths.sh) already unpacked on the
# remote box - both deploy scripts already guarantee this before this function is ever called.
deploy_final_health_check_remote() {
    local remote_host="$1" remote_deploy_dir="$2" env="$3" check_denidin="$4" check_morning="$5"
    local args=""
    if [ "$check_denidin" -eq 1 ]; then
        args="${args} --denidin-health-url \"\$(prober_denidin_health_url ${env})\""
    fi
    if [ "$check_morning" -eq 1 ]; then
        args="${args} --morning-health-url \"\$(prober_morning_health_url ${env})\""
    fi
    local remote_cmd="REPO_ROOT=\"\$HOME/${remote_deploy_dir}\"; source \"\$REPO_ROOT/scripts/health_monitoring/prober_paths.sh\"; python3 \"\$REPO_ROOT/scripts/health_monitoring/verify.py\"${args} --log-file \"\$(prober_verify_log_file ${env})\""
    local elapsed=0
    echo "== Waiting up to ${DEPLOY_HEALTH_GRACE_SECONDS}s for ${env} to report genuinely healthy (real /health check, ${remote_host}) =="
    while [ "$elapsed" -lt "$DEPLOY_HEALTH_GRACE_SECONDS" ]; do
        if remote_run "$remote_cmd"; then
            echo "✅ ${env} is genuinely healthy on ${remote_host} (real /health check passed, took ~${elapsed}s)."
            return 0
        fi
        sleep "$DEPLOY_HEALTH_POLL_INTERVAL"
        elapsed=$((elapsed + DEPLOY_HEALTH_POLL_INTERVAL))
    done
    echo "🚨 ${env} did not report genuinely healthy on ${remote_host} within ${DEPLOY_HEALTH_GRACE_SECONDS}s (real /health check never passed) - see logs/health_monitoring/${env}/verify.log on ${remote_host} for the exact per-check failures." >&2
    return 1
}
