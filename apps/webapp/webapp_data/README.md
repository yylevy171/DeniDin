# `webapp_data/` — the webapp's own writable data root (Feature 087)

This directory holds the webapp backend's own writable state
(`clients/client_comments.json`, `client_mapping.json`, `mapping_notes.json`,
`removed_clients.json`, `new_morning_clients.json`). It is **deliberately separate** from
`apps/denidin-app`'s `dev_data`/`data` — those mounts are read-only for the webapp and
must stay that way. Everything under `webapp_data/` itself is gitignored (real client
data) except this README.

## Corrected 2026-09-24: single folder, no per-env subfolder

There is no `webapp_data/dev/` or `webapp_data/prod/` split. Rapaport maintains **one**
dataset (`client_comments.json`/etc.) — there was never a genuinely separate "dev" vs
"prod" set of client comments, so splitting the folder by env only duplicated the same
content pointlessly. Instead:

- **This Mac** (every clone, via the multi-clone singleton convention below) has exactly
  one shared `webapp_data/clients/` folder, used by both a local dev container and a
  local prod-mode test run (`./run_webapp.sh dev` / `./run_webapp.sh prod`) alike — this
  is intentional, not a bug: this Mac's access to Rapaport's data is for
  development/testing, and testing "with prod-like data" just means using this same
  folder (which already holds Rapaport's real live data).
- **The real Windows-box prod deployment** is a physically separate machine with its own,
  independent single `webapp_data/clients/` folder — it can never collide with this Mac's
  copy since they're different filesystems entirely; it needs its own one-time seed (see
  below).

## Multi-clone singleton convention

Per the repo's "dev/prod data is a singleton across clones" rule (see root `CLAUDE.md`),
this directory lives at one canonical path shared by every clone on the machine — the
root clone's `apps/webapp/webapp_data/`, same idea as `apps/denidin-app/dev_data`. Each
clone's `docker-compose.dev.local.yml`/`docker-compose.prod.local.yml` redirects
`webapp-backend-<env>`'s `/app/webapp-data` volume to that one canonical copy — both env
overrides point at the **same** folder:

```yaml
webapp-backend-dev:      # and webapp-backend-prod, identically
  volumes:
    - ../apps/webapp/webapp_data:/app/webapp-data
```

## Source of truth: Rapaport's live analyst clone (`teammate5` as of 2026-09-24)

The actual, currently-maintained source of `client_comments.json`/`client_mapping.json`/
`mapping_notes.json` is `reports/mapping_tool/` inside **Rapaport's own working clone** —
`teammate5` as of this writing (the clone name may change if Rapaport's assignment
changes; confirm before re-seeding). That clone also holds the current
`generate_client_status.py`/`mapping_server.py` reference logic this feature ports.

The root/original clone's flat `reports/*.json` files are **not** the live source — they
lack even the `mapping_tool/` directory and were confirmed stale (smaller byte counts,
older content) on 2026-09-24. Do not re-seed from there.

## Required one-time seeding (human action, done once already — see below)

`clients/` is seeded **once** from Rapaport's real, live files
(`reports/mapping_tool/{client_comments,client_mapping,mapping_notes}.json` in Rapaport's
clone) as the authoritative starting state, since those files hold real,
actively-maintained operational data that must not be lost or reset on cutover — see
spec.md's REQ-087-04 and Clarifications.

**This is a one-time seed, already performed on 2026-09-24** (explicit user
authorization) at the canonical root-clone path. After seeding, all future edits happen
exclusively through the webapp UI against `webapp_data/clients/*.json` — Rapaport's
original files in their own clone remain untouched, permanent reference copies. If
Rapaport's files are updated significantly again before this feature ships, re-diff
before assuming another reseed is needed (an in-flight webapp edit could otherwise be
silently overwritten by a reseed).

**Still outstanding**: the real Windows-box prod deployment needs its own,
independently-seeded `apps/webapp/webapp_data/clients/` on that machine — no session
running on the Mac has access to seed it there. Copy the same three files there directly
before webapp is actually deployed to that box.

## Status as of 2026-09-24

Seeded at the canonical root-clone path
(`/Users/yaron/Projects/DeniDin/apps/webapp/webapp_data/clients/`) directly from
`teammate5`'s live files, with explicit user authorization to read Rapaport's clone and
write into the root clone's shared infra for this purpose. Every clone's
`docker-compose.dev.local.yml`/`docker-compose.prod.local.yml` should redirect to this
single path for both `webapp-backend-dev` and `webapp-backend-prod` (see each clone's own
override file for its current state).
