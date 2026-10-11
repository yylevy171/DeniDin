#!/bin/bash
# Shared helper library for the cross-clone dev/prod environment lock.
# Sourced by run_denidin.sh, stop_denidin.sh, run_morning_mcp.sh,
# stop_morning_mcp.sh, and killall_containers.sh in every clone (this
# original clone, teammate1, teammate2, ...). Not meant to be run directly.
#
# Model (2026-08-05 - dev+prod concurrency ban lifted): dev and prod may now
# both be active at once, independently - see CLAUDE.md's "Environments
# (dev/prod)" section, "Asymmetry update (2026-08-03)": each environment now
# has fully separate WhatsApp/Green API/Green Invoice infrastructure, so the
# original conflict (two containers polling the same Green API instance)
# no longer exists. What's still locked: "dev" is locked to whichever clone
# (coder) acquired it, until that same coder releases it (or -force is
# used) - this is a separate concern (two clones' dev containers can still
# collide with each other, e.g. on data volumes) and is unaffected by this
# change. "prod" is never owner-locked, was never affected by the dev+prod
# ban, and still isn't.
#
# Lock state lives in $SHARED_STATE_DIR/active_env.json (a directory shared
# across clones via a symlink at each clone's ./shared, resolved from each
# clone's own gitignored ./config/shared_state.local.json - see CLAUDE.md).
#
# Schema: {"active_envs": {"dev": {"owner": "<coder-id>"}, "prod": {"owner": null}}, "updated_at": "..."}
# An environment key is present in "active_envs" iff it's currently active;
# absence means not active. Either, both, or neither key may be present at
# once. "owner" is only meaningful under "dev"; always null under "prod".
#
# Old schema (pre-2026-08-05): {"active_env": "dev"|"prod"|null, "owner": ...}.
# watchdog.py in both apps was updated in lockstep (same commit) to read the
# new schema - see there for why an old-code/new-schema or new-code/old-schema
# mismatch during a rollout window degrades safely (skips its check) rather
# than false-triggering.

_env_lock_repo_root() {
    # REPO_ROOT must already be set by the sourcing script.
    echo "$REPO_ROOT"
}

# The one canonical, machine-wide DEV clone (Mac only). Hardcoded (same convention already used
# for scripts/deploy_release.sh's DEFAULT_ARTIFACTS_ROOT and the shared-state dir) rather than
# derived, because it must be a single fixed answer independent of which clone is asking. This has
# NOTHING to do with prod: prod runs on an entirely different machine (Feature 035's Windows box,
# a totally different folder, e.g. ~/denidin-prod) reached over SSH, is never owner-locked (see
# this file's header), and has no multi-clone concept at all - there is exactly one copy of prod's
# checkout, so there is nothing for it to ever collide with. Every function below that uses this
# constant is therefore dev-only and a hard no-op for prod, by construction (scoped on `$ENV`,
# never on `uname`/platform - see env_lock_require_canonical_root's own comment for why a
# platform-only gate isn't enough).
_ENV_LOCK_CANONICAL_ROOT="/Users/yaron/Projects/DeniDin"

