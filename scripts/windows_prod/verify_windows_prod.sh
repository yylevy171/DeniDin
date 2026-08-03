#!/usr/bin/env bash
# Read-only, non-disruptive acceptance checks for
# specs/035-windows-always-on-prod. Run from the Mac once the Windows box
# has been set up per quickstart.md. Never starts, stops, or reboots
# anything on the box — see verify_reboot_recovery.sh for the one
# disruptive check (T2.8), which is intentionally a separate script.
#
# Usage:
#   ./verify_windows_prod.sh <ssh-host-alias> [docker-context-name] [deploy-dir-name]
#
#   <ssh-host-alias>       Host entry in ~/.ssh/config for the Windows box,
#                          already pointing at user@<tailscale-hostname>
#                          with the right IdentityFile (see quickstart.md).
#   [docker-context-name]  Docker context to use/create. Default: denidin-winprod
#   [deploy-dir-name]      Deploy directory name on the box, relative to the
#                          logged-in user's home — NOT a git clone
#                          (corrected 2026-08-02, see quickstart.md §3).
#                          Default: denidin-prod
#
# NOTE (verified against the real box, 2026-08-03): the Windows box's
# OpenSSH sessions land in WSL2 bash (via a DefaultShell wrapper script —
# see quickstart.md §2.1a), not cmd.exe/PowerShell. Every native Windows
# CLI tool (`powercfg`, `schtasks`, `reg`, `netsh`) therefore needs an
# explicit `.exe` suffix to resolve through WSL interop — bash's PATH
# search doesn't do PATHEXT-style extension-less resolution the way
# cmd.exe does. `curl` and `docker` are native Linux binaries inside WSL
# and need no suffix. Also: `tailscale ping`/`tailscale ip` need the
# actual Tailscale machine hostname, not the `~/.ssh/config` alias
# (`$SSH_HOST`) — resolved below via `ssh -G`.

set -uo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> [docker-context-name] [deploy-dir-name]}"
DOCKER_CTX="${2:-denidin-winprod}"
DEPLOY_DIR="${3:-denidin-prod}"

# The Tailscale hostname (for `tailscale ping`/`tailscale ip`), resolved
# from the SSH alias's own configured HostName — these are two different
# identifiers even though they refer to the same box (see note above).
TS_HOST="$(ssh -G "$SSH_HOST" | awk '/^hostname /{print $2; exit}')"

PASS=0
FAIL=0
OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT

check() {
  local desc="$1"; shift
  if "$@" >"$OUT" 2>&1; then
    echo "PASS  $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL  $desc"
    sed 's/^/      /' "$OUT"
    FAIL=$((FAIL + 1))
  fi
}

ssh_run() {
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" "$@"
}
export -f ssh_run
export SSH_HOST

echo "== T1: connectivity & SSH access =="
check "Tailscale hostname resolved from SSH config alias" \
  bash -c "[ -n '$TS_HOST' ]"
check "Tailscale reachable (tailscale ping)" \
  tailscale ping -c 1 "$TS_HOST"
check "SSH key-based login succeeds, no password prompt" \
  ssh_run true
check "sshd firewall rule scoped to this box's own Tailscale IP" \
  bash -c "TS_IP=\$(tailscale ip -4 '$TS_HOST' 2>/dev/null); [ -n \"\$TS_IP\" ] && ssh_run 'netsh.exe advfirewall firewall show rule name=\"OpenSSH SSH Server (sshd)\" verbose' | grep -q \"LocalIP:.*\$TS_IP\""

echo
echo "== T1: deploy directory & config presence on the box (corrected 2026-08-02: no git clone) =="
check "Deploy directory exists at ~/$DEPLOY_DIR" \
  ssh_run "test -d ~/$DEPLOY_DIR"
check "Deploy directory is NOT a git repo (.git absent — build happens only on the Mac)" \
  bash -c "! ssh_run 'test -d ~/$DEPLOY_DIR/.git'"
check "config/config.prod.json present (both apps)" \
  ssh_run "test -f ~/$DEPLOY_DIR/apps/denidin-app/config/config.prod.json && test -f ~/$DEPLOY_DIR/apps/morning-mcp-app/config/config.prod.json"
