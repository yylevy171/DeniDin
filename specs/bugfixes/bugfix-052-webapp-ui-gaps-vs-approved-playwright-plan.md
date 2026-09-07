# Bugfix Spec: Ledger Web UI (Feature 068) behavior gaps vs. the approved Playwright test plan

## Bug ID
bugfix-052-webapp-ui-gaps-vs-approved-playwright-plan

## Title
The `apps/webapp` frontend, as first built for Feature 068, does not implement a number of
behaviors the **approved** `PLAYWRIGHT-TEST-PLAN.md` explicitly calls for. When the full
acceptance suite (`apps/webapp/e2e/`) was implemented (2026-09-06), the tests for these
behaviors were written but marked `test.fixme` — real, enumerated, plan-backed gaps rather than
test failures. This bugfix tracks closing them so every `test.fixme` in the suite flips to a
passing test.

## Priority
**P2** — the webapp is read-only, internal, and password-gated; none of these gaps corrupt data
or block the core "browse the ledger, expand a row, read the conversation" flow. Several are
visible-quality problems (horizontal page scroll on small screens, a chat panel that overgrows
its box) and two are correctness-of-filtering problems ("fuzzy" match is actually substring;
refresh silently drops your filters).

## Status
**Partially fixed.** **G1 (bulk) fixed 2026-09-06** — the mobile/narrow horizontal-page-scroll
gap, at the user's direct request after seeing it on a real phone (no separate BDD cycle: live
repro + the pre-written plan-approved failing tests were sufficient). `test.fixme` removed from
`0.10`, `0b.1`, `0b.3`, `6.3.3`; all now pass. The **remaining** gaps (0.4, G2–G7) are still
**Open** — next step for those is human approval of the root-cause analysis below.

Note on the BDD "failing test" gate: the failing tests **already exist and are already
plan-approved** — they are the `test.fixme` blocks in `apps/webapp/e2e/tests/`, each written
against a specific, numbered `PLAYWRIGHT-TEST-PLAN.md` case. Closing each gap = removing its
`test.fixme(...)` line and confirming the test (unchanged otherwise) passes. No new test code
needs to be authored or separately approved for the gaps that map 1:1 to an existing fixme.

## Date Opened
2026-09-06

## Reported By
yaronlev171, on reviewing the Feature 068 Playwright acceptance suite implementation — noticed
the skipped/fixme count and asked for the UI gaps to be tracked as their own bugfix.

## Affected Area
All in `apps/webapp/frontend/src/` (`App.tsx` / `ui.tsx`). The backend and the e2e suite are
not at fault — the suite documents the gaps correctly.

## The gaps (each = one or more `test.fixme`, cited to the plan)

### G1 — wide events table has no own horizontal-scroll container — ✅ FIXED 2026-09-06
- **Plan cases**: 0.10, 0b.1, 0b.3, 6.3.3 — all now passing. (0.4 was originally listed here
  too but is a *different* problem — see G1a below — and is still open.)
- **Was**: the row header + each row used fixed-width cells (`18+82+78+120+150+100` px + gaps
  ≈ 560px). Below ~768px the **page itself** scrolled horizontally
  (`documentElement.scrollWidth - clientWidth` ≈ 150px at 380px wide; ≈24px portrait mobile).
- **Fix** (`App.tsx`, all gated on the existing `isMobile = width < 768`, desktop path byte-
  identical — verified: all 5 Component-9 desktop visual baselines pass unchanged):
  1. the collapsed row's cell cluster gets `flexWrap: "wrap"` on mobile, so the fixed-width
     cells wrap to a 2nd line instead of overflowing the viewport;
  2. the desktop-only `<View flex:1>` spacer in that cluster is dropped on mobile (a flex:1
     item would force its own wrap line);
  3. the 6-fixed-column header is replaced on mobile by a compact bar with just the two
     interactive controls (`expand-all`/`collapse-all` toggle + date `sort-toggle`) — a fixed
     column header can't align to a wrapped card row anyway.
