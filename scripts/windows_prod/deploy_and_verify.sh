#!/usr/bin/env bash
# Deploys a new version to the Windows production box, entirely from the
# Mac, and runs an automated smoke check (clean startup, no errors in
# logs). Rewritten 2026-08-02: builds happen only on the Mac
# (build_and_package.sh), never on the Windows box — see spec.md/research.md's
# "build once on the Mac, deploy-only on Windows" correction. The box only
# ever runs `docker load` + `docker compose up -d` against an already-built
# image; it never runs `git pull` or `docker compose build` itself.
#
# What this does, in order:
#   1. build_and_package.sh — build both prod images (linux/amd64) and
#      package them + non-secret runtime files into artifacts/*.tar.gz
#   2. scp the artifact to the box's deploy directory
#   3. ssh in: extract the tarball (never touches config.prod.json,
#      data/, logs/, or shared/ — none of those are in the archive),
#      generate config/shared_state.local.json using the box's own $PWD
#      (can't be known correctly from the Mac side), docker load both
#      images, docker compose up -d
#   4. Smoke-check recent logs for startup errors
#
# The one thing this script deliberately does NOT do is the final,
# definitive proof that the new version actually works: sending a real
# WhatsApp message and confirming a DeniDin response. That's left manual
# (see acceptance-tests.md T-D.4) — it's the real production number and a
# real, billed OpenAI call, disproportionate to automate for what the
# operator can just as easily do by hand in 30 seconds.
#
# Usage: ./deploy_and_verify.sh <ssh-host-alias> [deploy-dir-name]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> [deploy-dir-name]}"
DEPLOY_DIR="${2:-denidin-prod}"

ssh_run() {
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" "$@"
}

echo "== Building and packaging on the Mac =="
ARTIFACT_PATH="$("$SCRIPT_DIR/build_and_package.sh")"
if [ -z "$ARTIFACT_PATH" ] || [ ! -f "$ARTIFACT_PATH" ]; then
  echo "FAIL: build_and_package.sh did not produce a usable artifact" >&2
  exit 1
fi
ARTIFACT_NAME="$(basename "$ARTIFACT_PATH")"
echo "Artifact: $ARTIFACT_PATH"

echo
echo "== Shipping the artifact to the box =="
if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$ARTIFACT_PATH" "$SSH_HOST:~/$ARTIFACT_NAME"; then
  echo "FAIL: scp" >&2
  exit 1
fi

echo
echo "== Extracting on the box (data/, logs/, shared/, config.prod.json are never in the archive — left untouched) =="
if ! ssh_run "mkdir -p ~/$DEPLOY_DIR && tar xzf ~/$ARTIFACT_NAME -C ~/$DEPLOY_DIR && rm ~/$ARTIFACT_NAME"; then
  echo "FAIL: remote extraction" >&2
  exit 1
fi

echo
echo "== Regenerating config/shared_state.local.json on the box (uses its own \$PWD — can't be known correctly from the Mac side) =="
if ! ssh_run "cd ~/$DEPLOY_DIR && mkdir -p config && printf '{\"shared_state_dir\": \"%s/shared\"}' \"\$(pwd)\" > config/shared_state.local.json"; then
  echo "FAIL: generating shared_state.local.json" >&2
  exit 1
fi

echo
echo "== Loading images on the box =="
if ! ssh_run "cd ~/$DEPLOY_DIR && docker load -i images/prod-images.tar"; then
  echo "FAIL: docker load" >&2
  exit 1
fi

COMPOSE="cd ~/$DEPLOY_DIR && docker compose --project-directory . -f docker/docker-compose.prod.yml -f docker/docker-compose.prod.local.yml"

echo
echo "== Recreating prod containers (never invokes build: — the loaded images already match) =="
if ! ssh_run "$COMPOSE up -d"; then
  echo "FAIL: docker compose up -d" >&2
  exit 1
fi

echo
echo "== Waiting for containers to settle =="
sleep 15
ssh_run "cd ~/$DEPLOY_DIR && docker compose -f docker/docker-compose.prod.yml ps"

echo
echo "== Smoke-checking recent logs for startup errors =="
SMOKE_LOG="$(mktemp)"
trap 'rm -f "$SMOKE_LOG"' EXIT
ssh_run "cd ~/$DEPLOY_DIR && docker compose -f docker/docker-compose.prod.yml logs --tail 50 denidin-app-prod" | tee "$SMOKE_LOG"
if grep -qiE 'traceback|critical|fatal' "$SMOKE_LOG"; then
  echo
  echo "FAIL: possible startup error found in logs — review above" >&2
  exit 1
fi

echo
echo "Automated deploy steps complete (Mac build + package + ship + remote load/up + log smoke-check all passed)."
echo
echo "Now do the manual step (T-D.4 in acceptance-tests.md):"
echo "  -> Send a real WhatsApp message to the bot and confirm you get a DeniDin response."
echo "     (Intentionally not automated — real number, real billed OpenAI call.)"
