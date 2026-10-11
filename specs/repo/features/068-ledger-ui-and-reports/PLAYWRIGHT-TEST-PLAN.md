# Playwright Test Plan — Feature 068 (Ledger Web UI)

**Status**: Approved test plan, component-by-component, as of 2026-09-05. This is the full
enumeration of every individual test case across all 9 components + Layout (Component 0).
🚨 Per explicit user instruction: **no implementation (Phases 1–10 in `tasks.md`) begins until
this plan is approved** — approval of the plan's content, not just its existence, gates the
start of any build work.

Total: **~303 individual test cases** across 10 components (see the Grand total line at the
bottom for the current count — it moves as audit passes add cases). Code for cases already
drafted lives in `contracts/playwright-draft.md`; the rest are specified here at the
exact-assertion level, ready to be turned into code once implementation is underway (or before,
per the gate above).

Key running decisions that apply across many components:
- Session token in `localStorage` (survives tab/browser close); expiry counted from **last
  activity**, 168h (1 week) default, **manual verification only, not automated**.
- All on-screen filters apply **client-side** over the loaded batch; only "days back" triggers
  a real backend reload. Client-name typeahead is the one real backend call
  (`GET /clients/search`, full history), fired after a **~300ms debounce**, not per keystroke.
- First-visit theme defaults to **light**; OS dark-mode preference is not auto-followed.
- Type/subtype dropdown options come from the **full loaded window**, not the post-filter
  visible set.
- Media URLs (`/media/<token>`) are **session-gated** — valid exactly as long as the session
  is; no separate per-file expiry.
- **Any Apply or "refresh data" collapses every expanded row**, and also **clears any shown Σ
  result** (not merely marks it stale).
- Same-date tiebreaker: `event_id`, direction mirrors the active sort order.
- Right panel (event detail) uses a per-type field manifest (`contracts/field-manifests.md`) —
  not a raw dump of every `LedgerEvent` field.
- Left panel is a WhatsApp-style chat (human right / bot left), fixed height with its own
  internal scroll, same on desktop and mobile.
- Σ summation in v1 is a deliberately naive raw sum — real semantics (sign correction, dedup,
  netting) are explicit future work, not tested here.

---

## Component 0 — Layout (11 tests)

**Filter bar** (always visible, single row that wraps — never a collapsible panel):
1. Desktop: all filter controls in one horizontal row above the list.
2. Mobile: same controls wrap onto multiple lines, never hidden behind a toggle.
3. No filter control is ever hidden behind a collapsed/closed panel at any viewport size.
4. Filter bar's RTL control order is consistent between desktop and mobile (only wrapping
   changes).
5. Apply button stays visible/reachable at every viewport size.

**Top bar** (fixed control set, shrink/wrap not overflow-menu):
6. Desktop top bar shows all 5 control groups (logo, gear, refresh, Σ, expand-all/collapse-all)
   simultaneously in consistent RTL order.
7. Mobile top bar keeps all controls visible (shrunk/wrapped), never an overflow "..." menu.
8. No top-bar control disappears entirely at any tested viewport width.
9. Mobile icon/touch targets remain large enough to tap accurately.

**Cross-cutting**:
10. Live browser resize (desktop→narrow) reflows correctly with no leftover artifacts.
11. RTL is consistent everywhere in this chrome — no accidental LTR-ordered element.

### Component 0b — General Responsiveness (6 tests)

Cross-cutting Layout concern — not mobile-specific: adapts to orientation, resolution, font
scaling, and available view area, both desktop and mobile.
1. Rotating a mobile device (portrait↔landscape) reflows correctly live.
2. Increasing browser zoom/OS font-size scaling doesn't overflow containers or break control
   usability.
3. Progressively resizing a desktop browser window narrower reflows smoothly through
   intermediate widths, not just jumping between two fixed breakpoints.
4. Reducing available viewport area (DevTools open, split-screen tablet) reflows correctly.
5. An extremely narrow width doesn't crash the layout (best-effort, not a guarantee).
6. An extremely wide desktop monitor doesn't leave the layout broken or absurdly stretched.

---

## Component 1 — Session & Auth (34 tests)

Token in `localStorage` (survives tab/browser close); expiry is 168h since **last activity**.

