#!/usr/bin/env bash
# Read-only, non-disruptive acceptance checks for
# specs/done/035-windows-always-on-prod. Run from the Mac once the Windows box
# has been set up per quickstart.md. Never starts, stops, or reboots
# anything on the box — see verify_reboot_recovery.sh for the one
# disruptive check (T2.8), which is intentionally a separate script.
#
# Usage:
#   ./verify_windows_prod.sh <ssh-host-alias> [docker-context-name] [deploy-dir-name] [remote-data-dir-name]
#
#   <ssh-host-alias>       Host entry in ~/.ssh/config for the Windows box,
#                          already pointing at user@<tailscale-hostname>
#                          with the right IdentityFile (see quickstart.md).
#   [docker-context-name]  Docker context to use/create. Default: denidin-winprod
#   [deploy-dir-name]      Deploy directory name on the box, relative to the
#                          logged-in user's home — NOT a git clone
#                          (corrected 2026-08-02, see quickstart.md §3).
#                          Default: denidin-prod
#   [remote-data-dir-name] The prod data folder's name, relative to the
#                          Windows-side home (NOT the deploy dir - see
#                          2026-08-03 note below). Default: denidin-prod-data
#
# NOTE (verified against the real box, 2026-08-03): OpenSSH's DefaultShell
# is left at its NATIVE default (cmd.exe) — pointing it at a WSL-bash
# wrapper breaks the SFTP subsystem `mount_data.sh`/sshfs depends on
# (subsystem launches get routed through a custom DefaultShell too, and
# either hang or exit instantly depending on how the path is spelled — the
# native default doesn't have this problem). So every remote *bash*
# command below wraps itself client-side instead, via `ssh_run` (see
# `_wsl_ssh.sh` — base64-encoded to sidestep nested cmd.exe/bash quoting
# entirely). Once inside that bash session, every native Windows CLI tool
# (`powercfg`, `schtasks`, `reg`, `netsh`) still needs an explicit `.exe`
# suffix to resolve through WSL interop — bash's PATH search doesn't do
# PATHEXT-style extension-less resolution the way cmd.exe does. `curl` and
# `docker` are native Linux binaries inside WSL and need no suffix. Also:
# `tailscale ping`/`tailscale ip` need the actual Tailscale machine
# hostname, not the `~/.ssh/config` alias (`$SSH_HOST`) — resolved below
# via `ssh -G`.
#
# Every check below is a dedicated named function, deliberately NOT
# `bash -c "...ssh_run..."` + `export -f` — `export -f` doesn't reliably
# propagate to a nested `bash -c` in every execution environment (verified
# 2026-08-03: silently absent from the environment in at least one real
# case, causing "ssh_run: command not found" failures that look like
# genuine check failures). Named functions in this same shell need no
# export at all.

set -uo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_wsl_ssh.sh"

SSH_HOST="${1:?Usage: $0 <ssh-host-alias> [docker-context-name] [deploy-dir-name] [remote-data-dir-name]}"
DOCKER_CTX="${2:-denidin-winprod}"
DEPLOY_DIR="${3:-denidin-prod}"
REMOTE_DATA_DIR="${4:-denidin-prod-data}"

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
  wsl_ssh_run "$SSH_HOST" "$@"
}

ts_host_resolved() { [ -n "$TS_HOST" ]; }

firewall_scoped_to_tailscale_ip() {
  local ts_ip
  ts_ip="$(tailscale ip -4 "$TS_HOST" 2>/dev/null)"
  [ -n "$ts_ip" ] && ssh_run 'netsh.exe advfirewall firewall show rule name="OpenSSH SSH Server (sshd)" verbose' | grep -q "LocalIP:.*$ts_ip"
}

deploy_dir_not_a_git_repo() {
  ! ssh_run "test -d ~/$DEPLOY_DIR/.git"
}

shared_state_local_json_valid() {
  ssh_run "cat ~/$DEPLOY_DIR/config/shared_state.local.json" | grep -q '"shared_state_dir": *"/[^"]*/shared"'
}

# Rewritten 2026-08-03: this file is no longer a generated no-op stub (see
# build_and_package.sh's header comment) - it's a one-time, hand-created,
# machine-specific override redirecting the data volume to a native
# Windows-side path (so sshfs can reach it - Windows SFTP can't traverse
# into WSL2's filesystem at all). Just check it exists and mentions the
# data volume's container-side mount point, not any specific content.
compose_local_override_present() {
  ssh_run "grep -q '/app/data' ~/$DEPLOY_DIR/docker/docker-compose.prod.local.yml"
}

sleep_timeout_never() {
  ssh_run 'powercfg.exe /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE' | grep -A2 'AC Power' | grep -q '0x00000000'
}

# Rewritten 2026-08-03: Task Scheduler is no longer used for reboot
# recovery at all - two real reboots both showed neither an "At startup"
# nor an "At logon" trigger ever fired (Last Run Time stayed at the
# never-ran placeholder both times), for reasons not pinned down despite
# real investigation. Replaced with a plain Startup-folder script instead
# (see quickstart.md §7) - much simpler, no trigger-timing behavior to get
# wrong.
startup_script_present() {
  ssh_run "cat \"\$(wslpath -u \"\$(cmd.exe /c echo %APPDATA% | tr -d '\\r')\")/Microsoft/Windows/Start Menu/Programs/Startup/DeniDinProdAutostart.cmd\"" | grep -qF 'run_all.sh prod'
}

