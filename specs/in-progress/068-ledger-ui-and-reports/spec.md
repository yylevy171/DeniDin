# Feature Specification: Ledger Web UI (v1 — read-only, no reports yet)

**Feature Branch**: `feature/068-ledger-ui-and-reports`
**Created**: 2026-09-04
**Status**: Draft — post speckit.plan (plan.md/research.md/data-model.md/contracts/quickstart.md
written), post speckit.analyze, pre speckit.tasks

## Scope note (2026-09-04)

This spec was originally opened as "UI and reports based on the ledger" (see the placeholder
notes below, kept for history). Scope for this pass is **UI only** — reports are explicitly
deferred to a later feature. Everything below describes the read-only ledger web UI.

## Input

User description (2026-09-04 conversation): a standalone, read-only webapp — a third app
alongside `denidin-app` and `morning-mcp-app`, under `apps/webapp/` — that lets a human browse
`LedgerEvent` records visually: a filterable, scrollable list, expandable rows showing full
event detail plus the originating WhatsApp image/conversation, and a running-total (Σ) button
over the current filtered view.

## User Experience

- A human opens a web page (desktop or mobile browser — responsive, not two separate builds).
- **Access gate**: on first load, a password entry screen (no username, no accounts). The
  backend stores a single hashed password in a file (salt: fixed literal `"denidin-pw"`,
  hash algorithm TBD in `plan.md`/`research.md` — e.g. `sha256(salt + password)` at minimum,
  open to a stronger KDF if `plan.md` finds one warranted); a correct password issues a session
  token the frontend holds in **`localStorage`** (survives tab/browser close — 2026-09-05
  decision; only explicit logout or the inactivity expiry below end a session) and sends on
  every BFF call. A
  "logout" action (in settings) clears that token client-side and returns to the password
  screen. This is a single shared password, not per-user login — matches "no login" in spirit
  (no accounts/roles) while gating access to real financial data. **Sessions expire after 1
  week (168 hours) of inactivity** (server-configurable — a login issued today stops working
  after that long with no activity, requiring the password again; verified manually, not by an
  automated test, per explicit user decision — see `research.md` §6a); multiple
  concurrent sessions/devices remain allowed (a new login does not kick out others), since
  there's no per-user identity to distinguish "whose" session should win. **Every login attempt
  (success or failure) is logged** (timestamp + outcome) to the backend's log file — no new UI,
  but gives the operator a way to notice unexpected access after the fact, given the shared
  password has no per-user audit trail otherwise. (2026-09-05, resolved after the user asked
  what a single successful login actually grants — see `research.md` §6a for the full
  discussion.) **Every URL/route the app serves post-login is auth-guarded** (user-requested,
  2026-09-05): navigating directly to any such URL without a valid, non-expired session — e.g.
  a copied link pasted fresh after logout — must show the password screen, never any ledger
  data, even momentarily. This holds at both layers: the backend rejects the request outright,
  and the frontend never renders protected content before that check resolves.
- Top bar: logo (top-right, RTL), settings gear (webapp settings), a refresh-data button, and a
  Σ (sigma) button that sums the current filtered view's amounts (see "Summation" below). Also
  an "expand all" / "collapse all" control for the row list (see below). **Layout (2026-09-05)**:
  all top-bar controls stay visible at every viewport size, in the same RTL order — on mobile
  they shrink/wrap rather than collapsing into an overflow menu.
