#!/bin/bash
# Zero-downtime daily prod backup (Feature 078).
#
# Builds one denidin-prod-backup-YYYY-MM-DD.tgz covering data/, config/, and
# logs/prod/, with every SQLite store replaced by a hot-consistent
# `.backup` snapshot (research.md R2) rather than a raw copy of a live file.
# Never touches docker/docker compose - operates purely as an external
# filesystem reader (research.md R6). Writes to a `.tgz.partial` path first
# and only `mv`s into place on full success, so a failed run never leaves a
# file that looks complete (contracts/script-contracts.md).
#
# Usage: run_daily_backup.sh --config <path> [--today YYYY-MM-DD] [--log-dir <dir>]
#
# --today is for deterministic testing only (freezes "today" instead of using
# the real date) - the real invocation (via register_backup_schedule.sh) never
# passes it.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=lib/load_config.sh
source "$SCRIPT_DIR/lib/load_config.sh"
# shellcheck source=lib/retention_purge.sh
source "$SCRIPT_DIR/lib/retention_purge.sh"
# shellcheck source=lib/sqlite_backup.sh
source "$SCRIPT_DIR/lib/sqlite_backup.sh"

CONFIG_PATH=""
TODAY_OVERRIDE=""
LOG_DIR="$SCRIPT_DIR/../../logs/backup_prod"

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
        --log-dir)
            LOG_DIR="$2"
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

if ! load_backup_config "$CONFIG_PATH" data_dir config_dir logs_prod_dir daily_backup_dir monthly_backup_dir; then
    exit 1
fi

if [ -n "$TODAY_OVERRIDE" ]; then
    TODAY="$TODAY_OVERRIDE"
else
    TODAY=$(TZ=Asia/Jerusalem date +%Y-%m-%d)
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run_daily_backup_${TODAY}.log"

log() {
    echo "$(TZ=Asia/Jerusalem date '+%Y-%m-%dT%H:%M:%S%z') $1" | tee -a "$LOG_FILE"
}

fail() {
    log "ERROR: $1"
    exit 1
}

log "=== run_daily_backup.sh starting for $TODAY ==="

mkdir -p "$DAILY_BACKUP_DIR" "$MONTHLY_BACKUP_DIR"

ARCHIVE_NAME="denidin-prod-backup-${TODAY}.tgz"
FINAL_PATH="${DAILY_BACKUP_DIR}/${ARCHIVE_NAME}"
PARTIAL_PATH="${FINAL_PATH}.partial"

STAGING_DIR=$(mktemp -d) || fail "could not create staging temp dir"
cleanup() {
    rm -rf "$STAGING_DIR"
    rm -f "$PARTIAL_PATH"
}
trap cleanup EXIT

# --- Non-blocking pre-flight roll-marker check (research.md R6a / F2) ---
# Never blocks or fails the backup - purely observability, since zero-downtime
# (REQ-078-02) outranks the ordering preference in REQ-078-04.
ROLL_MARKER_DB="${DATA_DIR}/memory_rolls/roll_markers.db"
if [ -f "$ROLL_MARKER_DB" ] && command -v sqlite3 >/dev/null 2>&1; then
    YESTERDAY=$(TZ=Asia/Jerusalem date -j -v-1d -f "%Y-%m-%d" "$TODAY" +%Y-%m-%d 2>/dev/null \
        || TZ=Asia/Jerusalem date -d "${TODAY} -1 day" +%Y-%m-%d 2>/dev/null)
    if [ -n "$YESTERDAY" ]; then
        COMMITTED_COUNT=$(sqlite3 "$ROLL_MARKER_DB" \
            "SELECT COUNT(*) FROM roll_markers WHERE date = '${YESTERDAY}' AND status = 'committed';" \
            2>/dev/null || echo "-1")
        if [ "$COMMITTED_COUNT" = "0" ] || [ "$COMMITTED_COUNT" = "-1" ]; then
            log "WARNING: no committed daily-summary roll marker found for ${YESTERDAY} - Feature 070's 02:00 roll may not have completed yet (REQ-078-04 ordering check, non-blocking, see research.md R6a)"
        fi
    fi
fi

# --- Stage ordinary files (config/, logs/prod/, and data/ minus known DBs) ---
mkdir -p "$STAGING_DIR/config" "$STAGING_DIR/logs_prod" "$STAGING_DIR/data"

if [ -d "$CONFIG_DIR" ]; then
    cp -R "$CONFIG_DIR/." "$STAGING_DIR/config/" || fail "failed staging config_dir"
fi
if [ -d "$LOGS_PROD_DIR" ]; then
    cp -R "$LOGS_PROD_DIR/." "$STAGING_DIR/logs_prod/" || fail "failed staging logs_prod_dir"
fi
if [ -d "$DATA_DIR" ]; then
    cp -R "$DATA_DIR/." "$STAGING_DIR/data/" || fail "failed staging data_dir"
fi

# --- Replace every staged SQLite/ChromaDB store with a hot-consistent backup ---
# (research.md R2: chat_index.db, roll_markers.db, reminders.db, chroma.sqlite3
# and any other *.db/*.sqlite3 found under data_dir, matched generically so a
# future new store is covered automatically.)
while IFS= read -r -d '' live_db; do
    rel_path="${live_db#"$DATA_DIR"/}"
    staged_path="$STAGING_DIR/data/$rel_path"
    if ! backup_sqlite_db "$live_db" "$staged_path"; then
        fail "hot backup failed for $live_db"
    fi
    log "backed up $rel_path"
done < <(find "$DATA_DIR" \( -name "*.db" -o -name "*.sqlite3" \) -print0 2>/dev/null)

# --- Assemble the archive atomically ---
# COPYFILE_DISABLE avoids macOS tar emitting AppleDouble "._foo" sidecar
# entries (harmless on the real Linux/WSL2 prod box, but they pollute local
# dev-box/test runs and would otherwise trip a naive "every *.db passes
# integrity_check" restore check on a sidecar that isn't really a database).
if ! COPYFILE_DISABLE=1 tar czf "$PARTIAL_PATH" -C "$STAGING_DIR" .; then
    fail "tar czf failed"
fi

mv "$PARTIAL_PATH" "$FINAL_PATH" || fail "could not move archive into place"
log "wrote $FINAL_PATH"

# --- Tier 1 retention purge (REQ-078-05) ---
purge_older_than "$DAILY_BACKUP_DIR" 30 days "$TODAY"
log "purged daily backups older than 30 days"

# --- Tier 2 monthly promotion + retention (REQ-078-06), 1st of month only ---
DAY_OF_MONTH=$(echo "$TODAY" | cut -d- -f3)
if [ "$DAY_OF_MONTH" = "01" ]; then
    cp "$FINAL_PATH" "${MONTHLY_BACKUP_DIR}/${ARCHIVE_NAME}" || fail "monthly promotion copy failed"
    log "promoted $ARCHIVE_NAME to monthly tier"
    purge_older_than "$MONTHLY_BACKUP_DIR" 36 months "$TODAY"
    log "purged monthly backups older than 36 months"
fi

log "=== run_daily_backup.sh completed successfully for $TODAY ==="
exit 0
