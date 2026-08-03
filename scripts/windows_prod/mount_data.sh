#!/usr/bin/env bash
# Mounts the Windows box's persistent apps/denidin-app/data folder locally
# on the Mac, read-only, via sshfs + macFUSE — browsable/backup-able like
# an ordinary local folder, no SSH session needed. Idempotent — safe to
# run again if already mounted. See spec.md FR6a, quickstart.md §9a.
#
# Prerequisite (one-time, manual — not done by this script):
#   brew install --cask macfuse   # then approve the system extension in
#                                  # Privacy & Security and reboot the Mac
#   brew install gromgit/fuse/sshfs-mac
#
# Usage: ./scripts/windows_prod/mount_data.sh <ssh-host-alias> [deploy-dir-name] [mount-point]

set -uo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> [deploy-dir-name] [mount-point]}"
DEPLOY_DIR="${2:-denidin-prod}"
MOUNT_POINT="${3:-$HOME/denidin-winprod-data}"

if ! command -v sshfs >/dev/null 2>&1; then
  echo "FAIL: sshfs not found. Install macFUSE + sshfs first:" >&2
  echo "  brew install --cask macfuse   # then approve the system extension + reboot" >&2
  echo "  brew install gromgit/fuse/sshfs-mac" >&2
  echo "See quickstart.md §9a." >&2
  exit 1
fi

if mount | grep -qF "on $MOUNT_POINT ("; then
  echo "Already mounted at $MOUNT_POINT."
  exit 0
fi

mkdir -p "$MOUNT_POINT"

echo "Mounting $SSH_HOST:$DEPLOY_DIR/apps/denidin-app/data -> $MOUNT_POINT (read-only)..."
sshfs "$SSH_HOST:$DEPLOY_DIR/apps/denidin-app/data" "$MOUNT_POINT" \
  -o reconnect,ro,volname=denidin-winprod-data

echo "Mounted. Browse with: ls $MOUNT_POINT"
