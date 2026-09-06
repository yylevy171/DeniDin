#!/bin/bash
# Shared argument resolution for the prober (bugfix-043), sourced by both
# run_prober_for_env.sh (what the OS scheduler actually invokes on each tick)
# and stop_env.sh (which must archive the exact same state file the scheduled
# runs use - both MUST agree, or an admin stop would archive the wrong file
# and leave a stale one behind for the next bootstrap check to trip over).
#
# All paths/ports are derived deterministically from REPO_ROOT + <env> - no
# separate config of their own, so there is nothing here that can drift out
# of sync with itself the way this whole bugfix exists to prevent.

# Requires REPO_ROOT to already be set by the caller.

prober_state_file() {
    echo "${REPO_ROOT}/logs/health_monitoring/$1/state.json"
}

prober_log_file() {
    echo "${REPO_ROOT}/logs/health_monitoring/$1/prober.log"
}

# Container names are derived from the ACTUAL compose project name (the compose file's own
# `name:` field), never hardcoded as "denidin-<env>" - deploy_release.sh already derives
# PROJECT_NAME the same way (see its own `grep -m1 '^name:'` line), and a scratch/test compose
# file deliberately uses a distinct project name specifically so it can never collide with a
# real running dev/prod environment on the same machine (see scripts/tests/conftest.py's
# scratch_deploy_repo docstring) - hardcoding the real repo's own project name here would defeat
# that isolation the moment this script ran against a scratch environment.
_prober_project_name() {
    local compose_file="${REPO_ROOT}/docker/docker-compose.$1.yml"
    grep -m1 '^name:' "$compose_file" | sed 's/^name:[[:space:]]*//'
}

prober_denidin_container() {
    echo "$(_prober_project_name "$1")-denidin-app-$1-1"
}

prober_morning_container() {
    echo "$(_prober_project_name "$1")-morning-mcp-app-$1-1"
}

# Reads config.<env>.json's health_check_port / mcp.port via python3 (already
# a hard dependency of this repo, no new tooling) rather than duplicating the
# port numbers as bash literals - these are real app config, not ops-script
# constants, and must never drift from what the app itself is actually bound
# to.
prober_denidin_health_url() {
    local env="$1"
    local config_path="${REPO_ROOT}/apps/denidin-app/config/config.${env}.json"
    local port
    port="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('health_check_port', 0))" "$config_path")"
    echo "http://127.0.0.1:${port}/health"
}

prober_morning_health_url() {
    local env="$1"
    local config_path="${REPO_ROOT}/apps/morning-mcp-app/config/config.${env}.json"
    local port
    port="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('mcp', {}).get('port', 8000))" "$config_path")"
    echo "http://127.0.0.1:${port}/health"
}
