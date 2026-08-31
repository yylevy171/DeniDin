# Feature Specification: Apply August 2026 Ledger Audit Findings to Prod

**Feature Branch**: audit material landed via `chore/august-ledger-audit` (renamed 064→065, collision with pre-existing 064-bank-deposit-full-cycle); implementation branch
TBD at pickup (e.g. `feature/065-august-ledger-audit-apply`)
**Created**: 2026-08-30
**Status**: In progress (`feature/065-august-ledger-audit-apply`, 2026-08-31) — the August prod
mutation described below (Type 1/2/3) has been applied and independently re-verified against the
real prod filesystem, via a temporary rw sshfs mount (torn down immediately after). Not a
speckit-pipeline feature — explicit user decision, "we're not doing speckit here, it's a chore."
Still open before this can move to `specs/done/`: (a) the 2 real prod duplicate pairs found
during the copy step (`B23082606010`/`B23082606020` אתי אסולין, `B23082606560`/`B23082607030`
גדי רוזן) only had one side copied into player/prod — the other side's dedup handling was never
finished; (b) the אורלי גרינפלד `הסכם` (`A23082611460`) vs `בנק` (`B24082606100`) reconciliation
was never resolved; (c) the planned July audit (see below) has not been started. See "Prod
Mutation Applied (2026-08-31)" below for the full record of what changed. PR: #269.
**Priority**: P2 — no urgency. The prod `בנק`/`הסכם` ledger is a manual cache, not a source of
truth (see `runtime_constitution.md` "cache over Morning" rule); Morning already holds the
authoritative record of every August shekel. This feature only improves the cache's accuracy.

---

## Background

A godfather/admin WhatsApp turn on 2026-08-30 ("כמה כסף נכנס באוגוסט רק לפי הפקדות מהבנק")
returned **105,117 ₪**, which the operator believed was too low. Investigation of the prod
ledger event store (`~/denidin-winprod-data/events/`, all `source_type=בנק` events for August
2026) found the low figure was a combination of:

- the model answering purely from `query_ledger_events` (the local cache), never cross-checking
  Morning;
- the cache itself being incomplete and containing duplicate captures and OCR-garbled client
  names;
- the model then applying its own (mostly reasonable) dedup + "pending" exclusions on top,
  landing at ~105k against a raw sum of ~152k.

This spec captures the manual reconciliation of that cache against the real Green Invoice
(Morning) August export, and the change-set to bring the cache into line.

## What was done (methodology)

1. Pulled all **33** `בנק` ledger events for August 2026 from the read-only prod data mount.
   Raw amount sum: **152,110 ₪**.
