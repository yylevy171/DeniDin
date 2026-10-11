#!/bin/bash
# Sourceable retention-purge helper for scripts/backup_prod/*.sh (Feature 078).
#
# Retention is derived purely from each archive's *filename* date
# (denidin-prod-backup-YYYY-MM-DD.tgz), never filesystem mtime - see
# research.md R5 for why: two independent hosts, connected only by an
# unreliable link, each converge to the same retention window purely from
# what's on their own disk, with no shared manifest.
#
# Portable across BSD date (macOS, used by tests) and GNU date (WSL2/Linux,
# used on the real prod box) - same uname-based branching precedent already
# used by scripts/health_monitoring/register_prober_schedule.sh.

_backup_prod_is_bsd_date() {
    date -v-1d >/dev/null 2>&1
}

# Epoch seconds for "<today_override, or the real today> minus N
# days/months", at local midnight. today_override (YYYY-MM-DD), if given,
# lets callers (and tests) freeze "today" instead of using the real date -
# without it every purge always measures against the real wall clock, which
# is what production always wants.
_backup_prod_cutoff_epoch() {
    local amount="$1"
    local unit="$2"  # "days" or "months"
    local today_override="${3:-}"

    if [ -n "$today_override" ]; then
        if _backup_prod_is_bsd_date; then
            local base_epoch
            base_epoch=$(_backup_prod_date_to_epoch "$today_override") || return 1
            if [ "$unit" = "months" ]; then
                date -j -v-"${amount}"m -r "$base_epoch" +%s
            else
                date -j -v-"${amount}"d -r "$base_epoch" +%s
            fi
        else
            # GNU/uutils date: combining "@<epoch> -N <unit>" in one -d string is
            # NOT portable - GNU coreutils accepts it, but uutils coreutils (the
            # `date` shipped on the real WSL2 prod box, confirmed live 2026-09-14)
            # rejects it outright ("invalid date"). Applying the relative offset
            # to the plain "<today_override> 00:00:00" string instead, rather than
            # round-tripping through an epoch first, works identically on both.
            date -d "${today_override} 00:00:00 -${amount} ${unit}" +%s
        fi
    else
        if _backup_prod_is_bsd_date; then
            if [ "$unit" = "months" ]; then
                date -v-"${amount}"m -v0H -v0M -v0S +%s
            else
                date -v-"${amount}"d -v0H -v0M -v0S +%s
            fi
        else
            date -d "-${amount} ${unit} 00:00:00" +%s
        fi
    fi
}

# Epoch seconds for a YYYY-MM-DD string, at local midnight.
_backup_prod_date_to_epoch() {
    local datestr="$1"
    if _backup_prod_is_bsd_date; then
        date -j -f "%Y-%m-%d %H:%M:%S" "${datestr} 00:00:00" +%s 2>/dev/null
    else
        date -d "${datestr} 00:00:00" +%s 2>/dev/null
    fi
}

# Extracts the YYYY-MM-DD date from a denidin-prod-backup-YYYY-MM-DD.tgz
# filename. Returns non-zero (no output) if the filename doesn't match.
_backup_prod_extract_date() {
    local fname="$1"
    echo "$fname" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1
}

# purge_older_than <dir> <amount> <days|months> [today_override YYYY-MM-DD]
#
# Deletes every *.tgz in <dir> whose filename date is strictly older than
# "<amount> <unit> before today" (local time; real today unless
# today_override is given - used by run_daily_backup.sh to keep purge math
# consistent with a frozen --today, and by tests for determinism). Files
# whose name doesn't carry a recognizable YYYY-MM-DD are left untouched
# (never guessed-at). A missing directory is a no-op, not an error.
purge_older_than() {
    local dir="$1"
    local amount="$2"
    local unit="$3"
    local today_override="${4:-}"

    [ -d "$dir" ] || return 0

    local cutoff_epoch
    cutoff_epoch=$(_backup_prod_cutoff_epoch "$amount" "$unit" "$today_override") || return 1

    local f
    for f in "$dir"/*.tgz; do
        [ -e "$f" ] || continue
        local base datestr file_epoch
        base=$(basename "$f")
        datestr=$(_backup_prod_extract_date "$base")
        [ -z "$datestr" ] && continue
        file_epoch=$(_backup_prod_date_to_epoch "$datestr") || continue
        if [ "$file_epoch" -lt "$cutoff_epoch" ]; then
            rm -f "$f"
        fi
    done

    return 0
}
