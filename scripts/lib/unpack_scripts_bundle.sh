#!/bin/bash
# Extracts a release's shared ops-scripts bundle (bugfix-043) into a target directory and
# verifies every expected file actually landed. Runs identically whether invoked locally (this
# is exactly how scripts/tests/test_release_scripts_bundle.py proves the mechanism works,
# without ever touching real prod) or remotely over SSH by scripts/deploy_release.sh's prod
# path (Feature 035's Windows box) - same code, same verification, no special-casing.
#
# Usage: unpack_scripts_bundle.sh <bundle-tar-path> <target-dir>
#   <bundle-tar-path> : a *-scripts.tar.gz produced by scripts/cut_release.sh
#   <target-dir>      : where to extract it - for a real prod deploy, the deploy directory
#                        root (e.g. ~/denidin-prod); for a test, any scratch directory.
#
# Exits 0 and prints "OK: ..." only if extraction succeeded AND every file in
# RELEASE_SCRIPTS_BUNDLE_FILES (scripts/lib/release_scripts_manifest.sh) is present afterward.
# Never partially "succeeds" - any missing file is a loud failure naming exactly what's missing.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/release_scripts_manifest.sh"

BUNDLE_TAR="$1"
TARGET_DIR="$2"

if [ -z "$BUNDLE_TAR" ] || [ -z "$TARGET_DIR" ]; then
    echo "Usage: $0 <bundle-tar-path> <target-dir>" >&2
    exit 2
fi

if [ ! -f "$BUNDLE_TAR" ]; then
    echo "Error: scripts bundle not found: ${BUNDLE_TAR}" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

set +e
tar -xzf "$BUNDLE_TAR" -C "$TARGET_DIR"
EXTRACT_STATUS=$?
set -e
if [ "$EXTRACT_STATUS" -ne 0 ]; then
    echo "Error: extracting ${BUNDLE_TAR} into ${TARGET_DIR} failed (tar exit ${EXTRACT_STATUS})." >&2
    exit 1
fi

MISSING=()
for f in "${RELEASE_SCRIPTS_BUNDLE_FILES[@]}"; do
    if [ ! -f "${TARGET_DIR}/${f}" ]; then
        MISSING+=("$f")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Error: scripts bundle extraction incomplete at ${TARGET_DIR} - missing: ${MISSING[*]}" >&2
    exit 1
fi

echo "OK: scripts bundle extracted and verified at ${TARGET_DIR} (${#RELEASE_SCRIPTS_BUNDLE_FILES[@]} files)"