2. Operator reviewed every event and marked:
   - **6 duplicate groups** (8 events) — same amount + txn date + near-identical description /
     bank account / Bit confirmation number, captured seconds-to-minutes apart.
   - **4 events to remove** — unsupported Bit transfers flagged `סטטוס: ממתין` in the slip OCR
     (never confirmed as settled deposits).
   - **16 client-name corrections** — the extractor had frequently stored the *debited-account
     name* off the transfer slip, an institution name (e.g. "סיטיבנק ישראל", "מקורות", "מתנ״ס
     נחל"), or an OCR fragment, instead of the real client.
3. Cross-checked the refined 21-event ledger against the August Green Invoice export
   (`august_morning.csv`, 47 active income documents, ~211,887 ₪ net paid income). Every one of
   the 21 refined deposits maps to a real Morning income document; one event (אסולין אסתר,
   554 ₪) has **no** Morning document at all.
4. Established that the ledger covers **~50%** of Morning's August paid income. The uncovered
   half is Morning-recorded income with no forwarded bank slip — **not** missing money.

## Findings — the change-set

All machine-readable detail is in **`ledger_changes_august.json`** (this folder). Summary:

| Change type | Events | ₪ effect |
|---|---|---|
| Approved duplicates (mark 8 events as dup-of-keep, 6 groups) | 8 | −33,371 |
| Removals — unsupported Bit transfers (`ממתין`) | 4 | −11,412 |
| Client-name corrections (some propagate to dup twins) | 15 applied (+1 recorded-only for a removed event) | 0 |
| **Refined ledger result** | **21 events** | **107,327 ₪** (raw was 152,110) |

**Duplicate keeps / dups** (event ids):

| Keep | Mark as duplicate |
|---|---|
| B09082606040 (04/08 3,000) | B09082606280 |
| B05082621120 (05/08 1,500) | B09082606041, B09082606350 |
| B09082606000 (06/08 2,000) | B09082606001, B09082606290 |
| B09082606003 (06/08 2,300) | B09082606220 |
| B23082606010 (21/08 1,071) | B23082606020 |
| B23082606560 (21/08 20,000) | B23082607030 |

**Removals — unsupported Bit transfers:** B06082613310 (רונית יעקובסון 3,776), B06082613311
(איילה הוניגמן 3,776), B07082606400 (רן סופר 2,360), B13082621150 (איילה 1,500).
⚠️ Note: **רונית יעקובסון #112297** and **רן סופר #112299** DO exist as closed
`חשבונית מס / קבלה` in Morning — removing them from the cache means the cache understates real
income by 6,136 ₪. Operator confirmed removal anyway (the slips were never confirmed settled);
revisit if the Morning-side documents turn out to reflect real receipts.

**Name corrections** — full `from → to` list with event ids in `ledger_changes_august.json`
`name_changes[]`. Highlights: OCR/institution names replaced with the real client
(e.g. "סיטיבנק ישראל גי" → "גלית סיטבון", "מתנ״ס נחל" → "מתנס שורק", "לור יעל" → "יעל לוריא",
"אלדר דוד" → "דודי אדלר").

## Coverage gap (informational — not a change-set)

Reconciliation categories are in **`august_ledger_vs_morning.csv`**:

- **Category 1 — in the bank ledger:** 20 Morning docs / 106,773 ₪ matched.
- **Category 2 — pre-onboarding gap:** 14 Morning docs / ~54,678 ₪ (2–4 Aug). DeniDin was not
  in the גבייה group until 2026-08-05 ~18:24 Israel time; the whole 2–4 Aug batch (incl. ~10
  invoices at 3,776 ₪) was never seen. Nothing recoverable from DeniDin's side. Green API
  `readchat` history pull is also currently blocked (`466 QUOTE_EXCEEDED` on the prod instance).
- **Category 3 — recorded in Morning, no bank slip:** 8 Morning docs / ~53,436 ₪, incl.
  נואז-טק פתרונות 23,000 (#112298), ריכטר דיין שולמית 6,000, ל.מ פאות קאולה ×2. All closed/paid
  in Morning — money is tracked, just not as a `בנק` cache event.
- One ledger event (אסולין אסתר 554 ₪, B06082606161) has **no** Morning document — likely an
  expense reimbursement, or a genuinely missing Morning receipt. Operator to decide.

## Scope of this feature (what "apply to prod" means)

To be refined during `speckit.plan`. Candidate approach:

1. **Decide the mutation mechanism.** Ledger event JSON files are documented as *immutable*
   (`ledger_event_manager.py`, one file per event). Options: (a) a one-shot, dry-run-capable,
   human-approved `apply_ledger_changes.py` that rewrites `client_name` in place and marks
   duplicates/removals via a new status field rather than deleting; (b) treat corrections as new
   superseding events with `replaced_event_id`/`replaces_hint` (fields already exist in the
   schema); (c) accept the cache as-is and only fix forward. **Immutability vs. correction is a
   human design decision — do not pick one here.**
2. **Duplicates & removals**: mark, don't hard-delete (preserve audit trail). Confirm whether
   `query_events` / `query_ledger_events` already filter a "superseded"/"duplicate" status or
   need to learn to.
3. **Name corrections**: apply the 15 confirmed `name_changes[]`, propagating to dup twins as
   listed.
4. **Re-run the same WhatsApp question** afterward as a `billed` acceptance check — expect a
   figure near 107,327 ₪ for bank-only, with the model still required to fall back to Morning
   per the constitution.
5. Every prod data mutation is gated by fresh explicit human approval, same as any
   environment-affecting action.

## Open decisions (for `speckit.clarify`)

- Immutability: rewrite-in-place vs. superseding-event vs. fix-forward-only.
- Keep or restore the two removed Bit transfers that have real Morning documents (רונית
  יעקובסון 3,776, רן סופר 2,360)?
- אסולין אסתר 554 ₪ event with no Morning doc — keep, remove, or flag for a manual Morning
  receipt?
- Should Category 2 (pre-onboarding, ~54,678 ₪) be backfilled into the `בנק` cache at all, or
  left to Morning as the authoritative record? (Overlaps Feature 062's Morning-sourced backfill
  question, but for `בנק`/manual-slip events specifically, which Morning cannot source.)
- `#112307 רומן ציקל 3,000` looks like a duplicate/mis-issue of `#112308 רומן אלטשולר` in
  Morning itself — out of scope here (Morning-side), but worth flagging to the operator.

## Second source: player-replay cross-check (2026-08-30)

Independently of the manual audit above, `chore/player-start-at-line-resume` re-ran the full
July–August WhatsApp export through the Feature 043 player (real message-by-message replay
through the actual bot pipeline, real OpenAI calls, real ledger-event capture — not a
simulation of the audit). Its output was itself reviewed item-by-item (86
`needs_clarification.jsonl` entries; full reasoning trail in
`apps/denidin-app/player_data/_review_decisions.jsonl`). That review surfaced findings that
either **corroborate** this audit or **extend** it:

### Corroborating findings (independent agreement)

- **`B06082613310` (רונית יעקובסון, 3,776 ₪, Bit transfer)** — the player replay captured this
  as a ledger event and flagged it for review; the human reviewer (unaware of this audit's
  parallel conclusion) independently marked it `מבוטל` for the same reason this audit removed
  it: an unsupported, never-settled (`ממתין`) Bit transfer. Two separate processes, same
  event, same call — see `specs/backlog/066-support-bit-and-paybox`.
- The player replay reproduced the same **duplicate-capture pattern** this audit found manually
  (repeated near-identical `העברה נוספת` deposits captured seconds/minutes apart for the same
  underlying transaction) — e.g. player events `B09082606040`/`B09082606280` (both עדי דניאל,
  3,000 ₪, 04/08) and `B09082606041`/`B09082606350` (both אוחנה אלעד, 1,500 ₪, 05/08) mirror
  this audit's own keep/dup pairs for the *same* client+amount+date. Confirms the duplicate
  mechanism is systemic (an artifact of the source WhatsApp export's own repeated forwards, not
  an audit-time or replay-time fluke) — relevant to `060-duplicate-bank-image-detection`'s
  general-mechanism design.
- The `reference: "צריך למצוא"` placeholder-leak (9 events fixed to `null` during the review)
  and the `client_name` = OCR/institution-name pattern (e.g. `"מתנ"ס נחל"`, `"סיטיבנק ישראל
  גי"`) both independently reproduce exactly the defect classes `069-mandatory-client-
  resolution-before-ledger-event` was opened to fix — the player replay hit the same
  extraction-time confusion on the same underlying screenshots.

### New finding: the player replay recovers most of the "pre-onboarding gap" (Category 2)

**This is the most actionable new fact for "fixing August."** DeniDin was not admitted to the
real WhatsApp group until 2026-08-05 ~18:24 — so the real prod ledger has **zero** `בנק` events
for 2–4 Aug (this audit's Category 2, 14 Morning docs / 54,678 ₪). But the player replay was run
against the **full WhatsApp export file**, which includes that pre-onboarding history (the
export captures the whole chat regardless of when the live bot joined it) — so the player
*did* generate ledger events for those dates. Matching player events (`txn_date`) to this
audit's Category 2 Morning docs (`creationDate`, 1 day later — normal bank-to-Morning lag) by
amount + near-identical client name:

| Morning doc | date | client (Morning) | amount | matched player event | client (player capture) |
|---|---|---|---|---|---|
| 112285 | 03/08 | סמי כהונאי | 1,888 | `B03082614414` | כהונאי מוריס,כהונאי סמירה |
| 112288 | 03/08 | אילן מוריץ | 3,776 | `B03082614412` | מוריץ אילן |
| 112287 | 03/08 | עליזה בניטה | 3,776 | `B03082614411` | בניטה עליזה ויוס |
| 112286 | 03/08 | אייל כהן | 3,776 | `B03082614410` | כהן איל |
| 112284 | 03/08 | גל פלג | 3,776 | `B03082614413` | עובד-פלג אפרת (desc also names "פלג גל") |
| 112283 | 03/08 | מירב יונתן דולב | 3,776 | `B03082614415` | דולב ירון,יונתן-דולב מירב |
| 112291 | 04/08 | רוני גרינבוים זיו | 1,030 | `B04082608510` | גרינבוים די רון |
| 112294 | 04/08 | סיגל רוטקוביץ | 3,776 | `B04082608513` | סיגל רוטקוביץ שר |
| 112293 | 04/08 | עופר גלברט | 3,776 | `B04082608512` | עו"ד גלברט עפרו י |
| 112292 | 04/08 | עפרה קפואה מלצר | 3,776 | `B04082608511` | מלצר עפרה וד"ר מ |

**10 of 14 Category-2 documents (33,126 ₪ of the 54,678 ₪ gap) have a matching player-captured
event**, with client names needing the same kind of normalization pass as `069` already
proposes (the player's OCR/extraction reproduced the same messy raw names this audit corrected
manually). The 4 that do **not** match any player event: `112282` (תניה סנקין, 4,000 ₪),
`112295` (אפרת הלוי, 3,776 ₪), `112290` (עמליה אור, 3,776 ₪), `112289` (אור משאלי 2020,
10,000 ₪) — genuinely unrecoverable from this source; either the underlying screenshot was
never forwarded to the group at all, or the player's clarification-loop dropped it silently
(needs a targeted look at the player's raw log around those dates before concluding "no data
exists" — see Required Actions below).

### Non-August findings from the same review, noted for completeness (not actioned here)

The player-review also produced a Bug-Driven-Development bugfix
(`bugfix-049-financial-status-answers-from-conversation-not-ledger.md` — model answering
financial-existence questions from conversation memory instead of a real ledger/Morning lookup)
and several open Category-B constitution-tuning candidates (spelling-variance policy, checks
(`שיק`)-unsupported wording, historical name-variant inconsistency for one client) — tracked
separately, out of scope for "fixing August" specifically.

## Required Actions — what "prod Aug data is good" means

Two separate, explicit deliverables, per the 2026-08-30 decision to start executing this
feature:

### (a) Ledger data must be correct

1. **Apply this audit's original change-set** to the real prod ledger
   (`~/denidin-winprod-data/events/`, via SSH/read-write path — the local mount is read-only,
   so this requires the equivalent write path, TBD in `speckit.plan`): 8 events marked
   duplicate-of-keep (6 groups), 4 Bit-transfer events marked `מבוטל` (with the caveat below),
   15 client-name corrections applied (propagating to dup twins per
   `ledger_changes_august.json`).
2. **Revisit the 2 Bit removals with real Morning documents** (רונית יעקובסון #112297, רן סופר
   #112299 — 6,136 ₪) — per the audit's own open decision: since `066-support-bit-and-paybox`
   is now being scoped, decide whether to (i) leave these `מבוטל` until 066 ships and then
   re-capture properly, or (ii) restore them now with a corrected payment-method field as an
   interim fix. **Human decision required, not to be inferred.**
3. **Backfill the 10 matched pre-onboarding-gap events** (table above) into the prod ledger as
   new events (not overwriting anything — this data never existed in prod), applying the same
   client-name normalization the other 15 corrections used. Mechanism (new events vs. some
   other representation) is a `speckit.plan` decision, same immutability question the original
   audit already flagged as open.
4. **`אסולין אסתר` (`B06082606161`/554 ₪, no Morning document)** — same open question the
   original audit raised; resolve one way or the other rather than leaving ambiguous.
5. Immutability mechanism (rewrite-in-place vs. superseding-event vs. mark-only) — still an open
   human decision from the original audit; must be settled before any of the above ledger
   mutations happen, since it governs how all of them are implemented.

### (b) Missing data must be tracked, not silently absorbed

Create a durable, human-readable "missing data" record (proposed:
`specs/backlog/065-august-ledger-audit-apply/missing_data_august.md`, one row per gap) covering
everything identified across both sources that is **not** going to be recovered by (a):

- The 4 unmatched Category-2 pre-onboarding docs (112282/112295/112290/112289, 21,552 ₪) —
  pending the targeted player-log look noted above; if still unrecoverable, recorded as a
  permanent, dated gap with the reason ("bot not yet admitted to group; no bank slip forwarded
  or replay could not recover it").
- Category 3 (8 Morning docs / ~53,436 ₪, real closed income with no bank-slip conversation at
  all — e.g. נואז-טק פתרונות #112298) — these are correctly absent from the `בנק` cache by
  design (no slip was ever sent), so the record should state that explicitly rather than imply
  a defect.
- `#112307 רומן ציקל 3,000` vs `#112308 רומן אלטשולר` — the original audit's flagged possible
  Morning-side duplicate/mis-issue, out of scope to fix here but must not be dropped.
- Any of the Category-B constitution-tuning items (above) that end up affecting future data
  quality, cross-referenced rather than duplicated.

## Related

- **Feature 062** (`specs/backlog/062-prod-morning-ledger-backfill-completion`) — Morning-sourced
  prod ledger backfill; complementary. 065 is about the manually-captured `בנק`/`הסכם` events
  Morning can't source; 062 is about Morning-sourced accounting documents.
- **Feature 052** (`specs/backlog/052-ledger-events-csv-export`) — ledger CSV export; the audit
  CSVs here are ad-hoc equivalents.
- **Feature 033** (`specs/done/v0.2.0/033-ledger-event-persistence`) — event schema / immutability.
- **Feature 044** (ledger querying) — `query_events` / `query_ledger_events`; the "cache over
  Morning" fallback rule the audit leans on.
- **bugfix-023** (`ledger-tool-overeager-on-morning-query`) — related model-behavior context.

## July audit (started 2026-08-30)

Same cross-check methodology applied to July, from two Morning-app screenshots (partial —
56 of 62 total July documents visible; full CSV export still needed to close this out
exhaustively). Full results: `missing_data_july.md`.

**Headline finding, confirmed by operator**: bank-deposit screenshots only started being
forwarded to the WhatsApp group **late July** — before that, no bank slip ever existed to
capture, so July's `בנק` cache is *expected* to cover only the last few days of the month, not
the whole month (unlike August). The player replay's 3 July `בנק` events (28–30 July) all
matched 1:1 against Morning documents (all posted 31/07/2026) by amount, and are staged —
Morning name substituted, `morning_document_id` set — in `backfill_events_july/*.json`:

| txn_date | Amount (₪) | Morning name | Morning doc # |
|---|---|---|---|
| 28/07 | 5,000 | דודי אדלר | 112280 |
| 30/07 | 10,620 | גדי אדלר | 112281 |
| 30/07 | 3,000 | יחיאל אוהב עמי | 130116 |

The other ~30 July Morning documents have no corresponding player event, by design (no slip was
ever sent for them) — tracked in `missing_data_july.md`, not treated as a defect.

## Prod Mutation Applied (2026-08-31)

`player_data/events/` (gitignored, local-only) was first corrected in place — Morning-verified
name/status fixes from `ledger_changes_august.json`, plus fixes found only by cross-checking
every player `בנק` event against `august_ledger_vs_morning.csv` (the real Morning export, more
complete than the JSON audit alone) — every edit backed up to `player_data/events/_originals/`
before mutation, same discipline used throughout this whole review. That corrected player store
was then the source for a real prod write, done via a temporary rw sshfs mount (`scripts/
env_lock.sh`/persistent-mount machinery untouched — this was a separate, explicitly-approved,
task-scoped mount, torn down immediately after use):

- **Type 1 — add new** (`type1_add_new_to_prod.csv`, 70 events): every player event with no prod
  counterpart under that event_id, copied into prod's `events/` as new files.
- **Type 2 — modify** (`type2_modify_in_prod.csv`, 26 events): prod's current file moved to
  `events/_modified/` (history preserved), player's corrected version copied in as the new live
  file.
- **Type 3 — delete** (3 events: `B06082613311`, `B07082606400`, `B13082621150`): unsupported
  Bit-transfer events with no player counterpart at all (player correctly never captured them) —
  moved to `events/_removed/` with a reason note, not left live.

Every step was independently re-verified against a fresh read of the real remote filesystem
(not just the applying script's own in-process claim) — the rw mount was found to have silently
died mid-run once during this work, so nothing here is reported done on trust alone. 130 macOS
AppleDouble sidecar files (`._*`, a side effect of writing to this filesystem from a Mac) were
found and cleaned up from prod's `events/`, `_modified/`, and `_removed/` before final
verification.

**Not yet applied** (see Status above): the 8 prod events copied into player as schema-v2 fixes
for the "no player coverage" gaps (`copy_prod_gap_events_to_player.py`) were written to *player*
only, as the source-of-truth correction — they were never a prod write target themselves (prod
already had them). Two real prod duplicate pairs found along the way
(`B23082606010`/`B23082606020`, `B23082606560`/`B23082607030`) only had one side reconciled; the
אורלי גרינפלד `הסכם`/`בנק` split (`A23082611460` vs `B24082606100`) is unresolved.

## Files in this folder

- `spec.md` — this file.
- `missing_data_august.md` — the durable, per-gap "not recovered" record required by this
  feature's own "missing data must be tracked" requirement.
- `missing_data_july.md` — the July equivalent, plus the "screenshots only started late July"
  root-cause note.
- `backfill_events_pre_onboarding/*.json` — 10 ready-to-apply August events (Morning-verbatim
  names), staged pending prod write.
- `backfill_events_july/*.json` — 3 ready-to-apply July events (Morning-verbatim names), staged
  pending prod write.
- `ledger_changes_august.json` — the machine-readable change-set (duplicates / removals /
  name_changes). The applier's input.
- `august_bank_deposits.csv` — the 21 refined deposits (txn_date, amount, client_name) after
  duplicates removed. Human reference.
- `prod_events_jul_aug_reconciliation.csv` / `player_events_jul_aug_reconciliation.csv` — full
  prod-vs-player diff (deterministic, read fresh from the live JSON files on disk every run, no
  jsonl/history/audit-file dependency), produced by `scripts/reconcile_prod_vs_player.py`.
- `type1_add_new_to_prod.csv` / `type2_modify_in_prod.csv` — the Type 1/Type 2 change-lists
  actually applied to prod (see "Prod Mutation Applied" above), derived from the two
  reconciliation CSVs by `scripts/build_type1_type2_csvs.py`.
- `scripts/` — every script used in this review: `reconcile_prod_vs_player.py`,
  `apply_audit_corrections_to_player.py`, `apply_csv_crosscheck_fixes.py`,
  `copy_prod_gap_events_to_player.py`, `build_type1_type2_csvs.py`,
  `apply_type1_add_new_to_prod.py`, `apply_type2_modify_in_prod.py`,
  `apply_type3_delete_from_prod.py`.
- `august_ledger_vs_morning.csv` — reconciliation: every August Morning income doc tagged
  `1_in_bank_ledger` / `2_pre_onboarding_gap` / `3_recorded_in_morning_no_bank_slip`.
- `august_morning.csv` — **gitignored** (real client PII + signed download URLs). The raw Green
  Invoice August export used as the reconciliation input. Local-only; regenerate from Morning if
  needed.
