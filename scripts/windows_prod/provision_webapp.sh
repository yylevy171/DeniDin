#!/usr/bin/env bash
# ONE-TIME: teach the Windows prod box about the Feature 068 webapp, so
# `scripts/deploy_release.sh webapp prod <version>` can deploy to it.
#
# The box's deploy dir (~/denidin-prod) is NOT a git checkout - it's a curated
# file tree, populated once during Feature 035 setup. This script adds the
# files the two new webapp compose services need:
#   - docker/docker-compose.prod.yml            (branch version, with webapp-* services;
#                                                verified append-only vs. the running one)
#   - apps/webapp/backend/config/config.prod.container.json   (no secrets)
#   - apps/webapp/backend/auth/password.hash                  (the login hash)
#   - a webapp-backend-prod block appended to docker/docker-compose.prod.local.yml
#     (so its read-only denidin-data mount uses the native Windows prod-data path,
#      same reason denidin-app-prod's data mount does)
#
# Idempotent. Non-disruptive: copies files, never starts / stops / rebuilds /
# recreates a container. The running denidin-app-prod / morning-mcp-app-prod
# are untouched.
#
# Usage (from the Mac, repo root):
#   ./scripts/windows_prod/provision_webapp.sh [ssh-host-alias] [deploy-dir-name]

set -euo pipefail

SSH_HOST="${1:-denidin-winprod}"
DEPLOY_DIR="${2:-denidin-prod}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_wsl_ssh.sh"
run() { wsl_ssh_run "$SSH_HOST" "$1"; }

COMPOSE_SRC="docker/docker-compose.prod.yml"
CONFIG_SRC="apps/webapp/backend/config/config.prod.container.json"
PWHASH_SRC="apps/webapp/backend/auth/password.hash"

for f in "$COMPOSE_SRC" "$CONFIG_SRC" "$PWHASH_SRC"; do
    [ -f "$f" ] || { echo "ERROR: missing local file: $f" >&2; exit 1; }
done

echo "== Preflight =="
run 'echo reachable' >/dev/null || { echo "ERROR: cannot reach $SSH_HOST." >&2; exit 1; }
run "cd ~/$DEPLOY_DIR; printf 'compose webapp lines (before): '; grep -c webapp docker/docker-compose.prod.yml || true; printf 'local.yml already patched: '; grep -q webapp-backend-prod docker/docker-compose.prod.local.yml && echo yes || echo no"

echo
echo "== [1/4] Shipping files to $SSH_HOST (Windows home) =="
scp -o BatchMode=yes -o ConnectTimeout=10 "$COMPOSE_SRC" "$SSH_HOST:~/_webapp_compose.prod.yml"
scp -o BatchMode=yes -o ConnectTimeout=10 "$CONFIG_SRC"  "$SSH_HOST:~/_webapp_config.prod.container.json"
scp -o BatchMode=yes -o ConnectTimeout=10 "$PWHASH_SRC"  "$SSH_HOST:~/_webapp_password.hash"

echo
echo "== [2/4] Placing files into ~/$DEPLOY_DIR on the box =="
# Resolve the Windows-side home (= scp/SFTP root) in its OWN one-shot call. cmd.exe
# is a stdin reader; running it inside a multi-line script piped to `bash` makes it
# drain the rest of the script. cd /mnt/c avoids the \\wsl.localhost UNC-cwd warning;
# </dev/null keeps it off stdin here too.
WIN_HOME_RAW=$(run 'cd /mnt/c && cmd.exe /c echo %USERPROFILE% </dev/null 2>/dev/null | tr -d "\r" | tail -1')
WIN_HOME=$(run "wslpath -u '$WIN_HOME_RAW' </dev/null")
echo "WIN_HOME = $WIN_HOME"
[ -n "$WIN_HOME" ] || { echo "ERROR: could not resolve Windows home." >&2; exit 1; }

PLACE=$(cat <<REMOTE
set -e
WH="$WIN_HOME"
DD="$DEPLOY_DIR"
for f in _webapp_compose.prod.yml _webapp_config.prod.container.json _webapp_password.hash; do
    test -f "\$WH/\$f" || { echo "ERROR: shipped file missing: \$WH/\$f" >&2; exit 1; }
done
cd ~/"\$DD"
mkdir -p apps/webapp/backend/config apps/webapp/backend/auth
cp "\$WH/_webapp_compose.prod.yml"           docker/docker-compose.prod.yml
cp "\$WH/_webapp_config.prod.container.json"  apps/webapp/backend/config/config.prod.container.json
cp "\$WH/_webapp_password.hash"               apps/webapp/backend/auth/password.hash
rm -f "\$WH/_webapp_compose.prod.yml" "\$WH/_webapp_config.prod.container.json" "\$WH/_webapp_password.hash"
echo "placed: \$(grep -c webapp docker/docker-compose.prod.yml) webapp lines in docker-compose.prod.yml"
REMOTE
)
run "$PLACE"

echo
echo "== [3/4] Appending webapp-backend-prod to docker-compose.prod.local.yml (if needed) =="
PATCH=$(cat <<'REMOTE'
set -e
DD="__DEPLOY_DIR__"
cd ~/"$DD"
LF=docker/docker-compose.prod.local.yml
if grep -q webapp-backend-prod "$LF"; then
    echo "already patched - leaving $LF as-is"
else
    cp "$LF" "$LF.pre-webapp.bak"
    {
        echo "  # 2026-09-06 (Feature 068): webapp-backend-prod's read-only denidin-data mount"
        echo "  # uses the same native Windows prod-data path as denidin-app-prod's data mount."
        echo "  webapp-backend-prod:"
        echo "    volumes:"
        echo "      - /mnt/c/Users/Yaron Levi/denidin-prod-data:/app/denidin-data:ro"
    } >> "$LF"
    echo "appended webapp-backend-prod block (backup: $LF.pre-webapp.bak)"
fi
REMOTE
)
run "${PATCH/__DEPLOY_DIR__/$DEPLOY_DIR}"

echo
echo "== [4/4] Verify merged compose parses; webapp mount + existing services intact =="
VERIFY=$(cat <<'REMOTE'
set -e
DD="__DEPLOY_DIR__"
cd ~/"$DD"
docker compose --project-directory . -f docker/docker-compose.prod.yml -f docker/docker-compose.prod.local.yml config > /tmp/_webapp_cfg.yml
echo "  merged config parses OK"
echo "  webapp services:"
grep -E 'webapp-(backend|frontend)-prod:' /tmp/_webapp_cfg.yml | sed 's/^/    /'
echo "  webapp-backend-prod denidin-data mount:"
grep -A40 'webapp-backend-prod:' /tmp/_webapp_cfg.yml | grep -m1 denidin-prod-data | sed 's/^/    /'
echo "  existing prod services still present:"
grep -E '^  (denidin-app|morning-mcp-app)-prod:' /tmp/_webapp_cfg.yml | sed 's/^/    /'
rm -f /tmp/_webapp_cfg.yml
REMOTE
)
run "${VERIFY/__DEPLOY_DIR__/$DEPLOY_DIR}"

echo
echo "OK - box provisioned for the Feature 068 webapp."
echo "Next (from the Mac): scripts/cut_release.sh webapp <VERSION> --summary \"...\"  then  scripts/deploy_release.sh webapp prod <VERSION>"