**1.1 Wrong/correct password** (10):
1. Empty submission shows a validation error.
2. Wrong password shows a visible error message.
3. Error clears on a new attempt.
4. Correct password reveals the app (list, top bar, filters).
5. No stale error lingers after a successful login.
6. Repeated wrong attempts each independently error (no lockout — rate-limiting out of scope).
7. Password field is masked, not plaintext.
8. Garbage/special-character input doesn't crash the request.
9. Pasting into the password field works normally.
10. Leading/trailing whitespace is compared **literally, no trimming** (2026-09-05 decision) —
    a stray space causes a genuine mismatch, not a silently-corrected match.

**1.7 Missing/corrupted password file at startup** (1, 2026-09-05 decision): the backend still
starts when `password.hash` is missing or unreadable at boot — every login attempt simply fails
until the file is fixed, rather than the whole app refusing to start over just the auth gate.

**1.2 Reload & tab-close persistence** (4):
1. Reload after login shows the app directly, no re-prompt.
2. Reload immediately post-login has no token-save race condition.
3. Closing and reopening the tab/browser keeps the session (`localStorage`).
4. Auth state isn't incorrectly re-fetched/reset on reload.

**1.3 Concurrent sessions** (6):
1. Login A succeeds.
2. Login B (same password, different device/tab) succeeds independently.
3. A still works with both active.
4. B still works with both active.
5. Logging out A doesn't affect B.
6. A third/fourth concurrent login also succeeds (no artificial cap).

**1.4 Login audit logging** (6, backend-only, no Playwright case — Story 1A):
1. A successful login writes one log line with timestamp + outcome.
2. A failed login writes one log line with timestamp + outcome.
3. The log line never contains the plaintext password.
4. The log line never contains the password hash.
5. Rapid repeated failures each get their own separate line (not deduplicated).
6. Log line format matches the app's standard logging format.

**1.5 Session expiry** (3, **manual-only, never automated**):
1. After 168h of zero activity, the next request is rejected back to the password screen.
2. Activity within the window resets the clock (using the app at hour 167 keeps it alive past
   the original 168h mark).
3. No stale data renders before the redirect on expiry.

**1.6 Post-logout URL guard** (4, 1 forward-looking):
1. A copied post-login URL, pasted fresh (new page, not reload) after logout, shows the
   password screen — zero ledger data ever rendered.
2. Same in a private/incognito window — confirms no bypass via a URL-embedded token.
3. No cached network response renders stale data before the guard resolves.
4. [Forward-looking, not testable in v1] the same guard applies to any future deep-linked
   per-event URL, once such URLs exist.

---

## Component 2 — Initial Load (21 tests)

**2.1 Default load window** (7):
1. Only events within the past 7 days are shown.
2. An event dated exactly 7 days ago (boundary) is included — inclusive.
3. An event dated 8 days ago is excluded.
4. Sort is newest-first (dates non-increasing top to bottom) by default.
5. Date computation uses Israel local time, not UTC.
6. Total count matches the fixture exactly (no off-by-one).
7. Two events on the identical date break ties by `event_id` descending (default newest-first
   direction).

**2.2 Empty result** (3):
1. Zero events in the window shows an explicit empty state.
2. No stuck loading spinner.
3. No unindicated blank area. (Same generic empty state covers both "nothing in window" and
   "filtered to zero" — no distinct wording required.)

**2.3 Changing days-back reloads immediately** (5):
1. Increasing the value immediately reloads wider, no separate refresh press needed.
2. Decreasing immediately reloads narrower.
3. Newly-revealed events sort correctly into the existing list (respecting the tiebreaker), not
   just appended at the end.
4. Setting the same value again is a safe no-op.
5. Rapid consecutive changes don't race (stale-response guard).

**2.4 Refresh button** (5, +1 addition):
1. Re-fetches from backend, not a re-render of cached data.
2. New server-side data appears after refresh.
3. Hypothetically-removed data disappears after refresh.
4. Visual feedback while refreshing.
5. Refresh re-applies whatever on-screen filters were already active, rather than resetting to
   the full loaded set.

---

## Component 3 — Filters (~85 tests)

Mental model: **all filters are always active** — an unset/empty filter passes everything
through; there is no "clear filters" button; the date range can never be fully unset.

**3.1 Apply gating** (10):
1. Selecting an event type without pressing Apply leaves the list unchanged.
2. Typing in the client-name field without pressing Apply leaves the list unchanged.
3. Typing in the global search field without pressing Apply leaves the list unchanged.
4. Changing the date range without pressing Apply leaves the list unchanged.
5. Selecting an event subtype without pressing Apply leaves the list unchanged.
6. Pressing Enter inside the client-name field does not apply.
7. Pressing Enter inside the global search field does not apply.
8. Setting multiple filters at once, none applied yet, still shows the unfiltered list.
9. Pressing Apply with nothing actually changed is a safe no-op.
10. Repeated identical Applies don't duplicate/corrupt the result.

