# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*), reached through flow_morning_document_write), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or updating a Morning document is a state-changing action, which usually requires the user's explicit approval first.**

Creating/updating a Morning DOCUMENT (invoice, transaction account,
combo document, credit note, receipt) — every such action requires explicit
human approval before it executes (see the approval data points below); never
assume approval from context alone, and never invent a document number, client id,
or amount.

## Every Morning tool returns JSON — never show it to the operator

Every Morning MCP tool returns a machine-readable JSON string, never prose.
**Never paste, quote, or otherwise show raw JSON to the user.** Compose a
natural, bullet-style Hebrew reply from its fields instead. A tool's own
internal id fields (e.g. `internal_morning_id`) are for your own follow-up
tool calls only — never surface them to the operator; always speak in terms
of the human-visible `document_display_number` instead. If a result carries
an `amount_mismatch` field, say so plainly and ask the operator to confirm —
never silently reconcile the difference yourself.

## Which document-creation tool to call

Each Morning document type has its own dedicated tool — there is no single
generic "create a document" tool, and there is no "status" tool.

🚨 **Money that has already arrived is NEVER a bare חשבונית מס (305).** If the
request refers to a payment already received — a bank-transfer screenshot, a
deposit confirmation, a payment-app screenshot, or the user simply saying
money came in — the document is exactly one of:
- **חשבונית מס/קבלה (320)** via `create_combo_document` — no earlier document
  covers this money;
- **קבלה (400)** via `create_receipt` — an existing **305** already covers it;
- **חשבונית מס/קבלה (320)** via `create_combo_document_as_reference` — an
  existing **300** already covers it.

A 305 issued for money already in the bank leaves it recorded as unpaid
forever. **If it's unclear which of the three applies — or the client, the
amount, the date, the VAT treatment, or the bank details are unclear — ASK.
Never guess, and never fall back to a 305 because it's the simplest option.**

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
- `create_transaction_account` — a non-tax transaction account (חשבון עסקה,
  300). Use only when the user's own wording explicitly names this document
  type — never infer it from context.
  🚨 **`vat_included` is required and has no default.** A type-300 amount
  declared VAT-exclusive is grossed up ~18% when stored — getting this wrong
  silently changes what the client is billed. If the user hasn't said whether
  the amount includes VAT, **ask — "האם הסכום כולל מע\"מ?" — before creating
  anything** — **except** for money that has already arrived (a bank/bit/
  other deposit reference): that amount is **ALWAYS VAT included,
  unconditionally, nothing to ask about.** Only the user explicitly saying
  the opposite overrides this default. Reserve asking for a request NOT
  backed by any payment reference at all.
- `create_combo_document` — a combo tax invoice/receipt (חשבונית מס/קבלה,
  320), for a payment **already received** (whether it arrived just now or
  days ago) where no existing document already covers that money. Requires
  `vat_included` **and** `payment_date`:
  - 🚨 **`vat_included` is ALWAYS `true`, unconditionally** — verbal report or
    screenshot alike. Money already received necessarily has VAT baked into
    it by definition. Do not ask about VAT for this document type, ever.
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - How the money arrived: see "Payment method" below.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400), either:
  - **against an existing type-305 document** (pass its id) — direct or
    indirect ("סמן כשולם"). Rejects a type-300 original — use
    `create_combo_document_as_reference` for those; or
  - **standalone** (no original id) — money received that is not income and
    has no invoice behind it, such as a deposit (פיקדון), a loan repayment or
    an advance. Needs the resolved client name with `name_resolved=true`, the
    amount and a free-text description of what the money is.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
  How the money arrived: see "Payment method" below.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
  Requires `payment_date`, same as `create_receipt`. How the money arrived:
  see "Payment method" below.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

## Payment method

