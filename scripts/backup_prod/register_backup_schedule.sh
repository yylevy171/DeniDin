#!/bin/bash
# Registers/enables, disables, or triggers-once the OS-native schedule for
# Feature 078's backup scripts. Mirrors
# scripts/health_monitoring/register_prober_schedule.sh's Darwin/Linux split
# exactly (see that script's own header comment for the full platform
# rationale - same wsl.exe/schtasks.exe interop deploy_release.sh already
# relies on for the real Windows prod box).
#
# Two distinct jobs, each tied to the one platform that actually runs it:
#   - "run"  (run_daily_backup.sh): Linux/WSL2 only - the real Windows prod
#     box, via a native Windows Scheduled Task, daily at 03:00 (system-local
#     time; the box's system timezone is expected to already be Israel per
#     Feature 035 setup - this script does not itself change system tz).
#   - "pull" (pull_backups.sh): Darwin only - a macOS LaunchAgent, hourly
#     (StartInterval), so the Mac catches up on whatever's new whenever it's
#     next awake, tolerating sleep across the Windows side's fixed 03:00 run
#     (research.md R4).
#
# Usage: register_backup_schedule.sh <run|pull> enable|disable|trigger-once --config <path>
#
# The Linux/schtasks.exe branch has NO automated test coverage (same
# documented gap as register_prober_schedule.sh's own Linux branch and
# deploy_release.sh's remote path) - verified manually against the real box.
# The Darwin/launchctl branch is real, testable launchd - covered by
# scripts/backup_prod/tests/test_register_backup_schedule.py.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ROLE="$1"
ACTION="$2"
CONFIG_PATH=""

shift 2 2>/dev/null || true
while [ $# -gt 0 ]; do
    case "$1" in
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [ "$ROLE" != "run" ] && [ "$ROLE" != "pull" ]; then
    echo "Usage: $0 run|pull enable|disable|trigger-once --config <path>" >&2
    exit 1
fi
if [ "$ACTION" != "enable" ] && [ "$ACTION" != "disable" ] && [ "$ACTION" != "trigger-once" ]; then
    echo "Usage: $0 run|pull enable|disable|trigger-once --config <path>" >&2
    exit 1
fi
if [ "$ACTION" != "disable" ] && [ -z "$CONFIG_PATH" ]; then
    echo "ERROR: --config <path> is required for enable/trigger-once" >&2
    exit 1
fi

LABEL="com.denidin.backup${ROLE}"
TASK_NAME="DeniDinBackup-${ROLE}"

_runner_for_role() {
    if [ "$ROLE" = "run" ]; then
        echo "$SCRIPT_DIR/run_daily_backup.sh"
    else
        echo "$SCRIPT_DIR/pull_backups.sh"
    fi
}

_darwin() {
    if [ "$ROLE" != "pull" ]; then
        echo "ERROR: role 'run' is Linux/WSL2-only (the real Windows prod box) - use 'pull' on Darwin." >&2
        exit 1
    fi

    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_path="${plist_dir}/${LABEL}.plist"
    local runner
    runner=$(_runner_for_role)
    local log_dir="${REPO_ROOT}/logs/backup_prod"

    case "$ACTION" in
        enable)
            mkdir -p "$plist_dir" "$log_dir"
            cat > "$plist_path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${runner}</string>
        <string>--config</string>
        <string>${CONFIG_PATH}</string>
    </array>
    <key>StartInterval</key><integer>3600</integer>
    <key>RunAtLoad</key><true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>StandardOutPath</key><string>${log_dir}/launchd.${ROLE}.out.log</string>
    <key>StandardErrorPath</key><string>${log_dir}/launchd.${ROLE}.err.log</string>
</dict>
</plist>
PLIST
            launchctl unload "$plist_path" >/dev/null 2>&1 || true
            launchctl load "$plist_path"
            echo "Enabled LaunchAgent ${LABEL} (${plist_path})"
            ;;
        disable)
            if [ -f "$plist_path" ]; then
                launchctl unload "$plist_path" >/dev/null 2>&1 || true
                rm -f "$plist_path"
            fi
            echo "Disabled LaunchAgent ${LABEL}"
            ;;
        trigger-once)
            if [ -f "$plist_path" ]; then
                launchctl start "$LABEL"
            else
                "$runner" --config "$CONFIG_PATH"
            fi
            echo "Triggered ${LABEL} once"
            ;;
    esac
}

_linux() {
    if [ "$ROLE" != "run" ]; then
        echo "ERROR: role 'pull' is Darwin-only (the Mac) - use 'run' on Linux/WSL2." >&2
        exit 1
    fi

    local runner
    runner=$(_runner_for_role)

    case "$ACTION" in
        enable)
            mkdir -p "${REPO_ROOT}/logs/backup_prod"
            schtasks.exe /Query /TN "$TASK_NAME" >/dev/null 2>&1 && \
                schtasks.exe /Change /TN "$TASK_NAME" /ENABLE >/dev/null || \
                schtasks.exe /Create /TN "$TASK_NAME" /SC DAILY /ST 03:00 \
                    /TR "wsl.exe -e bash -lc '${runner} --config ${CONFIG_PATH}'" \
                    /RL LIMITED /F >/dev/null
            echo "Enabled Scheduled Task ${TASK_NAME}"
            ;;
        disable)
            schtasks.exe /Change /TN "$TASK_NAME" /DISABLE >/dev/null 2>&1 || true
            echo "Disabled Scheduled Task ${TASK_NAME}"
            ;;
        trigger-once)
            schtasks.exe /Run /TN "$TASK_NAME" >/dev/null 2>&1 || "$runner" --config "$CONFIG_PATH"
            echo "Triggered ${TASK_NAME} once"
            ;;
    esac
}

case "$(uname)" in
    Darwin) _darwin ;;
    Linux) _linux ;;
    *)
        echo "Error: unsupported platform '$(uname)' for backup scheduling." >&2
        exit 1
        ;;
esac