**3.2 Event type filter** (7):
1. Selecting one event type shows only rows of that type.
2. Selecting two types shows rows matching either (OR).
3. Selecting all types equals no type filter at all.
4. Deselecting one of several narrows correctly on the next Apply.
5. Deselecting all returns to passthrough.
6. The dropdown lists exactly the distinct `source_type` values present in the full loaded
window — **computed from the full unfiltered load, not shrinking as other filters narrow the
visible rows** (2026-09-05 decision — stable, predictable option list).
7. A selected type with zero matches shows the Component-2-style empty state, not an error.

**3.3 Event subtype filter (dynamic scoping)** (8):
1. With no event type selected, every subtype is selectable, none grayed out.
2. Selecting one event type grays out subtypes invalid for it.
3. Selecting a second type un-grays subtypes valid for either.
4. Deselecting all types returns every subtype to selectable.
5. A previously-selected subtype that becomes invalid after the type selection changes is
   **auto-deselected** (2026-09-05 decision) — removed from the applied filter state.
6. Grayed-out options are genuinely unclickable.
7. Type + a valid subtype together AND-narrow correctly.
8. The subtype dropdown's enabled/grayed state updates live without reopening.

**3.4 Client-name typeahead + fuzzy filter** (22):
*Trigger*: 1. 2+ characters fires the suggestion search after a **~300ms debounce**
(2026-09-05 decision — waits for a pause in typing, not fired per keystroke). 2. 1 character
does not fire it. 3. Clearing the field closes the dropdown. 4. Additional characters re-query
and narrow further (each still debounced). 5. Matching is prefix-only — a mid-string match must
not appear as a suggestion. 6. Several keystrokes inside the debounce window fire only one
request for the final text, not one per keystroke.
*Dropdown interaction*: 7. Clicking a suggestion fills the field and closes the dropdown.
8. Typing again after picking reopens a fresh, re-narrowed dropdown. 9. Ignoring the dropdown
and typing freely is allowed. 10. Clicking outside closes the dropdown without changing the
text. 11. Escape closes the dropdown without changing the text. 12. Arrow keys move a highlight
through suggestions. 13. Enter while a suggestion is highlighted selects it into the field but
does NOT trigger Apply. 14. Zero matches shows an explicit "no matches" state.
*Reliability*: 15. A slow, stale suggestion response arriving after a newer one must not
overwrite the newer results. 16. A failed/network-error suggestion request shows a graceful
state, field remains usable. 17. Whitespace-only input is treated as empty/passthrough.
*Apply-time filtering*: 18. A typo still fuzzy-matches the intended client. 19. Gibberish
returns zero rows cleanly. 20. Apply immediately after picking a suggestion filters correctly.
21. Clearing to empty then Apply applies no restriction. 22. Editing another filter doesn't
clear/corrupt client-name text already typed.

**3.5 Global free-text search** (9):
1. Matches in `description`. 2. Matches in `amount` (numeric-as-text). 3. Matches in a date
field. 4. Matches in a field not shown anywhere in the UI (e.g. `bank_account`). 5. A typo
still fuzzy-matches. 6. No-match returns zero cleanly. 7. A broad/common-term match doesn't
error or hang. 8. Combines as AND with another filter. 9. Empty field is passthrough.

**3.6 Date range = load window** (8):
1. Initial range exactly equals the load window. 2. "From" picker clamped at the window start.
3. "To" picker clamped at today/window end. 4. Narrowing inward filters correctly. 5. An
invalid to-before-from range is prevented/auto-corrected. 6. Widening "days back" in settings
immediately widens this filter's selectable bounds. 7. Narrowing "days back" clamps an
out-of-range current selection back into bounds. 8. Narrowing this filter never triggers a new
backend load.

**3.7 Combined filters (AND across, OR within)** (6):
1. Type(OR)+client-name AND. 2. Triple combination (type+subtype+client-name). 3. Date-range-
narrowed+type. 4. All five categories set to match exactly one known row. 5. All five set so no
row satisfies all → zero rows. 6. Removing one category correctly widens the result.