- Above the list: filters — date range (from/to, date pickers), event type (multi-select
  dropdown, distinct `source_type` values), event subtype (multi-select dropdown, distinct
  `event_subtype` values, separate from event type), client name (typeahead + fuzzy free text),
  and a global fuzzy free-text search across all fields (every field treated as text for this
  purpose, including numeric/date fields). All filters are always visible; nothing re-filters
  until the user presses **Apply** — pressing Enter inside a text field does **not** trigger
  Apply. There is no "clear filters" button and the date range cannot be unset — the correct
  mental model is **all filters are always active**; an empty text field or an empty
  multi-select simply passes everything through (no restriction), and resetting a filter means
  manually unsetting/deselecting it, then pressing Apply. Filters combine with **AND** across
  categories; within a single multi-select (event type, event subtype), multiple selected
  values combine with **OR** (matches any of them).
  - **Event type / event subtype dependency**: subtype options are dynamically scoped by
    the currently-selected event type(s) — a subtype invalid for none of the selected types is
    shown **grayed out** (visible but unselectable), never hidden outright. With no event type
    selected, every subtype is selectable (passthrough).
  - **Client name**: an autocomplete field — typing 2+ characters triggers a backend prefix
    search over every client name that has ever appeared in the ledger (full history, not just
    the loaded window), showing matches in a dropdown; the user may pick one or keep typing
    freely. A short debounce (~300ms, 2026-09-05 decision) delays the search until typing
    pauses, avoiding a request per keystroke during fast typing. Whatever text ends up in the field (typed or picked) is used, on Apply, as a fuzzy
    filter against the loaded events' `client_name` field — it is not required to be an exact
    pick from the dropdown.
  - **Date range**: unlike the other filters, this one is never "empty" — it always holds a
    real from/to range, and it **starts as, and represents, the current load window** (defaults
    to whatever "days back" resolves to, e.g. the past 7 days); the on-screen filter's outer
    bounds track the load window (widening "days back" in settings widens what this filter can
    select; the filter itself never causes more data to load — only settings does that).
    The user can narrow this range further within the loaded window, but cannot widen it beyond
    what's loaded.
  - **Filter bar layout (2026-09-05)**: always visible, a single row on desktop that wraps onto
    multiple lines at narrow widths — never a collapsible/toggled panel.
- Main panel: a scrollable (effectively unbounded — no client-side page size limit once loaded)
  list of ledger events, one row each, RTL, showing (right to left): date, event type, event
  subtype, client name, amount, description. Sort order is newest-first by default,
  configurable in settings; two events sharing the identical date break ties by `event_id`,
  **descending under newest-first / ascending under oldest-first** — the tiebreak direction
  mirrors whichever primary sort direction is active (2026-09-05 decision, deterministic). **Row layout (2026-09-05)**: description may
  wrap onto a second sub-row within the row item if needed; the other five fields stay on the
  first line. No horizontal scrolling of a row is ever acceptable at any supported width. A
  firm field-removal policy for extremely narrow widths is deliberately not decided yet — a
  fallback to revisit only if it proves necessary in practice, not a rule to build against now.
- **Mobile/desktop breakpoint (2026-09-05)**: standard responsive CSS based on the browser's
  actual viewport width — below **768px** gets mobile (stacked) layout, at/above gets desktop
  (side-by-side). Not a device-type detection, purely viewport width, live-reactive to resize.
