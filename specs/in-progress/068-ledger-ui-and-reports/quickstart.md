# Quickstart: Ledger Web UI (Feature 068)

## Fastest way to view it (host dev, implemented 2026-09-05)

```bash
./apps/webapp/run_webapp.sh host         # backend :8100 (uvicorn), frontend :5173 (Vite), Ctrl-C stops both
# then open http://localhost:5173
```

`run_webapp.sh` is the single entrypoint: `host` (no Docker, live-reload, localhost only),
`dev` / `prod` (Docker Compose, LAN-reachable — see "Running containerized" below).

- **Password**: whatever is hashed into `apps/webapp/backend/auth/password.hash`
  (`sha256("denidin-pw" + password)`; the salt is hardcoded in `webapp_backend.auth.PASSWORD_SALT`,
  never in config). The gitignored dev file currently corresponds to `denidin`.
  Rotate: `python3 -c 'import hashlib,sys;open("apps/webapp/backend/auth/password.hash","w").write(hashlib.sha256(("denidin-pw"+sys.argv[1]).encode()).hexdigest())' NEWPASS`
- **Data source**: `apps/webapp/backend/config/config.dev.json`'s `denidin_data_root`.
  **dev points at dev data, prod points at prod data — never crossed.** The dev file points at
  the dev-data singleton `/Users/yaron/Projects/DeniDin/apps/denidin-app/dev_data` (the same
  place the dev containers mount via `docker-compose.dev.local.yml`; a `coderN` clone's own
  local `dev_data` is only an empty stub). Only `config.prod.json` points at
  `~/denidin-winprod-data` (the read-only sshfs mount of real prod data). The webapp is
  strictly read-only regardless — it never writes to either.
- First index load globs every `events/*.json` (~4k files in dev) → a few seconds' backend
  startup.

Backend tests: `cd apps/webapp/backend && ./venv/bin/python -m pytest -q` (55 pass).

---

*(Below is forward-looking — the containerized per-env flow and release tooling land in
Stories 9–10.)*

## Backend (BFF) dev setup
```bash
cd apps/webapp/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config/config.example.json config/config.dev.json
# edit config.dev.json: denidin_data_root -> /Users/yaron/Projects/DeniDin/apps/denidin-app/dev_data
# (the dev-data singleton in the root clone — NOT this clone's empty stub, and NOT the prod mount)
python3 -m pytest tests/ -v --tb=short
```

## Frontend dev setup
```bash
cd apps/webapp/frontend
npm install
npm test                 # Jest + React Native Testing Library, this feature's own test tier
npm run web               # local dev server, points at the backend's dev URL
```

## Running containerized, per-env (Story 10)

Three services per environment — `webapp-backend-<env>` (Starlette BFF, reads the denidin
data root **read-only**), `webapp-frontend-<env>` (nginx serving the built Vite bundle +
reverse-proxying `/api` and `/health` to the backend), `cloudflared-<env>` (Cloudflare Tunnel
connector — see below). Ports: frontend `5100`/`5101`, backend `8100`/`8101` (dev/prod).

```bash
cd apps/webapp
./run_webapp.sh dev        # or prod — ENV-LOCK AGNOSTIC: never touches shared/active_env.json,
                           # start it regardless of which clone owns dev (read-only viewer,
                           # no contention). Still requires this clone's docker-compose.<env>.local.yml.
./stop_webapp.sh dev       # 2nd arg accepted + ignored (no lock to release)
# then open http://localhost:5100  — or  http://<this-mac-LAN-IP>:5100  from a phone on the same WiFi
```

Bundled into the full stack via the repo-root scripts, in the confirmed order:
```bash
./scripts/run_all.sh dev   # morning-mcp-app -> denidin-app -> webapp
./scripts/stop_all.sh dev  # reverse: webapp -> denidin-app -> morning-mcp-app
```

**These only (re)deploy — they never build.** After any code change in `apps/webapp/`:
```bash
docker compose --project-directory . -f docker/docker-compose.dev.yml -f docker/docker-compose.dev.local.yml \
  build webapp-backend-dev webapp-frontend-dev
```
then `run_webapp.sh dev` again (same "merging to master doesn't redeploy" rule as the other apps).

