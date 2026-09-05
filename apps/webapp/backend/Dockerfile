# webapp-backend (Feature 068). Build context = repo root, so both this app and
# apps/denidin-app/src (imported at runtime for the reused managers) are available.
#   docker build -f apps/webapp/backend/Dockerfile -t webapp-backend .
# Compose wiring + the cloudflared sidecar are finalized in Feature 068 Story 10.
FROM python:3.11-slim

WORKDIR /app

COPY apps/webapp/backend/requirements.txt ./requirements.txt
COPY apps/denidin-app/requirements.txt ./denidin-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r denidin-requirements.txt

COPY apps/webapp/backend/ /app/
COPY apps/denidin-app/src/ /app/denidin-app/src/
COPY apps/webapp/VERSION /app/VERSION

ENV PYTHONPATH=/app/src:/app/denidin-app/src

EXPOSE 8100
VOLUME ["/app/config"]

CMD ["python", "-m", "webapp_backend.server", "config/config.dev.json"]
