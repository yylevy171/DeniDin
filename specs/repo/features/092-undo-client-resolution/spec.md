# Feature 092: Clients Tab — Resolution Corrections & Explicit Line Status

**Status**: Done (2026-10-03) — PR #672  
**Category**: Capability  
**App**: `apps/webapp` (backend `clients_reader.py`/`server.py`, frontend `ClientsView.tsx`)  
**Absorbs**: bugfix-068 ("לסגור" comment corrupting agreement totals) — that bugfix's file is now a
pointer to this spec; its fix ships here (R5, R6, R9, R10).

## Issue

The Clients tab (Feature 087) drives almost all of its state from two free-text fields:

- **Client-row comments** (`client_comments.json`) are parsed for Hebrew keywords
  (`לסגור`, `לבדוק`, `לקוח פעיל`, `למחוק`, `לאחד`, `הסכם <amount>`, `להוריד`, …) that change the
  row's section and, in the `לסגור` case, **overwrite its numbers**: `_apply_status_directives`
  sets `manual_agreement_amount = invoices_net = max(agreed, paid)` so the row lands green. That
  fakes the firm's financial data (bugfix-068).
- **Resolution-table notes** (`mapping_notes.json`) are parsed for a different keyword list to
  hide unmatched names.

Separately, the "Names to resolve" table has these gaps:

1. A resolution (`client_mapping.json`) can't be undone from the UI. A wrong mapping can only be
   fixed by hand-editing the JSON.
2. Every event with no client name collapses into one `"Unknown"` row. Those events belong to
   *different* clients, so a single name→client mapping can't resolve them.
3. There's no way to drop a name from the list except typing one of several keywords into its note.

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

**R2 — Name each `Unknown` event after its event_id.** When aggregation finds an event with no
client name (no `client_name` or `payer_name`, so today's raw client falls back to `"Unknown"`),
that event gets its own raw name: `Unknown-<event_id>` (e.g. `Unknown-A02022604480`). Each one is
then an ordinary raw name, one event per name.
- The **existing** name-mapping, note, **הסר מהרשימה** (R1) and unlink (R3) features apply to
  it unchanged. No per-event mapping and no special UI is needed.
- The name comes straight from the event's own `event_id`, so it's deterministic and stable: no
  numbering, no registry file, no shifting when older events are backfilled. A saved mapping can
  never move to a different event.
- Events whose **named** alias is mapped to `"Unknown"` in `client_mapping.json` keep today's
  behavior: they stay under their own raw name and are not renamed.
- Confirmed 2026-10-03: there are no existing `"Unknown"` keys in the mapping/notes data, so
  nothing needs carrying over.

**R3 — Undo name mappings (original 092 scope).** Each resolved alias listed on a client row
(`raw_names`) has an **unlink** control. This covers `UnknownN` names too. Unlinking:
- removes the entry from `client_mapping.json`;
- puts the raw name back in "Names to resolve" exactly as it was before it was resolved,
  including its note;
- reverts the client's totals.

**R4 — ESC closes the client dropdown.** While the `ClientPicker` dropdown is open, pressing
Escape closes it without choosing anything.

### B. Explicit per-line status (replaces comment-keyword routing; includes bugfix-068)

**R5 — Persisted line status.** Each client row gets an explicit, persisted override status
(e.g. `client_status.json`: `{official_name: "closed" | "check" | "active"}`). No entry means
the row's section is computed from the numbers, as today. The routing priority stays as
`_row_status` has it now: `check` > `active` > `closed` > `past` > computed
(`settled` / `debt` / `missing_agreement`).

**R6 — "לסגור" / "לפתוח" button.**
- Rows in any open section (`check`, `active`, `debt`, `missing_agreement`) get a
  green-shaded **לסגור** button. It sets status `closed`, and the row moves to the green
  section.
- Rows in green (`settled`) get a gray-shaded **לפתוח** button. It clears the closed status,
  and the row is re-routed like this:
  - agreed == paid (and > 0) → **לקוחות פעילים** (light blue) — sets status `active`, since
    otherwise the numbers would route it straight back to green.
  - otherwise → the computed section: red (`debt`) or yellow (`missing_agreement`).
- **Closing never changes any amount** (bugfix-068). `display_agreed` and `display_paid` stay
  the real values. The `*_inferred` YELLOW markers that only existed to flag the faked amounts
  go away with the hack. All other amount colouring is unchanged.

**R7 — "לבדוק" button (blue).** On every non-gray line. Sets status `check`, and the row moves to the
blue "לבדוק" section.

**R8 — "לקוח פעיל" button (light blue).** On every non-gray line. Sets status `active`, and the row moves
to the light-blue "לקוחות פעילים" section.

**Gray (`past`) rows get no buttons at all.** They'll be handled by an upcoming "inactive"
marking. A button whose target is the row's current section is shown disabled or hidden, not as a no-op.
One status per line: pressing a button replaces any previous override.

**R9 — Comments become text only.** Once R5–R8 ship, client-row comments are free text and are
**not parsed** for routing on `לסגור`/`אפשר לסגור`, `לבדוק`, or `לקוח פעיל`/`לקוחה פעילה`.
Every other comment-driven behavior is unchanged (see Clarifications).

**R10 — Preserve current state (one-time migration).**
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

- **Only the three routing keywords the buttons replace stop being parsed** (`לסגור`/`אפשר
  לסגור`, `לבדוק`, `לקוח פעיל`/`לקוחה פעילה`). Delete, merge, `הסכם <amount>`, `סה״כ
  הסכמים` and `להוריד` keep working from comments unchanged.
- **Amount colouring is out of scope.** The existing YELLOW/GRAY amount markers keep their
  current behavior, including `לבדוק`/`לא ברור`/`חסר` in a comment marking amounts as unclear.
  The one exception is the `*_inferred` markers, which were created only by the `לסגור` hack and
  go with it.
- **Resolve-list removal is a button, not a keyword.** No `למחוק` fallback (R1).
- **Gray rows: no buttons.** They'll be marked inactive in a later feature.
- **Each Unknown becomes `Unknown-<event_id>`** (R2). This replaces any
  per-event mapping, split, or event-level undo machinery. Everything else reuses name
  resolution as-is.

## User Acceptance Scenarios (APPROVED 2026-10-03 — Playwright tier, `apps/webapp/e2e/`)

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
6. **Unknowns named and resolved.** Three no-name events (₪500, ₪1,200, ₪3,000) appear as three
   separate rows, each named `Unknown-<its event_id>`. The user maps the first two to different
   clients, and each client's totals grow by exactly that event's amount. A fourth no-name event
   then arrives with an *older* date. It appears as its own new row, and the first three keep their
   names and mappings. Unlinking the first one from its client returns it to the list.
7. **Undo a name mapping.** The user maps "Yisrael I" to "Israel Israeli", then unlinks it from
   Israel Israeli's row. The alias disappears from the row, the totals revert, and "Yisrael I" is
   back in "Names to resolve" with its note.
8. **Remove from resolve list.** The user clicks **הסר מהרשימה** on an unmatched name. It
   disappears and stays gone after a refresh.
9. **ESC.** With the client dropdown open, Escape closes it and nothing is mapped.
