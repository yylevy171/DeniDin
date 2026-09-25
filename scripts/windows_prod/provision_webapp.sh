#!/usr/bin/env bash
# ONE-TIME (re-runnable): teach the Windows prod box about the webapp app, so
# `scripts/deploy_release.sh prod <version>` can deploy to it. Originally
# Feature 068; updated 2026-09-24 for Feature 087's config consolidation + webapp_data root.
#
# The box's deploy dir (~/denidin-prod) is NOT a git checkout - it's a curated
# file tree, populated once during Feature 035 setup. This script:
#   - Ships/places docker/docker-compose.prod.yml (branch version, with webapp-* services;
#     verified append-only vs. the running one), apps/webapp/backend/config/config.prod.json
#     (2026-09-24: no more separate ".container.json" file — this is the SAME file config.py
#     loads for both host and container mode; must have the real Morning API secrets pasted
#     in ON THE BOX itself after this runs, never committed anywhere), and
#     NEVER the password: apps/webapp/backend/auth/password.hash already lives on the box and is
#     deliberately NOT shipped, packaged, placed, or overwritten by this script (2026-09-25,
#     operator instruction - "you don't change passwords"). It is only checked for existence
#     (read-only) and the script aborts, before touching anything, if it is missing.
#   - Creates apps/webapp/webapp_data/clients/ if missing (empty scaffold only - this script
#     never copies real client data; that's a separate, explicit seed step - see its own
#     printed reminder at the end).
#   - Ensures a CORRECT webapp-backend-prod block exists in docker-compose.prod.local.yml (so
#     its read-only denidin-data mount uses the native Windows prod-data path, same reason
#     denidin-app-prod's data mount does) - replaces a stale block from a prior run rather
#     than just skipping if the service name is merely present (2026-09-24 fix: the old
#     skip-if-present check would have left a pre-087 STALE mount target in place forever).
#   - Cleans up the obsolete pre-087 apps/webapp/backend/config/config.prod.container.json
#     file if still present from an earlier provisioning run.
#
# Idempotent and self-correcting. Non-disruptive: copies/creates files and directories,
# never starts / stops / rebuilds / recreates a container. The running denidin-app-prod /
# morning-mcp-app-prod / webapp-backend-prod / webapp-frontend-prod are untouched - re-running
# this does NOT pick up a new webapp code/config shape in the already-running container; that
# still requires an explicit scripts/deploy_release.sh prod <version> afterward.
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
CONFIG_SRC="apps/webapp/backend/config/config.prod.json"

for f in "$COMPOSE_SRC" "$CONFIG_SRC"; do
    [ -f "$f" ] || { echo "ERROR: missing local file: $f" >&2; exit 1; }
done

echo "== Preflight =="
run 'echo reachable' >/dev/null || { echo "ERROR: cannot reach $SSH_HOST." >&2; exit 1; }
# The password is never provisioned by this script - it must already be on the box. Read-only
# existence check only (never prints or copies it); abort BEFORE any file is shipped/placed.
run "test -f ~/$DEPLOY_DIR/apps/webapp/backend/auth/password.hash" \
    || { echo "ERROR: ~/$DEPLOY_DIR/apps/webapp/backend/auth/password.hash is missing on $SSH_HOST. This script does not provision passwords - put the existing one there first. Nothing was changed." >&2; exit 1; }
echo "password.hash present on the box - left untouched"
run "cd ~/$DEPLOY_DIR; printf 'compose webapp lines (before): '; grep -c webapp docker/docker-compose.prod.yml || true; printf 'local.yml already patched: '; grep -q webapp-backend-prod docker/docker-compose.prod.local.yml && echo yes || echo no"

echo
echo "== [1/4] Shipping files to $SSH_HOST (Windows home) =="
scp -o BatchMode=yes -o ConnectTimeout=10 "$COMPOSE_SRC" "$SSH_HOST:~/_webapp_compose.prod.yml"
scp -o BatchMode=yes -o ConnectTimeout=10 "$CONFIG_SRC"  "$SSH_HOST:~/_webapp_config.prod.json"

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
for f in _webapp_compose.prod.yml _webapp_config.prod.json; do
    test -f "\$WH/\$f" || { echo "ERROR: shipped file missing: \$WH/\$f" >&2; exit 1; }
done
cd ~/"\$DD"
mkdir -p apps/webapp/backend/config apps/webapp/backend/auth apps/webapp/webapp_data/clients
cp "\$WH/_webapp_compose.prod.yml"  docker/docker-compose.prod.yml
cp "\$WH/_webapp_config.prod.json"  apps/webapp/backend/config/config.prod.json
rm -f "\$WH/_webapp_compose.prod.yml" "\$WH/_webapp_config.prod.json"
# Cleanup: obsolete pre-087 file, superseded by config.prod.json above - never needed again.
if [ -f apps/webapp/backend/config/config.prod.container.json ]; then
    rm -f apps/webapp/backend/config/config.prod.container.json
    echo "cleaned up: obsolete config.prod.container.json removed"