- Each row has a "+" (rightmost, RTL-leading) that expands it in place, pushing subsequent rows
  down (accordion-style, not a modal/navigation). **Multiple rows may be expanded
  simultaneously** — each expansion independently pushes rows below it further down. The top
  bar's "expand all" / "collapse all" control acts on every currently-loaded (post-filter) row
  at once. **Pressing Apply (any filter change) or "refresh data" collapses every expanded row**
  (2026-09-05 decision) — expand state never survives either action, avoiding stale panels
  referencing data that may no longer match what's visible. **A full page reload also resets
  every row to collapsed** (2026-09-05 decision) — expand state is never persisted. Expanded row shows two panels — side-by-side on wide viewports, **stacked
  vertically** on narrow (mobile) viewports:
  - **Right panel** (top when stacked): full ledger event detail — **not every raw field**,
    but a per-event-type curated set (some ALWAYS shown even if empty, some only IF-EXISTS,
    some NEVER shown at all) per the field manifest in `contracts/field-manifests.md`, each
    field with a real Hebrew label. Sourced entirely from the `LedgerEvent` record itself.
    Internal/bookkeeping fields (`event_id`, `agreement_id`, `component_id`, `session_id`,
    `message_id`, `captured_at`, `schema_version`) are never shown.
  - **Left panel** (bottom when stacked): a **WhatsApp-style chat view** — the human's ("user"
    role) messages on the right, the bot's ("assistant" role) replies on the left (2026-09-05
    decision), image attachments shown as clickable thumbnails that open a larger view
    dismissible with an "OK" (closing back to the chat view, not navigating away) — resolved
    via the event's `session_id`/`message_id` pointers into `SessionManager`'s stored
    session/media data (real files under `data/sessions/` and media storage — never re-derived
    or guessed). Shows the linked source message plus every message in that same session in
    the **preceding N minutes** (default 10, configurable in settings, capped at 60) —
    i.e. a fixed time-lookback window ending at the linked message, not a fixed message count
    or a full-session dump. **Video/audio messages are out of scope for v1** (2026-09-05
decision) — shown as a generic media-attachment placeholder or their extracted text, not a
playable control, even though denidin-app's media pipeline handles those message types
elsewhere; only images get the thumbnail/lightbox treatment. If the linked message carries no
media, this panel renders the
    message text itself (and the other in-window messages) rather than an image.
    **Panel height (2026-09-05)**: the left/chat panel is a **fixed height with its own
    internal scroll** — a constant, the same on desktop and mobile alike, the same across every
    row expansion (exact value TBD in implementation) — never growing to fit however much
    conversation is in the window, and never sharing scroll with the outer row list.
- Themes: light and dark, both built on a white/green/black palette (anchoring the DeniDin
  brand); theme choice is a settings item, switchable at any time, persisted per-browser.
  **First visit with no saved setting defaults to light** (2026-09-05 decision) — the OS/browser
  dark-mode preference is not auto-followed; the user opts into dark manually and it then
  persists.
- Settings (gear) contents for v1: color theme, logout, list sort order (newest-first /
  oldest-first), default load window in days (see "Initial load" below), and the WhatsApp
  left-panel lookback window in minutes (default 10, max 60). No date-format setting — always
  `DD/MM/YYYY`. No page-size setting — the list itself is unbounded/infinite-scroll; only the
  *initial load filter* (days back) is configurable.
- Read-only: no create/edit/delete of anything, anywhere in this feature.

## Initial Load

On page load, on every "refresh data" press, and **immediately whenever "days back" is changed
in settings** (no separate refresh press needed — the list reloads as soon as the setting
changes), the BFF returns only events within a trailing date window — **default the past 7
days, inclusive of the boundary day itself** (an event dated exactly 7 days ago is included; by
the row's own date field, `txn_date` where present else `event_datetime`), **configurable in
settings** as "days back to load" (no stated max — v1 only defines the default and that it's
user-configurable). This is a *load* filter,
distinct from the on-screen date-range filter above: widening the on-screen date filter beyond
the loaded window does **not** reveal more data until the user also widens "days back to load"
in settings and refreshes. `plan.md` should make this relationship explicit in the UI copy so
it isn't a silent gap (e.g. the date-range filter's own affordance should not imply it can see
further back than what's currently loaded). **Refresh preserves currently-applied on-screen
filters** (2026-09-05 decision) — pressing "refresh data" re-fetches from the backend and then
re-applies whatever filters were already active, rather than resetting to the full loaded set.

## Non-Goals (this pass)

- Reports (summaries, exports, per-client statements) — deferred.
- Editing/annotating ledger events from the UI.
- Login/user accounts/roles.
- Real-time push updates — data is loaded on page load and on explicit "refresh" press only.

## Architecture

- **New third app**: `apps/webapp/` (sibling to `apps/denidin-app/`, `apps/morning-mcp-app/`),
  fully independent per the repo's existing per-app isolation convention (own config, own
  Docker, own tests).
- **Frontend**: React Native Web (single codebase, web-only build for v1; leaves the door open
  to a native build later without a rewrite). No native mobile app ships in this feature.