- The 2 mobile Component-9 baselines (`collapsed-mobile`, `expanded-row-mobile`) were
  regenerated (`--update-snapshots`, committed) since the mobile layout legitimately changed.

### G1a — filter-bar RTL control order drifts on a narrow wrap
- **Plan case**: 0.4 (still `test.fixme`)
- **Observed**: when the filter bar wraps on a narrow viewport, `filter-apply` drops to a
  second line and its right-to-left x-order no longer matches desktop.
- **Expected**: `filter-date-from` stays rightmost and `filter-apply` stays leftmost at every
  width.
- **Likely fix locus**: `App.tsx` filter bar — control the wrap so the apply/Σ group stays at
  the RTL end, or restructure into explicit rows below the breakpoint.

### G2 — mobile chat panel doesn't hold its fixed height
- **Plan cases**: 6.5.4, 6.5.6
- **Observed**: on mobile the context panel sets `height: 240` but the inner `ChatPanel`
  `ScrollView` has `flex: 1`, which wins — the panel grows to its content height (~450px
  observed) instead of staying a fixed box with its own scrollbar. Because there is no bounded
  scroll region, wheel/touch scrolling inside the chat falls through to the page (6.5.6).
- **Expected**: fixed-height chat panel (same rule desktop and mobile), internal scroll only,
  outer list unaffected.
- **Likely fix locus**: `App.tsx` expanded-row layout (`isMobile` branch) + `ui.tsx`
  `ChatPanel` — give the panel a hard height and let the `ScrollView` fill it without `flex: 1`
  overriding.

### G3 — "refresh data" resets all filters instead of re-applying them
- **Plan case**: 2.4.5
- **Observed**: `load('refresh')` unconditionally clears `typeSel` / `subSel` / `clientText` /
  `globalText` / date range back to defaults (`App.tsx` `load()`), so a refresh throws away
  whatever the user had filtered to.
- **Expected**: refresh re-fetches the trailing window and then **re-applies the currently
  active on-screen filters** (2026-09-05 plan decision). Only a days-back change or a genuine
  reload starts from the unfiltered set.
- **Likely fix locus**: `App.tsx` `load()` — separate "reset filter state" (days-back change /
  first load) from "refetch + keep applied filters" (refresh button).

### G4 — "fuzzy" client-name and free-text matching is plain substring
- **Plan cases**: 3.4.18, 3.5.5
- **Observed**: `visible` filtering uses `norm(a).includes(norm(b))` for both client-name and
  global search — a case/diacritic-folded **substring** test. A typo (`ישראל ישראלl` → `ישראל
  ישראלי`) returns zero rows; the plan expects it to still match.
- **Expected**: a real fuzzy match at Apply time (the backend already has `rapidfuzz`-style
  fuzzy scoring in `LedgerEventManager.query_events`; the webapp could call a backend fuzzy
  endpoint, or do a small client-side fuzzy pass). Typeahead **suggestions** stay prefix-only
  (plan 3.4.5) — only the Apply-time row filter goes fuzzy.
- **Likely fix locus**: decide client-side (bring a tiny fuzzy lib) vs. server-side (new
  `?fuzzy=` behavior on `/api/events` or a dedicated filter endpoint). Server-side is more
  consistent with the ledger's own matching and is the recommended direction — confirm in the
  fix's own design step.

### G5 — subtype scoping edge cases
- **Plan cases**: 3.3.4, 3.3.5
- **Observed**: `disabledSubs` treats **only** the "all types selected" state as "no type
  filter". With **zero** types selected it greys **every** subtype (3.3.4). And a subtype that
  was checked before the type selection narrowed is kept in `subSel` even once it's invalid for
  the new type set — not auto-removed (3.3.5, a 2026-09-05 plan decision).
- **Expected**: zero-types-selected behaves like all-types for subtype availability (everything
  selectable); an invalidated subtype is dropped from the applied filter state automatically.
