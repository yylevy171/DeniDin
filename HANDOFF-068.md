# Feature 068 — Ledger Web UI — Session Handoff

**Date:** 2026-09-07
**Clone:** coder2 ("Bina")
**Branch:** `feature/068-ledger-ui-and-reports` (⚠️ everything below is **uncommitted** — no haleluya has been run)
**Prod status:** already deployed & live — `webapp v0.0.1-webapp`, reachable at `https://yaronlaptop.tail274e9b.ts.net/` (Tailscale Serve).

Per-test statuses live in a companion file: **`apps/webapp/e2e/TEST-STATUS.md`**.

---

## 1. What this session did (chronological)

### 1a. Playwright acceptance suite — implemented in full
- **Task 1:** fixed the stale note in `specs/in-progress/068-ledger-ui-and-reports/tasks.md` so it points at `PLAYWRIGHT-TEST-PLAN.md` as the authoritative, approved acceptance gate.
- **Task 2:** implemented the entire suite in **`apps/webapp/e2e/`** (whole directory is **untracked**). One spec file per component:
  | file | component |
  |---|---|
  | `tests/00-layout.spec.ts` | 0 Layout + 0b Responsiveness |
  | `tests/01-auth.spec.ts` | 1 Session & Auth |
  | `tests/02-initial-load.spec.ts` | 2 Initial Load |
  | `tests/03-filters.spec.ts` | 3 Filters |
  | `tests/04-expand-single.spec.ts` | 4 Row Expand (single) |
  | `tests/05-expand-multi.spec.ts` | 5 Expand (multi) |
  | `tests/06-mobile.spec.ts` | 6 Mobile viewport (mobile-chromium project only) |
  | `tests/07-sigma.spec.ts` | 7 Σ Summation |
  | `tests/08-settings.spec.ts` | 8 Settings |
  | `tests/09-visual.spec.ts` | 9 Visual Regression |
  | `tests/_helpers.ts` | shared login / rows / filters / manifest helpers |
- **Real stack, zero mocking:** `serve.sh` seeds a deterministic date-relative fixture (`seed_fixture.py`, events E1–E16 + sessions S1/S2/S3/S13/S14 + media) and starts **two real `webapp_backend` instances** — `:8130` (full fixture) and `:8131` (empty-window fixture). One Vite dev server on `:4173` serves the real frontend build; `?api=<origin>` (localhost-gated in `api.ts`) points the frontend at whichever backend a test needs.
- **`playwright.config.ts`:** `workers: 1`, `fullyParallel: false` (shared singleton fixture). Two projects — `desktop-chromium` (1280×900, `testIgnore: /06-mobile/`) and `mobile-chromium` (Pixel 7, `testMatch: /06-mobile/`). `expect.timeout 7s`, `toHaveScreenshot.maxDiffPixelRatio 0.02`.
- **`seed_fixture.py`** modified this session: added `e1-second.png` to message M2 so E1's chat has **two** working thumbnails (test 4.4.13). Fixture password: `sha256("denidin-pw" + "e2e-pass")`.

### 1b. Frontend testability changes (behaviour-neutral)
`apps/webapp/frontend/src/App.tsx`, `ui.tsx`, `api.ts` — all `vite build`-clean:
- `testID` / `data-testid` on every interactive element, `aria-expanded` on `expand-toggle-*`, `data-theme` on `<html>` mirroring `settings.theme`.
- **RNW gotcha fix pattern:** `react-native-web` strips spread `aria-*`/`data-*` props. Canonical fix used here — put `disabled={!!disabled}` **directly on `<Pressable>`** → RNW then emits `aria-disabled="true"` + `pointer-events:none` when true, nothing when false. Enabled assertions use `.not.toHaveAttribute("aria-disabled","true")`.
- Chat message testID renamed `context-message` → `chat-msg-${message_id}` (the old one matched nested sender/time spans).
- `api.ts` `resolveBase()` — only localhost/127.0.0.1 honours the `?api=` query override; otherwise `VITE_API_BASE` build env.
- **No production behaviour changed by any of the above.** The one real behaviour change this session is the G1 mobile fix — see §1f.

### 1c. `run_webapp.sh` merged into one script
- `run_webapp_dev.sh` **deleted**. `run_webapp.sh` now takes a mode argument:
  - `./run_webapp.sh host` — uvicorn :8100 + Vite :5173, live-reload, no Docker, Ctrl-C stops both (was `run_webapp_dev.sh`).
  - `./run_webapp.sh dev` / `prod` — Docker Compose (backend + nginx frontend + dormant `cloudflared`).
- Doc refs updated in `quickstart.md`, `tasks.md`.

### 1d. Env-lock agnostic
- `run_webapp.sh` / `stop_webapp.sh` **no longer acquire / release / check** `shared/active_env.json`. The webapp is a read-only viewer — no Green API traffic, mutates nothing, no contention — so it starts/stops regardless of which clone owns dev.
- **Still enforced:** `env_lock_require_local_override "$ENV"` (the mandatory per-clone `docker-compose.<env>.local.yml` check — data-fragmentation guard, unrelated to locking, never remove).
- `stop_webapp.sh` accepts + ignores a 2nd positional arg (so `stop_all.sh`'s `-force` pass-through doesn't break it).
- Comments updated in `docker/docker-compose.dev.yml`.

