#!/bin/bash
# Mac-side pull of prod backup archives from the Windows host (Feature 078,
# US2/US5). Read-only against the Windows host - never writes there, never
# touches the live data/config paths, strictly pulls already-finished
# `.tgz` files out of the two backup folders (contracts/script-contracts.md).
#
# Pull, not push (research.md R4): tolerates the Mac being asleep across
# several 03:00 windows by simply pulling whatever is new whenever it next
# runs.
#
# Usage: pull_backups.sh --config <path> [--today YYYY-MM-DD]
#
# --today freezes "today" for the local retention purge (testing only, same
# convention as run_daily_backup.sh's --today).
#
# Special config value: ssh_host_alias = "LOCAL_TEST" makes the "remote"
# side a plain local path instead of an ssh target - used only by this
# feature's own tests, so the real rsync/purge logic gets real (non-mocked)
# coverage without requiring passwordless SSH to an arbitrary host in a
# sandboxed test environment. Production config never sets this.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/load_config.sh
source "$SCRIPT_DIR/lib/load_config.sh"
# shellcheck source=lib/retention_purge.sh
source "$SCRIPT_DIR/lib/retention_purge.sh"

CONFIG_PATH=""
TODAY_OVERRIDE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        --today)
            TODAY_OVERRIDE="$2"
            shift 2
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [ -z "$CONFIG_PATH" ]; then
    echo "ERROR: --config <path> is required" >&2
    exit 1
fi

if ! load_backup_config "$CONFIG_PATH" daily_backup_dir monthly_backup_dir \
        mac_daily_backup_dir mac_monthly_backup_dir ssh_host_alias; then
    exit 1
fi

if [ -n "$TODAY_OVERRIDE" ]; then
    TODAY="$TODAY_OVERRIDE"
else
    TODAY=$(TZ=Asia/Jerusalem date +%Y-%m-%d)
fi

log() {
    echo "$(TZ=Asia/Jerusalem date '+%Y-%m-%dT%H:%M:%S%z') $1"
}

if [ "$SSH_HOST_ALIAS" = "LOCAL_TEST" ]; then
    REMOTE_DAILY="${DAILY_BACKUP_DIR}/"
    REMOTE_MONTHLY="${MONTHLY_BACKUP_DIR}/"
    RSYNC_SSH_OPT=""
else
    REMOTE_DAILY="${SSH_HOST_ALIAS}:${DAILY_BACKUP_DIR}/"
    REMOTE_MONTHLY="${SSH_HOST_ALIAS}:${MONTHLY_BACKUP_DIR}/"
    RSYNC_SSH_OPT="ssh -o ConnectTimeout=10 -o BatchMode=yes"
fi

mkdir -p "$MAC_DAILY_BACKUP_DIR" "$MAC_MONTHLY_BACKUP_DIR"

log "pulling daily backups from ${REMOTE_DAILY}"
if [ -n "$RSYNC_SSH_OPT" ]; then
    rsync -a -e "$RSYNC_SSH_OPT" --include='*.tgz' --exclude='*' "$REMOTE_DAILY" "$MAC_DAILY_BACKUP_DIR/"
else
    rsync -a --include='*.tgz' --exclude='*' "$REMOTE_DAILY" "$MAC_DAILY_BACKUP_DIR/"
fi
if [ $? -ne 0 ]; then
    echo "ERROR: pull_backups.sh: rsync failed pulling daily backups from ${REMOTE_DAILY}" >&2
    exit 1
fi

log "pulling monthly backups from ${REMOTE_MONTHLY}"
if [ -n "$RSYNC_SSH_OPT" ]; then
    rsync -a -e "$RSYNC_SSH_OPT" --include='*.tgz' --exclude='*' "$REMOTE_MONTHLY" "$MAC_MONTHLY_BACKUP_DIR/"
else
    rsync -a --include='*.tgz' --exclude='*' "$REMOTE_MONTHLY" "$MAC_MONTHLY_BACKUP_DIR/"
fi
if [ $? -ne 0 ]; then
    echo "ERROR: pull_backups.sh: rsync failed pulling monthly backups from ${REMOTE_MONTHLY}" >&2
    exit 1
fi

purge_older_than "$MAC_DAILY_BACKUP_DIR" 30 days "$TODAY"
purge_older_than "$MAC_MONTHLY_BACKUP_DIR" 36 months "$TODAY"
log "local retention purge complete"

log "pull_backups.sh completed successfully"
exit 0
