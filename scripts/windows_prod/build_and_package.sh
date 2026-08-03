#!/usr/bin/env bash
# Builds both prod images on the Mac and packages everything the Windows
# box needs to RUN (never build) into a single .tar.gz under the repo's
# gitignored artifacts/ folder. This is the 2026-08-02 "build once on the
# Mac, deploy-only on the Windows box" correction (spec.md/research.md) —
# no source code, no build tooling, ever touches the Windows box.
#
# Deliberately excluded from the artifact, always:
#   - config/config.prod.json (secrets — created once by hand on the box)
#   - apps/*/data, apps/*/logs, shared/ (persistent state — must survive
#     every redeploy untouched)
#   - config/shared_state.local.json — generated remotely at deploy time
#     instead (by deploy_and_verify.sh, using the Windows box's own $PWD),
#     since a correct absolute path can't be known from the Mac side.
#   - docker/docker-compose.prod.local.yml — corrected 2026-08-03: this
#     used to be generated fresh (a static no-op stub) on every deploy,
#     but on this box it needs to be a REAL, machine-specific override
#     (redirecting the data volume to a native Windows-side path so sshfs
#     can reach it - Windows' SFTP server can't traverse into WSL2's
#     filesystem at all). A real override can't be safely regenerated
#     blindly every deploy, so like config.prod.json it's now a one-time,
#     hand-created file on the box, never touched by any deploy again.
#
# Usage: ./build_and_package.sh [output-basename]
#
#   [output-basename]   Base name for the artifact, without .tar.gz.
#                        Default: denidin-prod-<short-git-sha>-<UTC-timestamp>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="docker/docker-compose.prod.yml"
LOCAL_OVERRIDE="docker/docker-compose.prod.local.yml"
COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE")
if [ -f "$LOCAL_OVERRIDE" ]; then
  COMPOSE_ARGS+=(-f "$LOCAL_OVERRIDE")
fi

GIT_SHA="$(git rev-parse --short HEAD)"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_NAME="${1:-denidin-prod-${GIT_SHA}-${TIMESTAMP}}"

ARTIFACTS_DIR="$REPO_ROOT/artifacts"
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

mkdir -p "$ARTIFACTS_DIR"

# All progress output goes to stderr - stdout is reserved for the final
# artifact path only, so callers (deploy_and_verify.sh) can do
# ARTIFACT_PATH="$(build_and_package.sh)" without any output scraping.
echo "== Building prod images for linux/amd64 (the Windows box's architecture, regardless of this Mac's own chip) ==" >&2
docker compose "${COMPOSE_ARGS[@]}" build --platform linux/amd64 denidin-app-prod morning-mcp-app-prod >&2

echo >&2
echo "== Resolving the exact image names Compose targets (no guessing its naming convention) ==" >&2
IMAGES="$(docker compose "${COMPOSE_ARGS[@]}" config --images)"
echo "$IMAGES" >&2
if [ -z "$IMAGES" ]; then
  echo "FAIL: docker compose config --images returned nothing" >&2
  exit 1
fi

echo >&2
echo "== Saving images to one tar ==" >&2
mkdir -p "$STAGE_DIR/images"
# shellcheck disable=SC2086
docker save -o "$STAGE_DIR/images/prod-images.tar" $IMAGES >&2

echo >&2
echo "== Staging non-secret runtime files ==" >&2
mkdir -p "$STAGE_DIR/docker" "$STAGE_DIR/scripts" \
         "$STAGE_DIR/apps/denidin-app/config" "$STAGE_DIR/apps/morning-mcp-app"

cp "$COMPOSE_FILE" "$STAGE_DIR/docker/"

# docker-compose.prod.local.yml is deliberately NOT generated here anymore
# (see the header comment above) - it's a one-time, hand-created file on
# the box itself, excluded from every artifact so a redeploy never
# clobbers its machine-specific data-volume override.

cp scripts/run_all.sh scripts/stop_all.sh scripts/killall_containers.sh scripts/env_lock.sh \
  "$STAGE_DIR/scripts/"

cp apps/denidin-app/run_denidin.sh apps/denidin-app/stop_denidin.sh apps/denidin-app/restart_denidin.sh \
  "$STAGE_DIR/apps/denidin-app/"
cp apps/denidin-app/config/runtime_constitution.md \
  "$STAGE_DIR/apps/denidin-app/config/"

cp apps/morning-mcp-app/run_morning_mcp.sh apps/morning-mcp-app/stop_morning_mcp.sh apps/morning-mcp-app/restart_morning_mcp.sh \
  "$STAGE_DIR/apps/morning-mcp-app/"

echo >&2
echo "== Packaging ==" >&2
ARTIFACT_PATH="$ARTIFACTS_DIR/$OUT_NAME.tar.gz"
tar czf "$ARTIFACT_PATH" -C "$STAGE_DIR" .

echo >&2
echo "Artifact ready: $ARTIFACT_PATH ($(du -h "$ARTIFACT_PATH" | cut -f1))" >&2
echo "$ARTIFACT_PATH"
