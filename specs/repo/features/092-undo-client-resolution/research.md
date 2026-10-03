# Research: Feature 092

All decisions are grounded in a full read of
`apps/webapp/backend/src/webapp_backend/clients_reader.py` (as of `f096e06`), `server.py`'s
clients routes, and `frontend/src/ClientsView.tsx`.

## R-1 How a line's section is decided today

`_row_status` reads flags off the per-client `stats` dict, highest priority first:
`is_check` → `check`, `is_active_client` → `active`, `is_manually_settled` → `settled`, then
`past`, then the numbers (`settled` / `debt` / `missing_agreement`). The three flags come only
from `_apply_status_directives`, which parses the client's comment:

| Flag | Set when comment contains | Notes |
|---|---|---|
| `is_active_client` | `לקוח פעיל` / `לקוחה פעילה` | set **before** the delete check, so it survives `למחוק` |
| `is_delete_past` | `למחוק`, `== "להסיר"`, `להסיר מהרשימה` (unless merged away) | `continue`s, so check/close are skipped |
| `is_check` | `לבדוק` | |
| `is_manually_settled` | `לסגור` / `אפשר לסגור`, **and not** `is_check` | then the hack: `manual_agreement_amount = invoices_net = max(agreed, paid)` plus `*_inferred` YELLOW markers |

`is_manually_settled` also matters in `_build_client_rows`: a past row keeps its
`manual_agreement_amount` only if it's manually settled, and a closed row outranks `past`.

**Decision:** keep `_row_status` and the downstream uses of these three flags exactly as they
are. Only the **source** of the flags changes: the new `client_status.json` instead of comment
keywords. The delete/merge/agreement/`להוריד` parsing is untouched (spec Clarifications).

## R-2 Line-status storage

- **Decision:** a new `client_status.json` in `clients_data_root`: `{official_name: "closed" |
  "check" | "active"}`. One value per line, and an absent key means "computed".
- **Rationale:** it follows the existing per-concern JSON files (`client_comments.json`,
  `client_mapping.json`, `mapping_notes.json`), it's keyed the same way comments are, and it's
  written with the same `_save_json` helper.
- **Alternatives considered:**
  - Embedding a status in `client_comments.json`. Rejected: it changes that file's shape
    (`str` → object) and every reader of it.
  - Several boolean flags per client. Rejected: the buttons are mutually exclusive by spec, and
    one value removes conflicting combinations.
- **Known limitation, unchanged from comments:** it's keyed by the Morning display name, so a
  client renamed in Morning loses its status, exactly as it loses its comment today.

## R-3 "לפתוח" (reopen) logic lives in the backend

- **Decision:** the endpoint takes an **action** (`close` / `reopen` / `check` / `active`), not
  a raw status. `reopen` is resolved server-side:
  - First compute the line's section with its status cleared.
  - If that would be computed-`settled` (agreed == paid > 0), store `active`.
  - Otherwise delete the key, and the numbers route it to `debt` / `missing_agreement`.
- **Rationale:** agreed/paid equality depends on `manual_agreement_amount` (from `הסכם`
  comments), merges, and rounding to 2 places (`_row_status`). Recomputing that in TypeScript
  would duplicate it and drift. The backend already holds the computed row.
- `reopen` on a line that has no status but is computed-green (agreed == paid) → `active`.
  Same rule, same code path.

## R-4 One-time migration (spec R10)

- **Decision:**
  - A frozen copy of today's comment→flag detection (R-1 table, same precedence including the
    `active`-survives-delete quirk) becomes `_legacy_comment_status(comment) -> Optional[str]`.
  - It returns the **highest** of `check` > `active` > `closed`, matching what `_row_status`
    would have shown.
  - It runs once on the first `_compute_report` under the existing `self._lock`, but only if
    `migrations.json` lacks the key `"092_comment_line_status"`.
  - It writes statuses only for clients with no existing `client_status.json` entry, then
    records the key with a `now_local()` ISO timestamp.
- **Idempotent:** the marker plus never overwriting existing entries.
- **Section parity is the acceptance bar:**
  - A unit test feeds a matrix of real-shaped comments (including combined keywords:
    `לבדוק … לסגור`, `לקוח פעיל … למחוק`, `לקוח פעיל … לסגור`) through the legacy routing
    (old flags) and through the migration + new routing, and asserts the same section.
  - Quickstart adds a one-off prod parity check before and after deploy (`quickstart.md` §3).
