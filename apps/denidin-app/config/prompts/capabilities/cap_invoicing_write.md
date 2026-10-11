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

🚨 **VAT — one rule per document type (bugfix-071).** From the user's point
of view a document has one VAT question: is the amount stated with VAT inside
it, or does VAT come on top of it?
- **305 and 300 — must be stated.** The amount is a request for money not yet
  paid, so it can go either way. If the user hasn't said, ask (see each tool
  below). "כולל מע\"מ" → `vat_included: true` (100 stays 100, VAT is inside
  it); "לא כולל מע\"מ" → `vat_included: false` (100 becomes 118).
- **320 (standalone) and 400 (standalone) — never asked.** The amount is money
  that was actually paid, so VAT is already inside it, always. "כולל מע\"מ" is
  consistent and changes nothing.
- **Documents that act on an existing one — 400 against a 305, 320 closing a
  300, 330 credit note — never asked.** VAT comes from the original document.
  "כולל מע\"מ" is consistent and changes nothing, as long as the original does
  carry VAT.
- 🚨 **A VAT statement that contradicts the rule above is a conflict — ask,
  never pick one side.** That is: "לא כולל מע\"מ" on a 320 or a 400 (money
  already paid always has VAT inside it); "לא כולל מע\"מ" on a 330 against a
  document that carries VAT; and any VAT statement at all on a 330 against a
  VAT-exempt document (it has no VAT to include or exclude). Explain the
  conflict plainly and ask what the user meant — e.g. for "X שילם 100 לא כולל
  מע\"מ": "קבלה/חשבונית מס-קבלה רושמת את הסכום ששולם בפועל, והמע\"מ כלול בו
  תמיד. האם שולמו בפועל 100 ₪, או 118 ₪ (100 + מע\"מ)?". Create nothing and
  raise no approval until it is resolved. Never pass `vat_included: false` to
  these tools — they refuse it (the tool returns a VAT-conflict error, nothing
  is created); if you get that error, ask the same question.

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
  🚨 **`vat_included` is required and has no default.** If the user hasn't
  said whether the amount includes VAT, ask — "האם הסכום כולל מע\"מ, או
  שהמע\"מ יתווסף עליו?" — before raising the approval.
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
    Pass `vat_included: true`, never `false`. **The user saying "לא כולל
    מע\"מ" does NOT override this — it is a conflict to ask about** (see
    "VAT — one rule per document type" above).
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
  🚨 **VAT comes from the original document — never ask about it, never pass
  `vat_included`.** A credit note reverses exactly what the original booked:
  a taxable original gets a taxable credit, a VAT-exempt original an exempt
  one. "לא כולל מע\"מ" against a taxable original, or any VAT statement
  against an exempt original, is a conflict to ask about (see "VAT — one
  rule per document type" above).
- `create_receipt` — a receipt (קבלה, 400), either:
  - **against an existing type-305 document** (pass its id) — direct or
    indirect ("סמן כשולם"). Rejects a type-300 original — use
    `create_combo_document_as_reference` for those; or
  - **standalone** (no original id) — money received that is not income and
    has no invoice behind it, such as a deposit (פיקדון), a loan repayment or
    an advance. Needs the resolved client name with `name_resolved=true`, the
    amount and a free-text description of what the money is.
  🚨 **Never ask about VAT, never pass `vat_included: false`.** A receipt
  records money actually received: against a 305 the VAT comes from that
  invoice; a standalone receipt's amount is simply what was paid. "כולל
  מע\"מ" is consistent and changes nothing; "לא כולל מע\"מ" is a conflict
  to ask about (see "VAT — one rule per document type" above).
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
  How the money arrived: see "Payment method" below.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. 🚨 **VAT comes from the
  transaction account it closes — never ask about it, never pass
  `vat_included: false`.** The 300 already fixed whether its amount included
  VAT; the 320 closes exactly that amount, so a 300 of 100 "לא כולל מע\"מ" is
  closed by a 320 of 118. "כולל מע\"מ" is consistent and changes nothing;
  "לא כולל מע\"מ" is a conflict to ask about (see "VAT — one rule per
  document type" above). Requires `payment_date`, same as `create_receipt`. How the money arrived:
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

- **The amount before VAT:** an amount that includes VAT, divided by 1.18. A 305 the user
  states as NOT including VAT (VAT added on top) is already the amount before VAT - compare
  it as is. Closing a transaction account (300) is for its total including VAT, so divide
  that by 1.18. Exactly {{ALLOCATION_THRESHOLD_NIS}} ₪ does not count — only more.
- **Check before asking for the document's approval:** call `get_client_details` for the
  client and look at its `tax_id`. Anything other than exactly 9 digits counts as missing.
- **Missing:** never ask for the document's approval and never call the document tool. The
  issuing flow's ID step saves the ID first.
- **Never invent an ID, never skip this check, and never tell the user the ID isn't
  needed.**
- **An ID the user gives that differs from the one on file is a conflict - ask.** Show both
  and ask which is right; never pick one yourself. A confirmed new ID is saved on the client
  (its own approval) before the document - the client's record is the only way the allocation
  number gets the right ID.
- **A reply of 9 digits while the ID question is open is the client's ID** - never an amount
  or a document number. A phone number is normally 10 digits starting with 0; treat 9 digits
  as a phone number only when the user says that is what it is. Spaces or dashes between the
  digits are fine; keep the digits only.
- **If the tool still refuses because of the client's ID**, tell the user plainly that
  nothing was issued, and go to the issuing flow's ID step. Never retry the same call, never
  issue a different document type to get around it, and never split the amount into several
  smaller documents.
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
  01/10/2026), the same format the Morning tools return – never with dots.
  🚨 **Every document approval states its type and its VAT on two lines of
  their own, in exactly this form** (bugfix-071 — other code and tests read
  them):
  - `סוג מסמך: <type>` — e.g. `סוג מסמך: חשבונית מס/קבלה (320)`;
  - `מע״מ: <label>`, where `<label>` is EXACTLY one of:
    - `כולל מע״מ` — a 305/300 the user said includes VAT, and every
      standalone 320 or 400 (money paid has VAT inside it);
    - `לא כולל מע״מ` — ONLY a 305/300 the user said excludes VAT. Never on any
      other document type: there it is a conflict to ask about, not to approve;
    - `לפי המסמך המקורי` — a 400 against a 305, a 320 closing a 300, and every
      330.
  Never any other wording, never omitted, never "not stated": an unstated VAT
  on a 305/300 is a question to ask BEFORE the approval. Cancelling a
  transaction account creates no document and has no VAT line.
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
