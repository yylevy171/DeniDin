#!/bin/bash
# Starts an environment (run_all.sh) and BLOCKS until it's actually confirmed
# healthy or a grace period expires (bugfix-043, 2026-09-07 fix).
#
# run_all.sh itself stays untouched as the simple building block it already
# is (docker compose up -d, nothing more) - this wraps it rather than
# changing its behavior, since other callers rely on it returning as soon as
# the containers are started. What was missing was a way to know whether
# that start actually SUCCEEDED (the app came up healthy) or FAILED (it
# never did) - a container merely existing/starting is not the same claim.
#
# This is what the health-monitoring prober now calls instead of run_all.sh
# directly (see prober.py's run_soft_restart) - a real incident (2026-09-07,
# live prod) showed that a bare `run_all.sh` return was mistaken by the
# calling scheduled task for "done", well before the app inside had finished
# booting - so the OS's own already-correct "don't start a new instance
# while one is already running" protection (Windows Task Scheduler's
# MultipleInstancesPolicy=IgnoreNew) never actually covered the boot window,
# and the next ~1-minute tick restarted the still-booting container out from
# under itself, repeatedly. Blocking here until health is confirmed (or the
# grace period is exhausted) closes that gap at its source, with no separate
# in-flight-tracking state needed anywhere else.
#
# Calls scripts/health_monitoring/verify.py DIRECTLY (2026-09-07 revision) -
# an earlier version of this fix went through a verify_healthy.sh shell
# wrapper in between; removed, since verify.py is already the single
# implementation both this script and prober.py (in-process, via a plain
# Python import) need, and the extra .sh layer added nothing.
#
# Usage: ./scripts/run_all_and_verify_healthy.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"  # this file lives at REPO_ROOT/scripts/ - prober_paths.sh needs the real repo root

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

# shellcheck source=/dev/null
source "$SCRIPT_DIR/health_monitoring/prober_paths.sh"

# How long a fresh start is allowed to take before this is reported as a
# failure - generous on purpose (a real prod cold boot, including OpenAI/
# ChromaDB/Green API/Morning-tunnel connectivity checks, has been observed
# to take longer than the 30s a much tighter deploy-verification poll used
# elsewhere in this repo assumed, which itself proved too short live).
GRACE_SECONDS=300
POLL_INTERVAL_SECONDS=10

"$SCRIPT_DIR/run_all.sh" "$ENV"

# webapp (Feature 068) - include it in the health gate only when its containers exist on this
# box/env (it's deployed independently, not present everywhere). Both containers checked
# independently (backend deep /health + frontend nginx /healthz). Same guard as
# run_prober_for_env.sh.
WEBAPP_VERIFY_ARGS=()
if docker inspect "$(prober_webapp_container "$ENV")" >/dev/null 2>&1; then
    WEBAPP_VERIFY_ARGS+=(--webapp-health-url "$(prober_webapp_health_url "$ENV")")
fi
if docker inspect "$(prober_webapp_frontend_container "$ENV")" >/dev/null 2>&1; then
    WEBAPP_VERIFY_ARGS+=(--webapp-frontend-health-url "$(prober_webapp_frontend_health_url "$ENV")")
fi

echo "== Waiting up to ${GRACE_SECONDS}s for $ENV to report healthy =="
elapsed=0
while [ "$elapsed" -lt "$GRACE_SECONDS" ]; do
    if python3 "$SCRIPT_DIR/health_monitoring/verify.py" \
        --denidin-health-url "$(prober_denidin_health_url "$ENV")" \
        --morning-health-url "$(prober_morning_health_url "$ENV")" \
        "${WEBAPP_VERIFY_ARGS[@]}" \
        --log-file "$(prober_verify_log_file "$ENV")"
    then
        echo "== $ENV is healthy (took ~${elapsed}s) =="
        exit 0
    fi
    sleep "$POLL_INTERVAL_SECONDS"
    elapsed=$((elapsed + POLL_INTERVAL_SECONDS))
done

echo "🚨 $ENV did not become healthy within ${GRACE_SECONDS}s grace period - reporting failure." >&2
exit 1
