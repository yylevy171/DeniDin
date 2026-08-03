#!/usr/bin/env bash
# Tails live logs for a prod service on the Windows box, from the Mac, via
# a Docker remote context — no SSH session, no remote-desktop needed.
# Creates the context automatically if it doesn't exist yet (idempotent —
# safe to run repeatedly). Wraps the command previously just documented as
# prose in quickstart.md's "Day-to-day operation" section. See spec.md
# FR4/FR5.
#
# Run this from the repo root (relies on the Mac's own local
# docker/docker-compose.prod.yml — the Windows box's copy is never read
# directly; Compose CLI always reads the file client-side).
#
# Usage: ./scripts/windows_prod/tail_logs.sh <ssh-host-alias> [service] [docker-context-name]
#
#   <ssh-host-alias>       Host entry in ~/.ssh/config for the Windows box.
#   [service]              denidin-app-prod (default) or morning-mcp-app-prod
#   [docker-context-name]  Docker context to use/create. Default: denidin-winprod

set -uo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> [service] [docker-context-name]}"
SERVICE="${2:-denidin-app-prod}"
DOCKER_CTX="${3:-denidin-winprod}"

if [ "$SERVICE" != "denidin-app-prod" ] && [ "$SERVICE" != "morning-mcp-app-prod" ]; then
  echo "Usage: $0 <ssh-host-alias> [denidin-app-prod|morning-mcp-app-prod] [docker-context-name]" >&2
  exit 1
fi

if ! docker context inspect "$DOCKER_CTX" >/dev/null 2>&1; then
  echo "Docker context '$DOCKER_CTX' not found — creating it..." >&2
  # Point the context at the ~/.ssh/config alias itself (ssh://<alias>), not
  # a spelled-out user@host: Docker's SSH URL parser rejects usernames
  # containing spaces (e.g. "yaron levi") outright, even percent-encoded
  # (verified against the real box, 2026-08-03 - "remote username contains
  # invalid characters"), whereas letting plain `ssh <alias>` resolve
  # User/HostName/IdentityFile from ~/.ssh/config itself works fine.
  docker context create "$DOCKER_CTX" --docker "host=ssh://$SSH_HOST"
fi

echo "Tailing $SERVICE on $SSH_HOST (Ctrl-C stops watching — does not stop the container)..." >&2
docker --context "$DOCKER_CTX" compose -f docker/docker-compose.prod.yml logs -f --tail 100 "$SERVICE"
