#!/bin/bash
# Registers/enables, disables, or triggers-once the OS-native schedule that
# runs run_prober_for_env.sh on a ~1-minute cadence for one environment
# (bugfix-043, 2026-09-06 revision). This is the mechanism that ties the
# prober's own on/off state directly to admin-initiated stop/start - see
# scripts/stop_env.sh / scripts/run_env.sh, and prober.py's module docstring
# for the full rationale (no separately-maintained "intentionally down"
# flag - the schedule's own enabled/disabled state IS the signal).
#
# Platform is detected via `uname` (same repo already has a real precedent
# for platform-conditional ops scripts talking to Windows - see
# deploy_release.sh's wslpath/cmd.exe interop for WIN_HOME resolution):
#   - Darwin (a Mac dev clone): a per-clone, per-env LaunchAgent
#     (~/Library/LaunchAgents/com.denidin.healthprobe.<env>.plist),
#     load/unload via launchctl. Fully covered by real tests
#     (scripts/health_monitoring/tests/test_register_prober_schedule.py) -
#     no mocking, a real (uniquely-labeled, throwaway) LaunchAgent is
#     loaded/unloaded/verified against the real launchd.
#   - Linux (WSL2, which is how this script actually runs on the real prod
#     box over SSH per Feature 035 - see scripts/windows_prod/_wsl_ssh.sh):
#     a native Windows Scheduled Task via schtasks.exe, created to run
#     wsl.exe with this script's own path. Has NO automated coverage here -
#     same reason deploy_release.sh's remote/SSH path has none (see that
#     script's own test file's docstring) - relies on a manual gate against
#     the real box instead.
#
# Usage: ./scripts/health_monitoring/register_prober_schedule.sh <env> enable|disable|trigger-once

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
ACTION="$2"

if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod enable|disable|trigger-once" >&2
    exit 1
fi
if [ "$ACTION" != "enable" ] && [ "$ACTION" != "disable" ] && [ "$ACTION" != "trigger-once" ]; then
    echo "Usage: $0 dev|prod enable|disable|trigger-once" >&2
    exit 1
fi

RUNNER="$SCRIPT_DIR/run_prober_for_env.sh"
LABEL="com.denidin.healthprobe.${ENV}"

_darwin() {
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_path="${plist_dir}/${LABEL}.plist"

    case "$ACTION" in
        enable)
            mkdir -p "$plist_dir"
            cat > "$plist_path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${RUNNER}</string>
        <string>${ENV}</string>
    </array>
    <key>StartInterval</key><integer>60</integer>
    <key>RunAtLoad</key><true/>
    <key>StandardOutPath</key><string>${REPO_ROOT}/logs/health_monitoring/${ENV}/launchd.out.log</string>
    <key>StandardErrorPath</key><string>${REPO_ROOT}/logs/health_monitoring/${ENV}/launchd.err.log</string>
</dict>
</plist>
PLIST
            mkdir -p "${REPO_ROOT}/logs/health_monitoring/${ENV}"
            # Idempotent: unload first (ignoring failure - it may not be loaded yet), then load.
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
                # Not registered yet (shouldn't normally happen - run_env.sh
                # always enables first) - run it directly instead of failing.
                "$RUNNER" "$ENV"
            fi
            echo "Triggered ${LABEL} once"
            ;;
    esac
}

_linux() {
    local task_name="DeniDinHealthProbe-${ENV}"
    # This box's real shell is cmd.exe (Feature 035) - schtasks.exe is reached
    # the same way deploy_release.sh resolves WIN_HOME: through a WSL bash
    # session shelling out to cmd.exe. wsl.exe re-enters this exact WSL
    # distro/user to run the runner script, so the scheduled task survives a
    # full reboot (Windows-native, not dependent on any WSL session being
    # already open) and picks up run_prober_for_env.sh from this same
    # checkout every time it fires.
    case "$ACTION" in
        enable)
            mkdir -p "${REPO_ROOT}/logs/health_monitoring/${ENV}"
            schtasks.exe /Query /TN "$task_name" >/dev/null 2>&1 && \
                schtasks.exe /Change /TN "$task_name" /ENABLE >/dev/null || \
                schtasks.exe /Create /TN "$task_name" /SC MINUTE /MO 1 \
                    /TR "wsl.exe -e bash -lc '${RUNNER} ${ENV}'" \
                    /RL LIMITED /F >/dev/null
            echo "Enabled Scheduled Task ${task_name}"
            ;;
        disable)
            schtasks.exe /Change /TN "$task_name" /DISABLE >/dev/null 2>&1 || true
            echo "Disabled Scheduled Task ${task_name}"
            ;;
        trigger-once)
            schtasks.exe /Run /TN "$task_name" >/dev/null 2>&1 || "$RUNNER" "$ENV"
            echo "Triggered ${task_name} once"
            ;;
    esac
}

case "$(uname)" in
    Darwin) _darwin ;;
    Linux) _linux ;;
    *)
        echo "Error: unsupported platform '$(uname)' for prober scheduling." >&2
        exit 1
        ;;
esac
