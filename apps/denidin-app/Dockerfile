FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# config/, data/, and logs/ are expected to be bind-mounted or volume-mounted at
# runtime: config/config.json is gitignored (contains secrets) and data/logs
# are mutable runtime state, neither belongs baked into the image.
VOLUME ["/app/config", "/app/data", "/app/logs"]

# denidin.py handles SIGINT/SIGTERM directly, so it runs as the container's
# PID 1 without needing run_denidin.sh/stop_denidin.sh (those scripts exist
# for PID-file single-instance enforcement on bare metal, a concern Docker
# already handles by construction; their `nohup ... &` backgrounding pattern
# would break Docker's signal delivery to PID 1).
CMD ["python3", "denidin.py"]