**3.8 No clear button, manual reset** (4):
1. Full manual reset across all filters restores the full loaded set. 2. Partial reset leaves
remaining filters still active. 3. No "clear all" control exists anywhere (absence check).
4. Resetting a multi-select per-value/chip works the same as reopening and unchecking each one.

---

## Component 4 — Row Expand (single) (~60 tests)

Right panel uses the field manifest (`contracts/field-manifests.md`). Left panel is a
WhatsApp-style chat (human right / bot left), fixed height + internal scroll (see Component 6).
Lookback boundary is **inclusive**.

**4.1 Pressing "+" opens both panels correctly** (8):
1. Right panel shows the correct event's data. 2. Left panel shows the correct session/messages
for that event. 3. Row expands in place (no navigation/modal). 4. Rows below visibly shift
down. 5. Toggle icon changes state. 6. Right panel sits right of left panel on desktop.
7. Identical behavior regardless of which row. 8. No flash of wrong/blank content before real
data appears.

**4.2 Collapsing back** (5):
1. Toggle again closes both panels. 2. Row/icon revert to collapsed. 3. Rows below shift back
up. 4. Collapsing one row doesn't affect another independently-expanded row. 5. Re-expanding
shows fresh correct data.

**4.3 Right panel field manifest correctness** (23, per `contracts/field-manifests.md`):
*הסכם*: 1. Common fields always shown. 2. Manifest fields shown when populated. 3. Same fields
absent when empty. 4. reference/reference_hint ALWAYS shown when subtype ≠ "יצירה". 5. Same
fields IF-EXISTS-only when subtype = "יצירה". 6. `event_id`/`agreement_id`/`component_id`
never appear.
*בנק*: 7. Subtype "הפקדה" → bank fields + vat_status shown even null. 8. Other subtypes → same
fields IF-EXISTS only. 9. payer_name always IF-EXISTS. 10. split fields never shown, any
subtype/value.
*חשבונית*: 11. display_number always shown. 12. status_label always shown. 13. vat_status
always shown. 14. status/status_code never shown regardless of value. 15. payment_method
IF-EXISTS. 16. Subtype 320/400 + "העברה בנקאית" → bank fields shown even empty. 17. Subtype
320/400 + other payment method → bank fields completely absent. 18. Subtype 305/300 → bank
fields completely absent regardless. 19. Subtype 330 → reference/reference_hint shown even
empty. 20. Other subtypes → IF-EXISTS only.
*Cross-cutting*: 21. Hebrew labels render correctly (spot-check). 22. Internal/bookkeeping
fields never appear for any type.
*Defensive*: 23. A record with an unrecognized `source_type` (outside הסכם/בנק/חשבונית) shows an
explicit "unrecognized event type" / unsupported message in the right panel instead of any
fields (2026-09-05 decision — loudly visible, not a silent generic fallback).

**4.4/4.5 Left panel — WhatsApp-style chat** (17):
1. User messages render on the right. 2. Assistant messages render on the left. 3. Chronological
order. 4. Only messages within the lookback window shown. 5. The anchor message is always
included. 6. An image attachment renders as a thumbnail, not inline full-size. 7. Clicking a
thumbnail opens a larger view. 8. The larger view has an "OK" to dismiss. 9. Dismissing returns
to the chat view without leaving the expanded row. 10. A text-only message shows just its
bubble, no broken-image placeholder. 11. Sender name renders correctly. 12. Timestamp shown/
orderable. 13. Multiple images each have independent thumbnail/lightbox behavior. 14. A message
just outside the window is excluded. 15. A message exactly at the boundary is included
(inclusive). 16. A video or audio message shows a generic, non-playable placeholder in v1
(2026-09-05 decision — video/audio are explicitly out of scope for playback this feature).
17. A document attachment (PDF/DOCX) renders as a clickable thumbnail exactly like an image
(2026-09-05 decision); clicking opens the document in the same larger view, relying on the
browser's native PDF/doc rendering, dismissed with "OK" like the image lightbox.

**4.6 Graceful degradation** (5):
1. Missing/unresolvable session shows a clear "unavailable" message in the left panel. 2. Right
panel renders fully and correctly from the `LedgerEvent` itself even when the left panel fails
— the ledger detail never depends on the session being resolvable (2026-09-05 decision). 3. No crash/infinite spinner on
unresolvable context. 4. Same graceful handling when the session resolves but the specific
message doesn't. 5. Same graceful handling when a message's `image_path` points to a file no
longer on disk.

