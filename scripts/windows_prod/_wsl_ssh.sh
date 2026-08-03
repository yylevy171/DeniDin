# Shared helper, sourced by every scripts/windows_prod/*.sh that runs bash
# commands on the Windows box over SSH. Not standalone, not executable.
#
# Windows OpenSSH's DefaultShell is deliberately left at its native default
# (cmd.exe) — NOT pointed at a WSL-bash wrapper — because doing so breaks
# the SFTP subsystem sshfs/mount_data.sh depends on (verified against the
# real box, 2026-08-03: with a custom DefaultShell, `sftp-server.exe`
# either hangs or exits instantly depending on how its path is spelled,
# since subsystem launches get routed through the custom shell too, unlike
# with the native default). So every remote *bash* command instead wraps
# itself client-side via `wsl.exe -e bash -c "..."` — base64-encoded, to
# sidestep nested cmd.exe/bash quoting entirely (a base64 payload has no
# shell-special characters at any layer, no escaping needed).
wsl_ssh_run() {
  local ssh_host="$1"; shift
  local cmd="$*"
  local b64
  b64="$(printf '%s' "$cmd" | base64 | tr -d '\n')"
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$ssh_host" "wsl.exe -e bash -c \"echo $b64 | base64 -d | bash\""
}
export -f wsl_ssh_run
