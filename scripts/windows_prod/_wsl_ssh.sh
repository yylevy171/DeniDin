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
  # `< /dev/null` (bugfix-085, 2026-09-13): ssh forwards the calling shell's own stdin to the
  # remote command by default (BatchMode=yes only suppresses interactive prompts, it does NOT
  # stop stdin forwarding) - so a caller invoking this from inside a
  # `while read ... done <<< "$multi_line_string"` loop (deploy_release.sh's R5/R7 webapp
  # retag/presence-check loops, the only two-image app) had each ssh call silently drain the
  # REST of that here-string as its own stdin. The loop's next `read` then saw EOF and exited
  # after one iteration - no error anywhere, since nothing counted "did every line get
  # processed." Reproduced live against the real prod box (2 markers touched in a 2-line loop
  # became 1 without this fix, 2 with it) before landing this one-line change. Explicitly
  # detaching stdin here makes every remote_run call immune to whatever stdin its caller
  # happens to have open, regardless of call site.
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$ssh_host" "wsl.exe -e bash -c \"echo $b64 | base64 -d | bash\"" < /dev/null
}
export -f wsl_ssh_run
