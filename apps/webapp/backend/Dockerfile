# webapp-backend (Feature 068). Build context = repo root, so both this app and
# apps/denidin-app/src (imported at runtime for the reused managers) are available.
#   docker build -f apps/webapp/backend/Dockerfile -t webapp-backend .
#
# The in-repo directory layout is PRESERVED inside the image (not flattened to /app/):
# webapp_backend/__init__.py and ledger_reader.py both resolve apps/denidin-app/src via
# `Path(__file__).resolve().parents[4] / "denidin-app"`, and server.read_version() via
# parents[3] / "VERSION". Flattening breaks both. Keep the tree shape identical to the repo.
FROM python:3.11-slim

WORKDIR /app/apps/webapp/backend

COPY apps/webapp/backend/requirements.txt ./requirements.txt
COPY apps/denidin-app/requirements.txt /app/apps/denidin-app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r /app/apps/denidin-app/requirements.txt

COPY apps/webapp/backend/ /app/apps/webapp/backend/
COPY apps/denidin-app/src/ /app/apps/denidin-app/src/
COPY apps/webapp/VERSION /app/apps/webapp/VERSION

ENV PYTHONPATH=/app/apps/webapp/backend/src:/app/apps/denidin-app/src

EXPOSE 8100

# Compose mounts the env-specific container config over config/config.json (read-only),
# the denidin data root over /app/denidin-data (read-only), and auth/password.hash.
CMD ["python", "-m", "webapp_backend.server", "config/config.json"]