- **Backend (BFF)**: Python. Reuses `denidin-app`'s existing `LedgerEventManager` (imported, not
  reimplemented) for reading/filtering events, and reuses `SessionManager`/media-storage reads
  for resolving an event's linked WhatsApp image/conversation. Read-only against
  `denidin-app`'s data — the webapp never writes to `data/`/`dev_data/`, and never touches
  `denidin-app`'s own running process (fully decoupled, per the "UI never interferes with
  DeniDin" requirement — this reuse is source-level, not a runtime dependency on a live
  `denidin-app` container).
- **Deployment**: new Docker services per environment — `webapp-backend-<env>` and
  `webapp-frontend-<env>` — bundled into the existing `docker/docker-compose.<env>.yml` files,
  following the same `env_lock`/multi-clone-override conventions as the other two apps (own
  `docker-compose.<env>.local.yml` overrides for data-volume mounts pointing at the shared
  `dev_data`/`data` root, exactly like `denidin-app`'s pattern). `dev` webapp reads
  `dev_data`; `prod` webapp reads `data` — same environment separation as the rest of the
  project, no new data root introduced.
- **Data access**: BFF loads all `LedgerEvent`s at startup/on-refresh via `LedgerEventManager`'s
  existing in-memory index (or a thin read-only wrapper around it), matching filtering behavior
  used elsewhere in the codebase rather than re-deriving fuzzy-search logic independently.
- **Versioning**: `webapp` is a real, independently-versioned app under Feature 034's machinery
  — its own `VERSION`/`CHANGELOG.md`/`RELEASES.md`, own `webapp-v<version>` git tag, and
  `scripts/cut_release.sh`/`scripts/deploy_release.sh` extended to accept `webapp` as a valid
  `<app>` argument alongside the other two. Starting version `0.5.4` (a one-time alignment with
  denidin-app's current version at cut time, not an ongoing lockstep guarantee). Own
  `run_webapp.sh`/`stop_webapp.sh dev|prod` for direct start/stop, same `env_lock.sh`
  conventions as the other two apps. See `plan.md`/`quickstart.md` for full detail.
- **Hosting/ingress**: `denidin-app`/`morning-mcp-app` are never internet-exposed, in either
  environment — only the webapp itself is reachable from outside the local network/tailnet, via
  one **Cloudflare Tunnel per environment** (`dev`, `prod`), each routed only to that
  environment's `webapp-frontend`/`webapp-backend` ports. This is a new ingress pattern for the
  repo (distinct from Tailscale, which remains the *operator's* access path to the Windows prod
  box). Domain/subdomain naming is a deployment-time detail, not fixed by this spec. See
  `research.md` §6.

## Summation (Σ button)

🚨 **v1 is a deliberately naive placeholder, not real financial math — the actual summation
semantics are explicitly TBD, tracked as a real follow-up, not solved here** (2026-09-05).
Known real-world nuances already identified, none of them implemented in v1:
- A positive-valued `חשבון זיכוי` (credit note) should actually count as *negative* in any real
  total — the raw stored `amount` sign doesn't reflect its true financial direction.
- Bank deposits and Morning-sourced accounting documents can both describe the **same
  underlying payment** — a naive sum would double-count it; real logic needs to recognize and
  count such a payment only once.
- Per-client netting: agreement amounts are the "owed" (plus) side, payments against them are
  the "received" (minus) side — a real balance calculation nets these against each other, which
  a flat sum of raw `amount` values does not do at all.

**v1's actual (naive) behavior, to be replaced later**: sums each visible (post-filter) event's
own `amount` field exactly as stored — no sign correction, no dedup, no netting, no VAT
normalization. Result is displayed next to the button (e.g. "Σ (12 events): ₪48,300"), labeled
with the event count so it's legible as a raw sum, not a financial statement. Events with a
null/unparseable amount are excluded from both the sum and the displayed count. **Σ is
on-demand, not live**: if the filtered view changes (Apply, refresh) after a sum is shown, the
previous result **disappears immediately** (2026-09-05 decision, revised) rather than staying
visible in any form — the user must press Σ again to see a number for the new view. **The Σ
button is disabled while a refresh is in flight** (2026-09-05 decision) — it cannot be pressed
until the refresh completes, avoiding a sum over an ambiguous, half-updated data set.

## Row Fields (collapsed list row, RTL right→left)

1. Date — `txn_date` where present, else `event_datetime`'s date portion.
2. Event type (`source_type`)
3. Event subtype (`event_subtype`)
4. Client name (`client_name`)
5. Amount (`amount`)
6. Description (`description`)

Same six fields for every event type in v1 (no per-type row variation) — the expanded detail
panel is where per-type richness shows up.

## Testing Methodology

Same spec-driven discipline as the rest of the repo, with one deliberate new tier: **Playwright
is this feature's real acceptance test — the direct UI equivalent of `billed`/`expensive`**
(per explicit user direction, 2026-09-04): real browser, real CSS layout engine, real data, no
mocking, run once at the end of `speckit.implement` against the actual running app. It is what
proves the things that matter to the user — a row's "+" actually opens both panels with the
right data, panels are positioned correctly, mobile viewports actually stack — not just that
components render *something*. Location: `apps/webapp/frontend/e2e/` (`npx playwright test`).
BFF unit/integration tests (pytest, real `LedgerEventManager`/`SessionManager`, no mocking of
internal components — no OpenAI/third-party calls exist in this feature so there's nothing to
mock at all) and any Jest/React Native Testing Library component tests are optional, non-gating
developer-loop scaffolding only — not part of acceptance. Full detail: `plan.md`'s Verification
section, `research.md` §4.

---

## Original placeholder notes (kept for history — reports are now out of scope for this pass)

- Broader than `052-ledger-events-csv-export` (raw CSV dump of `{data_root}/events/*.json`).
  This item implies **formatted / summarised reports** — per client, per month, per matter.
- Overlaps: `052-ledger-events-csv-export`, `051-hourly-reporting-payment-request`, `044` ledger
  querying, Feature 033 (`ledger_event_manager.py`).
- The August audit (`065-august-ledger-audit-apply`) produced ad-hoc reconciliation CSVs by
  hand — examples of the kind of output a *future* reports feature would make repeatable.

## Open questions for `speckit.clarify` — RESOLVED (2026-09-04)

All seven were resolved directly with the user before `speckit.clarify` and folded into the
body above:

1. Expand behavior: **multiple rows may be expanded simultaneously**; an expand-all/collapse-all
   control was added to the top bar as a result of this question.
2. Settings gear (v1): color theme, logout, sort order, default load window (days back,
   default 7), WhatsApp-panel lookback minutes (default 10, max 60). No date-format setting
   (always `DD/MM/YYYY`), no page-size setting (infinite scroll).
3. Event type and event subtype are **two separate** multi-select dropdown filters. All filters
   always shown, editable/clearable anytime, applied only on pressing **Apply**.
4. Left panel for a text-only source message: renders the message text (plus other in-window
   messages) rather than an image.
5. Mobile layout: the two panels **stack vertically** (right/ledger-detail panel on top, left/
   WhatsApp panel below) rather than side-by-side.
6. Access: a single shared **password** (not a raw token) gates the app; hashed
   (`salt="denidin-pw"`, exact algorithm TBD in `plan.md`) and stored server-side as a file;
   correct entry issues a client-held session token; "logout" (in settings) clears it.
7. Initial/refresh load is filtered to a **trailing window (default 7 days back)**, not "all
   events" — configurable in settings, no stated max. This is a distinct concept from the
   on-screen date-range filter (see "Initial Load" above) and must be surfaced clearly in the
   UI so widening the on-screen filter doesn't appear to silently fail to reveal older data.
8. (Follow-up, resolved same session) The left panel's "conversation before the event" window
   is a **fixed time lookback** (default 10 minutes, configurable, capped at 60 minutes) ending
   at the linked message — not a fixed message count and not a full-session dump.

No further open questions remain for `speckit.clarify` from this round; `plan.md`/`research.md`
should still resolve the smaller implementation-level TBDs flagged inline above (exact password
hash algorithm, precise Σ display copy).
