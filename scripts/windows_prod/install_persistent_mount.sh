#!/usr/bin/env bash
# One-time (per Mac) setup: installs and loads the LaunchAgent that keeps
# the Windows-prod data mount (~/denidin-winprod-data) permanently up -
# "if the Mac is on, the mount should be there, always" (explicit
# requirement, 2026-08-20). See com.denidin.winprod-mount.plist's own
# comments for exactly what this buys (RunAtLoad, KeepAlive) and
# mount_data_foreground.sh for what actually runs.
#
# Idempotent - safe to re-run (e.g. after moving/re-cloning the repo, or to
# pick up a plist/script change) - unloads any existing copy of the agent
# first, then installs+loads the current one fresh.
#
# Prerequisite: macFUSE + sshfs already installed (see quickstart.md §9a
# steps 1-2) and the `denidin-winprod` SSH host alias already set up in
# ~/.ssh/config (quickstart.md §2) - this script does not do either of
# those, only the LaunchAgent wiring.
#
# Usage: ./scripts/windows_prod/install_persistent_mount.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LABEL="com.denidin.winprod-mount"
PLIST_SRC="${SCRIPT_DIR}/${AGENT_LABEL}.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/${AGENT_LABEL}.plist"

if [ ! -f "$PLIST_SRC" ]; then
  echo "FAIL: ${PLIST_SRC} not found." >&2
  exit 1
fi

if ! command -v sshfs >/dev/null 2>&1; then
  echo "FAIL: sshfs not found. Install macFUSE + sshfs first - see quickstart.md §9a steps 1-2." >&2
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs"

# The installed plist's ProgramArguments points at THIS clone's own
# mount_data_foreground.sh by absolute path (see that file's comments on
# why paths are clone-specific) - copy as-is, do not template/rewrite it.
cp "$PLIST_SRC" "$PLIST_DEST"

echo "Reloading ${AGENT_LABEL}..."
launchctl bootout "gui/$(id -u)/${AGENT_LABEL}" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
launchctl enable "gui/$(id -u)/${AGENT_LABEL}"

sleep 3
if mount | grep -qF "on ${HOME}/denidin-winprod-data ("; then
  echo "✅ Installed and running - ${HOME}/denidin-winprod-data is mounted."
else
  echo "⚠️  Agent loaded but mount isn't up yet - check ${HOME}/Library/Logs/denidin-winprod-mount.log" >&2
fi