- **Accepted, intended differences:** lines closed via `לסגור` show their real amounts, and
  lose the `*_inferred` YELLOW markers. For a combined `לקוח פעיל … לסגור` line, the section
  (active) is unchanged, but its amounts are no longer inflated either.
- **Edge (documented, accepted):** in the old code, `is_manually_settled` also preserved
  `manual_agreement_amount` on a past row. For a past row whose comment had both `לקוח פעיל`
  and `לסגור`, the migration stores `active` (the visible section). Its displayed agreed amount
  then falls back from the manual figure to the ledger figure. This combination is expected to
  be vanishingly rare; the prod parity check in the quickstart will list any such line by name
  before deploy.

## R-5 Unknown naming (spec R2)

- **Decision:** in `_aggregate_events`, when `client_name` and `payer_name` are both empty (or
  literally `"Unknown"`), set `raw_client = f"Unknown-{event_id}"`. If an event somehow has no
  `event_id`, it keeps plain `"Unknown"` (never observed; logged at WARNING).
- **Rationale:** `event_id` is unique and immutable per ledger event (Feature 033 format), so
  the name is deterministic, with no registry and no renumbering when older events are
  backfilled.
- **Fuzzy matching:** `difflib.get_close_matches(cutoff=0.8)` against Morning names can't
  plausibly hit an `Unknown-A0…` string. The smart-candidate "same amount" reason now works per
  event, which is a free improvement.
- **Verified 2026-10-03 by the user:** no existing `"Unknown"` key in mapping/notes data.

## R-6 Undo is limited to explicit mappings

- `raw_names` on a client line includes three kinds of names:
  1. explicit `client_mapping.json` entries;
  2. fuzzy matches (`difflib` ≥ 0.8);
  3. merge sources (`לאחד`).
- Only (1) can be undone meaningfully. Removing a fuzzy match has nowhere to go (it would
  re-match), and merges are comment-driven and out of scope.
- **Decision:** the row payload gains `mapped_aliases: [raw_name, …]`, the subset of
  `raw_names` that are explicit mapping keys pointing at this client. Only those get an unlink
  control.

## R-7 Hiding an unmatched name (spec R1)

- **Decision:** a new `hidden_unmatched.json` holds a sorted JSON list of raw names.
  `_split_unmatched` skips names in the list. There's no unhide endpoint, by spec.
- The existing note-keyword hiding stays.

## R-8 ESC closes the dropdown (spec R4)

- **Decision:** while `ClientPicker` is open, a `useEffect` registers a `window` `keydown`
  listener. On `Escape` it calls `setOpen(false)` and clears the query.
- This uses react-native-web, which renders to DOM, so a `window` listener is the reliable
  hook. The existing `Field` doesn't expose `onKeyPress` uniformly, and the user may press ESC
  after tabbing away from the input.
- The listener is removed on close and on unmount.

## R-9 Feature flag (CONSTITUTION §VI) — no flag (APPROVED by user 2026-10-03)

- §VI says new behavior ships behind a default-off flag, with the flag-off path byte-identical.
- **Recommendation: no flag for 092.**
  1. Part of this is a bug fix (068). Gating the fix behind "off" keeps the corruption live by
     default.
  2. The migration writes a new file. A flag-off path that ignores it while comments keep
     routing would let the two silently diverge the moment anyone presses a button with the
     flag on and then off, and turning the flag off would quietly move lines.
  3. The webapp is a single-operator, read-only-over-ledger tool, released through versioned
     artifacts. `deploy_release.sh` with the previous version **is** the rollback, and the
     comment files are never modified, so rolling back restores today's behavior exactly.
     The only new files (`client_status.json`, `hidden_unmatched.json`, `migrations.json`) are
     ignored by the old version.
- Precedent: Feature 087's plan also took §VI as N/A for the Clients tab.
- **Recorded in `plan.md` Complexity Tracking. Approved by the user 2026-10-03.**

## R-10 Morning sandbox capacity for the e2e fixture

- **Verified 2026-10-03** (read-only `search_clients`, sandbox URL): `total = 3666` clients.
- The extended seeder can therefore pick several distinct real clients: debt line, fully paid
  line, past line, two mapping targets, and migration lines. Nothing is created in Morning.
