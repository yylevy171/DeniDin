#!/usr/bin/env bash
# DISRUPTIVE: reboots the real Windows production box to verify
# FR2a/FR2b/US5/SC5 (auto-logon + Scheduled Task reboot recovery) end to
# end. This is a live test against real production, not a simulation.
#
# Run this only deliberately (e.g. a planned maintenance window) — same
# discipline this repo already applies to `billed`/`expensive` pytest
# tests: explicit human approval for that specific run, never routine,
# never bundled into a sweep of other checks.
#
# An AI agent must NEVER invoke this script on its own initiative. It
# restarts real production, which CLAUDE.md's "never start an environment
# without explicit approval" rule squarely covers — treat a run of this
# script exactly like starting an environment: ask first, every time.
#
# Usage:
#   ./verify_reboot_recovery.sh <ssh-host-alias> --i-understand-this-reboots-production [deploy-dir-name]

set -uo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> --i-understand-this-reboots-production [deploy-dir-name]}"
CONFIRM="${2:-}"
DEPLOY_DIR="${3:-denidin-prod}"

if [ "$CONFIRM" != "--i-understand-this-reboots-production" ]; then
  echo "Refusing to run: this reboots the real production Windows box." >&2
  echo "Re-run with: $0 $SSH_HOST --i-understand-this-reboots-production" >&2
  exit 1
fi

echo "Rebooting $SSH_HOST ..."
ssh -o BatchMode=yes "$SSH_HOST" "shutdown /r /t 0"

echo "Waiting for it to actually go down..."
sleep 15

echo "Polling for it to come back over Tailscale (up to 10 minutes)..."
UP=0
for i in $(seq 1 60); do
  if ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" true 2>/dev/null; then
    echo "Back up after ~$((i * 10))s"
    UP=1
    break
  fi
  sleep 10
done

if [ "$UP" -eq 0 ]; then
  echo "FAIL: box did not come back over Tailscale within 10 minutes" >&2
  exit 1
fi

echo "Checking Docker Desktop started and both containers came back up on their own..."
sleep 30  # give Docker Desktop + the Scheduled Task a moment after login
ssh -o BatchMode=yes "$SSH_HOST" \
  "cd ~/$DEPLOY_DIR && docker compose -f docker/docker-compose.prod.yml ps"
