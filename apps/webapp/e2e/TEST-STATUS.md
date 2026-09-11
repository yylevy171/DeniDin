# Feature 068 — Playwright acceptance suite: per-test status

**Last full run:** 2026-09-06 (after the bugfix-052 **G1** mobile fix landed).
**Command:** `cd apps/webapp/e2e && ./node_modules/.bin/playwright test`
**Result:** **~270 tests · 256 passed · 0 failed · 14 skipped**
- `desktop-chromium` (1280×900, ignores `06-mobile`): 244 passed · 12 skipped
- `mobile-chromium` (Pixel 7, only `06-mobile`): 12 passed · 2 skipped

> The 256 / 0 / 14 totals are authoritative (from the actual run). The per-file
> pass counts below are a faithful reconstruction and may be off by ±1 on a
> file; the **skipped list is exact** (14 = 11 `test.fixme` + 3 `test.skip`).
> To regenerate exact per-test titles: `grep -n 'test(' tests/<file>.spec.ts`
> or `./node_modules/.bin/playwright test --list`.

---

## Summary by component

| file | component | tests | pass | skipped |
|---|---|---:|---:|---:|
| `00-layout.spec.ts` | 0 Layout + 0b Responsiveness | 17 | 16 | 1 `fixme` |
| `01-auth.spec.ts` | 1 Session & Auth | 24 | 21 | 3 `skip` |
| `02-initial-load.spec.ts` | 2 Initial Load | 19 | 18 | 1 `fixme` |
| `03-filters.spec.ts` | 3 Filters | 74 | 70 | 4 `fixme` |
| `04-expand-single.spec.ts` | 4 Row Expand (single) | 52 | 50 | 2 `fixme` |
| `05-expand-multi.spec.ts` | 5 Expand (multi) | 20 | 19 | 1 `fixme` |
| `06-mobile.spec.ts` | 6 Mobile viewport | 14 | 12 | 2 `fixme` |
| `07-sigma.spec.ts` | 7 Σ Summation | 17 | 17 | 0 |
| `08-settings.spec.ts` | 8 Settings | 25 | 25 | 0 |
| `09-visual.spec.ts` | 9 Visual Regression | 9 | 9 | 0 |

---

## The 14 skipped tests (exact)

### 3 × `test.skip` — manual-only by design (NOT bugs, NOT bugfix-052)
Component 1.5 (session expiry after 168h) — the `PLAYWRIGHT-TEST-PLAN.md` designates
these manual-only, never automated.

| test | file |
|---|---|
| `1.5.1` session-expiry (manual) | `01-auth.spec.ts` |
| `1.5.2` session-expiry (manual) | `01-auth.spec.ts` |
| `1.5.3` session-expiry (manual) | `01-auth.spec.ts` |

### 11 × `test.fixme` — real plan-backed gaps, tracked as **bugfix-052**

| test | file | bugfix-052 group | gap |
|---|---|---|---|
| `0.4` filter bar RTL control order is consistent desktop vs mobile | `00-layout` | **G1a** | when the filter bar wraps on a narrow viewport, `filter-apply` drops to a 2nd line and its RTL x-order no longer matches desktop |
| `2.4.5` refresh re-applies active filters | `02-initial-load` | **G3** | `load('refresh')` unconditionally clears `typeSel`/`subSel`/`clientText`/`globalText`/date range back to defaults instead of refetching + re-applying the active filters |
| `3.3.4` zero types selected keeps every subtype selectable | `03-filters` | **G5** | `disabledSubs` treats only "all types selected" as "no filter"; with **zero** types it greys **every** subtype |
| `3.3.5` invalidated subtype is auto-pruned when the type set narrows | `03-filters` | **G5** | a subtype checked before the type selection narrowed is kept in `subSel` even once invalid for the new type set |
| `3.4.18` fuzzy client-name match tolerates a typo | `03-filters` | **G4** | client-name filter is `norm(a).includes(norm(b))` — plain folded substring, not fuzzy |
| `3.5.5` fuzzy free-text match tolerates a typo | `03-filters` | **G4** | same — global search is substring-only |
| `4.4.16` video/audio message shows a non-playable placeholder | `04-expand-single` | **G6** | no placeholder for video/audio; also no fixture message carries one yet |
| `4.4.17` document attachment renders as a clickable thumbnail | `04-expand-single` | **G6** | `ChatImage` renders every `media_url` as `<img>`; a PDF/DOCX URL fails to decode → shows `[מדיה לא זמינה]`, no thumbnail, no click-to-open |
| `5.2.1` one-click "collapse all" closes every open row regardless of how it was opened | `05-expand-multi` | **G7** | header toggle-all derives from a separate `allMode` state that only tracks the last toggle-all press; rows expanded individually need expand-all first, then collapse-all (two presses) |
| `6.5.4` mobile chat panel holds its fixed ~240px height, not full page height | `06-mobile` | **G2** | context panel sets `height:240` but inner `ChatPanel` `ScrollView` `flex:1` wins → panel grows to content height |
| `6.5.6` scrolling inside the mobile chat panel doesn't scroll the outer row list | `06-mobile` | **G2** | no bounded scroll region → wheel/touch inside the chat falls through to the page (`overscroll-behavior: contain` missing) |

