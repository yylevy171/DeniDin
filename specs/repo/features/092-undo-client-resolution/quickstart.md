# Quickstart: Feature 092

## 1. Backend tests (unit + integration)

From `apps/webapp/backend/`, using **this clone's** venv only:

```bash
cd apps/webapp/backend
venv/bin/python -m pytest tests/ -v --tb=short
```

> **AI agents:** don't run this bare. Use the repo's unit/integration wrapper per
> CONSTITUTION §XIX, or whichever wrapper the tasks phase confirms covers `apps/webapp/backend`.
> If none does, stop and ask.

## 2. Acceptance — Playwright (UAT 1–9)

```bash
cd apps/webapp/e2e
./node_modules/.bin/playwright test -c playwright.clients.config.ts
```

- `clients_serve.sh` re-seeds `.fixture/clients` and starts a real backend on `:8132`, wired to
  the Morning **sandbox** (read-only).
- The seeder for this feature also pre-writes `client_comments.json` with legacy routing
  keywords, so UAT 5 (migration) observes a genuine first-run migration.
- This needs no dev/prod environment.

## 3. Pre-deploy migration preview (read-only, prod data)

Before the first deploy of 092 to `prod`, run the read-only preview script (added in tasks)
against a **copy** of prod's `webapp_data/clients/`:

```bash
apps/webapp/backend/venv/bin/python apps/webapp/backend/scripts/preview_092_migration.py \
    --clients-dir <copy-of-prod-webapp_data/clients> \
    --events-dir ~/denidin-winprod-data/events \
    --config <copy of the box's apps/webapp/backend/config/config.prod.json>
```

`--events-dir` is prod's ledger (the read-only mount). `--config` supplies the production Morning
credentials for one read-only client-list call - the Mac's own `config.prod.json` deliberately
holds placeholders, so use a temporary copy of the box's file and delete it afterwards.
Done 2026-10-03: 0 section changes, 118 closed / 62 active / 16 check, 115 amount changes (all
`לסגור` lines; 56 of them show agreed 0) - approved by the PM.

It prints:
- every client whose comment will produce a status (`check` / `active` / `closed`);
- every line whose **section** would differ between legacy and new routing (expected: none);
- every line whose displayed **amounts** change (expected: exactly the `לסגור` lines, plus the
  rare `לקוח פעיל`+`לסגור` past-row edge from research R-4).

The user reviews that list before deploying. Deploying stays a separate, explicit, human-only
step (`scripts/deploy_release.sh`).

## 4. Rollback

Redeploy the previous webapp version with `scripts/deploy_release.sh`. 092 never modifies
`client_comments.json` / `client_mapping.json` / `mapping_notes.json` shapes, and the old
version ignores the new files. Rollback restores pre-092 routing exactly, including the `לסגור`
amount hack.

One exception: unlinks and hides done under 092 stay in effect.
- An unlink deleted a mapping key, so after rollback that name is simply unresolved again.
- A hide only lives in `hidden_unmatched.json`, so the name reappears after rollback.
