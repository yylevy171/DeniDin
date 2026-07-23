"""Watchdog process for morning-mcp-app containers (2026-07-21, env-mismatch
incident response).

Runs as the container's PID 1, launched by docker-entrypoint.sh in place of
directly exec'ing the server (ngrok tunnel setup + status-file writing in
docker-entrypoint.sh happens first, unchanged). Spawns the real MCP server as
a child subprocess and periodically confirms this container's own declared
environment (`config.environment`, from the mounted config file) still
matches `shared/active_env.json` (mounted read-only at
/app/active-env/active_env.json), the single shared source of truth for
which environment is currently allowed to be active - checked two
independent ways:

1. INTERNAL: GET http://127.0.0.1:<port>/health inside the container.
2. EXTERNAL: GET <public ngrok URL from the status file>/health, over the
   real tunnel - this is what actually caught the 2026-07-21 incident (a
   container reachable over its tunnel while a *different* environment was
   supposed to be the only one active).

Both responses carry `{"environment": "..."}`. If either disagrees with
shared/active_env.json, the server subprocess is killed and NOT respawned -
the watchdog itself keeps running (container stays "Up" in `docker ps`
rather than being silently recreated by Docker's restart policy) but does
nothing further until a human tears the container down (see
killall_containers.sh) and starts the correct environment explicitly. No
automatic retry, by design.
"""
from __future__ import annotations

import json
import logging
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - watchdog - %(levelname)s - %(message)s",
)
logger = logging.getLogger("watchdog")

sys.path.insert(0, "/app/src")
from denidin_mcp_morning.config import load_config  # noqa: E402

CONFIG_PATH = Path("/app/config/config.json")
ACTIVE_ENV_PATH = Path("/app/active-env/active_env.json")
CHECK_INTERVAL_SECONDS = 30
HEALTH_TIMEOUT_SECONDS = 5


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


def _fetch_health_environment(url: str) -> Optional[str]:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body.get("environment")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning(f"health check at {url} failed: {exc}")
        return None


def _resolve_status_path(raw_status_file: Optional[str]) -> Optional[Path]:
    if not raw_status_file:
        return None
    path = Path(raw_status_file)
    return path if path.is_absolute() else Path("/app") / raw_status_file


def _external_tunnel_health_environment(status_path: Optional[Path]) -> Optional[str]:
    """Reads the current public tunnel URL from the status file this same
    container's docker-entrypoint.sh writes, then health-checks THROUGH it
    (real ngrok round trip, not just localhost) - this is the check that
    would have caught 2026-07-21's stale/wrong-tunnel incident. Returns None
    (no-op, not a mismatch) if no tunnel is configured or the status file
    doesn't yet report "running" - that's a normal startup/no-ngrok state,
    not evidence of anything wrong."""
    if status_path is None or not status_path.exists():
        return None
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if status.get("status") != "running":
        return None
    server_url = status.get("server_url")
    if not server_url:
        return None
    return _fetch_health_environment(f"{server_url}/health")


def main() -> None:
    config = load_config(CONFIG_PATH)
    own_env = config.environment
    logger.info(f"watchdog starting - this container's own declared environment: {own_env!r}")

    process = subprocess.Popen([sys.executable, "-m", "denidin_mcp_morning.server"])
    logger.info(f"spawned denidin_mcp_morning.server (pid={process.pid})")

    def _forward_signal(signum, _frame):
        logger.info(f"received signal {signum} - forwarding to server subprocess and exiting")
        if process.poll() is None:
            process.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _forward_signal)
    signal.signal(signal.SIGINT, _forward_signal)

    internal_health_url = f"http://127.0.0.1:{config.mcp_port}{'/health'}"
    status_path = _resolve_status_path(config.mcp_status_file)

    torn_down = False
    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)

        if process.poll() is not None and not torn_down:
            logger.warning(f"server subprocess exited on its own (code={process.returncode}) - watchdog idling")
            torn_down = True
            continue

        if torn_down:
            continue

        active_env = _read_active_environment()
        if active_env is None or own_env is None:
            continue

        internal_env = _fetch_health_environment(internal_health_url)
        external_env = _external_tunnel_health_environment(status_path)

        mismatches = []
        if own_env != active_env:
            mismatches.append(f"own config.environment={own_env!r}")
        if internal_env is not None and internal_env != active_env:
            mismatches.append(f"internal /health reported environment={internal_env!r}")
        if external_env is not None and external_env != active_env:
            mismatches.append(f"external tunnel /health reported environment={external_env!r}")

        if mismatches:
            logger.error(
                f"ENVIRONMENT MISMATCH (active_env={active_env!r}): {'; '.join(mismatches)} - "
                f"tearing down the server subprocess (pid={process.pid}). "
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
