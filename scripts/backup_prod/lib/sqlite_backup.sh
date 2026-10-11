#!/bin/bash
# Sourceable hot-SQLite-backup helper for scripts/backup_prod/*.sh (Feature 078).
#
# Uses SQLite's own online-backup facility (`.backup`, the SQLite Backup API)
# rather than a raw file copy - safe against concurrent writers, produces a
# fully consistent snapshot with no app-side coordination needed. See
# research.md R2 for the full rationale and measured timing.

# backup_sqlite_db <src_db> <dest_path>
#
# Copies <src_db> into a hot-consistent snapshot at <dest_path> (parent dir
# created if needed). Returns non-zero on any sqlite3 failure.
backup_sqlite_db() {
    local src="$1"
    local dest="$2"

    if [ ! -f "$src" ]; then
        echo "ERROR: backup_sqlite_db: source not found: '$src'" >&2
        return 1
    fi

    if ! command -v sqlite3 >/dev/null 2>&1; then
        echo "ERROR: backup_sqlite_db: 'sqlite3' CLI not found on PATH" >&2
        return 1
    fi

    mkdir -p "$(dirname "$dest")"

    if ! sqlite3 "$src" ".backup '${dest}'"; then
        echo "ERROR: backup_sqlite_db: sqlite3 .backup failed for '$src' -> '$dest'" >&2
        return 1
    fi

    return 0
}