### 1e. Ingress — Cloudflare dropped, Tailscale adopted
- User has **no domain** and won't buy one → Cloudflare Tunnel is **deferred indefinitely**. The `cloudflared-dev` / `cloudflared-prod` services stay **dormant** in both compose files (`env_file required:false`, `restart:"no"`, deploy scripts skip them without a token file) — zero cost, kept as a future option.
- **Real remote access:**
  - **prod:** Tailscale Serve, already configured on the Windows box → `https://yaronlaptop.tail274e9b.ts.net/` (HTTPS, TLS-terminated by Tailscale, **no port**). `yaronlaptop` is the box's real Tailscale hostname — **not** the `denidin-winprod` SSH alias.
  - **dev:** LAN/WiFi only → `http://10.0.0.6:5100` (Docker binds `0.0.0.0`; `10.0.0.6` is this Mac's LAN IP). No Serve config on the dev Mac.
- Updated: `run_webapp.sh` (header + echo), `docker/docker-compose.dev.yml`, `docker/docker-compose.prod.yml`, `specs/in-progress/068-.../{quickstart,research,plan,spec,tasks}.md`.

### 1f. bugfix-052 **G1 fixed** — mobile horizontal page scroll
User opened the dev webapp on their phone and it rendered broken (content shoved off-screen right, blank left half). Root cause = `COLUMNS` in `App.tsx` are ~610px of fixed-width cells in a non-wrapping row (both the column header and every event row), with no own overflow container → page body scrolls sideways → RTL opens it on the wrong edge.

**Fix (all inside the existing `isMobile = width < 768` branch — desktop path byte-identical):**
1. collapsed-row cell cluster gets `flexWrap: "wrap"` on mobile;
2. the desktop-only `<View flex:1>` spacer in that cluster is dropped on mobile;
3. the 6-fixed-column header is replaced on mobile by a compact bar with only the two interactive controls (`expand-all`/`collapse-all` toggle + date `sort-toggle`).

**Verification done this session:**
- `test.fixme` removed from `0.10`, `0b.1`, `0b.3`, `6.3.3` → all now **pass**.
- All **5 desktop** Component-9 visual baselines pass **byte-unchanged** (file timestamps unchanged) → desktop provably untouched.
- **2 mobile** visual baselines regenerated via `--update-snapshots` and committed (`collapsed-mobile-*.png`, `expanded-row-mobile-*.png`) — mobile layout legitimately changed.
- `test.fixme` **restored** on `0.4`, `6.5.4`, `6.5.6` (a regex over-stripped them; G1 does not fix those — they're G1a / G2).
- `webapp-frontend-dev` image rebuilt + container recreated so the phone gets the fix.

### 1g. Dev webapp brought up for manual QA (⚠️ now stopped)
- Built `webapp-backend-dev` + `webapp-frontend-dev` images (they didn't exist — only prod-release + old experiment tags did) and started via `run_webapp.sh dev`.
- Was reachable at `http://10.0.0.6:5100`, password **`denidin`**, serving **live dev ledger data** (read-only mount, `index_size=4173`, 82 events in the default 7-day window).
- **As of this handoff the containers show `Exited (255) ~12h ago`** — almost certainly a colima/Docker restart on machine sleep (`restart: "no"` everywhere, and the webapp isn't covered by `~/bin/colima-keepalive.sh`). **Needs a plain `./apps/webapp/run_webapp.sh dev` to come back** (images still exist unless pruned).
- Killed two stale host processes from earlier sessions: a `python` uvicorn on `127.0.0.1:8100` and a `node` Vite on `:5173`. Left the unrelated `ssh` `*:8100` forward alone.

### 1h. Docs / tracking updated
- **`specs/bugfixes/bugfix-052-webapp-ui-gaps-vs-approved-playwright-plan.md`** (untracked, new): 7 root-cause groups G1–G7. **G1 marked FIXED (2026-09-06)**, new **G1a** split out (filter-bar RTL order on narrow wrap — still open). Status now "Partially fixed."
- **`tasks.md`** acceptance block: `256 passed, 0 failed, 14 test.fixme`.
- **`apps/webapp/e2e/README.md`**: fixme inventory updated (14, tracked as bugfix-052), G1 marked done.

---

## 2. Current test state

**`cd apps/webapp/e2e && ./node_modules/.bin/playwright test`** → **270 tests: 256 passed · 0 failed · 14 skipped**
- desktop-chromium: 244 passed · 12 skipped
- mobile-chromium: 12 passed · 2 skipped

The 14 skipped = **11 `test.fixme`** (real plan-backed gaps, tracked as bugfix-052) + **3 `test.skip`** (Component 1.5 session-expiry — designated manual-only by the plan, never automated). Full breakdown with every test number, title, reason and bugfix-052 group is in **`apps/webapp/e2e/TEST-STATUS.md`**.

---

## 3. Uncommitted working tree (branch `feature/068-ledger-ui-and-reports`)

```
 M apps/webapp/frontend/src/App.tsx          # testIDs + data-theme + G1 mobile fix
 M apps/webapp/frontend/src/api.ts           # resolveBase() / ?api= gating
 M apps/webapp/frontend/src/ui.tsx           # testIDs + RNW aria fixes + chat-msg-* rename
 M apps/webapp/run_webapp.sh                 # merged host|dev|prod, lock-agnostic, Tailscale
 D apps/webapp/run_webapp_dev.sh             # merged into run_webapp.sh host
 M apps/webapp/stop_webapp.sh                # lock-agnostic
 M docker/docker-compose.dev.yml             # webapp comment: lock-agnostic + cloudflared dormant
 M docker/docker-compose.prod.yml            # cloudflared dormant / Tailscale Serve comment
 M specs/in-progress/068-ledger-ui-and-reports/plan.md
 M specs/in-progress/068-ledger-ui-and-reports/quickstart.md
 M specs/in-progress/068-ledger-ui-and-reports/research.md
 M specs/in-progress/068-ledger-ui-and-reports/spec.md
 M specs/in-progress/068-ledger-ui-and-reports/tasks.md
?? apps/webapp/e2e/                          # ENTIRE Playwright suite (untracked)
?? specs/bugfixes/bugfix-052-webapp-ui-gaps-vs-approved-playwright-plan.md
```

`apps/webapp/e2e/.gitignore` covers `node_modules/`, `.fixture/`, `playwright-report/`, `test-results/`, `blob-report/`, `.last-run.json`. The 7 visual baseline PNGs in `tests/09-visual.spec.ts-snapshots/` **are meant to be committed**.

---

## 4. What is NOT done / open decisions

| item | state | who decides |
|---|---|---|
| **Manual mobile QA on dev** | user was mid-QA; found G1, G1 fixed; dev webapp now stopped — restart & continue | user |
| **bugfix-052 G1a + G2–G7** | Open. Root cause written; needs human approval before any fix (BDD gate) | user |
| **Feature 068 haleluya** | not started — all work uncommitted. Only on explicit `haleluya`/`/haleluya` | user |
| **Cut a new webapp release** | prod is on `v0.0.1-webapp`; a new cut is a human-only version decision | user |
| **webapp reboot-recovery** | webapp containers are `restart:"no"` and not in any keepalive; ride **bug43** once it lands (add `webapp-backend-<env>` / `webapp-frontend-<env>` to its start-set) | — |

---

## 5. How to resume

```bash
# 1. restart the dev webapp for QA (lock-agnostic, safe regardless of who owns dev)
cd /Users/yaron/Projects/DeniDin/coder2
./apps/webapp/run_webapp.sh dev
#   phone → http://10.0.0.6:5100   password: denidin

# 2. run the acceptance suite
cd apps/webapp/e2e
lsof -ti :8130 :8131 :4173 | xargs kill 2>/dev/null   # clear stale servers first
./node_modules/.bin/playwright test                    # NOT `npx playwright` — wrong global version
#   single project:  ./node_modules/.bin/playwright test --project=mobile-chromium
#   single test:     ./node_modules/.bin/playwright test -g "6.3.3"

# 3. rebuild dev webapp after a frontend/backend code change (compose `up` never rebuilds)
docker compose --project-directory . \
  -f docker/docker-compose.dev.yml -f docker/docker-compose.dev.local.yml \
  build webapp-backend-dev webapp-frontend-dev
./apps/webapp/run_webapp.sh dev
```

### Gotchas
- **Confined to coder2 ("Bina").** Never read/list/grep/cd/run in sibling clones (coder1, root) — even read-only.
- **Never** haleluya / commit / push / PR / merge / deploy / cut a release / pick a version without the explicit word from the user.
- **`./node_modules/.bin/playwright`**, never bare `npx playwright` (resolves to a wrong global 1.63 — "Available projects: ''").
- **Fixture is date-relative.** `seed_fixture.py` writes dates relative to seed day. A stale reused server (`reuseExistingServer`) after a calendar rollover drifts the 7-day window and flakes 3.8.1 / 7.5.2 — kill `:8130 :8131 :4173` for a fresh reseed.
- **Visual baselines** change ONLY via a deliberate `--update-snapshots` run + human review of the PNGs (plan §9.5). 5 desktop + 2 mobile = 7 files.
- Dev webapp images: `denidin-dev-webapp-{backend,frontend}-dev`. Prod-release tags: `webapp-{backend,frontend}:0.0.1-webapp`. Old experiment tags (`ctxfix1/2`, `logo1`) can be pruned.
- Backend `/health` reports `version` from `apps/webapp/VERSION` (`0.0.1-webapp`). The host uvicorn's own resolution differs (`0.5.4`) — irrelevant, don't chase it.