# True iff $repo_root is either the canonical root itself, or a clone nested inside it
# (teammate1-5 are real subdirectories of the canonical root's own working tree, not siblings -
# confirmed via `git status` listing them as untracked entries inside it). This is what makes
# every function below automatically safe for: prod (an unrelated path on a different machine,
# never matches), and every existing test's scratch tmp_path fixture (scripts/tests/,
# scripts/health_monitoring/tests/, which copy these real scripts into an isolated throwaway tree
# under pytest's own tmp dir - nowhere near this constant either) - neither needs any special
# platform/env carve-out, because neither path ever matches this pattern in the first place.
_env_lock_is_canonical_family() {
    case "$1" in
        "$_ENV_LOCK_CANONICAL_ROOT"|"$_ENV_LOCK_CANONICAL_ROOT"/*) return 0 ;;
        *) return 1 ;;
    esac
}

# Resolves the right absolute deploy-target root for THIS invocation of scripts/deploy_release.sh
# (its local, dev/prod-on-this-Mac path only): if this checkout is the canonical root clone or one
# of its nested teammate clones, always the canonical root itself (regardless of which one was
# actually invoked) - if it's anything else (a test's scratch repo, living entirely outside this
# family), the checkout's own REPO_ROOT, unchanged, so self-contained test fixtures keep working
# exactly as before. deploy_release.sh's own top-level code still runs wherever it was invoked
# (its flags/logic never move) - only which stop_env.sh/run_env.sh it hands off to changes.
env_lock_deploy_target_root() {
    local repo_root
    repo_root="$(_env_lock_repo_root)"
    if _env_lock_is_canonical_family "$repo_root"; then
        echo "$_ENV_LOCK_CANONICAL_ROOT"
    else
        echo "$repo_root"
    fi
}

# Refuses to continue if THIS script is a nested teammate clone's own copy being run directly for
# `dev` (bypassing deploy_release.sh's own hand-off above) - dev's runtime state
# (config.dev.json, active_env.json, mcp-status-dev, logs, the health-monitoring LaunchAgent) is a
# single, machine-global target, never per-clone. A true no-op for: `prod` (never owner-locked, no
# multi-clone concept at all - not even worth a platform check, since prod's real path, on a
# different machine entirely, could never accidentally match this constant anyway - see this
# file's header), running from the canonical root itself, and every existing test's scratch
# tmp_path fixture (never lives anywhere under $_ENV_LOCK_CANONICAL_ROOT to begin with).
#
# 2026-09-28 design (replaces an earlier same-day attempt at silently RETARGETING REPO_ROOT
# mid-script, and before that, a `uname`-only Darwin gate - both were too broad: the first
# accumulated "did every downstream path get retargeted correctly" bugs, the second would have
# refused inside this exact same Mac's own real, non-mocked test suite, which copies these real
# scripts into scratch tmp_path trees and runs them for real). Path-prefix + `$ENV` scoping is both
# necessary and sufficient: it catches exactly the real incident (a nested teammate clone invoked
# directly for dev) and nothing else.
#
# Real incident this exists to prevent (2026-09-27): a dev deploy run from a teammate clone
# silently rebound the local docker compose --project-directory AND the health-monitoring
# LaunchAgent to that clone's own checkout.
#
# Usage: env_lock_require_canonical_root <dev|prod>   (reads $REPO_ROOT, already set by the caller)
env_lock_require_canonical_root() {
    local env="$1" repo_root
    if [ "$env" != "dev" ]; then
        return 0
    fi
    repo_root="$(_env_lock_repo_root)"
    if [ "$repo_root" = "$_ENV_LOCK_CANONICAL_ROOT" ]; then
        return 0
    fi
    if ! _env_lock_is_canonical_family "$repo_root"; then
        return 0
    fi
    echo "🚨 ERROR: this script must run from the canonical DeniDin folder ($_ENV_LOCK_CANONICAL_ROOT)," >&2
    echo "          not $repo_root." >&2
    echo "" >&2
    echo "dev's runtime state (config.dev.json, active_env.json, mcp-status-dev, logs, the" >&2
    echo "health-monitoring LaunchAgent) is a single, machine-global target - it is never per-clone." >&2
    echo "Run this via scripts/deploy_release.sh (fine to invoke from any clone - it resolves this" >&2
    echo "path itself before handing off), or run it directly from $_ENV_LOCK_CANONICAL_ROOT." >&2
    exit 1
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
# declared in ./config/shared_state.local.json. Self-healing: creates the
# symlink (and the canonical dir, if genuinely missing) if not already set up.
env_lock_ensure_shared_symlink() {
    local repo_root config_file shared_link canon
    repo_root="$(_env_lock_repo_root)"
    config_file="$repo_root/config/shared_state.local.json"
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

# Reads the lock into $LOCK_DEV_ACTIVE / $LOCK_DEV_OWNER / $LOCK_PROD_ACTIVE
# ("true"/"false" for the *_ACTIVE vars, "null" string for an unset owner).
# Tolerates a missing file (nothing active) and the old pre-2026-08-05
# single-active_env schema (read as "nothing active" - see this file's
# header comment on why that's a safe degraded state, not a bug).
env_lock_read() {
    local repo_root lock_file
    repo_root="$(_env_lock_repo_root)"
    lock_file="$repo_root/shared/active_env.json"

    if [ ! -f "$lock_file" ]; then
        LOCK_DEV_ACTIVE="false"
        LOCK_DEV_OWNER="null"
        LOCK_PROD_ACTIVE="false"
        return
    fi

    LOCK_DEV_ACTIVE="$(python3 -c "
import json
d = json.load(open('$lock_file'))
print('true' if 'dev' in (d.get('active_envs') or {}) else 'false')
")"
    LOCK_DEV_OWNER="$(python3 -c "
import json
d = json.load(open('$lock_file'))
dev = (d.get('active_envs') or {}).get('dev') or {}
print(dev.get('owner') or 'null')
")"
    LOCK_PROD_ACTIVE="$(python3 -c "
import json
d = json.load(open('$lock_file'))
print('true' if 'prod' in (d.get('active_envs') or {}) else 'false')
")"
}

# Sets/clears exactly one environment's entry, leaving the other's untouched.
# Usage: _env_lock_write_env dev|prod <owner-or-null> | _env_lock_write_env dev|prod REMOVE
_env_lock_write_env() {
    local env="$1" owner_or_remove="$2"
    local repo_root lock_file
    repo_root="$(_env_lock_repo_root)"
    lock_file="$repo_root/shared/active_env.json"

    python3 -c "
import json
from datetime import datetime, timezone
try:
    with open('$lock_file', encoding='utf-8') as f:
        d = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    d = {}
active_envs = d.get('active_envs') or {}
env = '$env'
action = '$owner_or_remove'
if action == 'REMOVE':
    active_envs.pop(env, None)
else:
    owner = None if action == 'null' else action
    active_envs[env] = {'owner': owner}
with open('$lock_file', 'w', encoding='utf-8') as f:
    json.dump({'active_envs': active_envs, 'updated_at': datetime.now(timezone.utc).isoformat()}, f, indent=2)
    f.write('\n')
"
}

# Call before building compose args, before env_lock_acquire. Exits loudly
# if this clone's mandatory per-clone compose override file
# (docker/docker-compose.$env.local.yml) is missing. EVERY clone - the
# root/canonical one included - MUST have this file created by hand; the
# root clone's own copy is an intentional no-op stub ("services: {}"), since
# its paths are already canonical, but the file itself must still exist so
# this check can't silently skip it.
#
# Real incident this check exists to prevent (2026-07-30, teammate2/Bina): this
# file was missing in a coderN clone, so docker-compose.<env>.yml's own
# plain relative volume paths resolved against THAT clone's own directory
# instead of being overridden to point at the shared root-clone paths - the
# dev container silently started writing session/memory/log data into the
# clone's own apps/denidin-app/dev_data instead of the real, shared history,
# with no error or warning of any kind. This must never happen silently
# again - refusing to start at all (not a warning) is deliberate.
#
# Usage: env_lock_require_local_override dev|prod
env_lock_require_local_override() {
    local env="$1" repo_root override_file
    repo_root="$(_env_lock_repo_root)"
    override_file="$repo_root/docker/docker-compose.$env.local.yml"

    if [ ! -f "$override_file" ]; then
        echo "ERROR: $override_file not found." >&2
        echo "" >&2
        echo "Every clone (root, teammate1, teammate2, ...) MUST have this file, created by hand -" >&2
        echo "see CLAUDE.md's 'Multi-clone lock' / 'dev/prod data is also a singleton across" >&2
        echo "clones' sections. Without it, this clone's dev/prod data+log volumes silently" >&2
        echo "fall back to THIS clone's own directory instead of the shared canonical" >&2
        echo "location (real incident, 2026-07-30 - a coderN clone's dev container wrote" >&2
        echo "session/log data into its own apps/denidin-app/dev_data instead of the real" >&2
        echo "shared history, with zero warning)." >&2
        echo "" >&2
        echo "Fix: create $override_file. Copy an existing coderN clone's file (e.g." >&2
        echo "teammate1's docker/docker-compose.dev.local.yml) and adjust if needed; if this IS" >&2
        echo "the root/canonical clone, use a no-op stub: 'services: {}'." >&2
        echo "Refusing to start until this file exists - this is deliberate, not a bug." >&2
        exit 1
    fi
}

# Call before starting dev/prod containers. Exits with an error message if
# the requested env is not startable right now (dev locked by a different
# clone). On success, acquires/refreshes that env's entry, leaving the
# other environment's entry (active or not) untouched - dev and prod may
# both be active at once (2026-08-05 - see this file's header comment).
#
# Usage: env_lock_acquire dev|prod
env_lock_acquire() {
    local requested="$1" me
    me="$(env_lock_identity)"
    env_lock_ensure_shared_symlink
    env_lock_read

    if [ "$requested" = "dev" ]; then
        if [ "$LOCK_DEV_ACTIVE" = "true" ] && [ "$LOCK_DEV_OWNER" != "null" ] && [ "$LOCK_DEV_OWNER" != "$me" ]; then
            echo "ERROR: dev is locked by '$LOCK_DEV_OWNER'. Ask them to free it (stop_*.sh dev), or use -force to override." >&2
            exit 1
        fi
        _env_lock_write_env "dev" "$me"
    else
        _env_lock_write_env "prod" "null"
    fi
}

# Call before stopping/releasing dev/prod containers for THIS clone/service.
# Exits with an error if a non-owner tries to release a dev lock without
# -force. On success, clears that env's entry only - the other environment's
# entry (active or not) is untouched.
#
# Usage: env_lock_release dev|prod [-force]
env_lock_release() {
    local requested="$1" force="$2" me
    me="$(env_lock_identity)"
    env_lock_ensure_shared_symlink
    env_lock_read

    if [ "$requested" = "dev" ] && [ "$LOCK_DEV_ACTIVE" = "true" ]; then
        if [ "$LOCK_DEV_OWNER" != "null" ] && [ "$LOCK_DEV_OWNER" != "$me" ] && [ "$force" != "-force" ]; then
            echo "ERROR: dev is locked by '$LOCK_DEV_OWNER', not '$me'. Refusing to stop/release it." >&2
            echo "       Pass -force to override (only if you're sure), or ask '$LOCK_DEV_OWNER' to stop it." >&2
            exit 1
        fi
    fi

    _env_lock_write_env "$requested" "REMOVE"
}