### Container config
`apps/webapp/backend/config/config.{dev,prod}.container.json` (committed — no secrets;
container paths only) are mounted over `config/config.json`. `auth/password.hash` (gitignored)
is mounted read-only from the host — rotate it exactly as in the host-dev section above.

### Per-clone follow-up (MANDATORY, same as the other apps)
Every clone's gitignored `docker/docker-compose.{dev,prod}.local.yml` needs a
`webapp-backend-<env>` entry remapping the denidin-data mount to the shared root-clone path
(a `coderN` clone must not read a stale local `dev_data` stub):
```yaml
  webapp-backend-dev:
    volumes:
      - ../apps/denidin-app/dev_data:/app/denidin-data:ro
  webapp-backend-prod:
    volumes:
      - ../apps/denidin-app/data:/app/denidin-data:ro
```
(The root clone's copies keep the base file's own `./apps/...` paths — no override needed there.)

## Access

The Docker frontend binds `0.0.0.0` (`5100` dev / `5101` prod):

- **Same host**: `http://localhost:5100` (dev) / `http://localhost:5101` (prod).
- **Same LAN/WiFi**: `http://<host-LAN-IP>:5100` — e.g. a phone on the same WiFi as the dev Mac.
- **Tailscale (the real remote path for prod)**: **Tailscale Serve** is already configured on
  the Windows prod box — it proxies HTTPS 443 on the box's Tailscale MagicDNS name to the
  local frontend port and terminates TLS with an automatic cert. The URL is
  **`https://yaronlaptop.tail274e9b.ts.net/`** (HTTPS, no port), reachable from any tailnet
  device (Mac, or a phone with the Tailscale app), anywhere. Note `yaronlaptop` is the box's
  real Tailscale hostname — **not** the `denidin-winprod` SSH alias (see Feature 035
  `WINDOWS_GOTCHAS.md` §10). Dev has no Serve config; use LAN/WiFi.

**Backend note**: Tailscale Serve fronts the *frontend* container only; nginx there already
reverse-proxies `/api` + `/health` to the backend, so no separate Serve rule for :8101.

`denidin-app` / `morning-mcp-app` are never exposed on any of these paths — only the webapp
frontend has a published port. First load: password screen (see `contracts/api.md`'s
`/auth/login`).

### Reboot recovery (pending)
The webapp containers are `restart: "no"` like the rest of the repo, so nothing brings them
back after a prod-box reboot on their own. The prod reboot-recovery wiring is being done in
**bug43**; once it lands, add `webapp-backend-<env>` / `webapp-frontend-<env>` (and the
`cloudflared-<env>` sidecar if ever enabled) to whatever start-set that mechanism drives.
Until then, `./scripts/run_all.sh prod` (or `run_webapp.sh prod`) after a reboot.

### Cloudflare Tunnel (optional, unused — no domain)
A `cloudflared-<env>` sidecar is defined in both compose files for a possible future
domain-based public URL, but it is **not in use**: it needs a Cloudflare account + an owned
domain, and without `docker/cloudflared.<env>.env` (gitignored, absent) the container simply
fails and stays down (`env_file required: false`, `restart: "no"`) with zero effect on the
rest of the stack. `deploy_release.sh` / `cut_release.sh` already skip it unless that token
file exists. To enable it later: create a tunnel in Cloudflare Zero Trust → Networks →
Tunnels, route a hostname (`ledger-dev.<domain>`) to `http://webapp-frontend-<env>:80` (the
frontend only), `cp docker/cloudflared.env.example docker/cloudflared.<env>.env` and paste the
connector token as `TUNNEL_TOKEN=...`.

## Release/deploy (once cut)
```bash
scripts/cut_release.sh webapp <version>       # human-supplied version, every time
scripts/deploy_release.sh webapp dev <version>
scripts/deploy_release.sh webapp prod <version>
```
Same human-only version/deploy-decision rules as `denidin-app`/`morning-mcp-app` apply
unchanged — see CLAUDE.md's "VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY" section.
