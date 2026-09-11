#!/bin/bash
# Cuts a release for ALL apps at ONE shared version + ONE shared summary (2026-09-07, bugfix-043
# follow-up) - one call to scripts/cut_release_single.sh per app, in a fixed order, same version
# string and same --summary text for every app.
#
# Why this exists: scripts/cut_release_single.sh cuts exactly one app per call. When every app is
# being released together at the same version (the common case - e.g. this bugfix's own b43v3/
# b43v4 cuts, done as two manual back-to-back calls before this script existed), calling it once
# per app by hand means retyping the same version/summary N times, with no guard against a typo
# making them drift. This script is that loop, made explicit and safe.
#
# App list is intentionally a single, easy-to-extend array (ADD_NEW_APPS_HERE) - two more apps
# (UI-frontend, UI-backend) are already waiting on this same release tooling; adding either one
# here is the only change needed to include it in every future "all apps" cut. Order matches
# scripts/run_all.sh's own start order (morning-mcp-app before denidin-app - see CLAUDE.md's
# "Order matters" note) purely for consistency with scripts/deploy_release.sh's app list; cutting
# itself has no cross-app ordering dependency (each cut_release_single.sh call is independent).
#
# Each app's cut still goes through cut_release_single.sh UNCHANGED - same preconditions
# (uncommitted-changes check, bundle-file-presence check, immutability check), same permanent-
# action confirmation prompt (once per app - deliberately not merged into a single combined
# prompt; each app's cut is its own permanent, independent side effect, per REQ-REL-006), same
# specs/done/ sweep (idempotent across apps - the second app's call finds nothing left to sweep
# once the first has already moved everything into the shared vVERSION/ folder, a harmless no-op,
# see cut_release_single.sh's own step 3b comment), same failure/revert behavior. This script adds
# nothing except the loop and the "same version+summary for every app" convenience - it is not a
# reimplementation.
#
# Stops on the first app's failure (bash `set -e` propagating a non-zero cut_release_single.sh
# exit) - whichever apps already cut successfully stay cut (REQ-REL-006: a cut is permanent and
# immutable once it happens), and the remaining apps are simply not attempted. Rerunning this
# script for the same version after a partial failure is safe: cut_release_single.sh's own
# immutability precondition (existing tag/artifact) means an already-cut app is skipped as an
# error you'd see and can work around by cutting only the remaining app(s) via
# cut_release_single.sh directly - this script has no "resume" mode of its own.
#
# 🚨 HUMAN-ONLY, HARD CONSTRAINT (CLAUDE.md): <version> and --summary below must always come
# directly from a human in that specific request. No AI agent may compute, suggest, or default a
# version number or summary text - see REQ-REL-002/003. This is the exact same rule as
# cut_release_single.sh's own - looping over apps changes nothing about who decides these values.
#
# Usage: ./scripts/cut_release.sh <version> --summary "<text>" [--artifacts-root <path>]
#   <version> : exact semantic version, e.g. 1.4.2 (no leading "v") - applied to EVERY app
#   --summary : required, human-written one-line summary - the SAME text used for every app's
#               CHANGELOG.md/RELEASES.md entry (REQ-REL-003). For genuinely independent per-app
#               summaries, use cut_release_single.sh separately for each app instead.
#   --artifacts-root : optional override of the artifacts folder (test-only seam; real
#                      invocations never pass this - defaults to the real shared folder)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ADD_NEW_APPS_HERE - the single place to extend this script to a new app.
# webapp (Feature 068) is a two-image app; cut_release_single.sh handles that fan-out
# internally, so it's just another entry here. Cutting has no cross-app ordering dependency.
APPS=(morning-mcp-app denidin-app webapp)

DEFAULT_ARTIFACTS_ROOT="/Users/yaron/Projects/DeniDin/artifacts"

VERSION=""
SUMMARY=""
ARTIFACTS_ROOT="$DEFAULT_ARTIFACTS_ROOT"

POSITIONAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --summary)
            SUMMARY="$2"
            shift 2
            ;;
        --artifacts-root)
            ARTIFACTS_ROOT="$2"
            shift 2
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

VERSION="${POSITIONAL[0]}"

usage() {
    echo "Usage: $0 <version> --summary \"<text>\" [--artifacts-root <path>]" >&2
}

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$ ]]; then
    echo "Error: <version> must be MAJOR.MINOR.PATCH with an optional -suffix (got: '${VERSION}')." >&2
    usage
    exit 2
fi

if [ -z "$SUMMARY" ]; then
    echo "Error: --summary \"<text>\" is required (human-written, not auto-generated - REQ-REL-003)." >&2
    usage
    exit 2
fi

CUT_SINGLE_SCRIPT="$SCRIPT_DIR/cut_release_single.sh"
if [ ! -f "$CUT_SINGLE_SCRIPT" ]; then
    echo "Error: ${CUT_SINGLE_SCRIPT} not found." >&2
    exit 1
fi

echo "== Cutting v${VERSION} for ${#APPS[@]} app(s): ${APPS[*]} =="
for APP in "${APPS[@]}"; do
    echo ""
    echo "== [$APP] cutting v${VERSION} =="
    if ! "$CUT_SINGLE_SCRIPT" "$APP" "$VERSION" --summary "$SUMMARY" --artifacts-root "$ARTIFACTS_ROOT"; then
        echo "🚨 CUT FAILED for ${APP} v${VERSION} - stopping. Any app(s) already cut above remain cut (immutable, REQ-REL-006); ${APP} and every app after it in the list (${APPS[*]}) were not attempted." >&2
        exit 1
    fi
done

echo ""
echo "✅ Cut v${VERSION} successfully for all ${#APPS[@]} app(s): ${APPS[*]}"
