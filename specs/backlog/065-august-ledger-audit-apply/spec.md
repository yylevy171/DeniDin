# Feature Specification: Apply August 2026 Ledger Audit Findings to Prod

**Feature Branch**: audit material landed via `chore/august-ledger-audit` (renamed 064→065, collision with pre-existing 064-bank-deposit-full-cycle); implementation branch
TBD at pickup (e.g. `feature/065-august-ledger-audit-apply`)
**Created**: 2026-08-30
**Status**: Backlog — holding spec. Records the audit that was already done (2026-08-30) plus the
concrete change-set it produced. Full `speckit.specify`/`clarify`/`plan`/`tasks` pipeline still
needs to run before any prod mutation.
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

## Related

- **Feature 062** (`specs/backlog/062-prod-morning-ledger-backfill-completion`) — Morning-sourced
  prod ledger backfill; complementary. 065 is about the manually-captured `בנק`/`הסכם` events
  Morning can't source; 062 is about Morning-sourced accounting documents.
- **Feature 052** (`specs/low-priority/052-ledger-events-csv-export`) — ledger CSV export; the audit
  CSVs here are ad-hoc equivalents.
- **Feature 033** (`specs/done/v0.2.0/033-ledger-event-persistence`) — event schema / immutability.
- **Feature 044** (ledger querying) — `query_events` / `query_ledger_events`; the "cache over
  Morning" fallback rule the audit leans on.
- **bugfix-023** (`ledger-tool-overeager-on-morning-query`) — related model-behavior context.

## Files in this folder

- `spec.md` — this file.
- `ledger_changes_august.json` — the machine-readable change-set (duplicates / removals /
  name_changes). The applier's input.
- `august_bank_deposits.csv` — the 21 refined deposits (txn_date, amount, client_name) after
  duplicates removed. Human reference.
- `august_ledger_vs_morning.csv` — reconciliation: every August Morning income doc tagged
  `1_in_bank_ledger` / `2_pre_onboarding_gap` / `3_recorded_in_morning_no_bank_slip`.
- `august_morning.csv` — **gitignored** (real client PII + signed download URLs). The raw Green
  Invoice August export used as the reconciliation input. Local-only; regenerate from Morning if
  needed.
