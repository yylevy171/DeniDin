#!/bin/bash
# Pre-start guard for a docker compose service (bugfix-066, 2026-09-25). SOURCED by each app's
# run_*.sh right before its `docker compose up -d`, never run on its own:
#
#   source "$REPO_ROOT/scripts/lib/prepare_compose_service.sh"
#   prepare_compose_service "$SERVICE" "${COMPOSE_ARGS[@]}" || exit 1
#
# It does two things, both born from the 2026-09-25 prod outage (deploy of v0.7.6):
#
# 1. Refuses to start a service whose bind-mounted CONFIG paths are missing or the wrong type.
#    docker-compose.prod.yml bind-mounts ledger_recognition_prompt.md and
#    fee_agreement_templates/ from the box's deploy dir, where nothing had ever put them. Docker
#    does not fail on a missing bind source - it silently creates it as a root-owned EMPTY
#    DIRECTORY, and the file mount then dies with "not a directory: Are you trying to mount a
#    directory onto a file". That surfaced only as a container stuck in state `created`, with the
#    real error buried in `docker inspect`. Now the start aborts BEFORE Docker gets the chance,
#    naming each bad path. Rules, applied to every bind mount of the service whose source path
#    contains "/config/" (real config never auto-creates - unlike data/log dirs, which Docker
#    may legitimately create):
#      - source must exist;
#      - a source whose name has a file extension must be a regular file;
#      - a source without an extension must be a non-empty directory.
#    Any bind source WITH a file extension that is a directory is also rejected wherever it
#    lives (the exact "directory where a file belongs" shape Docker creates).
#
# 2. Removes containers of this service stuck in state `created` (never started). `compose up -d`
#    reuses such a container as-is, so a mount source that was wrong when it was created (and has
#    since been fixed on disk) keeps failing forever - Docker Desktop froze the stale mount into
#    it. A never-started container holds no data, so removing it is lossless.
#
# Returns 0 if the service is safe to start, 1 (with a clear message on stderr) otherwise.

prepare_compose_service() {
    local service="$1"
    shift
    local compose_args=("$@")

    # (2) never-started containers first - harmless, and independent of the mount check.
    local stale
    stale="$(docker compose "${compose_args[@]}" ps -a --status created -q "$service" 2>/dev/null || true)"
    if [ -n "$stale" ]; then
        echo "== Removing never-started (state 'created') container(s) of ${service} so compose recreates them fresh =="
        # shellcheck disable=SC2086
        docker rm -f $stale >/dev/null
    fi

    # (1) bind-source check, against the fully merged compose config (base + local override).
    local cfg
    if ! cfg="$(docker compose "${compose_args[@]}" config --format json 2>&1)"; then
        echo "ERROR: could not resolve the compose config for ${service}: ${cfg}" >&2
        return 1
    fi
    printf '%s' "$cfg" | python3 -c '
import json, os, sys

service = sys.argv[1]
cfg = json.load(sys.stdin)
svc = (cfg.get("services") or {}).get(service)
if svc is None:
    sys.exit(0)  # nothing to check (service not in this compose file)

problems = []
for vol in svc.get("volumes") or []:
    if vol.get("type") != "bind":
        continue
    src = vol.get("source") or ""
    tgt = vol.get("target")
    name = os.path.basename(src.rstrip("/"))
    has_ext = os.path.splitext(name)[1] != ""
    is_config = "/config/" in src or src.rstrip("/").endswith("/config")
    exists = os.path.lexists(src)
    if has_ext and exists and os.path.isdir(src):
        problems.append(f"{src} is a DIRECTORY but is mounted as a file ({tgt}) - remove it and put the real file there")
    elif is_config and not exists:
        problems.append(f"{src} does not exist (mounted at {tgt}) - Docker would create it as an empty root-owned directory")
    elif is_config and has_ext and not os.path.isfile(src):
        problems.append(f"{src} must be a regular file (mounted at {tgt})")
    elif is_config and not has_ext and os.path.isdir(src) and not os.listdir(src):
        problems.append(f"{src} is an EMPTY directory (mounted at {tgt}) - its contents were never shipped")

if problems:
    print(f"ERROR: refusing to start {service} - its bind-mounted config is not in place:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    print("  Only per-environment config (config.<env>.json) is mounted from the host and must be "
          "created on the box by hand; everything else under config/ is baked into the image.", file=sys.stderr)
    sys.exit(1)
' "$service"
}
