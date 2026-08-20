#!/usr/bin/env bash
# Unmounts the sshfs data-folder mount. Ordinary macOS unmount — no special
# sshfs teardown needed, no effect on the Windows box or its live data (the
# mount was always just a read-only local view).
#
# 2026-08-20: if the always-on LaunchAgent (com.denidin.winprod-mount, see
# mount_data_foreground.sh + com.denidin.winprod-mount.plist) is installed
# and loaded, a plain `umount` alone gets silently re-mounted within
# ~15s (that's its whole point - "if the Mac is on, the mount should be
# there, always"). So THIS script unloads the agent FIRST when present, so
# an intentional unmount actually sticks - re-enable with:
#   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.denidin.winprod-mount.plist
#
# Usage: ./scripts/windows_prod/unmount_data.sh [mount-point]

set -uo pipefail

MOUNT_POINT="${1:-$HOME/denidin-winprod-data}"
AGENT_LABEL="com.denidin.winprod-mount"

if launchctl print "gui/$(id -u)/${AGENT_LABEL}" >/dev/null 2>&1; then
  echo "Unloading the always-on mount LaunchAgent (${AGENT_LABEL}) first, so it doesn't just re-mount this..."
  launchctl bootout "gui/$(id -u)/${AGENT_LABEL}" 2>/dev/null || true
  sleep 1
fi

if ! mount | grep -qF "on $MOUNT_POINT ("; then
  echo "Not mounted at $MOUNT_POINT — nothing to do."
  exit 0
fi

umount "$MOUNT_POINT" 2>/dev/null || diskutil unmount force "$MOUNT_POINT"
echo "Unmounted $MOUNT_POINT."