fi
echo "placed: \$(grep -c webapp docker/docker-compose.prod.yml) webapp lines in docker-compose.prod.yml"
if [ -z "\$(ls -A apps/webapp/webapp_data/clients 2>/dev/null)" ]; then
    echo "NOTE: apps/webapp/webapp_data/clients/ is empty - needs seeding from Rapaport's live"
    echo "      analyst files before webapp's Clients tab has any real data (see"
    echo "      apps/webapp/webapp_data/README.md in the repo for what to copy)."
else
    echo "apps/webapp/webapp_data/clients/ already has \$(ls apps/webapp/webapp_data/clients | wc -l) file(s) - not touched."
fi
REMOTE
)
run "$PLACE"

echo
echo "== [3/4] Ensuring a CORRECT webapp-backend-prod block in docker-compose.prod.local.yml =="
# Self-correcting, not just skip-if-present (2026-09-24 fix): a prior run of this script may
# have appended a now-stale block (pre-087's flat /app/denidin-data mount target). Since this
# script only ever APPENDS its own block, and only ever at the end of the file, the safe way
# to correct it is to drop everything from the FIRST "  webapp-backend-prod:" line onward, then
# append a fresh, current block - never touching whatever precedes it (denidin-app-prod's own
# block, etc.).
CORRECT_TARGET='/app/apps/denidin-app/data'
PATCH=$(cat <<REMOTE
set -e
DD="$DEPLOY_DIR"
cd ~/"\$DD"
LF=docker/docker-compose.prod.local.yml
cp "\$LF" "\$LF.pre-webapp.bak"
if grep -qF '$CORRECT_TARGET' "\$LF" && grep -q webapp-backend-prod "\$LF"; then
    echo "already correct - leaving \$LF as-is"
    rm -f "\$LF.pre-webapp.bak"
else
    if grep -q webapp-backend-prod "\$LF"; then
        echo "stale webapp-backend-prod block found - replacing it (backup: \$LF.pre-webapp.bak)"
        sed -i '/^  webapp-backend-prod:/,\$d' "\$LF"
    else
        echo "no webapp-backend-prod block found - appending one (backup: \$LF.pre-webapp.bak)"
    fi
    {
        echo "  # 2026-09-06 (Feature 068): webapp-backend-prod's read-only denidin-data mount"
        echo "  # uses the same native Windows prod-data path as denidin-app-prod's data mount."
        echo "  # 2026-09-24: mount target mirrors the repo tree (matches config.prod.json's"
        echo "  # relative denidin_data_root, resolved from /app/apps/webapp/backend) - no more"
        echo '  # separate ".container.json"/flat-path convention.'
        echo "  webapp-backend-prod:"
        echo "    volumes:"
        echo "      - /mnt/c/Users/Yaron Levi/denidin-prod-data:$CORRECT_TARGET:ro"
    } >> "\$LF"
    echo "webapp-backend-prod block is now current"
fi
REMOTE
)
run "$PATCH"

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
echo "  compose bind-mounted config assets present (would otherwise become empty root-owned dirs):"
for f in apps/denidin-app/config/runtime_constitution.md apps/denidin-app/config/ledger_recognition_prompt.md apps/denidin-app/config/fee_agreement_templates/manifest.json; do
    [ -f "$f" ] && echo "    ok  $f" || { echo "    MISSING  $f - a release ships these (RELEASE_CONFIG_ASSET_FILES); deploy_release.sh will put them in place" >&2; }
done
echo "  no obsolete config.prod.container.json left behind:"
if [ -f apps/webapp/backend/config/config.prod.container.json ]; then
    echo "    WARNING: still present - cleanup step above should have removed it"
else
    echo "    confirmed absent"
fi
echo "  webapp_data/clients/ present:"
[ -d apps/webapp/webapp_data/clients ] && echo "    yes ($(ls apps/webapp/webapp_data/clients | wc -l) file(s))" || echo "    MISSING"
echo "  config.prod.json Morning credentials filled in (not placeholder):"
python3 -c "
import json
d = json.load(open('apps/webapp/backend/config/config.prod.json'))
kid = d.get('morning_api_key_id', '')
if not kid or kid.startswith('PASTE_YOUR') or kid == 'to-paste-here':
    print('    NOT SET - paste real prod Morning credentials into config.prod.json on this box before deploying')
else:
    print('    set (value not printed)')
"
REMOTE
)
run "${VERIFY/__DEPLOY_DIR__/$DEPLOY_DIR}"

echo
echo "OK - box provisioned for the webapp (Features 068 + 087)."
echo "Remaining manual steps on the box before a real deploy:"
echo "  1. Paste real prod Morning API credentials into apps/webapp/backend/config/config.prod.json"
echo "  2. Seed apps/webapp/webapp_data/clients/ from Rapaport's live analyst files (see"
echo "     apps/webapp/webapp_data/README.md) if not already done"
echo "Then (from the Mac): scripts/cut_release.sh webapp <VERSION> --summary \"...\"  then  scripts/deploy_release.sh prod <VERSION>   (all apps; or deploy_release_single.sh webapp prod <VERSION>)"
