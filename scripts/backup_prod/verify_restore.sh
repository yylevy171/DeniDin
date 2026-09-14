#!/bin/bash
# Restore-integrity verification (Feature 078, US3 / SC-002 / UAT 3).
#
# Un-tars a named backup archive into a fresh, throwaway temp directory
# (never touches any real/live data path) and runs `PRAGMA integrity_check`
# against every SQLite store found, reporting each individually so a single
# corrupt store is identifiable rather than just "something failed".
#
# The full "boot denidin-app against the extracted data" smoke check
# (contracts/script-contracts.md's second half of this contract) is
# deliberately NOT automated here - it requires a real Docker daemon and an
# ephemeral compose override, which is exactly the class of
# real-environment-dependent step this repo consistently leaves as a manual,
# explicitly-approved gate (same treatment as register_prober_schedule.sh's
# schtasks.exe branch) - see quickstart.md step 4 and tasks.md T014.
#
# Usage: verify_restore.sh <path-to-archive.tgz>
# Exit code: 0 iff every SQLite store found passes integrity_check.

set -u

ARCHIVE="${1:-}"

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
    echo "Usage: $0 <path-to-archive.tgz>" >&2
    echo "ERROR: archive not found: '$ARCHIVE'" >&2
    exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "ERROR: 'sqlite3' CLI not found on PATH" >&2
    exit 1
fi

EXTRACT_DIR=$(mktemp -d) || { echo "ERROR: could not create temp dir" >&2; exit 1; }
cleanup() { rm -rf "$EXTRACT_DIR"; }
trap cleanup EXIT

echo "Extracting $ARCHIVE into throwaway $EXTRACT_DIR ..."
if ! tar xzf "$ARCHIVE" -C "$EXTRACT_DIR"; then
    echo "ERROR: failed to extract archive: $ARCHIVE" >&2
    exit 1
fi

OVERALL_OK=0
FOUND_ANY=0

while IFS= read -r -d '' db_file; do
    FOUND_ANY=1
    rel_path="${db_file#"$EXTRACT_DIR"/}"
    result=$(sqlite3 "$db_file" "PRAGMA integrity_check;" 2>&1)
    if [ "$result" = "ok" ]; then
        echo "PASS: $rel_path"
    else
        echo "FAIL: $rel_path - $result"
        OVERALL_OK=1
    fi
done < <(find "$EXTRACT_DIR" \( -name "*.db" -o -name "*.sqlite3" \) -print0 2>/dev/null)

if [ "$FOUND_ANY" -eq 0 ]; then
    echo "WARNING: no .db/.sqlite3 files found in archive - nothing to verify"
fi

if [ "$OVERALL_OK" -eq 0 ]; then
    echo "All SQLite stores passed integrity_check."
else
    echo "One or more SQLite stores FAILED integrity_check - see above." >&2
fi

exit $OVERALL_OK
