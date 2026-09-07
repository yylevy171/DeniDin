# Feature 068 — Ledger Web UI: Playwright acceptance suite

End-to-end acceptance tests for `apps/webapp`, implementing
[`PLAYWRIGHT-TEST-PLAN.md`](../../../specs/in-progress/068-ledger-ui-and-reports/PLAYWRIGHT-TEST-PLAN.md)
(the full, case-by-case-approved plan — ~270 cases across 10 components, 0–9).

This is **not** part of the Python `pytest` tiers (`unit`/`integration`/`billed`/`expensive`)
and **not** CI (there is no CI here). It is its own JS test tier, run on demand.

## Running

```bash
cd apps/webapp/e2e
npm install            # first time only
npx playwright install chromium   # first time only
./node_modules/.bin/playwright test                     # everything (both projects)
./node_modules/.bin/playwright test --project=desktop-chromium
./node_modules/.bin/playwright test 04-expand-single --project=desktop-chromium
./node_modules/.bin/playwright test --ui                # interactive
```

`playwright.config.ts`'s `webServer` block starts everything automatically:

- **`serve.sh`** runs `seed_fixture.py` (rebuilds `.fixture/`), then starts **two real
  `webapp_backend` instances** — `:8130` (the "full" 16-event fixture) and `:8131` (an
  "empty window" fixture). No mocking: the backend reads `.fixture/<name>/` exactly as it
  reads denidin-app's data root in production.
- one **Vite dev server** on `:4173` serves the real frontend. `?api=<origin>` (localhost-gated
  in `api.ts`) points a page at whichever backend a test needs.

## Fixture is date-relative — re-seed after a calendar-day rollover

`seed_fixture.py` writes every event/message date **relative to the day it runs**, so the
trailing-window and lookback assertions never go stale. Consequence: if a `webServer` from a
*previous* day is still running, `reuseExistingServer` will reuse its now-stale fixture and the
7-day-window tests will drift by a day. If you see window-count failures, kill the stragglers
and let the suite restart the server fresh:

```bash
lsof -ti :8130 :8131 :4173 | xargs kill
```

## `test.fixme` — known gaps (14), tracked as bugfix-052

Tests marked `test.fixme` document real behavior the plan calls for that the current build
doesn't do yet — the "viewable → done" bucket from `tasks.md` (Stories 0/0b and 4–8). They are
written, skipped, and carry a one-line note pointing at the plan section + bugfix-052 group.
Grep:

```bash
grep -rn "test.fixme" tests/
```

**Fixed 2026-09-06 (bugfix-052 G1)**: mobile/narrow horizontal page scroll — 0.10 / 0b.1 /
0b.3 / 6.3.3 now pass (`App.tsx` `isMobile` branch: collapsed-row cells wrap, compact mobile
column header; desktop unchanged).

Remaining headline gaps: filter-bar RTL order drifts on a narrow wrap (0.4); mobile chat panel
doesn't hold its fixed height / nested-scroll bleed (6.5.4 / 6.5.6); refresh resets filters
instead of re-applying them (2.4.5); fuzzy client/free-text matching is substring-only (3.4.18
/ 3.5.5); subtype scoping edges — zero-types greys every subtype, invalidated subtype not
pruned (3.3.4 / 3.3.5); document attachments render as "media unavailable" not a thumbnail
(4.4.16 / 4.4.17); one-click collapse-all only works after an expand-all (5.2.1 / 5.2.2). Plus
3 manual-only session-expiry `test.skip` (1.5).

## Visual regression baselines (Component 9)

Baseline PNGs live in `tests/09-visual.spec.ts-snapshots/` and **are committed**. Per plan
§9.5 they change **only** via a deliberate, reviewed update:

```bash
./node_modules/.bin/playwright test 09-visual --update-snapshots
git add tests/09-visual.spec.ts-snapshots/    # review the diff like any code change
```

Because the fixture is date-relative, regenerate the baselines whenever you re-seed on a new
calendar day and intend to commit — it's the same deliberate step §9.5 already requires.

## Frontend test hooks

The suite relies on `testID` / `data-testid`, `data-theme` (on `<html>`), and `aria-checked`
/ `aria-disabled` / `aria-expanded` attributes added purely for testability. `?api=` routing in
`api.ts` is localhost-gated. None of this changes production behavior.
