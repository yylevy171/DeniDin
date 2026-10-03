# Feature 092: Clients Tab — Resolution Corrections & Explicit Line Status

**Status**: In Progress  
**Category**: Capability  
**App**: `apps/webapp` (backend `clients_reader.py`/`server.py`, frontend `ClientsView.tsx`)  
**Absorbs**: bugfix-068 ("לסגור" comment corrupting agreement totals) — that bugfix's file is now a
pointer to this spec; its fix ships here (R5–R7, R10).

## Issue

The Clients tab (Feature 087) drives almost all of its state from two free-text fields:

- **Client-row comments** (`client_comments.json`) are parsed for Hebrew keywords
  (`לסגור`, `לבדוק`, `לקוח פעיל`, `למחוק`, `לאחד`, `הסכם <amount>`, `להוריד`, …) that change the
  row's section and, in the `לסגור` case, **overwrite its numbers**: `_apply_status_directives`
  sets `manual_agreement_amount = invoices_net = max(agreed, paid)` so the row lands green. That
  fakes the firm's financial data (bugfix-068).
- **Resolution-table notes** (`mapping_notes.json`) are parsed for a different keyword list to
  hide unmatched names.

Separately, the "Names to resolve" table has three gaps:

1. A resolution (`client_mapping.json`) can't be undone from the UI. A wrong mapping can only be
   fixed by hand-editing the JSON.
2. Every event with no client name collapses into one `"Unknown"` row. Those events belong to
   *different* clients, so a single name→client mapping can't resolve them.
3. `למחוק` in a resolution note does nothing, unlike in client comments.

## Business Value

- Financial integrity: the agreed and paid amounts shown are always the real ones.
- Users can fix their own mapping mistakes and classify lines with one click, with no keyword
  memorization and no hand-editing of data files.

## Requirements

### A. Names-to-resolve table

**R1 — `למחוק` hides an unmatched name.** If a resolution-table note contains `למחוק`, that raw
name is removed from the "Names to resolve" list, like the existing `להסיר` and similar terms in
`_split_unmatched`. Clearing the note brings it back.

**R2 — Per-event rows for `Unknown`.** Events whose raw client is `Unknown` (no `client_name`
or `payer_name`, or explicitly mapped to `"Unknown"`) are no longer aggregated into one row.
Each such event gets its own row in the resolution table, showing its date, type, amount and
description, and keyed by its ledger `event_id`.

**R3 — Map individual events.** Any unmatched row, whether a named alias or an `Unknown` event,
can be expanded to list its events. Each event can be mapped to an official client on its own.
- Precedence: **per-event mapping > name mapping > exact/fuzzy match**.
- Persisted separately from `client_mapping.json` (e.g. `event_mapping.json`:
  `{event_id: official_name}`).
- A per-event-mapped event counts toward that client's totals and appears in its events list,
  exactly as a name-mapped event would.

**R4 — Undo / unlink (original 092 scope).**
- Each resolved alias listed on a client row (`raw_names`) has an "unlink" control.
- Each per-event mapping is unlinkable from the client row's event list.
- Unlinking removes the entry from `client_mapping.json` / `event_mapping.json`. The name (or
  `Unknown` event) reappears in "Names to resolve" exactly as it was before it was resolved,
  including its note.

**R5 — ESC closes the client dropdown.** While the `ClientPicker` dropdown is open, pressing
Escape closes it without choosing anything and without clearing the saved state.

### B. Explicit per-line status (replaces comment-keyword routing; includes bugfix-068)

**R6 — Persisted line status.** Each client row gets an explicit, persisted override status
(e.g. `client_status.json`: `{official_name: "closed" | "check" | "active"}`). No entry means
the row's section is computed from the numbers, as today. The routing priority stays as
`_row_status` has it now: `check` > `active` > `closed` > `past` > computed
(`settled` / `debt` / `missing_agreement`).

**R7 — "לסגור" / "לפתוח" button (on every line).**
- Rows in any non-closed section (`check`, `active`, `debt`, `missing_agreement`) get a
  green-shaded **לסגור** button. It sets status `closed`, and the row moves to the green
  section.
- Rows in green (`settled`) or gray (`past`) get a gray-shaded **לפתוח** button. It clears the
  closed status, and the row is re-routed like this:
  - agreed == paid (and > 0) → **לקוחות פעילים** (light blue) — sets status `active`, since
    otherwise the numbers would route it straight back to green.
  - otherwise → the computed section: red (`debt`) or yellow (`missing_agreement`).
