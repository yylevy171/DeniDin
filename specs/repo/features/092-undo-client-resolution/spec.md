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

**R1 — "הסר מהרשימה" button on unresolved rows.** Each row in "Names to resolve" gets a
**הסר מהרשימה** button. Pressing it removes the row from the list permanently. The removal is
persisted (e.g. `hidden_unmatched.json`), and there is no in-UI restore. No keyword is added:
`למחוק` in a note is **not** parsed. The existing note-keyword hiding in `_split_unmatched`
(`להסיר`, `לא לקוחה`, `אוחד`, …) is left as-is for existing data.

**R2 — Per-event rows for `Unknown` only.** Events whose raw client is `Unknown` (no
`client_name` or `payer_name`, or explicitly mapped to `"Unknown"`) are no longer aggregated into
one row. Each such event gets its own row in the resolution table, showing its date, type, amount
and description, and keyed by its ledger `event_id`. Named aliases keep today's behavior: one row
per raw name, mapped as a whole.

**R3 — Map an `Unknown` event to a client.** Each `Unknown` event row uses the same client
dropdown as the named rows, and maps that single event.
- Persisted separately from `client_mapping.json` (e.g. `event_mapping.json`:
  `{event_id: official_name}`).
- A per-event mapping wins over the `Unknown` fallback.
- A mapped event counts toward that client's totals and appears in its events list, exactly as a
  name-mapped event would.
- This is **not** a generic per-event mapping capability. Named aliases are not expandable or
  mappable per event.

**R4 — Undo name mappings (original 092 scope).** Each resolved alias listed on a client row
(`raw_names`) has an **unlink** control. Unlinking:
- removes the entry from `client_mapping.json`;
- puts the raw name back in "Names to resolve" exactly as it was before it was resolved,
  including its note;
- reverts the client's totals.

**R4a — Undo `Unknown` event mappings: SHOULD, droppable.** Unlinking a per-event mapping from
the client row's event list. Deleting the backend entry is trivial; the cost is in the UI, which
has to tell which events on a client row came from a per-event mapping. Decide at plan time. If
it's dropped, it's an accepted gap, not a bug.

**R5 — ESC closes the client dropdown.** While the `ClientPicker` dropdown is open, pressing
Escape closes it without choosing anything.

### B. Explicit per-line status (replaces comment-keyword routing; includes bugfix-068)

**R6 — Persisted line status.** Each client row gets an explicit, persisted override status
(e.g. `client_status.json`: `{official_name: "closed" | "check" | "active"}`). No entry means
the row's section is computed from the numbers, as today. The routing priority stays as
`_row_status` has it now: `check` > `active` > `closed` > `past` > computed
(`settled` / `debt` / `missing_agreement`).

**R7 — "לסגור" / "לפתוח" button.**
- Rows in any open section (`check`, `active`, `debt`, `missing_agreement`) get a
  green-shaded **לסגור** button. It sets status `closed`, and the row moves to the green
  section.
- Rows in green (`settled`) get a gray-shaded **לפתוח** button. It clears the closed status,
  and the row is re-routed like this:
  - agreed == paid (and > 0) → **לקוחות פעילים** (light blue) — sets status `active`, since
    otherwise the numbers would route it straight back to green.
  - otherwise → the computed section: red (`debt`) or yellow (`missing_agreement`).
- **Closing never changes any amount** (bugfix-068). `display_agreed` and `display_paid` stay
  the real values, and no `*_inferred` YELLOW amount markers are set by closing.

**R8 — "לבדוק" button (blue).** On every non-gray line. Sets status `check`, and the row moves to the
blue "לבדוק" section.

**R9 — "לקוח פעיל" button (light blue).** On every non-gray line. Sets status `active`, and the row moves
to the light-blue "לקוחות פעילים" section.

**Gray (`past`) rows get no buttons at all.** They'll be handled by an upcoming "inactive"
marking. A button whose target is the row's current section is shown disabled or hidden, not as a no-op.
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

## Clarifications (2026-10-03)

- **"Comments become text only" covers only the three keywords the buttons replace**
  (`לסגור`/`אפשר לסגור`, `לבדוק`, `לקוח פעיל`/`לקוחה פעילה`). Delete, merge, `הסכם <amount>`,
  `סה״כ הסכמים`, `להוריד` and the `לא ברור`/`חסר` amount markers keep working from comments
  unchanged. Note that `לבדוק` stops routing the row to the check section (R10), but it still
  counts as an "unclear" flag for the YELLOW amount markers in `_apply_comment_rules`. That's
  amount colouring, not routing, so it's left as-is.
- **Resolve-list removal is a button, not a keyword.** No `למחוק` fallback (R1).
- **Gray rows: no buttons.** They'll be marked inactive in a later feature.
- **Per-event mapping is for `Unknown` only** (R2/R3). Undoing it is optional (R4a).

## User Acceptance Scenarios (draft — awaiting approval)

1. **Close without faking numbers.** A client agreed ₪10,000 and paid ₪2,000 (red). The user
   clicks **לסגור**. The row moves to green and still shows Agreed ₪10,000, Paid ₪2,000.
   **לפתוח** sends it back to red.
2. **Reopen a fully paid client.** A green row with agreed == paid. The user clicks **לפתוח**.
   It moves to **לקוחות פעילים**.
3. **Check / active buttons.** Clicking **לבדוק** on a row moves it to the blue section.
   Clicking **לקוח פעיל** moves it to light blue. Typing `לבדוק` or `לסגור` in that row's
   comment afterward doesn't change its section.
4. **Gray rows are inert.** A `past` row shows none of the four buttons.
5. **Migration preserves state.** After deploy, every row that was in `check` / `active` /
   closed-green because of its comment is in the same section, and its comment text is
   unchanged.
6. **Unknown split + per-event mapping.** Three no-name events (₪500, ₪1,200, ₪3,000) appear as
   three separate rows. The user maps the first two to different clients. Each client's totals
   grow by exactly that event's amount. The third stays unresolved.
7. **Undo a name mapping.** The user maps "Yisrael I" to "Israel Israeli", then unlinks it from
   Israel Israeli's row. The alias disappears from the row, the totals revert, and "Yisrael I" is
   back in "Names to resolve" with its note.
8. **Remove from resolve list.** The user clicks **הסר מהרשימה** on an unmatched name. It
   disappears and stays gone after a refresh.
9. **ESC.** With the client dropdown open, Escape closes it and nothing is mapped.
