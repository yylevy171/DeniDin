FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# config/, data/, and logs/ are expected to be bind-mounted or volume-mounted at
# runtime: config/config.json is gitignored (contains secrets) and data/logs
# are mutable runtime state, neither belongs baked into the image.
VOLUME ["/app/config", "/app/data", "/app/logs"]

# watchdog.py runs as the container's PID 1 (2026-07-21, env-mismatch
# incident response): it spawns denidin.py as a child process, forwards
# SIGINT/SIGTERM to it for graceful shutdown, and periodically confirms this
# container's own declared environment still matches shared/active_env.json
# - tearing the app subprocess down (without exiting the container itself,
# so Docker's restart policy can't silently recreate it) on a mismatch. No
# PID-file logic needed (run_denidin.sh/stop_denidin.sh exist for bare-metal
# single-instance enforcement, a concern Docker already handles by
# construction).
CMD ["python3", "watchdog.py"]
