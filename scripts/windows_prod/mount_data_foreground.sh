#!/usr/bin/env bash
# Foreground sshfs mount for the Windows-prod data folder - meant to run
# UNDER supervision by a LaunchAgent (see com.denidin.winprod-mount.plist in
# this directory), not invoked directly for a one-off mount (use
# mount_data.sh for that instead - it's idempotent and returns immediately).
#
# Why this exists as a separate script (2026-08-20): sshfs on this Mac's
# sshfs-mac/macFUSE build does not cleanly daemonize - confirmed live,
# `sshfs ... ` printed "fuse: daemonize requested after mount started;
# continuing in foreground" and the calling script hung rather than
# returning. Backgrounding it with `&` from within a plain script is
# fragile (unclear whether the child survives the parent script's own exit
# once launchd's own process-group handling is involved) - the robust fix
# is to let this process STAY in the foreground and have launchd itself
# supervise it directly as the "service" (KeepAlive=true in the plist
# restarts it whenever it exits, for any reason - a real crash, the SSH
# connection dropping past sshfs's own `-o reconnect` retry budget, or an
# explicit `umount`). This is the standard/idiomatic launchd pattern for a
# foreground daemon process, not a workaround.
#
# Usage: ./scripts/windows_prod/mount_data_foreground.sh <ssh-host-alias> [remote-data-dir-name] [mount-point]

set -uo pipefail

# launchd's default PATH for a LaunchAgent is the bare minimum
# (/usr/bin:/bin:/usr/sbin:/sbin) - it does NOT include Homebrew's bin dirs,
# so a bare `sshfs` call fails with "command not found" under launchd even
# though it works fine interactively (confirmed live, 2026-08-20). Covers
# both Homebrew layouts (Intel /usr/local, Apple Silicon /opt/homebrew) so
# this doesn't silently break if this Mac/agent is ever migrated.
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> [remote-data-dir-name] [mount-point]}"
REMOTE_DATA_DIR="${2:-denidin-prod-data}"
MOUNT_POINT="${3:-$HOME/denidin-winprod-data}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] mount_data_foreground.sh starting: $SSH_HOST:$REMOTE_DATA_DIR -> $MOUNT_POINT"

# Clear any stale mount entry left behind by a previous, abnormally-terminated
# sshfs process (e.g. `mount` still lists it but any real access fails with
# "Device not configured") - a fresh sshfs call onto a stale mount point
# otherwise silently no-ops instead of actually reconnecting. Failures here
# are expected and fine (nothing to clear, or already clean) - never fatal.
umount -f "$MOUNT_POINT" 2>/dev/null || diskutil unmount force "$MOUNT_POINT" 2>/dev/null || true

mkdir -p "$MOUNT_POINT"

# `-f`: stay in the foreground (explicit, not relying on daemonize failing).
# `reconnect`: survive a brief network drop (e.g. Wi-Fi hiccup) without
#   launchd needing to notice and restart us.
# `ServerAliveInterval`/`ServerAliveCountMax`: detect a truly-dead SSH
#   connection (e.g. after a long sleep) in ~45s instead of waiting on a much
#   longer TCP timeout - the sooner this process exits, the sooner launchd's
#   KeepAlive restarts it and the mount is healthy again.
exec sshfs "$SSH_HOST:$REMOTE_DATA_DIR" "$MOUNT_POINT" \
  -o reconnect,ro,volname=denidin-winprod-data,ServerAliveInterval=15,ServerAliveCountMax=3 -f