**4.7 Layout/positioning** (3):
1. Right panel positioned right of left panel on desktop (bounding-box check). 2. Both panels
sit directly below the expanded row. 3. Expanding one row doesn't visually corrupt/overlap
unrelated rows.

---

## Component 5 — Row Expand (multi / expand-all / collapse-all) (20 tests)

**Any Apply or "refresh data" collapses every expanded row.**

**5.1 Multiple independent expansions** (5):
1. Expanding row 2 doesn't close row 1. 2. Both show correct, non-bleeding data. 3. Rows below
shift down by the combined expansion height. 4. A 3rd row also stays independent. 5. Collapsing
one of several open rows doesn't affect the others.

**5.2 Collapse-all** (4):
1. Closes every expanded row regardless of count. 2. Works on a mix of individually- and
expand-all-expanded rows. 3. All return to collapsed height. 4. No-op with zero expanded.

**5.3 Expand-all** (5):
1. Opens every currently-loaded (post-filter) row, including untouched ones. 2. Already-open
rows aren't double-expanded/glitched. 3. Each shows correct data. 4. Scales to a long list (no
hardcoded cap). 5. No-op with all already expanded.

**5.4 Apply collapses everything** (3):
1. Pressing Apply (even with no real value change) collapses all expanded rows. 2. Holds
regardless of how many/how they got expanded. 3. The newly-filtered list starts fully
collapsed.

**5.5 Refresh collapses everything** (2):
1. Pressing "refresh data" collapses all expanded rows. 2. The refreshed list starts fully
collapsed.

**5.6 Reload resets expand state** (1):
1. A full page reload (not refresh/Apply) always returns the list fully collapsed, regardless of
what was expanded before the reload (2026-09-05 decision).

---

## Component 6 — Mobile Viewport Layout (14 tests)

Chat/left panel is a **fixed height with its own internal scroll** on both desktop and mobile.
Mobile/desktop breakpoint is **768px viewport width** (2026-09-05 decision), standard responsive
CSS, live-reactive to window resize (no reload needed to cross the breakpoint).

**6.1 Single expanded row stacks vertically** (2):
1. Right (detail) panel appears above the left (chat) panel on mobile. 2. Both panels are
full/near-full width.

**6.2 Multiple expanded rows on mobile** (2):
1. Each independently expanded row shows its own correctly-stacked pair of panels. 2. Stacking
applies uniformly across every expansion.

**6.3 Row list at mobile width** (4):
1. Description wraps onto a second sub-row when needed. 2. The other five fields stay on the
first line under normal circumstances. 3. No row ever requires horizontal scrolling. 4. Amount
and date remain fully visible/un-truncated even under tight width.

**6.5 WhatsApp chat panel usability + fixed height** (6):
1. Chat bubbles remain legible at mobile width. 2. Tapping a thumbnail opens the larger view,
correctly sized for the smaller screen. 3. "OK" remains reachable/tappable. 4. The chat panel
occupies its fixed height on mobile, not the full remaining page height. 5. The panel has its
own internal scrollbar, independent of the outer page scroll. 6. Scrolling inside the chat
panel never scrolls the outer row list, and vice versa. (Desktop uses the same fixed-height +
internal-scroll rule — verified once, applies to both.)

---

## Component 7 — Σ Summation (18 tests)

🚨 v1 is a deliberately naive placeholder — real semantics (sign-correcting `חשבון זיכוי`,
bank/Morning payment dedup, per-client agreement-vs-payment netting) are explicit future work,
NOT tested here.

**7.1 Basic sum/count display** (4):
1. Correct total matching the sum of every visible row's `amount`. 2. Displayed count matches
events actually contributing. 3. Repeat press with nothing changed is deterministic. 4. A
single-row view shows that row's amount with count 1.

**7.2 Sum disappears on view change** (4):
1. Applying a filter change clears the previously-shown sum entirely (not stale-marked).
2. Pressing refresh also clears it entirely. 3. The sum only reappears by pressing Σ again.
4. Merely expanding/collapsing rows does NOT clear an already-shown sum.

**7.3 Excluding null/unparseable amounts** (3):
1. An event with a null amount is excluded from the sum. 2. Also excluded from the displayed
count. 3. A view where every event has a null amount shows ₪0 / count 0, not an error.

**7.4 Independence from expand/collapse state** (2):
1. Sum is identical whether computed with zero or all rows expanded. 2. Expanding/collapsing
does not itself clear or recompute the sum.

