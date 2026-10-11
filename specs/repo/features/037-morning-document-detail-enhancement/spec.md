# Feature Spec: Morning Document Detail Enhancement

**Feature ID**: 037-morning-document-detail-enhancement
**Priority**: TBD
**Status**: Draft
**Created**: August 4, 2026

---

## Origin

Raised live via WhatsApp by an admin user against prod (`v0.1.0`, 2026-08-04,
`logs/prod/denidin.log`) as two related feature requests:

1. (2026-08-04 04:06:43) — "תוסיף לך feature request להוציא שעות מחשבוניות
   במורנינג" — display each invoice's production/issue *time* (not just
   date).

2. (2026-08-04 04:15:55) — "תוסיף לך feature request להוציא בכלל עוד פרטים
   מהמסמך עצמו במורנינג. סוג תשלום בהחלט מופיע, ובטח חסרים עוד שדות" — the
   model expanded this into **"הרחבת שליפת פרטי מסמכים ממורנינג"**
   (broadening Morning document detail retrieval): payment method/type,
   issue date and time, full payment details, linked documents, VAT
   details, transaction description, client/payee details, and any other
   field present on the original Morning document.

## Problem Statement

`get_invoice_details` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`,
line 452) does not surface the complete document data Morning actually
holds. Confirmed live: issue **time-of-day** is missing from its output even
though the underlying Morning document has it. The formatter
(`format_invoice_details` in `formatters.py`) only assembles a curated subset
of fields — number, client, amount, doc type, status, dates, PDF link,
internal `invoice_id`, plus payments/linked-documents on top of
`format_invoice_confirmation`'s base block (`models.py`'s `Invoice` class,
line 136, mirrors this same curated subset).

Separately — and observed in the same incident — when a user asks for a
field that isn't present in `list_invoices`' lightweight summary output
(`format_invoice_list`), the model does not automatically know to call
`get_invoice_details` to look deeper. The user had to explicitly force a
details lookup, only to then discover the field (issue time) was missing
there too. Two distinct problems, one feature:

1. **Data gap**: `get_invoice_details` must expose every field Morning's API
   returns for a document — the full raw payload, not the current curated
   subset — and OpenAI must have access to all of it.
2. **Model-behavior gap**: the model must understand, structurally (via tool
   description/instructions, not user-forced follow-up), that
   `list_invoices` is a lightweight summary and `get_invoice_details` is the
   source of truth for any field not present in the list view, so it chains
   the calls itself whenever a user asks about something the list output
   didn't include.

**Explicit non-goal**: `list_invoices` itself stays as-is (lightweight
per-item summary, `format_invoice_list`) — this is a `get_invoice_details` +
model-behavior fix, not a list-format change.

## Requirements (draft)

- `get_invoice_details` returns Morning's complete document data for the
  requested invoice — including issue time-of-day and any other field the
  Green Invoice API provides that isn't in the current curated formatter —
  not a hand-picked subset.
- The model reliably recognizes when a user's question needs a field that
  `list_invoices` doesn't carry, and calls `get_invoice_details` on its own
  initiative to find it, rather than answering "not available" or requiring
  the user to force a details lookup themselves.

## Open Questions (for `speckit.clarify`)

- Does "every field" mean a raw passthrough of Morning's document JSON, or a
  maintained superset explicitly mapped into `Invoice`/formatter fields
  (and kept in sync as Morning's schema evolves)?
- How should the "check details when list lacks a field" behavior actually
  be enforced — tool description wording, a system-prompt/constitution
  rule, or something more structural?

---

*No `speckit.plan`/`user-stories.md`/`tasks.md` has been run yet — this is a
definition-only draft, not a fully specified feature.*
