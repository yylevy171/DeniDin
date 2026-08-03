#!/usr/bin/env bash
# Unmounts the sshfs data-folder mount created by mount_data.sh. Ordinary
# macOS unmount — no special sshfs teardown needed, no effect on the
# Windows box or its live data (the mount was always just a read-only
# local view).
#
# Usage: ./scripts/windows_prod/unmount_data.sh [mount-point]

set -uo pipefail

MOUNT_POINT="${1:-$HOME/denidin-winprod-data}"

if ! mount | grep -qF "on $MOUNT_POINT ("; then
  echo "Not mounted at $MOUNT_POINT — nothing to do."
  exit 0
fi

umount "$MOUNT_POINT"
echo "Unmounted $MOUNT_POINT."