auto_logon_configured() {
  # Loosened 2026-08-03: reg.exe's output has a trailing blank line whose
  # own \r survives bash's command-substitution trailing-newline-stripping
  # (only \n gets stripped, not \r), which occasionally left a stray \r
  # right before grep's real match line in a way that intermittently broke
  # a strict end-of-line anchor here - not worth chasing further (the
  # setting itself is independently confirmed correct via manual
  # `reg.exe query`); match anywhere on the line instead of anchoring.
  ssh_run 'reg.exe query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon' | grep -qE 'REG_SZ\s+1\b'
}

both_containers_up() {
  docker --context "$DOCKER_CTX" compose -f docker/docker-compose.prod.yml ps --format '{{.State}}' | grep -c '^running$' | grep -q '^2$'
}

morning_health_responds() {
  ssh_run "cd ~/$DEPLOY_DIR && PORT=\$(docker compose -f docker/docker-compose.prod.yml port morning-mcp-app-prod 8000 | cut -d: -f2) && curl -sf http://127.0.0.1:\$PORT/health"
}

data_mount_present() {
  mount | grep -qF "on $HOME/denidin-winprod-data ("
}

# Rewritten 2026-08-03: compares against the native Windows-side data
# path (resolved dynamically via wslpath, same technique as
# deploy_and_verify.sh), not the old WSL-relative path - Windows SFTP
# (which sshfs rides) can't reach the WSL filesystem at all, so the data
# volume lives on the Windows side now (see docker-compose.prod.local.yml).
data_mount_contents_match() {
  data_mount_present && diff <(ls ~/denidin-winprod-data | sort) <(ssh_run "WIN_HOME=\$(wslpath -u \"\$(cmd.exe /c echo %USERPROFILE% | tr -d '\\r')\") && ls \"\$WIN_HOME/$REMOTE_DATA_DIR\"" | sort)
}

data_mount_is_read_only() {
  data_mount_present && ! touch "$HOME/denidin-winprod-data/.verify_write_test_$$" 2>/dev/null
}

echo "== T1: connectivity & SSH access =="
check "Tailscale hostname resolved from SSH config alias" \
  ts_host_resolved
check "Tailscale reachable (tailscale ping)" \
  tailscale ping -c 1 "$TS_HOST"
check "SSH key-based login succeeds, no password prompt" \
  ssh_run true
check "sshd firewall rule scoped to this box's own Tailscale IP" \
  firewall_scoped_to_tailscale_ip

echo
echo "== T1: deploy directory & config presence on the box (corrected 2026-08-02: no git clone) =="
check "Deploy directory exists at ~/$DEPLOY_DIR" \
  ssh_run "test -d ~/$DEPLOY_DIR"
check "Deploy directory is NOT a git repo (.git absent — build happens only on the Mac)" \
  deploy_dir_not_a_git_repo
check "config/config.prod.json present (both apps)" \
  ssh_run "test -f ~/$DEPLOY_DIR/apps/denidin-app/config/config.prod.json && test -f ~/$DEPLOY_DIR/apps/morning-mcp-app/config/config.prod.json"
check "config/shared_state.local.json present and points at an absolute .../shared path" \
  shared_state_local_json_valid
check "docker-compose.prod.local.yml present, overrides the data volume to a Windows-side path" \
  compose_local_override_present

echo
echo "== T2: always-on power settings =="
echo "NOTE: lid-close action is NOT automated (verified 2026-08-03) — on this"
echo "Windows build, that setting isn't exposed under the classic powercfg"
echo "SUB_BUTTONS/LIDACTION alias at all (neither the general scheme dump nor"
echo "a direct GUID query returns it), only via the modern Settings app"
echo "(System > Power & battery > 'Closing the lid will make my PC...'). Eyeball"
echo "that setting manually instead — see acceptance-tests.md T2.1."
check "AC-power sleep timeout = never" \
  sleep_timeout_never

echo
echo "== T2a/T2b: reboot-recovery configuration (static config only — see verify_reboot_recovery.sh for the live end-to-end test) =="
check "Startup-folder script present, targets run_all.sh prod" \
  startup_script_present
check "Windows auto-logon is configured (AutoAdminLogon=1)" \
  auto_logon_configured

echo
echo "== T4/T5: Docker remote context, logs, health & uptime =="
check "Docker context reachable" \
  docker context inspect "$DOCKER_CTX"
check "docker compose ps reachable via remote context" \
  docker --context "$DOCKER_CTX" compose -f docker/docker-compose.prod.yml ps
check "Both containers report Up (not Restarting/Exited)" \
  both_containers_up
check "Log output readable via remote context" \
  docker --context "$DOCKER_CTX" compose -f docker/docker-compose.prod.yml logs --tail 5 denidin-app-prod
check "morning-mcp-app-prod internal /health responds" \
  morning_health_responds

echo
echo "== T-M: sshfs data-folder mount on the Mac (FR6a, added 2026-08-02) =="
# T-M.2/T-M.3 deliberately hard-fail (not skip) if not mounted, rather than
# comparing/writing against a plain empty local directory - a `mkdir -p`'d
# but unmounted ~/denidin-winprod-data would otherwise make both checks
# trivially (and wrongly) PASS: an empty `ls` "matches" another empty `ls`,
# and `touch` "fails" on a merely-nonexistent path for the wrong reason.
check "~/denidin-winprod-data is mounted" \
  data_mount_present
check "Mount contents match the box's own data directory listing" \
  data_mount_contents_match
check "Mount is read-only (a write attempt fails)" \
  data_mount_is_read_only

echo
echo "== Summary: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