**7.5 Sign/decimal/currency correctness** (4, raw-value only):
1. A genuinely negative stored amount correctly reduces the total. 2. A view netting to a
negative raw total displays that correctly, not floored at zero. 3. Non-integer amounts sum
without visible rounding distortion. 4. Currency formatting stays consistent regardless of
sign.

**7.6 Σ disabled during refresh** (1):
1. The Σ button is disabled while a refresh is in flight (2026-09-05 decision) — cannot be
pressed mid-refresh, re-enables once the refresh completes.

---

## Component 8 — Settings (24 tests)

Same-date tiebreaker mirrors sort direction. No maximum on "days back" in v1.

**8.1 Theme switching** (5):
1. Dark theme changes colors app-wide. 2. Switching back restores light app-wide. 3. Applies
immediately, no reload. 4. An open expanded row's panels also restyle correctly. 5. A
first-visit browser with no saved theme and an OS set to dark mode still loads in **light**
(2026-09-05 decision — OS preference is not auto-followed).

**8.2 Sort order toggle** (4):
1. Oldest-first re-sorts immediately. 2. Newest-first restores original order. 3. The
tiebreaker flips direction to match. 4. The change is a client-side re-sort, no new backend
load.

**8.3 Days-back validation** (4, no max):
1. A valid value reloads immediately and persists. 2. Zero/negative input rejected/clamped.
3. Non-numeric input rejected. 4. Clearing the field falls back to a defined default.

**8.4 Lookback-minutes validation** (5):
1. A valid value (0–60) takes effect on next expansion. 2. Above-60 clamped/rejected
client-side. 3. Negative rejected. 4. Non-numeric rejected. 5. Backend independently clamps to
[0,60] regardless.

**8.5 Persistence** (2):
1. All four settings preserved exactly after reload. 2. Settings persist across tab/browser
close too.

**8.6 Settings panel open/close** (3):
1. Opening shows current values pre-filled. 2. Closing without changes leaves everything
unchanged. 3. Reopening shows consistent values.

**8.7 Logout reachable from settings** (1):
1. The logout control triggers the flow already fully tested in Component 1.

---

## Component 9 — Visual Regression (8 tests + 1 process rule)

Catches what no functional test can: something still *works* but visually looks wrong (broken
spacing, clashing colors, overlapping elements). A saved reference screenshot ("baseline") is
compared pixel-by-pixel against a fresh screenshot on every run.

**9.1 Collapsed list baseline** (1):
1. Desktop, default light theme, seeded fixture — matches baseline within a small
anti-aliasing tolerance.

**9.2 Expanded row baseline** (2):
1. A single expanded row (both panels, desktop) matches its baseline. 2. An expanded row whose
chat panel includes an image thumbnail matches its baseline (covers real image content).

**9.3 Mobile baselines** (2):
1. Collapsed list at mobile width matches its baseline. 2. Expanded row at mobile width
(stacked panels) matches its baseline.

**9.4 Dark theme baseline** (2):
1. Collapsed list in dark theme matches its baseline. 2. Expanded row in dark theme matches
its baseline.

**9.5 Baseline governance** (1 process rule, not an automated test):
1. A baseline image is only ever updated through a deliberate developer-run "update snapshots"
command whose new images are committed and reviewed like any other code change (2026-09-05
decision) — never auto-accepted just because a run produced a new screenshot.

---

## Grand total: ~303 individual test cases across 10 components (0–9)

## Open items

None carried forward. All gaps found during the 2026-09-05 audit pass are resolved and folded
in above: 3.3 auto-deselect; 768px mobile/desktop breakpoint (Component 6); unrecognized
`source_type` shows an explicit error (4.3.23); video/audio messages show a non-playable
placeholder in v1 (4.4/4.5.16); page reload always resets expand state (5.6); Σ button disabled
during an in-flight refresh (7.6); missing/corrupted password file starts the backend anyway,
all logins fail (1.7); password comparison is literal with no whitespace trimming (1.1.10);
client-name typeahead debounces ~300ms before firing (3.4); document attachments render/open
like images relying on browser rendering (4.4/4.5.17); type/subtype dropdown options come from
the full loaded window, not the post-filter visible set (3.2/3.3); visual-regression baselines
update only via a deliberate committed "update snapshots" step (9.5). Explicitly out of scope
for v1: torn/partial reads of denidin-app's data mid-write (ledger events are atomic single-file
writes — not tested). **This document is the full,
approved test plan gating the start of implementation** (per the standing 2026-09-05
instruction: no Phase 1–10 build work begins until this plan is approved).
