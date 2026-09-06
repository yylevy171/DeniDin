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

# 2026-09-06 fix: the HOST-reachable port for a service is NOT the same
# thing as the app's own config.<env>.json port field, and must never be
# resolved from it - config.json's port is the container's *internal*
# listen port, which stays identical across dev/prod by design (the two
# environments are otherwise-isolated containers, not two ports on one
# process), while the HOST port they're published under differs per env
# purely via docker-compose.<env>.yml's own `ports:` mapping (e.g.
# morning-mcp-app: container port 8000 in both envs, published as host
# 8000 for dev / host 8001 for prod, so dev+prod can run concurrently
# without colliding - see docker-compose.prod.yml). The old
# config.json-based resolution was silently wrong for morning-mcp-app prod
# (it would have resolved to dev's own host port 8000) and made
# denidin-app's health check entirely unreachable in both envs (no `ports:`
# entry existed for it at all until this fix) - the prober's escalation
# logic then saw denidin-app as permanently "unhealthy" and soft-restarted
# it in an endless ~3-minute loop, confirmed live against a real dev
# deploy. The compose file's own `ports:` mapping is the only true source
# of what's actually reachable from the host, so that's what's parsed here
# instead - config.json is no longer consulted for this at all.
_prober_host_port() {
    local env="$1" service="$2"
    local compose_file="${REPO_ROOT}/docker/docker-compose.$env.yml"
    awk -v svc="  ${service}:" '
        $0 == svc { in_service = 1; next }
        in_service && /^  [A-Za-z]/ { in_service = 0 }
        in_service && /^    ports:/ { in_ports = 1; next }
        in_ports && (/^[[:space:]]*#/ || /^[[:space:]]*$/) { next }
        in_ports && /^      - / {
            line = $0
            gsub(/^      - ["'"'"']?/, "", line)
            gsub(/["'"'"']?[[:space:]]*$/, "", line)
            split(line, parts, ":")
            print parts[1]
            exit
        }
        in_ports { in_ports = 0 }
    ' "$compose_file"
}

prober_denidin_health_url() {
    local env="$1"
    local port
    port="$(_prober_host_port "$env" "denidin-app-$env")"
    echo "http://127.0.0.1:${port}/health"
}

prober_morning_health_url() {
    local env="$1"
    local port
    port="$(_prober_host_port "$env" "morning-mcp-app-$env")"
    echo "http://127.0.0.1:${port}/health"
}