- **Closing never changes any amount** (bugfix-068). `display_agreed` and `display_paid` stay
  the real values, and no `*_inferred` YELLOW amount markers are set by closing.

**R8 — "לבדוק" button (blue).** On every line. Sets status `check`, and the row moves to the
blue "לבדוק" section.

**R9 — "לקוח פעיל" button (light blue).** On every line. Sets status `active`, and the row moves
to the light-blue "לקוחות פעילים" section.

A button whose target is the row's current section is shown disabled or hidden, not as a no-op.
One status per line: pressing a button replaces any previous override.

**R10 — Comments become text only.** Once R6–R9 ship, client-row comments are free text and are
**not parsed** for `לסגור`, `לבדוק`, or `לקוח פעיל`/`לקוחה פעילה`. (See OQ1 on the other
keywords.)

**R11 — Preserve current state (one-time migration).**
- On first run, every client whose comment *today* triggers `check`, `active`, or the
  close/settled routing gets the matching explicit status written to `client_status.json`.
  Precedence follows the current code: `check` beats close.
- Comment text is left untouched.
- The migration is idempotent and runs once: it never overwrites an existing status entry.
- After migration, every row sits in the same section it was in before the deploy. The one
  intended difference: rows closed via `לסגור` now show their **real** agreed and paid amounts
  instead of the inflated ones (that's the bugfix).

## Out of Scope

- Editing agreement amounts from the UI (Feature 089).
- Changes to the Events tab.
- Any `denidin-app` or `morning-mcp-app` change. The ledger itself is read-only here; all new
  state lives in the webapp's `clients_data_root` JSON files.

## Open Questions (clarify before plan)

- **OQ1 — Scope of "comments become text only".** Comments also drive `למחוק`/`להסיר` (delete),
  `לאחד`/`אוחד` (merge), `הסכם <amount>` / `סה״כ הסכמים` (manual agreement amount, which also
  feeds `latest_activity`), and `להוריד` (dedupe deposits). None of these has a button.
  - **Recommendation:** in this feature, stop parsing only the three keywords that now have
    buttons. Leave the rest as-is, and track their button/UI replacement as a follow-up (Feature
    089 already covers agreement edits).
  - Turning them all off now would silently change real numbers on existing rows.
- **OQ2 — R1 vs R10.** `למחוק` in a resolution-table note is new keyword parsing, which runs the
  opposite way to R10. Is a keyword acceptable there, or should it also be a button
  ("הסר מהרשימה") per unmatched row? **Recommendation:** a button, and keep `למחוק` working as
  a fallback, for consistency.
- **OQ3 — "לפתוח" on a gray (`past`) row.** A past row is gray because its latest activity is
  before 2025-09-01, not because of a status. Reopening it needs a status that outranks `past`.
  Confirm it follows the same rule as green: `active` if agreed == paid, otherwise
  `debt`/`missing_agreement`, regardless of date.

## User Acceptance Scenarios (draft — awaiting approval)

1. **Close without faking numbers.** A client agreed ₪10,000 and paid ₪2,000 (red). The user
   clicks **לסגור**. The row moves to green and still shows Agreed ₪10,000, Paid ₪2,000.
   **לפתוח** sends it back to red.
2. **Reopen a fully paid client.** A green row with agreed == paid. The user clicks **לפתוח**.
   It moves to **לקוחות פעילים**.
3. **Check / active buttons.** Clicking **לבדוק** on any row moves it to the blue section.
   Clicking **לקוח פעיל** moves it to light blue. Typing `לבדוק` in that row's comment afterward
   changes nothing.
4. **Migration preserves state.** After deploy, every row that was in `check` / `active` /
   closed-green because of its comment is in the same section, and its comment text is
   unchanged.
5. **Unknown split + per-event mapping.** Three no-name events (₪500, ₪1,200, ₪3,000) appear as
   three separate rows. The user maps the first two to different clients. Each client's totals
   grow by exactly that event's amount. The third stays unresolved.
6. **Undo.** The user maps "Yisrael I" to "Israel Israeli", then unlinks it from Israel
   Israeli's row. The alias disappears from the row, the totals revert, and "Yisrael I" is back
   in "Names to resolve" with its note. The same works for a per-event mapping.
7. **Delete from resolve list.** A note of `למחוק` on an unmatched name removes it from the list.
   Clearing the note brings it back.
8. **ESC.** With the client dropdown open, Escape closes it and nothing is mapped.
