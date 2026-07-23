#!/bin/bash
# Shared helper library for the cross-clone dev/prod environment lock.
# Sourced by run_denidin.sh, stop_denidin.sh, run_morning_mcp.sh,
# stop_morning_mcp.sh, and killall_containers.sh in every clone (this
# original clone, coder1, coder2, ...). Not meant to be run directly.
#
# Model: at most one environment (dev OR prod, never both) may be active
# across ALL clones on this machine at once. "dev" is additionally locked
# to whichever clone (coder) acquired it, until that same coder releases it
# (or -force is used). "prod" is never owner-locked - any clone may
# start/stop it once no dev lock is held.
#
# Lock state lives in $SHARED_STATE_DIR/active_env.json (a directory shared
# across clones via a symlink at each clone's ./shared, resolved from each
# clone's own gitignored ./shared_state.local.json - see CLAUDE.md).
#
# Schema: {"active_env": "dev"|"prod"|null, "owner": "<coder-id>"|null, "updated_at": "..."}
# "owner" is only meaningful when active_env == "dev"; always null otherwise.

_env_lock_repo_root() {
    # REPO_ROOT must already be set by the sourcing script.
    echo "$REPO_ROOT"
}

# Identity of the clone invoking the script: the personality NAME assigned
# to that clone (not the folder name) - each coder's lock ownership is
# tracked by who they are, not where they happen to be checked out.
# Mirrors the .claude/personalities/<dirname>.md dispatch convention
# (dirname -> personality file -> Name: line), with the same "DeniDin"
# folder -> root personality special case.
env_lock_identity() {
    local dirname personality_file name
    dirname="$(basename "$(_env_lock_repo_root)")"
    if [ "$dirname" = "DeniDin" ]; then
        dirname="root"
    fi
    personality_file="$(_env_lock_repo_root)/.claude/personalities/$dirname.md"

    if [ -f "$personality_file" ]; then
        name="$(grep -m1 '^Name: ' "$personality_file" | sed 's/^Name: //')"
    fi

    if [ -n "$name" ]; then
        echo "$name"
    else
        echo "$dirname"
    fi
}

# Ensure ./shared resolves to the canonical per-machine shared-state dir
# declared in ./shared_state.local.json. Self-healing: creates the symlink
# (and the canonical dir, if genuinely missing) if not already set up.
env_lock_ensure_shared_symlink() {
    local repo_root config_file shared_link canon
    repo_root="$(_env_lock_repo_root)"
    config_file="$repo_root/shared_state.local.json"
    shared_link="$repo_root/shared"

    if [ ! -f "$config_file" ]; then
        echo "ERROR: $config_file not found." >&2
        echo "Create it with: {\"shared_state_dir\": \"/absolute/path/to/canonical/shared-state\"}" >&2
        exit 1
    fi

    canon="$(python3 -c "import json; print(json.load(open('$config_file'))['shared_state_dir'])")"

    if [ -z "$canon" ]; then
        echo "ERROR: shared_state_dir missing/empty in $config_file" >&2
        exit 1
    fi

    mkdir -p "$canon"

    if [ -L "$shared_link" ]; then
        local current
        current="$(readlink "$shared_link")"
        if [ "$current" != "$canon" ]; then
            echo "ERROR: $shared_link already symlinked to '$current', not '$canon'." >&2
            echo "Resolve manually before continuing (do not overwrite silently)." >&2
            exit 1
        fi
    elif [ -e "$shared_link" ]; then
        echo "ERROR: $shared_link exists and is not a symlink. Resolve manually." >&2
        exit 1
    else
        ln -s "$canon" "$shared_link"
    fi
}

# Reads the lock into $LOCK_ACTIVE_ENV / $LOCK_OWNER ("null" string if unset).
env_lock_read() {
    local repo_root lock_file
    repo_root="$(_env_lock_repo_root)"
    lock_file="$repo_root/shared/active_env.json"

    if [ ! -f "$lock_file" ]; then
        LOCK_ACTIVE_ENV="null"
        LOCK_OWNER="null"
        return
    fi

    LOCK_ACTIVE_ENV="$(python3 -c "
import json
d = json.load(open('$lock_file'))
print(d.get('active_env') or 'null')
")"
    LOCK_OWNER="$(python3 -c "
import json
d = json.load(open('$lock_file'))
print(d.get('owner') or 'null')
")"
}

_env_lock_write() {
    local active_env="$1" owner="$2"
    local repo_root lock_file
    repo_root="$(_env_lock_repo_root)"
    lock_file="$repo_root/shared/active_env.json"

    python3 -c "
import json
from datetime import datetime, timezone
active_env = $( [ "$active_env" = "null" ] && echo "None" || echo "'$active_env'" )
owner = $( [ "$owner" = "null" ] && echo "None" || echo "'$owner'" )
with open('$lock_file', 'w', encoding='utf-8') as f:
    json.dump({'active_env': active_env, 'owner': owner, 'updated_at': datetime.now(timezone.utc).isoformat()}, f, indent=2)
    f.write('\n')
"
}

# Call before starting dev/prod containers. Exits with an error message if
# the requested env is not startable right now. On success, acquires/
# refreshes the lock.
#
# Usage: env_lock_acquire dev|prod
env_lock_acquire() {
    local requested="$1" me
    me="$(env_lock_identity)"
    env_lock_ensure_shared_symlink
    env_lock_read

    if [ "$requested" = "dev" ]; then
        if [ "$LOCK_ACTIVE_ENV" = "prod" ]; then
            echo "ERROR: prod is currently active. Stop it first (./killall_containers.sh, or stop_*.sh prod) before starting dev." >&2
            exit 1
        fi
        if [ "$LOCK_ACTIVE_ENV" = "dev" ] && [ "$LOCK_OWNER" != "null" ] && [ "$LOCK_OWNER" != "$me" ]; then
            echo "ERROR: dev is locked by '$LOCK_OWNER'. Ask them to free it (stop_*.sh dev), or use -force to override." >&2
            exit 1
        fi
        _env_lock_write "dev" "$me"
    else
        if [ "$LOCK_ACTIVE_ENV" = "dev" ]; then
            echo "ERROR: dev is currently active (owner: $LOCK_OWNER). Stop it first before starting prod." >&2
            exit 1
        fi
        _env_lock_write "prod" "null"
    fi
}

# Call before stopping/releasing dev/prod containers for THIS clone/service.
# Exits with an error if a non-owner tries to release a dev lock without
# -force. On success, clears the lock to null/null.
#
# Usage: env_lock_release dev|prod [-force]
env_lock_release() {
    local requested="$1" force="$2" me
    me="$(env_lock_identity)"
    env_lock_ensure_shared_symlink
    env_lock_read

    if [ "$requested" = "dev" ] && [ "$LOCK_ACTIVE_ENV" = "dev" ]; then
        if [ "$LOCK_OWNER" != "null" ] && [ "$LOCK_OWNER" != "$me" ] && [ "$force" != "-force" ]; then
            echo "ERROR: dev is locked by '$LOCK_OWNER', not '$me'. Refusing to stop/release it." >&2
            echo "       Pass -force to override (only if you're sure), or ask '$LOCK_OWNER' to stop it." >&2
            exit 1
        fi
    fi

    _env_lock_write "null" "null"
}
