FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# data/ and logs/ are expected to be bind-mounted at runtime (mutable runtime
# state that doesn't belong baked into the image).
#
# /app/config deliberately dropped from this list (bugfix-062, 2026-09-16):
# declaring it here made it an anonymous Docker volume, and `docker compose
# up -d` (what run_denidin.sh/deploy_release_single.sh actually call) does
# NOT refresh an existing anonymous volume on redeploy - any file under
# config/ not individually bind-mounted in docker-compose.*.yml got silently
# frozen at whatever content that volume held on its first creation, even
# across later image rebuilds that added/changed it. Confirmed live in prod:
# that volume was created 2026-09-07 and neither config/ledger_recognition_
# prompt.md nor config/fee_agreement_templates/ (both added after that date)
# ever reached the running container for over a week - contributing to a
# real dropped bank-deposit ledger event. Without this VOLUME entry, any
# config/ path not explicitly bind-mounted now serves straight from the
# image layer instead, which is always current as of that build.
VOLUME ["/app/data", "/app/logs"]

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
