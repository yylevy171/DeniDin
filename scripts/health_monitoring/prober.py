#!/usr/bin/env python3
"""One-shot health-check prober + auto-restart escalation (bugfix-043).

Invoked externally, once per run, on a ~1-minute cadence - Windows Task
Scheduler in prod (real, unattended, auto-restart-capable), or by hand /
cron for a dev demo. This script deliberately does NOT run its own
scheduling loop or keep state in memory - "last_up_time" lives in a plain
JSON file between invocations, per explicit design decision ("I actually
prefer that" - state in a file, not an app's memory, and the scheduling
itself is a system-level mechanism, not a new bespoke long-running process).

Escalation (both timed thresholds measured from the last time ALL checks passed):
  - no state file at all (BOOTSTRAP): immediate proper-channels restart, same
    mechanism as SOFT below, no waiting. This is the normal case on every
    legitimate start - run_env.sh's job is only to (re-)enable this script's
    own schedule; THIS script is what actually calls run_all.sh, every time,
    on every kind of start (fresh install, admin-requested, crash recovery,
    reboot recovery) - see stop_env.sh/run_env.sh below for why. stop_env.sh
    archives (never deletes-without-a-trace) the state file on every
    deliberate stop specifically so the next start lands here instead of
    wrongly escalating against a stale pre-stop timestamp.
  - < 3 min (with a real, non-stale state file): no action, just log.
  - >= 3 min: SOFT restart - stop_all.sh <env> -force && run_all.sh <env>.
              The proper-channels path (env_lock, active_env.json bookkeeping
              all respected) - tried first because it's the well-behaved one.
  - >= 10 min: HARD restart - `docker restart` on both containers directly.
               Bypasses all of that bookkeeping - the blunt fallback, only
               reached if the soft path already had its chance and didn't
               resolve things.

Admin-initiated stop/start (bugfix-043, 2026-09-06 revision): an admin deciding
an environment should be down is NOT an outage, and must not be fought by this
script. Rather than a separately-maintained "intentionally down" flag (the same
class of bug as the original incident - a piece of state someone has to
remember to keep correct), the fix ties the prober's own on/off state directly
to the human-facing stop/start actions themselves:
  - scripts/stop_env.sh <env>: disables/unregisters this script's own OS-level
    schedule for <env> FIRST (so it can't race with the shutdown), archives the
    state file (see archive_state_file - never silently deleted), then stops
    the apps (stop_all.sh <env> -force).
  - scripts/run_env.sh <env>: (re-)registers/enables this script's schedule for
    <env> (idempotent - a no-op if already enabled) and triggers one immediate
    probe cycle. That immediate probe sees no state file -> BOOTSTRAP -> calls
    run_all.sh itself. run_env.sh never calls run_all.sh directly - the whole
    point is that the prober's own bring-up code path is exercised on every
    single start, not just during a rare real crash.

Usage (dev demo, dry-run - logs what it WOULD do, never actually restarts):
    python3 prober.py --env dev \\
        --denidin-health-url http://127.0.0.1:8100/health \\
        --morning-health-url http://127.0.0.1:8000/health \\
        --state-file /tmp/health-prober-state.json \\
        --log-file /tmp/health-prober.log \\
        --scripts-dir /path/to/repo/root \\
        --denidin-container denidin-dev-denidin-app-dev-1 \\
        --morning-container denidin-dev-morning-mcp-app-dev-1 \\
        --dry-run

Real prod invocation (Windows Task Scheduler, 1-minute repeating trigger,
"don't start a new instance if already running") drops --dry-run and points
--scripts-dir at the box's own deploy directory (~/denidin-prod, per Feature
035 - NOT a git clone, see that spec's quickstart).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# Escalation thresholds, in seconds since the last all-checks-passed moment.
SOFT_RESTART_THRESHOLD_SECONDS = 180   # 3 minutes
HARD_RESTART_THRESHOLD_SECONDS = 600   # 10 minutes

PROBE_TIMEOUT_SECONDS = 10.0


def probe_health(url: str, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    """True iff `url` (a /health endpoint) responds with HTTP 200 - both
    apps' /health handlers already return 200 only when every check they
    know about succeeded, and a non-200 (5xx) or any transport failure both
    correctly count as "not healthy" here."""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False


def read_last_up_time(state_path: Path) -> Optional[float]:
    """Returns the persisted last-known-all-good timestamp, or None if the
    state file doesn't exist yet or is unreadable - the caller treats None
    as "no baseline yet", not as "definitely unhealthy for a very long
    time", to avoid an over-eager restart on a brand-new install before the
    very first successful probe has ever had a chance to run."""
    try:
        data = json.loads(state_path.read_text())
        value = data.get("last_up_time")
        return float(value) if value is not None else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def write_last_up_time(state_path: Path, timestamp: float) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"last_up_time": timestamp}))


def archive_state_file(state_path: Path, now: float) -> Optional[Path]:
    """Called by stop_env.sh when an admin deliberately stops an environment. Renames the live
    state file (if any) to a timestamped archive path instead of deleting it - the last-known-up
    timestamp is kept as a historical record (the timestamp is baked into the archive filename so
    repeated stops never overwrite each other), but nothing is left at state_path afterward. That
    absence is what makes the very next probe after a later start correctly see "no baseline" and
    bootstrap immediately (see decide_action's "bootstrap" branch) instead of measuring elapsed
    time against a stale pre-stop timestamp and misfiring a "hard" restart on what was actually a
    perfectly ordinary admin-requested start.

    Returns the archive path, or None if there was no state file to archive (e.g. the env was
    never successfully probed even once before being stopped).
    """
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    data["stopped_at"] = now
    archive_path = state_path.parent / f"{state_path.stem}_stopped_{int(now)}{state_path.suffix}"
    archive_path.write_text(json.dumps(data))
    state_path.unlink()
    return archive_path


def decide_action(last_up_time: Optional[float], now: float) -> str:
    """Pure decision function, deliberately separated from all I/O
    (probing, restarting, logging) so the escalation math is trivially
    unit-testable in isolation - see tests/test_prober.py.

    Returns "none", "bootstrap", "soft", or "hard".

    "bootstrap" (no persisted last_up_time at all) is treated as an immediate, proper-channel
    restart (run_soft_restart, i.e. run_all.sh) rather than "do nothing" - this is what makes
    run_env.sh's "just start the prober, let it bring the apps up itself" model work: a missing
    state file means either a genuinely fresh install, or (far more commonly) that stop_env.sh
    just archived it moments ago on a deliberate stop. Either way it means "nothing to escalate
    from, start it now" - not "wait out an arbitrary timer for a state we already know is
    intentional." A real crash/reboot recovery, in contrast, always has a real (now-stale)
    last_up_time on disk, so it still goes through the soft (>=3min) / hard (>=10min) escalation
    ladder unchanged.
    """
    if last_up_time is None:
        return "bootstrap"
    elapsed = now - last_up_time
    if elapsed >= HARD_RESTART_THRESHOLD_SECONDS:
        return "hard"
    if elapsed >= SOFT_RESTART_THRESHOLD_SECONDS:
        return "soft"
    return "none"


def run_soft_restart(env: str, scripts_dir: Path) -> None:
    """The proper-channels restart: the same sanctioned scripts a human
    would run by hand (env_lock acquire/release, active_env.json
    bookkeeping all respected)."""
    subprocess.run([str(scripts_dir / "scripts" / "stop_all.sh"), env, "-force"], check=False)
    subprocess.run([str(scripts_dir / "scripts" / "run_all.sh"), env], check=False)


def run_hard_restart(denidin_container: str, morning_container: str) -> None:
    """The blunt fallback: bypasses env_lock/active_env.json bookkeeping
    entirely - a direct container-runtime restart, morning-mcp-app first
    (denidin-app depends on it discovering the tunnel), then denidin-app,
    matching this project's own established start ordering."""
    subprocess.run(["docker", "restart", morning_container], check=False)
    subprocess.run(["docker", "restart", denidin_container], check=False)


def _write_log_entry(
    log_file: Path,
    now: float,
    denidin_ok: bool,
    morning_ok: bool,
    last_up_time: Optional[float],
    action: str,
    dry_run: bool,
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": now,
        "denidin_health": "success" if denidin_ok else "fail",
        "morning_health": "success" if morning_ok else "fail",
        "last_up_time": last_up_time,
        "action": action,
        "dry_run": dry_run,
    }
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run_once(
    env: str,
    denidin_health_url: str,
    morning_health_url: str,
    state_file: Path,
    log_file: Path,
    scripts_dir: Path,
    denidin_container: str,
    morning_container: str,
    dry_run: bool = False,
    now: Optional[float] = None,
) -> str:
    """Runs exactly one probe-and-decide cycle. Returns the action taken
    ("none"/"bootstrap"/"soft"/"hard") so callers (tests, a manual dev demo) can assert
    on it directly instead of parsing the log file."""
    now = now if now is not None else time.time()
    denidin_ok = probe_health(denidin_health_url)
    morning_ok = probe_health(morning_health_url)
    all_ok = denidin_ok and morning_ok

    last_up_time = read_last_up_time(state_file)

    if all_ok:
        write_last_up_time(state_file, now)
        action = "none"
    else:
        action = decide_action(last_up_time, now)
        if action in ("soft", "bootstrap") and not dry_run:
            run_soft_restart(env, scripts_dir)
        elif action == "hard" and not dry_run:
            run_hard_restart(denidin_container, morning_container)

    _write_log_entry(log_file, now, denidin_ok, morning_ok, last_up_time, action, dry_run)
    return action


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    parser.add_argument("--denidin-health-url")
    parser.add_argument("--morning-health-url")
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--scripts-dir", type=Path, help="Repo root containing scripts/stop_all.sh and scripts/run_all.sh")
    parser.add_argument("--denidin-container")
    parser.add_argument("--morning-container")
    parser.add_argument("--dry-run", action="store_true", help="Log what would happen, never actually restart anything")
    parser.add_argument(
        "--archive-state", action="store_true",
        help="Archive the current state file (rename it with a _stopped_<timestamp> suffix) and "
             "exit immediately - no probing, no restart decision. Used by stop_env.sh when an "
             "admin deliberately stops an environment, so the state file's absence makes the "
             "next run_env.sh start bootstrap immediately instead of escalating against a stale "
             "pre-stop timestamp.",
    )
    args = parser.parse_args(argv)

    if args.archive_state:
        archived = archive_state_file(args.state_file, time.time())
        print(f"archived={archived}" if archived is not None else "archived=none (no existing state file)")
        return 0

    required_for_probe = {
        "--denidin-health-url": args.denidin_health_url,
        "--morning-health-url": args.morning_health_url,
        "--log-file": args.log_file,
        "--scripts-dir": args.scripts_dir,
        "--denidin-container": args.denidin_container,
        "--morning-container": args.morning_container,
    }
    missing = [name for name, value in required_for_probe.items() if value is None]
    if missing:
        parser.error(
            f"the following arguments are required unless --archive-state is passed: {', '.join(missing)}"
        )

    action = run_once(
        env=args.env,
        denidin_health_url=args.denidin_health_url,
        morning_health_url=args.morning_health_url,
        state_file=args.state_file,
        log_file=args.log_file,
        scripts_dir=args.scripts_dir,
        denidin_container=args.denidin_container,
        morning_container=args.morning_container,
        dry_run=args.dry_run,
    )
    print(f"action={action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
