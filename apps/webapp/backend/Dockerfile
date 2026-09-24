# syntax=docker/dockerfile:1
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

# Two layers of caching for the slow install step (denidin-app's requirements pull heavy wheels
# - chromadb/onnxruntime/numpy - painful under x86 emulation):
#  - requirements.txt COPYed on its own line, before the app source, so the whole install layer
#    is reused on any cut whose requirements didn't change (plain layer cache).
#  - --mount=type=cache on pip's cache dir persists downloaded/built wheels across builds
#    (BuildKit, not part of any image layer - so the image stays as lean as --no-cache-dir gave
#    us), so even a requirements change only re-installs, doesn't re-download/re-build wheels.
COPY apps/webapp/backend/requirements.txt ./requirements.txt
COPY apps/denidin-app/requirements.txt /app/apps/denidin-app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -r /app/apps/denidin-app/requirements.txt

COPY apps/webapp/backend/ /app/apps/webapp/backend/
COPY apps/denidin-app/src/ /app/apps/denidin-app/src/
COPY apps/webapp/VERSION /app/apps/webapp/VERSION

ENV PYTHONPATH=/app/apps/webapp/backend/src:/app/apps/denidin-app/src

EXPOSE 8100

# Compose mounts the real config.dev.json/config.prod.json (2026-09-24: same single file
# host mode reads too - see AppConfig; no separate ".container.json" variant) over
# config/config.json (read-only), the denidin data root over /app/apps/denidin-app/dev_data
# or /app/apps/denidin-app/data (mirroring the repo tree, matching config's relative paths),
# the webapp data root over /app/apps/webapp/webapp_data, and auth/password.hash. None of
# these mounts involve git - they're plain data directories/files, never git-tracked.
CMD ["python", "-m", "webapp_backend.server", "config/config.json"]
