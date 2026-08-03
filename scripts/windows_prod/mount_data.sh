#!/usr/bin/env bash
# Mounts the Windows box's persistent prod data folder locally on the Mac,
# read-only, via sshfs + macFUSE — browsable/backup-able like an ordinary
# local folder, no SSH session needed. Idempotent — safe to run again if
# already mounted. See spec.md FR6a, quickstart.md §9a.
#
# Corrected 2026-08-03: the data folder lives at a native Windows-side
# path (e.g. C:\Users\<name>\denidin-prod-data), NOT under the WSL-side
# deploy directory (~/denidin-prod/apps/denidin-app/data) - confirmed
# Windows' native OpenSSH SFTP server cannot traverse into the WSL2
# filesystem at all (neither a direct UNC path nor an NTFS symlink
# pointing at one worked), so this volume was relocated via a one-time,
# hand-created docker-compose.prod.local.yml override (see quickstart.md
# §3) specifically so sshfs (which rides SFTP) can reach it.
#
# Prerequisite (one-time, manual — not done by this script):
#   brew install --cask macfuse   # then approve the system extension in
#                                  # Privacy & Security and reboot the Mac
#   brew install gromgit/fuse/sshfs-mac
#
# Usage: ./scripts/windows_prod/mount_data.sh <ssh-host-alias> [remote-data-dir-name] [mount-point]

set -uo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> [remote-data-dir-name] [mount-point]}"
REMOTE_DATA_DIR="${2:-denidin-prod-data}"
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

echo "Mounting $SSH_HOST:$REMOTE_DATA_DIR -> $MOUNT_POINT (read-only)..."
sshfs "$SSH_HOST:$REMOTE_DATA_DIR" "$MOUNT_POINT" \
  -o reconnect,ro,volname=denidin-winprod-data

echo "Mounted. Browse with: ls $MOUNT_POINT"
