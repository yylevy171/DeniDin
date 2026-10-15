# Feature 089 - environment config changes (to apply by hand after testing)

Config files are never edited by the agent. These are the gitignored per-environment files that need
new keys before 089 is deployed. `config.example.json` in each app already carries the placeholders.
Use ONE shared secret per environment (any long random string); it must be identical in the two apps
of that environment. Dev and prod use different secrets.

## 1. denidin-app - `apps/denidin-app/config/config.dev.json` and `config.prod.json`

Add (top level):

```json
"agreements_api": {"port": 8300, "auth_token": "<SECRET for this environment>"}
```

- `port: 0` (the example default) leaves the API off; with it off the webapp's Clients tab shows an
  "agreements unavailable" error instead of agreed totals, so it must be 8300 wherever the webapp runs.
- Nothing else changes in denidin-app config. `config.test.json` (gitignored) needs the same block only if
  you want to run the API standalone from it (the Playwright suites generate their own configs).

## 2. webapp backend - `apps/webapp/backend/config/config.dev.json` and `config.prod.json`

Add (top level, next to the existing `denidin_data_root` etc.):

```json
"denidin_agreements_url": "<URL below>",
"denidin_agreements_token": "<the SAME secret as denidin-app's agreements_api.auth_token for this environment>"
```

| Where the webapp backend runs | `denidin_agreements_url` |
|---|---|
| dev, in Docker (`run_webapp.sh dev`) | `http://denidin-app-dev:8300` |
| prod, in Docker (`run_webapp.sh prod`) | `http://denidin-app-prod:8300` |
| `run_webapp.sh local` (local code, dev denidin-app running in Docker) | `http://127.0.0.1:8300` (dev compose publishes it on 127.0.0.1 only) |

Which file gets which value:

- **Dev in Docker** (`run_webapp.sh dev`) mounts `<root clone>/apps/webapp/backend/config/config.dev.json`:
  put `http://denidin-app-dev:8300` and the dev token in THAT file.
- **`run_webapp.sh local`** (local code, dev dependencies) reads `apps/webapp/backend/config/config.local.json`
  in the clone you run it from (gitignored; template `config.local.example.json`): `http://127.0.0.1:8300`, the
  SAME dev token, the root clone's `dev_data` / `webapp_data` / `auth/password.hash` as absolute paths. The script
  refuses to start while any `PASTE_` placeholder remains.

Prod is Docker-only (`config.prod.json` on the prod box).

## 3. Already in the repo (nothing to do)

- `docker/docker-compose.dev.yml`: publishes `127.0.0.1:8300:8300` on `denidin-app-dev`.
- `docker/docker-compose.prod.yml`: deliberately does NOT publish the port; the prod webapp backend reaches
  `denidin-app-prod` by service name. Both apps must be on the same compose project/network for the service
  name to resolve (they are in the existing compose files).
- Order on start: denidin-app first (it hosts the API), then the webapp backend. If the API is down the
  webapp returns `502 agreements_unavailable` for agreement routes and the Clients agreed total shows an error.

## 4. After deploy

Prod needs the one-time migration (separate human-run step, `apps/denidin-app/scripts/migrate_agreements_089.py`)
before the Clients tab agreed totals are right: until agreements exist in the DB, the agreed total reads 0 plus
hours-worked lines.
