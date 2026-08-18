# Bugfix Spec: Ledger bugs

## Bug ID
bugfix-034-ledger-bugs

## Title
Six confirmed defects in the ledger-event store (Feature 033), found together in the 7–9 Aug
2026 production review. Together they make the event log unreliable as a book of record: ~38%
of rows are duplicates, none is linked to the document it produced, and several capture paths
lose events silently. Filed as one bug by user decision (2026-08-09).

## Priority
**P2** — backend accounting internals with no direct impact on user messages, per the ranking
rule set 2026-08-09. Nothing downstream currently consumes these events automatically, so no
money is wrong *today* — but the store cannot be trusted until this is fixed.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root causes before test-gap analysis.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-6/7/9/10/11/13 + P3-1).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (now in `specs/done/bugfixes/`).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/denidin-app/src/managers/ledger_event_manager.py` — event persistence, ID generation
- `apps/denidin-app/src/handlers/ai_handler.py` — `capture_ledger_event` tool wiring,
  the bugfix-018 at-most-once guard, malformed-arguments handling, Morning-turn suppression
- `apps/denidin-app/config/runtime_constitution.md` — Ledger Event Recognition rules
- Data: `{data_root}/events/*.json`

## Scope — the window's evidence
21 event files for **13 distinct real-world facts** (9 bank deposits + 4 fee agreements).

---

### L1 · No idempotency key — one deposit captured up to 3× *(was P2-6)*

| Bank ref (אסמכתה) | Events | Client name recorded each time |
|---|---|---|
| 3314 | **3×** | `רלי אוחנה` / `אוחנה אלעד` / `אוחנה אלעד` |
| 3319 | **3×** | `טחה שלמה נדרי` / `שלמה נדרי` / `שלמה נדרי` |
| 3320 | 2× | `קרעאן טאל` / `קראאן טלאל` |
| 3312 | 2× | `עזו דניאל` / `עדי דניאל` |
| 1078-6562-13301 | 2× | `רונית יעקובסון` / `איילה הוניגמן` |

The bank reference is a natural idempotency key, is present in the extracted text of every
duplicate, and is **unused** — the dedicated `reference` field is `null` on all 21 events; the
number survives only inside `raw_message_excerpt` prose.

Duplicates also **disagree with each other**, and the later capture is usually the worse one:
ref 3314 is `רלי אוחנה` on first capture (correct — resolved from the memo line
*"ייעוץ רלי אוחנה"*) and `אוחנה אלעד` on both re-captures (the payer's bank-account name). Any
"latest row wins" read would take the wrong one.

### L2 · Events are never linked to the documents created from them *(was P2-7)*
0 of 21 have `invoice_number`, `morning_document_id`, or `invoice_status` set — including the
four events that directly produced invoices 100012–100015.

Prod log names the cause:
```
[024] Suppressing N ledger-event capture(s) for request … — Morning MCP was this turn's
      data source, not yet a supported ledger-event source (specs/backlog/025-…)
```

The ledger therefore cannot answer *"has this deposit been invoiced?"* — the question it
exists to answer. Also blocks the richer duplicate detection in bugfix-029 P1-1.

### L3 · A batched capture discards **every** event *(was P2-9)*
```
WARNING [bugfix-018] Rejecting 12 capture_ledger_event call(s) for request req_… —
        more than one call in a single turn violates the at-most-once-per-message rule;
        nothing persisted
```
The at-most-once guard is reasonable; **"nothing persisted" as its failure mode is not.**
12 events were lost in one turn with no user-visible signal.

### L4 · Truncated tool arguments silently drop an event *(was P2-10)*
```
WARNING Malformed 'capture_ledger_event' function_call arguments discarded:
        Unterminated string starting at: line 1 column 16 (char 15)
```
A truncated JSON payload loses the event with no retry and no signal.

### L5 · `replaced_event_id` holds prose, not an ID *(was P2-11)*
`A05082620180`:
```json
"replaced_event_id": "צריך למצוא",
"replaces_hint": "הסכם שכר טרחה עבור הסתדרות … שבו המע״מ לא צוין"
```
`"צריך למצוא"` means *"need to find"* — the model wrote a placeholder into an identifier
field. Supersession is therefore **non-functional**: two live ₪40,000 הסתדרות agreement events
both stand, the second intended to replace the first. Nothing validates that this field is an
event ID.

### L6 · The payee is recorded as the client *(was P2-13)*
`B06082613311` records `client_name: "איילה הוניגמן"` — the firm's own operator, the person
sending the screenshots — as the *client* on an **incoming** bit transfer, with
`payer_name: "מרונית יעקבסון"`. The sibling capture of the same transfer (`B06082613310`,
same bit confirmation `1078-6562-13301`) got it right: `client_name: "רונית יעקובסון"`.

Direction of the transfer is being inferred inconsistently from the same source document.

### L7 · `event_date` is the capture date, not the transaction date *(was P3-1)*
All ten Aug 9 events carry `event_date: 09/08/2026` for deposits with `txn_date` of 04–07/08,
and `event_id` encodes the capture time too (`B09082606000` = 09/08 06:00). Events therefore
sort by *when someone got round to screenshotting*, not by when money moved.

> **Not a duplicate of bugfix-028 A3** (checked at triage): A3 is the `payment[0].date` field
> in the **Morning document payload** — a different field in a different system. The ledger's
> own `txn_date` is already correct, and A3 will *consume* it. L7 is about which date the event
> presents as its primary one.

---

## Expected
- Extract the bank reference into the existing `reference` field and use it as an idempotency
  key: re-capture supersedes or is rejected, never blindly appended.
- Populate `invoice_number` / `morning_document_id` / `invoice_status` when a document is
  created from an event (depends on spec 025).
- A batched or malformed capture must persist what it can and surface what it couldn't —
  never silently drop everything.
- `replaced_event_id` must be a real event ID or `null`; validate it.
- Resolve transfer direction consistently so the firm's own people are never recorded as
  clients.
- Make the event's primary date the transaction date (or make it unambiguous which is which).

## Related Work
- `specs/backlog/025-morning-sourced-ledger-events/` — prerequisite for L2.
- `specs/bugfixes/bugfix-029-conversation-quality-p1-cluster.md` — P1-1 (tell the user a
  deposit is a duplicate) is the user-facing half of L1; that one is P1 and does **not** wait
  for this.
- bugfix-018 — introduced the at-most-once rule whose failure mode L3 challenges.
- Feature 033 — created the event store.
