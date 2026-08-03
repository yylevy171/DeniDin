#!/bin/bash
# Cuts a release for one app: bumps VERSION, builds+tags+exports a Docker image as a durable
# artifact, appends CHANGELOG.md/RELEASES.md entries, and applies a git tag. Deploys nothing
# anywhere - see scripts/deploy_release.sh for that (Feature 034, REQ-REL-001/005).
#
# 🚨 HUMAN-ONLY, HARD CONSTRAINT (CLAUDE.md): <app> and <version> below must always come
# directly from a human in that specific request. No AI agent may compute, suggest, or default
# a version number - see REQ-REL-002.
#
# Usage: ./scripts/cut_release.sh <app> <version> --summary "<text>" [--artifacts-root <path>]
#   <app>     : denidin-app | morning-mcp-app
#   <version> : exact semantic version, e.g. 1.4.2 (no leading "v")
#   --summary : required, human-written one-line summary for CHANGELOG.md/RELEASES.md
#   --artifacts-root : optional override of the artifacts folder (test-only seam; real
#                      invocations never pass this - defaults to the real shared folder)
#
# See specs/in-progress/034-versioning-release-mgmt/contracts/cut_release_cli.md for the full
# contract (preconditions, side effects, exit codes).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DEFAULT_ARTIFACTS_ROOT="/Users/yaron/Projects/DeniDin/artifacts"

APP=""
VERSION=""
SUMMARY=""
ARTIFACTS_ROOT="$DEFAULT_ARTIFACTS_ROOT"

# First two positional args, then optional flags in any order.
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

APP="${POSITIONAL[0]}"
VERSION="${POSITIONAL[1]}"

usage() {
    echo "Usage: $0 <denidin-app|morning-mcp-app> <version> --summary \"<text>\" [--artifacts-root <path>]" >&2
}

if [ "$APP" != "denidin-app" ] && [ "$APP" != "morning-mcp-app" ]; then
    echo "Error: <app> must be denidin-app or morning-mcp-app (got: '${APP}')." >&2
    usage
    exit 2
fi

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

APP_DIR="apps/${APP}"
TAG="${APP}-v${VERSION}"
TAR_PATH="${ARTIFACTS_ROOT}/${APP}/${APP}-v${VERSION}.tar"
MANIFEST_PATH="${ARTIFACTS_ROOT}/${APP}/${APP}-v${VERSION}.json"

# --- Preconditions (fail before any side effect) ---

if git rev-parse --verify --quiet "refs/tags/${TAG}" >/dev/null; then
    echo "Error: tag ${TAG} already exists - refusing to re-cut an existing release (REQ-REL-006)." >&2
    exit 1
fi

if [ -f "$TAR_PATH" ]; then
    echo "Error: artifact already exists at ${TAR_PATH} - refusing to overwrite (REQ-REL-006)." >&2
    exit 1
fi

if [ -n "$(git status --porcelain "$APP_DIR")" ]; then
    echo "Error: ${APP_DIR} has uncommitted changes - commit or stash before cutting a release." >&2
    exit 1
fi

# --- Interactive confirmation (before anything irreversible) ---

CURRENT_VERSION="$(cat "${APP_DIR}/VERSION" 2>/dev/null || echo unknown)"
echo "About to cut ${APP} v${VERSION}:"
echo "  - from commit: $(git rev-parse --short HEAD)"
echo "  - VERSION file: ${CURRENT_VERSION} -> ${VERSION}"
echo "  - git tag: ${TAG} (new)"
echo "  - artifact: ${TAR_PATH}"
echo ""
echo "This is permanent (REQ-REL-006) - continue? [y/N]"
read -r CONFIRM
if ! [[ "$CONFIRM" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    echo "Aborted - nothing changed."
    exit 0
fi

# --- Side effects (in order) ---
#
# IMPORTANT (2026-08-02, real-world bug found cutting the actual first release): the build step
# is the one most likely to fail (Docker daemon down, network, etc.), so it MUST happen BEFORE
# any git commit - otherwise a failed build leaves a dangling "release:" commit with no matching
# tag/artifact, and a naive re-run appends a SECOND duplicate CHANGELOG.md/RELEASES.md entry on
# top of it (exactly what happened; caught and cleaned up by hand before this fix landed).
# VERSION/CHANGELOG/RELEASES are updated on disk first (the build needs the bumped VERSION baked
# in), but nothing is committed until the build AND save both succeed - a failure at either point
# reverts those working-tree changes and exits, leaving zero trace.

RELEASE_DATE="$(date -u +%Y-%m-%d)"

_revert_uncommitted_release_files() {
    git checkout -- "${APP_DIR}/VERSION" "${APP_DIR}/CHANGELOG.md" "${APP_DIR}/RELEASES.md"
}

# 1. Update VERSION (uncommitted)
echo "$VERSION" > "${APP_DIR}/VERSION"

# 2. Prepend/append CHANGELOG.md entry (terse index, uncommitted)
{
    echo ""
    echo "## [${VERSION}] - ${RELEASE_DATE}"
    echo ""
    echo "$SUMMARY"
} >> "${APP_DIR}/CHANGELOG.md"

# 3. Append RELEASES.md section (fuller notes, uncommitted)
{
    echo ""
    echo "## ${APP} v${VERSION} — ${RELEASE_DATE}"
    echo ""
    echo "$SUMMARY"
} >> "${APP_DIR}/RELEASES.md"

# 4. Build the image - BEFORE any commit (see note above)
set +e
docker build -t "${APP}:${VERSION}" "${APP_DIR}" -q >/dev/null
BUILD_STATUS=$?
set -e
if [ "$BUILD_STATUS" -ne 0 ]; then
    echo "Error: docker build failed - reverting VERSION/CHANGELOG.md/RELEASES.md, no commit made." >&2
    _revert_uncommitted_release_files
    exit 1
fi

# 5. Export it as the durable artifact - also before any commit
mkdir -p "${ARTIFACTS_ROOT}/${APP}"
set +e
docker save "${APP}:${VERSION}" -o "$TAR_PATH"
SAVE_STATUS=$?
set -e
if [ "$SAVE_STATUS" -ne 0 ]; then
    echo "Error: docker save failed - reverting VERSION/CHANGELOG.md/RELEASES.md, no commit made." >&2
    rm -f "$TAR_PATH"
    _revert_uncommitted_release_files
    exit 1
fi

# 6. NOW commit - both docker steps already succeeded, so this commit will always have a
#    matching artifact/tag.
git add "${APP_DIR}/VERSION" "${APP_DIR}/CHANGELOG.md" "${APP_DIR}/RELEASES.md"
git commit -q -m "release: ${APP} v${VERSION}"
COMMIT_SHA="$(git rev-parse HEAD)"

# 7. Write the manifest
IMAGE_ID="$(docker inspect --format '{{.Id}}' "${APP}:${VERSION}")"
cat > "$MANIFEST_PATH" <<EOF
{
  "app": "${APP}",
  "version": "${VERSION}",
  "date": "${RELEASE_DATE}",
  "git_commit": "${COMMIT_SHA}",
  "image_id": "${IMAGE_ID}"
}
EOF

# 8. Tag the commit
git tag "$TAG"

echo "Cut ${TAG} successfully: ${TAR_PATH}"
