# Quickstart: 089 (developer)

All commands from the repo root of your own clone. Dev/prod containers are never started without
the per-action approval rule in CLAUDE.md; nothing here needs a container.

## Run the Agreements API standalone on a throwaway data root (what Playwright does)

```bash
cd apps/denidin-app
python3 -m src.services.agreements_api --config config/config.test.json --port 8300
curl -s localhost:8300/is_alive
curl -s -H "Authorization: Bearer <token from config.test.json>" "localhost:8300/agreements?client_name=ישראל%20ישראלי"
```

## Tests (always through the wrapper scripts, never bare pytest)

```bash
cd apps/denidin-app
scripts/run_unit_integration_tests.sh tests/unit/test_agreements_manager.py
scripts/run_unit_integration_tests.sh tests/integration/test_agreements_api.py
scripts/run_single_test.sh "tests/billed/test_agreements_whatsapp.py::TestUat51::test_query"   # billed
cd ../webapp/e2e && npx playwright test agreements                                            # [UI]
```

## Migration rehearsal (on a COPY, never prod)

```bash
cd apps/webapp/backend && python3 scripts/export_name_resolution.py --config <cfg> --out <scratch>/name_resolution.json
cd apps/denidin-app && python3 scripts/migrate_agreements_089.py --data-root <copy> \
    --resolution <scratch>/name_resolution.json --dry-run
```
(`<scratch>` is your scratchpad directory, not `/tmp`.) A real run needs its own explicit human
go-ahead and is part of the release procedure, not of development.

## Smoke check of the finished feature (manual UAT walk-through)

1. Open Clients tab, expand a client: a "הסכמים" section lists agreements and components (UAT 1.1-1.2).
2. Edit a retainer amount: one new ledger event appears (UAT 2.2).
3. Ask the bot about that agreement on WhatsApp: it reports the edited amount (UAT 4.2).
4. Mark the agreement Completed: Active components become Completed, Pending become Cancelled (UAT 3.5).