check "config/shared_state.local.json present and points at an absolute .../shared path" \
  bash -c "ssh_run 'cat ~/$DEPLOY_DIR/config/shared_state.local.json' | grep -q '\"shared_state_dir\": *\"/[^\"]*/shared\"'"
check "docker-compose.prod.local.yml present and matches build_and_package.sh's generated no-op template" \
  bash -c "ssh_run 'grep -q \"^services: {}\$\" ~/$DEPLOY_DIR/docker/docker-compose.prod.local.yml'"

echo
echo "== T2: always-on power settings =="
echo "NOTE: lid-close action is NOT automated (verified 2026-08-03) — on this"
echo "Windows build, that setting isn't exposed under the classic powercfg"
echo "SUB_BUTTONS/LIDACTION alias at all (neither the general scheme dump nor"
echo "a direct GUID query returns it), only via the modern Settings app"
echo "(System > Power & battery > 'Closing the lid will make my PC...'). Eyeball"
echo "that setting manually instead — see acceptance-tests.md T2.1."
check "AC-power sleep timeout = never" \
  bash -c "ssh_run 'powercfg.exe /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE' | grep -A2 'AC Power' | grep -q '0x00000000'"

echo
echo "== T2a/T2b: reboot-recovery configuration (static config only — see verify_reboot_recovery.sh for the live end-to-end test) =="
check "Scheduled Task exists, enabled, targets run_all.sh prod" \
  bash -c "ssh_run 'schtasks.exe /query /tn DeniDinProdAutostart /v /fo list' | grep -qi 'Ready'"
check "Windows auto-logon is configured (AutoAdminLogon=1)" \
  bash -c "ssh_run 'reg.exe query \"HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon\" /v AutoAdminLogon' | grep -q '0x1$'"

echo
echo "== T4/T5: Docker remote context, logs, health & uptime =="
check "Docker context reachable" \
  docker context inspect "$DOCKER_CTX"
check "docker compose ps reachable via remote context" \
  docker --context "$DOCKER_CTX" compose -f docker/docker-compose.prod.yml ps
check "Both containers report Up (not Restarting/Exited)" \
  bash -c "docker --context '$DOCKER_CTX' compose -f docker/docker-compose.prod.yml ps --format '{{.State}}' | grep -c '^running$' | grep -q '^2$'"
check "Log output readable via remote context" \
  docker --context "$DOCKER_CTX" compose -f docker/docker-compose.prod.yml logs --tail 5 denidin-app-prod
check "morning-mcp-app-prod internal /health responds" \
  bash -c "ssh_run \"cd ~/$DEPLOY_DIR && PORT=\\\$(docker compose -f docker/docker-compose.prod.yml port morning-mcp-app-prod 8000 | cut -d: -f2) && curl -sf http://127.0.0.1:\\\$PORT/health\""

echo
echo "== T-M: sshfs data-folder mount on the Mac (FR6a, added 2026-08-02) =="
# T-M.2/T-M.3 deliberately hard-fail (not skip) if not mounted, rather than
# comparing/writing against a plain empty local directory - a `mkdir -p`'d
# but unmounted ~/denidin-winprod-data would otherwise make both checks
# trivially (and wrongly) PASS: an empty `ls` "matches" another empty `ls`,
# and `touch` "fails" on a merely-nonexistent path for the wrong reason.
check "~/denidin-winprod-data is mounted" \
  bash -c "mount | grep -qF 'on $HOME/denidin-winprod-data ('"
check "Mount contents match the box's own apps/denidin-app/data listing" \
  bash -c "mount | grep -qF 'on $HOME/denidin-winprod-data (' && diff <(ls ~/denidin-winprod-data | sort) <(ssh_run 'ls ~/$DEPLOY_DIR/apps/denidin-app/data' | sort)"
check "Mount is read-only (a write attempt fails)" \
  bash -c "mount | grep -qF 'on $HOME/denidin-winprod-data (' && ! touch ~/denidin-winprod-data/.verify_write_test_$$ 2>/dev/null"

echo
echo "== Summary: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