---

## bugfix-052 **G1 — FIXED 2026-09-06** (4 tests flipped `fixme` → `pass`)

Mobile / narrow-viewport horizontal **page** scroll. Fix in `App.tsx`, entirely inside the
existing `isMobile = width < 768` branch (desktop render byte-identical — all 5 desktop
visual baselines pass unchanged). These now **pass**:

| test | file | assertion |
|---|---|---|
| `0.10` live resize desktop→narrow reflows with no h-scroll | `00-layout` | `documentElement.scrollWidth - clientWidth <= 1` at 1200/900/700/500/380 px |
| `0b.1` mobile portrait↔landscape reflows live, no h-scroll | `00-layout` | same, at 390×844 and 844×390 |
| `0b.3` progressive desktop narrowing, no h-scroll through intermediate widths | `00-layout` | same, 1440→360 step 90 |
| `6.3.3` no row ever requires horizontal scrolling | `06-mobile` | same, Pixel 7 width |

2 mobile visual baselines were regenerated for this change and committed:
`tests/09-visual.spec.ts-snapshots/collapsed-mobile-desktop-chromium-darwin.png`,
`…/expanded-row-mobile-desktop-chromium-darwin.png`. The 5 desktop baselines were **not**
touched.

---

## Passing tests — component detail

Full verbatim titles: `grep -n 'test(' tests/<file>.spec.ts`. Verified-verbatim titles are
given for Components 0 and 6 (greps captured them this session); others are by number +
sub-block.

### Component 0 / 0b — `00-layout.spec.ts` (16 pass, 1 fixme)
```
0.1  desktop: all filter controls visible in one bar above the list          PASS
0.2  mobile: same controls wrap onto multiple lines, never behind a toggle   PASS
0.3  no filter control is hidden behind a collapsed panel at any viewport    PASS
0.4  filter bar RTL control order is consistent desktop vs mobile            FIXME (G1a)
0.5  Apply button stays visible/reachable at every viewport size             PASS
0.6  desktop top bar shows every control group in consistent RTL order       PASS
0.7  mobile top bar keeps all controls visible, never an overflow menu       PASS
0.8  no top-bar control disappears at any tested viewport width              PASS
0.9  mobile icon/touch targets are large enough (>= 32px)                    PASS
0.10 live resize desktop->narrow reflows, no leftover artifacts / no h-scroll PASS  (was FIXME — G1)
0.11 RTL is consistent in the chrome (html dir=rtl, no accidental LTR row)   PASS
0b.1 rotating a mobile device (portrait<->landscape) reflows live           PASS  (was FIXME — G1)
0b.2 browser zoom / font-scaling doesn't overflow containers                PASS
0b.3 progressive desktop narrowing reflows smoothly through widths          PASS  (was FIXME — G1)
0b.4 reduced viewport area (DevTools/split-screen) reflows correctly        PASS
0b.5 an extremely narrow width doesn't crash the layout                     PASS
0b.6 an extremely wide monitor doesn't leave the layout broken/stretched    PASS
```

### Component 1 — `01-auth.spec.ts` (21 pass, 3 skip)
Sub-blocks: 1.1 login screen, 1.2 wrong password, 1.3 successful login + token, 1.4 logout,
**1.5 session expiry (3 × `test.skip`, manual-only)**, 1.6 token persistence across reload,
1.7 401 handling / re-auth. 21 automated tests pass.

### Component 2 — `02-initial-load.spec.ts` (18 pass, 1 fixme)
Sub-blocks: 2.1 default 7-day window + Israel-local date math, 2.2 record count, 2.3 empty
state, 2.4 refresh button (**2.4.5 `fixme` — G3**), 2.5 sort default (desc), loading state.
18 pass.

### Component 3 — `03-filters.spec.ts` (70 pass, 4 fixme)
Sub-blocks: 3.1 no-Apply-is-a-no-op, 3.2 date range (incl. "from" pulling older history),
3.3 type / subtype multi-select (**3.3.4, 3.3.5 `fixme` — G5**), 3.4 client-name +
typeahead (**3.4.18 `fixme` — G4**), 3.5 free-text search (**3.5.5 `fixme` — G4**), 3.6
filters never trigger a fetch, 3.7 combined filters, 3.8 clear / reset (3.8.1 uses
`expect.poll` for load-flake tolerance). 70 pass.

