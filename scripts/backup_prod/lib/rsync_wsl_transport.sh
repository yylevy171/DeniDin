#!/bin/bash
# Custom "ssh" replacement for pull_backups.sh's `rsync -e`, routing the
# remote `rsync --server` invocation through WSL2 on the real Windows prod
# box.
#
# Why this exists: that box's SSH DefaultShell is deliberately cmd.exe, not
# WSL bash (see scripts/windows_prod/_wsl_ssh.sh's own header - a custom
# DefaultShell would break the SFTP subsystem sshfs depends on). A plain
# `rsync -e "ssh ..."` sends its remote command as ONE concatenated string
# for the remote shell to parse - fine for a real POSIX login shell, but
# cmd.exe re-splits on spaces differently, and this box's real backup dirs
# live under a Windows username with a space in it ("Yaron Levi") - a raw
# invocation fails outright (confirmed live, 2026-09-14:
# `link_stat "/mnt/c/Users/Yaron" failed`).
#
# Fix: never let cmd.exe see the remote rsync command line at all.
#   1. Reconstruct rsync's intended remote command from our own argv
#      (POSIX-quoted via `printf %q`, built entirely in bash before cmd.exe
#      is ever involved) and write it to a small script at a FIXED,
#      space-free path inside WSL (one ssh round-trip, one-shot, base64-
#      encoded the same way scripts/windows_prod/_wsl_ssh.sh's
#      wsl_ssh_run() already does elsewhere in this repo for exactly this
#      DefaultShell constraint).
#   2. `exec` a SECOND ssh call that just runs that fixed-path script
#      directly - no spaces on this command line, so cmd.exe can't
#      mis-split it, and critically no `| base64 -d | bash` PIPE this time
#      (a pipe breaks rsync's duplex protocol stream by handing rsync a
#      pipe's read end as stdin instead of the real SSH channel - confirmed
#      live, 2026-09-14: "connection unexpectedly closed").
#
# rsync invokes the -e program as:
#   <this-script> [ssh-opts...] <host> rsync <remote-rsync-server-args...>
# so the host is identified as the argv slot immediately before the literal
# "rsync" token (rsync's own remote command always starts with the binary
# name) rather than by any flag-counting, which would need to know every
# ssh option that consumes a following value.
set -e

ARGS=("$@")
CMD_IDX=-1
i=0
for a in "${ARGS[@]}"; do
    if [ "$a" = "rsync" ]; then
        CMD_IDX=$i
        break
    fi
    i=$((i+1))
done

if [ "$CMD_IDX" -lt 1 ]; then
    echo "rsync_wsl_transport.sh: could not find 'rsync' in argv: ${ARGS[*]}" >&2
    exit 1
fi

HOST_IDX=$((CMD_IDX - 1))
HOST="${ARGS[$HOST_IDX]}"

SSH_OPTS=()
for ((j = 0; j < HOST_IDX; j++)); do
    SSH_OPTS+=("${ARGS[$j]}")
done

REMOTE_CMD_ARGS=("${ARGS[@]:$CMD_IDX}")

REMOTE_CMD=""
for a in "${REMOTE_CMD_ARGS[@]}"; do
    REMOTE_CMD="${REMOTE_CMD} $(printf '%q' "$a")"
done

REMOTE_SCRIPT_PATH="/tmp/.denidin_rsync_cmd.sh"
SCRIPT_CONTENT="#!/bin/bash
exec ${REMOTE_CMD}
"
B64=$(printf '%s' "$SCRIPT_CONTENT" | base64 | tr -d '\n')

ssh "${SSH_OPTS[@]}" "$HOST" "wsl.exe -e bash -c \"echo $B64 | base64 -d > $REMOTE_SCRIPT_PATH\"" < /dev/null

exec ssh "${SSH_OPTS[@]}" "$HOST" "wsl.exe -e bash $REMOTE_SCRIPT_PATH"
