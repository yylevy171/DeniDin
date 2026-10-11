#!/bin/bash
# Sourceable config loader for scripts/backup_prod/*.sh (Feature 078).
#
# Usage: source this file, then call:
#   load_backup_config "<path-to-config.json>" required_key1 required_key2 ...
# On success, sets one uppercased global var per JSON top-level key present in
# the file (e.g. "data_dir" -> $DATA_DIR). On failure (file missing, invalid
# JSON, or a required key missing/empty) prints a clear message to stderr and
# returns non-zero - never exits the calling shell (callers decide whether to
# `exit` on failure), consistent with this being a sourced library, not a
# standalone script.
#
# Requires the `jq` CLI (CONSTITUTION SS I: config-is-code, no env vars - see
# plan.md's Primary Dependencies / speckit.analyze finding F1 for why this
# dependency is called out explicitly rather than assumed).

load_backup_config() {
    local config_path="$1"
    shift
    local required_keys=("$@")

    if ! command -v jq >/dev/null 2>&1; then
        echo "ERROR: load_backup_config: 'jq' is required but not found on PATH" >&2
        return 1
    fi

    if [ -z "$config_path" ] || [ ! -f "$config_path" ]; then
        echo "ERROR: load_backup_config: config file not found: '$config_path'" >&2
        return 1
    fi

    if ! jq empty "$config_path" >/dev/null 2>&1; then
        echo "ERROR: load_backup_config: '$config_path' is not valid JSON" >&2
        return 1
    fi

    local key
    for key in "${required_keys[@]}"; do
        local value
        value=$(jq -r --arg k "$key" 'if has($k) then (.[$k] // "") else "" end' "$config_path")
        if [ -z "$value" ]; then
            echo "ERROR: load_backup_config: required key '$key' missing or empty in '$config_path'" >&2
            return 1
        fi
        local var_name
        var_name=$(echo "$key" | tr '[:lower:]' '[:upper:]')
        export "${var_name}=${value}"
    done

    return 0
}
