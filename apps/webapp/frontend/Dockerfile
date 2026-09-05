# webapp-frontend (Feature 068). Build context = repo root (matches the backend Dockerfile).
#   docker build -f apps/webapp/frontend/Dockerfile -t webapp-frontend .
#
# Multi-stage: build the Vite bundle with Node, then serve the static dist/ with nginx.
# nginx also reverse-proxies /api and /health to the backend service so the browser only
# ever talks to one origin (the Cloudflare Tunnel hostname) — VITE_API_BASE stays "".
FROM node:20-slim AS build
WORKDIR /build
COPY apps/webapp/frontend/package.json apps/webapp/frontend/package-lock.json ./
RUN npm ci
COPY apps/webapp/frontend/ ./
RUN npx vite build

FROM nginx:1.27-alpine
# ${BACKEND_UPSTREAM} (e.g. webapp-backend-dev:8100) is filled in at container start by the
# nginx image's envsubst step; NGINX_ENVSUBST_FILTER (set in compose) keeps it from also
# clobbering nginx's own $host/$remote_addr/... runtime variables.
COPY apps/webapp/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /build/dist /usr/share/nginx/html
EXPOSE 80