- **Likely fix locus**: `App.tsx` `disabledSubs` memo + a `useEffect` that prunes `subSel`
  when `typeSel` changes.

### G6 — document attachments render as "media unavailable"
- **Plan case**: 4.4.17 (+ 4.4.16 for video/audio)
- **Observed**: `ChatImage` renders every `media_url` as an `<img>`. A PDF/DOCX URL fails to
  decode → the message shows the `[מדיה לא זמינה]` state. There is no thumbnail, no click-to-
  open. Video/audio messages have no placeholder at all (no fixture carries one yet either).
- **Expected** (2026-09-05 decision): a document attachment renders as a clickable thumbnail
  exactly like an image; clicking opens it in the same lightbox, relying on the browser's
  native PDF rendering, dismissed with "OK". Video/audio show a generic non-playable
  placeholder in v1.
- **Likely fix locus**: `ui.tsx` `ChatImage` / `ChatPanel` — branch on the media's content type
  (the backend `/api/media/<token>` response already sets `Content-Type`); render a doc icon
  thumbnail + open the raw URL in the overlay/an iframe. Also add a video/audio fixture message
  to `seed_fixture.py` so 4.4.16 has something to assert against.

### G7 — one-click "collapse all" only works after an "expand all"
- **Plan cases**: 5.2.1, 5.2.2
- **Observed**: the header toggle-all button's `testID`/label is `expand-all` while
  `allMode === "expand"`, and pressing it **expands** (then flips to `collapse` mode). Rows
  expanded individually can't be collapsed in a single action — you must expand-all first, then
  collapse-all (two presses).
- **Expected**: if **any** row is expanded, the toggle-all offers "collapse all" and one press
  closes every open row regardless of how it was opened.
- **Likely fix locus**: `App.tsx` — derive the toggle-all mode from "is anything currently
  expanded?" rather than from a separate `allMode` state that only tracks the last toggle-all
  press.

## Out of scope for this bugfix
- The 3 `test.skip` cases (Component 1.5, session expiry after 168h) — the plan itself designates
  these **manual-only, never automated**. Not a bug; no code change.
- Σ real semantics (sign-correcting credit notes, payment dedup, netting) — the plan explicitly
  defers these as future work; v1's naive raw sum is intended behavior.
- Any change to the e2e suite's structure, fixture, or the testability-only frontend hooks
  (`testID` etc.) added alongside it — those are correct as-is.

## Verification (when fixed)
For each gap: delete the corresponding `test.fixme(...)` line(s) in `apps/webapp/e2e/tests/`,
run that component's spec, confirm the previously-skipped case now passes with **no other change
to the test body**. Then a full-suite run (`cd apps/webapp/e2e && ./node_modules/.bin/playwright
test`) must show **0 failed, 3 skipped** (only the manual-only session-expiry cases). Regenerate
the Component 9 visual baselines (`--update-snapshots`) if a fix changes the rendered layout, and
review the new PNGs as code (plan §9.5).

**G1 done (2026-09-06)**: `mobile-chromium` 12 passed / 2 skipped (6.5.4, 6.5.6 = G2);
`desktop-chromium` 244 passed / 12 skipped / 0 failed. All 5 desktop visual baselines
unchanged; 2 mobile baselines regenerated + committed. Remaining `test.fixme`: 0.4 (G1a),
6.5.4/6.5.6 (G2), 2.4.5 (G3), 3.4.18/3.5.5 (G4), 3.3.4/3.3.5 (G5), 4.4.16/4.4.17 (G6),
5.2.1/5.2.2 (G7), + the 3 manual-only 1.5 skips.

## Related
- Feature 068 (`specs/in-progress/068-ledger-ui-and-reports/`) — the feature these gaps belong
  to; its `tasks.md` "viewable → done" Stories 0/0b and 4–8 describe the same shortfalls in
  prose.
- `apps/webapp/e2e/README.md` — how to run the suite and the current `test.fixme` inventory.