### Component 4 — `04-expand-single.spec.ts` (50 pass, 2 fixme)
Sub-blocks: 4.1 expand/collapse toggle + icon, 4.2 detail panel field manifest per source
type (`detail-field-<key>`), 4.3 context/chat panel (message window by `message_id`,
`side`/`sender_name`, `context_unavailable`), 4.4 media — image thumbnails + lightbox
(4.4.13 needs the 2nd fixture thumbnail added this session), **4.4.16 video/audio `fixme` —
G6**, **4.4.17 documents `fixme` — G6**. 50 pass.

### Component 5 — `05-expand-multi.spec.ts` (19 pass, 1 fixme)
Sub-blocks: 5.1 multiple independent expansions don't interfere, 5.2 expand-all /
collapse-all header toggle (**5.2.1 `fixme` — G7**). 19 pass.

### Component 6 — `06-mobile.spec.ts` (12 pass, 2 fixme) — mobile-chromium only
```
6.1.1 detail panel appears above the chat panel on mobile                    PASS
6.1.2 both panels are full / near-full width                                 PASS
6.2.1 each independently expanded row shows its own correctly-stacked pair   PASS
6.2.2 stacking applies uniformly across every expansion                      PASS
6.3.1 description wraps onto a second sub-row when needed                     PASS
6.3.2 the core fields stay on the first line under normal circumstances      PASS
6.3.3 no row ever requires horizontal scrolling                              PASS  (was FIXME — G1)
6.3.4 amount and date remain fully visible / un-truncated under tight width  PASS
6.5.1 chat bubbles remain legible at mobile width                            PASS
6.5.2 tapping a thumbnail opens the larger view, sized for the smaller screen PASS
6.5.3 'OK' remains reachable / tappable                                      PASS
6.5.4 the chat panel occupies its fixed height, not full page height         FIXME (G2)
6.5.5 the panel has its own internal scrollbar, independent of outer scroll  PASS
6.5.6 scrolling inside the chat panel doesn't scroll the outer row list      FIXME (G2)
```
(mobile `expand()` helper uses `scrollIntoViewIfNeeded()` + `click({force:true})` — a note
in the file explains it was for the pre-G1 h-overflow interception; harmless now.)

### Component 7 — `07-sigma.spec.ts` (17 pass, 0 skipped)
Σ button computes count + raw sum over the currently-visible rows; sign handling
(`₪-500`), bidi-mark stripping in `parseSigma`, recompute on filter change, disabled while
refreshing. `expected(page)` recomputes the raw sum from `rowIds` + `readEvent`. All 17
pass. (7.5.2 can flake only on a stale fixture server after a calendar rollover — reseed.)

### Component 8 — `08-settings.spec.ts` (25 pass, 0 skipped)
Sub-blocks: 8.1 theme toggle (+ `data-theme` on `<html>`, 8.1.5 OS-dark still loads light),
8.2 panel layout, 8.3 days-back MiniNum (garbage input → asserts substantive behavior:
never applied, no `/api/events` call, `rowIds` unchanged, authoritative value on reopen —
**not** visual snap-back, a known minor gap), 8.4 lookback MiniNum (clamped 0–60), 8.5
`localStorage` persistence (`denidin_ledger_settings`), 8.6 open/close (backdrop, Esc), 8.7
logout → back to password screen. All 25 pass.

### Component 9 — `09-visual.spec.ts` (9 pass, 0 skipped)
```
9.1.1 collapsed list, desktop 1280x900, light        toHaveScreenshot  PASS  (baseline unchanged by G1)
9.2.1 single expanded row, desktop                    toHaveScreenshot  PASS  (baseline unchanged)
9.2.2 expanded row with image thumbnail, desktop      toHaveScreenshot  PASS  (baseline unchanged)
9.3.1 collapsed list, mobile 390x844                  toHaveScreenshot  PASS  (baseline REGENERATED for G1)
9.3.2 expanded row, mobile (stacked panels)           toHaveScreenshot  PASS  (baseline REGENERATED for G1)
9.4.1 collapsed list, desktop dark theme              toHaveScreenshot  PASS  (baseline unchanged)
9.4.2 expanded row, desktop dark theme                toHaveScreenshot  PASS  (baseline unchanged)
9.5   baselines change only via a deliberate committed --update-snapshots run  PASS  (process rule)
```
Baselines in `tests/09-visual.spec.ts-snapshots/` (7 PNGs) **are committed**. Change only
via `--update-snapshots` + human review of the diff (plan §9.5).

---

## How each gap gets verified when fixed (per bugfix-052)

For each `test.fixme`: delete the `test.fixme(...)` line, run that spec, confirm the
previously-skipped case passes with **no other change to the test body**. Then a full run
must show `0 failed`. Regenerate Component-9 baselines (`--update-snapshots`) only if the
fix changes the rendered layout, and review the new PNGs as code.

Target once G1a + G2–G7 are all closed: **0 failed · 3 skipped** (only the manual-only
Component 1.5 session-expiry cases).