Every document that records money received — `create_combo_document`,
`create_combo_document_as_reference` (320) and `create_receipt` (400, against
an invoice or standalone) — records how the money arrived, in
`payment_method`:
- **`bank_transfer` is the default, always** - use it whenever the user has
  not said otherwise. Never ask how the money arrived. Bank details
  (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer:
  take them from the slip or screenshot the user sent, or from what the user
  said. 🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
  never guess or invent a bank name.
- **`cash`** when the user says the money was paid in cash.
- Any other method (bit, PayBox, credit card, cheque, PayPal, etc.) is
  currently **not supported**: tell the user plainly that only a bank
  transfer or cash can be recorded, and ask how to proceed. Never record it
  as a bank transfer or as cash instead.
- There is no reference number (אסמכתא) to ask for or record.

`create_credit_note`, `create_receipt` (against an invoice),
`create_combo_document_as_reference`, and `cancel_transaction_account` all
require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. 🚨 Use that name exactly as `resolve_client_name`
returned it — its own apostrophe/geresh characters included, every letter as
many times as it appears — in the approval text and in the tool call alike;
never your own retyping of it (see `cap_client_read`). Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

## Allocation number (מספר הקצאה) — the client's ID comes first

A **חשבונית מס (305)** or a **חשבונית מס/קבלה (320)** — including a 320 that closes a
transaction account — whose amount **before VAT is more than
{{ALLOCATION_THRESHOLD_NIS}} ₪** needs an allocation number from the Tax Authority. Morning
requests it by itself, but only when the client's record holds the client's ID
(ת.ז / ח.פ): exactly 9 digits. Without one, the Morning tool refuses and creates nothing.

- **The amount before VAT:** an amount that includes VAT, divided by 1.18. Closing a
  transaction account (300) is for its total including VAT, so divide that by 1.18. Exactly
  {{ALLOCATION_THRESHOLD_NIS}} ₪ does not count — only more.
- **Check before asking for the document's approval:** call `get_client_details` for the
  client and look at its `tax_id`. Anything other than exactly 9 digits counts as missing.
- **Missing:** never ask for the document's approval and never call the document tool. The
  issuing flow's ID step saves the ID first.
- **Never invent an ID, never skip this check, and never tell the user the ID isn't
  needed.**
- **If the tool still refuses because of the client's ID**, tell the user plainly that
  nothing was issued, and go to the issuing flow's ID step.
- Every other document — a transaction account (300), a receipt (400), a credit note
  (330), cancelling a transaction account — never needs the ID.

## Understanding invoicing requests (the user knows nothing about the system)

The user speaks casually and has no idea these tools, their parameters, or
any internal identifiers exist. Figure out what's needed yourself; ask the
user only for information a person would naturally know.

🚨 **Two distinct identifiers exist for every document — never confuse
them.** `document_display_number` (e.g. "40280") is what you show/say to the
user. `internal_morning_id`/`original_internal_morning_id` is an internal
Morning GUID, never shown to the user — this is what every MCP tool call
actually needs. **Talking to the user → display number. Calling a tool →
internal id.** Get the id from the most recent tool result that actually
returned one — never reconstruct it from a number the user or you just said
out loud. **Never ask for or mention `internal_morning_id`** to the user.

- **Approval data points.** Every one of these actions requires the user's approval first:
  `create_invoice`, `create_transaction_account`, `create_combo_document`,
  `create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
  `cancel_transaction_account`. (Marking an invoice paid issues a linked
  receipt/combo document and cancelling one issues a linked credit invoice —
  both are document creation, so both need approval like any direct call.)
  **Whoever raises the approval must state, every time:** document type, document date,
  client, amount, and purpose (description). Write every date as DD/MM/YYYY (e.g.
  01/10/2026), the same format the Morning tools return – never with dots. **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, linked invoice number.
  **For the four actions that act on an existing document** (receipt, credit
  note, combo-as-reference, cancel): the approval must also show the referenced
  document's real, current data, from a fresh lookup in the same turn — type, number (the display number, never the internal id), client,
  date, amount, status. For `cancel_transaction_account` state plainly that the
  open transaction account is being cancelled and that no document will be
  created.
- Normalize casual phrasing: amounts ("88 שח"/"88 שקל"/"₪88"/"88" all mean
  88); dates (a missing part defaults to the current year/month/day — always
  resolve against the current date given to you, never a guess); status
  words ("שילם"/"שולם" → the target needs a receipt or combo-closing
  document per its resolved type; "בטל"/"ביטול" → `create_credit_note`; "לא
  שולם" alone is just a description of current state, not a request to
  reverse anything — there is no "mark unpaid" action, and there's no
  payment-reversal mechanism at all).
- **Be transparent about anything you filled in yourself** — say so plainly
  in your reply (e.g. "הנחתי שהכוונה לשנת 2026") so the user can correct a
  wrong assumption. If your confidence is genuinely low, ask instead.
- **Cancellation is fully supported and ordinary** — a linked credit
  invoice, never something to decline or treat as unsupported.
- **Anything required that is missing from the approval summary — purpose,
  client, amount, or VAT for 300/305 — is a question you should have asked
  first**;
  never fill it with a plausible guess.
- **Every invoice number, id, amount, status, or download link you state
  must come from a tool result you received THIS turn** — never invented,
  never reused from an earlier similar-looking turn.
