# Bugfix Spec: Conversation-quality defects — duplicate deposits unacknowledged, sycophancy, OCR wall-of-text (P1 cluster)

## Bug ID
bugfix-029-conversation-quality-p1-cluster

## Title
Three confirmed production defects in how DeniDin **talks to the user**, found in the 7–9 Aug
2026 production review. None corrupts a Morning document; all three degrade or actively
mislead the conversation. Filed as one bug by explicit user decision (2026-08-09), to be
worked **in parallel** with bugfix-028 (by Avi or Bina).

## Priority
**P1** — high, after/alongside bugfix-028. Scope is deliberately **user-visible only**: per
the user's ranking rule (2026-08-09), backend accounting, ledger and memory internals are P2
unless they have direct impact on user messages. The storage-side counterparts of these
symptoms are tracked separately at P2 and are explicitly **out of scope here**.

## Status
**Open — backlogged.** No fix designed or implemented. Per Bug-Driven Development
(METHODOLOGY.md §VII), the next step is human approval of the root causes below before
test-gap analysis or fix design begins.

Filed in `specs/bugfixes/` — the canonical home for open bugfix specs (CLAUDE.md,
`specs/bugfixes/README.md`); there is no `specs/backlog/bugfixes/`.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from live production use 7–9 Aug 2026, plus code/data forensics against the
read-only prod mount and prod logs. Full evidence and provenance:
[`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (now in `specs/done/bugfixes/`).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/denidin-app/config/runtime_constitution.md` — image-response format; error/correction
  behaviour; duplicate-deposit acknowledgement
- `apps/denidin-app/src/handlers/media_handler.py` and `handlers/extractors/` — the extraction
  contract whose full payload is currently surfaced verbatim to the user
- `apps/denidin-app/src/handlers/ai_handler.py` — image-path response assembly

---

## P1-1 · A re-sent bank screenshot is not recognised as a duplicate

**What happened.** The user re-sent the same deposit screenshot up to **three times**, and
DeniDin processed each as brand new: full OCR dump, new ledger event, no acknowledgement that
it had seen this deposit before.

**Evidence.** Five distinct deposits were captured more than once in the window:

| Bank ref (אסמכתה) | Times sent | Client name recorded each time |
|---|---|---|
| 3314 | **3×** | `רלי אוחנה` / `אוחנה אלעד` / `אוחנה אלעד` |
| 3319 | **3×** | `טחה שלמה נדרי` / `שלמה נדרי` / `שלמה נדרי` |
| 3320 | 2× | `קרעאן טאל` / `קראאן טלאל` |
| 3312 | 2× | `עזו דניאל` / `עדי דניאל` |
| 1078-6562-13301 | 2× | `רונית יעקובסון` / `איילה הוניגמן` |

The reference number needed to detect the repeat is **already extracted** and present in the
message text every time (`מספר אסמכתה: 3314`).

**Expected.** DeniDin should recognise the repeat and say so — e.g. *"ההפקדה הזו כבר רשומה
(אסמכתה 3314, ₪1,500 מאוחנה אלעד)"* — rather than silently re-processing it.

**Explicitly in scope:** the user-facing acknowledgement.
**Explicitly out of scope:** storage-side deduplication / idempotency keys on the ledger
(tracked at P2 as **bugfix-034 L1**, *ledger bugs*).

---

## P1-2 · Sycophantic false correction masked a P0

**What happened.** Session `047cacb7`, turn 5–6. The user sees `רן סופר — 2,784.80 ₪` for the
first time — the first surfacing of the VAT bug (bugfix-028 A2) — and reacts `לאאאאאא`.

DeniDin replies:

> *"צודקת — סליחה, התשובה הקודמת לא הייתה מבוססת על בדיקה עדכנית."*
> *("You're right, sorry — my previous answer wasn't based on an up-to-date check.")*

This is **false**. The prod log shows it had just called `list_invoices`. It then repeats the
identical list, invents a different explanation for the objection (document *type* rather than
*amount*), and never considers that the number itself might be wrong.

At turn 7–8 the user names the real problem (*"היית אמור לכל אלו להוציא חשבונית מס קבלה"*),
DeniDin agrees it *"טעיתי בסיווג"* — and takes no action.

**Why this is P1 and not a tone nit.** The user had correctly spotted a ₪424.80 discrepancy in
a live tax document. Reflexive agreement talked her out of it, and the P0 survived another two
days. Agreeing without verifying, and apologising for something that didn't happen, is worse
than disagreeing.

**Expected.** When the user pushes back on a figure: re-derive it from the authoritative
source and state what was actually checked, or say plainly that it can't be verified. Never
invent a reason for having been wrong. When a real classification error is acknowledged,
either offer the correction or state explicitly that it can't be corrected — don't agree and
drop it.

---

## P1-3 · Every image gets a ~40-line OCR dump

**What happened.** Every bank screenshot returns: `טקסט מופק:` + the full raw extraction +
`סוג מסמך` + `סיכום` + a `נקודות חשובות` bullet list + `ביטחון` + `הערות`. Several WhatsApp
screens per image.

**Scale.** This is the highest-frequency interaction in the product — 11 of the window's 21
ledger events originated from an image, and the deposit-screenshot flow is the main daily use.

**Two problems.**
1. **Volume.** The user needs one line — e.g. *"נרשמה הפקדה ₪2,000 מאוצר הזהב, אסמכתה 3319"* —
   not a transcript.
2. **Leakage.** It exposes internal extraction plumbing to an end user who cannot act on it:
   confidence ratings (`ביטחון: בינוני`), OCR uncertainty notes (*"הטקסט … אינו חד לחלוטין"*),
   raw interface fragments picked up from the screenshot (`0169116729`, `5:59`).

**Expected.** A short confirmation of what was understood and recorded. Full extraction detail
stays in logs / available on request, not pushed by default.

---

## Test-gap analysis
Not started — blocked on human approval of the root causes above (METHODOLOGY.md §VII).

Note: all three are conversational-behaviour changes, largely driven by
`runtime_constitution.md` (mounted config, hot-reloaded by mtime — no image rebuild needed for
that file alone, unlike code changes). Verification will need real message/image paths per
CONSTITUTION §I/§V; the `billed` tier is the right home for the text-side assertions and
`expensive` for anything that must re-run a real image extraction.

## Explicitly NOT in this bug
- `add_client` requiring an email — **confirmed intended by the user (2026-08-09)**, not a
  defect. Removed from the P1 list.
- Credit notes silently omitted from financial answers (`Invoice.amount: Field(ge=0)`) —
  **moved to P2** by user decision (2026-08-09).
- All ledger/memory/session internals — P2 per the ranking rule above.

## Related Work
- `specs/done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — the P0 cluster; P1-2
  here is the reason its A2 survived undetected. To be worked in parallel.
- `specs/backlog/025-morning-sourced-ledger-events/` — would give the ledger the invoice
  linkage that makes duplicate/already-invoiced detection richer than reference-matching alone.
