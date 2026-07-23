"""Watchdog process for denidin-app containers (2026-07-21, env-mismatch
incident response).

Runs as the container's PID 1 (see Dockerfile), replacing `python3 denidin.py`
as the direct entrypoint. Spawns the real app as a child subprocess and
periodically checks that this container's own declared environment
(`config.environment`, from the mounted config file - see
src/models/config.py) still matches `shared/active_env.json` (mounted
read-only at /app/active-env/active_env.json - see docker-compose.<env>.yml),
the single shared source of truth for which environment is currently allowed
to be active.

If they disagree, the app subprocess is killed and NOT respawned - the
watchdog itself keeps running (so the container stays "Up" in `docker ps`,
rather than exiting and being silently recreated by Docker's restart policy)
but does nothing further until a human tears the container down (see
killall_containers.sh) and starts the correct environment explicitly. No
automatic retry, by design (CONSTITUTION-adjacent: silent auto-recovery from
a cross-environment mismatch is exactly the failure mode this exists to
prevent - see the 2026-07-21 incident in CLAUDE.md).
"""
from __future__ import annotations

import json
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - watchdog - %(levelname)s - %(message)s",
)
logger = logging.getLogger("watchdog")

CONFIG_PATH = Path("/app/config/config.json")
ACTIVE_ENV_PATH = Path("/app/active-env/active_env.json")
CHECK_INTERVAL_SECONDS = 30


def _read_own_environment() -> Optional[str]:
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"Could not read own config at {CONFIG_PATH}: {exc}")
        return None
    return raw.get("environment")


def _read_active_environment() -> Optional[str]:
    if not ACTIVE_ENV_PATH.exists():
        logger.warning(f"{ACTIVE_ENV_PATH} not found - no environment is declared active")
        return None
    try:
        raw = json.loads(ACTIVE_ENV_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"Could not read {ACTIVE_ENV_PATH}: {exc}")
        return None
    return raw.get("active_env")


def main() -> None:
    own_env = _read_own_environment()
    logger.info(f"watchdog starting - this container's own declared environment: {own_env!r}")

    process = subprocess.Popen([sys.executable, "denidin.py"])
    logger.info(f"spawned denidin.py (pid={process.pid})")

    def _forward_signal(signum, _frame):
        logger.info(f"received signal {signum} - forwarding to app subprocess and exiting")
        if process.poll() is None:
            process.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _forward_signal)
    signal.signal(signal.SIGINT, _forward_signal)

    torn_down = False
    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)

        if process.poll() is not None and not torn_down:
            logger.warning(f"app subprocess exited on its own (code={process.returncode}) - watchdog idling")
            torn_down = True
            continue

        if torn_down:
            continue

        active_env = _read_active_environment()
        if active_env is not None and own_env is not None and active_env != own_env:
            logger.error(
                f"ENVIRONMENT MISMATCH: this container is '{own_env}' but "
                f"shared/active_env.json declares '{active_env}' active - "
                f"tearing down the app subprocess (pid={process.pid}). "
                f"Container stays up (no auto-restart); run scripts/killall_containers.sh "
                f"and start the correct environment explicitly."
            )
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            torn_down = True


if __name__ == "__main__":
    main()
