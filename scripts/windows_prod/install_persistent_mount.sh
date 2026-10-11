#!/usr/bin/env bash
# One-time (per Mac) setup: installs and loads the LaunchAgent that keeps
# the Windows-prod data mount (~/denidin-winprod-data) permanently up -
# "if the Mac is on, the mount should be there, always" (explicit
# requirement, 2026-08-20). See com.denidin.winprod-mount.plist's own
# comments for exactly what this buys (RunAtLoad, KeepAlive) and
# mount_data_foreground.sh for what actually runs.
#
# The agent NEVER runs anything out of a teammate/coder clone (2026-10-03: the
# installed agent pointed at a since-renamed clone and the mount stayed silently
# dead from 2026-09-14 until noticed). Instead this script copies
# mount_data_foreground.sh to the ROOT clone's scripts/ (gitignored there, see
# .gitignore) and points the agent at that copy - so it works the same no matter
# which clone you run the installer from.
#
# Idempotent - safe to re-run (e.g. to pick up a change to
# mount_data_foreground.sh or the plist) - unloads any existing copy of the
# agent first, then installs+loads the current one fresh.
#
# Prerequisite: macFUSE + sshfs already installed (see quickstart.md §9a
# steps 1-2) and the `denidin-winprod` SSH host alias already set up in
# ~/.ssh/config (quickstart.md §2) - this script does not do either of
# those, only the LaunchAgent wiring.
#
# Usage: ./scripts/windows_prod/install_persistent_mount.sh [--root-clone <dir>]
#   --root-clone  the root clone's directory; by default it is derived: the
#                 clone this script lives in if that IS the root clone, else
#                 the git repo directly above it (teammate clones live inside
#                 the root clone's directory).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LABEL="com.denidin.winprod-mount"
PLIST_SRC="${SCRIPT_DIR}/${AGENT_LABEL}.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/${AGENT_LABEL}.plist"
MOUNT_SRC="${SCRIPT_DIR}/mount_data_foreground.sh"
MOUNT_POINT="${HOME}/denidin-winprod-data"
LOG_FILE="${HOME}/Library/Logs/denidin-winprod-mount.log"
DOMAIN="gui/$(id -u)"

ROOT_CLONE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --root-clone) ROOT_CLONE="${2:?--root-clone needs a directory}"; shift 2 ;;
    *) echo "FAIL: unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$ROOT_CLONE" ]; then
  THIS_CLONE="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
  PARENT="$(dirname "$THIS_CLONE")"
  if [ "$(git -C "$PARENT" rev-parse --show-toplevel 2>/dev/null || true)" = "$PARENT" ]; then
    ROOT_CLONE="$PARENT"
  else
    ROOT_CLONE="$THIS_CLONE"
  fi
fi
ROOT_CLONE="$(cd "$ROOT_CLONE" && pwd)"

case "$(basename "$ROOT_CLONE")" in
  teammate*|coder*)
    echo "FAIL: resolved root clone '${ROOT_CLONE}' looks like a teammate/coder clone." >&2
    echo "      The agent must never point at one - pass --root-clone <root clone dir>." >&2
    exit 1 ;;
esac

for f in "$PLIST_SRC" "$MOUNT_SRC"; do
  [ -f "$f" ] || { echo "FAIL: ${f} not found." >&2; exit 1; }
done

if ! command -v sshfs >/dev/null 2>&1; then
  echo "FAIL: sshfs not found. Install macFUSE + sshfs first - see quickstart.md §9a steps 1-2." >&2
  exit 1
fi

MOUNT_SCRIPT="${ROOT_CLONE}/scripts/mount_data_foreground.sh"
mkdir -p "${ROOT_CLONE}/scripts" "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs"
cp "$MOUNT_SRC" "$MOUNT_SCRIPT"
chmod +x "$MOUNT_SCRIPT"
if git -C "$ROOT_CLONE" rev-parse --git-dir >/dev/null 2>&1 \
   && ! git -C "$ROOT_CLONE" check-ignore -q scripts/mount_data_foreground.sh; then
  echo "WARN: ${MOUNT_SCRIPT} is not gitignored in the root clone yet (pull master, or add" >&2
  echo "      '/scripts/mount_data_foreground.sh' to its .git/info/exclude)." >&2
fi

sed -e "s#__MOUNT_SCRIPT__#${MOUNT_SCRIPT}#" -e "s#__LOG_FILE__#${LOG_FILE}#g" "$PLIST_SRC" > "$PLIST_DEST"
plutil -lint "$PLIST_DEST" >/dev/null

echo "Reloading ${AGENT_LABEL} -> ${MOUNT_SCRIPT}"
launchctl bootout "${DOMAIN}/${AGENT_LABEL}" 2>/dev/null || true
# bootout returns before the service is fully gone; bootstrapping too early fails with
# "Bootstrap failed: 5: Input/output error".
for _ in $(seq 1 20); do
  launchctl print "${DOMAIN}/${AGENT_LABEL}" >/dev/null 2>&1 || break
  sleep 0.5
done
launchctl bootstrap "$DOMAIN" "$PLIST_DEST"
launchctl enable "${DOMAIN}/${AGENT_LABEL}"

# Success means the mount is actually READABLE - a stale mount from a dead sshfs still
# shows up in `mount`, which is exactly how this went unnoticed before.
for _ in $(seq 1 15); do
  if [ -n "$(ls -A "$MOUNT_POINT" 2>/dev/null)" ]; then
    echo "✅ Installed and running - ${MOUNT_POINT} is mounted and readable."
    exit 0
  fi
  sleep 2
done
echo "⚠️  Agent loaded but ${MOUNT_POINT} isn't readable after 30s - check ${LOG_FILE}" >&2
exit 1
