#!/usr/bin/env bash
set -uo pipefail

# Feature 059 - drift check for the sanity suite.
#
# The sanity subset is defined in two places (see scripts/run_sanity.sh's
# header for why): the @pytest.mark.sanity decorators, and the node-id arrays
# in run_sanity.sh. This script asserts they match exactly, per app.
#
# Run it by hand after adding/removing a @pytest.mark.sanity anywhere, or
# after editing run_sanity.sh's arrays. Nothing runs it automatically (no CI).
# Exit 0 = in sync; exit 1 = drift (prints the diff).

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_SANITY="${ROOT}/scripts/run_sanity.sh"
RC=0

check_app() {
  local app_dir="$1" want_app="$2"
  local py="${app_dir}/venv/bin/python3"
  if [ ! -x "$py" ]; then
    echo "SKIP ${app_dir##*/}: no venv at $py" >&2
    return 0
  fi

  # What pytest thinks is @pytest.mark.sanity (authoritative for -m sanity).
  local collected
  collected="$(cd "$app_dir" && "$py" -m pytest -m sanity --collect-only -q 2>/dev/null \
    | grep -E '^tests/.*::' | sed 's/\[[0-9]*\]$//' | sort -u)"

  # What run_sanity.sh lists for this app. Array entries are "<app>|<nodeid>"
  # where <app> is `mm` or `den`; strip the prefix, keep only this app's.
  local listed
  listed="$(grep -oE '"(mm|den)\|tests/[^"]+"' "$RUN_SANITY" | tr -d '"' \
    | grep "^${want_app}|" | sed "s/^${want_app}|//" | sort -u)"

  local d
  d="$(diff <(echo "$collected") <(echo "$listed"))"
  if [ -n "$d" ]; then
    echo "DRIFT in ${app_dir##*/} (< only @pytest.mark.sanity, > only in run_sanity.sh):"
    echo "$d"
    RC=1
  else
    echo "OK ${app_dir##*/}: $(echo "$collected" | grep -c .) sanity tests, lists match."
  fi
}

check_app "${ROOT}/apps/denidin-app" "den"
check_app "${ROOT}/apps/morning-mcp-app" "mm"

exit "$RC"
