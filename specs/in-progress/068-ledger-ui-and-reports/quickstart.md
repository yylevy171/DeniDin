# Quickstart: Ledger Web UI (Feature 068)

## Fastest way to view it (host dev, implemented 2026-09-05)

```bash
./apps/webapp/run_webapp_dev.sh          # backend :8100 (uvicorn), frontend :5173 (Vite)
# then open http://localhost:5173
```

- **Password**: whatever is hashed into `apps/webapp/backend/auth/password.hash`
  (`sha256("denidin-pw" + password)`). The gitignored dev file currently corresponds to `denidin`.
  Rotate: `python3 -c 'import hashlib,sys;open("apps/webapp/backend/auth/password.hash","w").write(hashlib.sha256(("denidin-pw"+sys.argv[1]).encode()).hexdigest())' NEWPASS`
- **Data source**: `apps/webapp/backend/config/config.dev.json`'s `denidin_data_root`. The dev
  file points at `~/denidin-winprod-data` (the read-only sshfs mount of real prod data) so
  there's something real to look at. The webapp is strictly read-only — it never writes there.
  Point it at `apps/denidin-app/dev_data` instead for local dev data.
- First index load globs every `events/*.json`; over the sshfs mount that's a ~10s backend
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
# edit config.dev.json: data_root -> ../../denidin-app/dev_data (read-only mount in Docker;
# a plain relative path when running the BFF directly on the host for dev-loop convenience)
python3 -m pytest tests/ -v --tb=short
```

## Frontend dev setup
```bash
cd apps/webapp/frontend
npm install
npm test                 # Jest + React Native Testing Library, this feature's own test tier
npm run web               # local dev server, points at the backend's dev URL
```

## Running both together (containerized, per-env)
```bash
cd apps/webapp
./run_webapp.sh dev       # or prod — sources scripts/env_lock.sh identically to the other apps
./stop_webapp.sh dev
```
Bundled into the full stack via the repo-root scripts, in the confirmed order:
```bash
./scripts/run_all.sh dev   # morning-mcp-app -> denidin-app -> webapp
./scripts/stop_all.sh dev  # reverse order
```

## Access (once deployed)
- **Local/dev loop**: `http://localhost:<webapp-frontend-port>`.
- **Remote (dev/prod)**: via that environment's Cloudflare Tunnel URL — `denidin-app`/
  `morning-mcp-app` are never reachable from the internet, only the webapp. Exact
  domain/subdomain TBD at deploy time (see `research.md` §6).
- First load: password screen (see `contracts/api.md`'s `/auth/login`).

## Release/deploy (once cut)
```bash
scripts/cut_release.sh webapp <version>       # human-supplied version, every time
scripts/deploy_release.sh webapp dev <version>
scripts/deploy_release.sh webapp prod <version>
```
Same human-only version/deploy-decision rules as `denidin-app`/`morning-mcp-app` apply
unchanged — see CLAUDE.md's "VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY" section.
