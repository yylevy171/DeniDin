# Flow: Morning document write

Goal: the user may want a Morning document created or cancelled. Work out exactly which document they mean, asking when it is unclear, and then load the one flow for that document. This flow never writes anything itself.

Capabilities: none of its own.
Flows it may load: `flow_issue_invoice_for_payment_due`, `flow_issue_invoice_receipt_combo`, `flow_issue_transaction_account`, `flow_issue_receipt_without_invoice`, `flow_issue_payment_received_with_reference_doc`, `flow_cancel_document_with_credit_note`, `flow_cancel_transaction_account`, `flow_invoicing_query`.

## The Morning documents

- **חשבונית מס (tax invoice, 305)** - a demand for payment of money that is still owed. It is income for VAT purposes from the moment it is issued. Common names: "חשבונית", "חשבונית מס", "תפיק חשבונית ל...". Never for money that has already arrived.
- **חשבון עסקה (transaction account, 300)** - a request for payment that is not a tax document; the tax invoice comes only once the money arrives. Common names: "חשבון עסקה", "דרישת תשלום". Only when the user's own wording names this document; a plain "חשבונית" is never a 300.
- **חשבונית מס/קבלה (combo invoice/receipt, 320)** - an invoice and a receipt in one, for money that has already been received and that no earlier document covers. The most common way to record incoming money. Common names: "חשבונית מס קבלה", "חשבונית קבלה", or a payment report with a request to issue a document for it ("X העביר לי 500, תפיק").
- **קבלה (receipt, 400)** - confirms that money was received:
  - against an existing tax invoice (305): closes it ("סמן כשולם", "תוציא קבלה על החשבונית");
  - standalone, with no invoice at all: money that is not income, such as a deposit (פיקדון), a loan repayment, or an advance on future work.
- **Closing a transaction account (300)** - money arrived for an existing transaction account; a combo invoice/receipt (320) is issued against it and closes it ("סמן כשולם" on a transaction account).
- **חשבונית זיכוי (credit note, 330)** - cancels an issued document, fully or partly ("בטל את החשבונית", "תפיק זיכוי"). An issued tax invoice is never deleted; it is cancelled only this way.
- **Cancelling a transaction account (300)** - the deal fell through and no money moved; the account is cancelled and no document of any kind is created.

## Which flow

- A tax invoice (305) for money still owed: `flow_issue_invoice_for_payment_due`.
- A transaction account (300), named as such: `flow_issue_transaction_account`.
- Money already received, no existing document covers it, and it is income: `flow_issue_invoice_receipt_combo`.
- Money already received that is not income (a deposit, a loan repayment, an advance), with no invoice behind it: `flow_issue_receipt_without_invoice`.
- Money already received for an existing tax invoice (305) or transaction account (300): `flow_issue_payment_received_with_reference_doc`.
- Cancelling an issued document other than a transaction account: `flow_cancel_document_with_credit_note`.
- Cancelling an open transaction account: `flow_cancel_transaction_account`.

Money that has already arrived is never a bare tax invoice (305).

Follow these steps in order, to the letter.

1. Decide from the user's wording and the conversation whether they are asking for a Morning document at all, and if so which one, by the definitions above. If either is unclear, use `cap_send_to_user` to ask - name the options in plain words - and wait. Never pick one yourself.
2. If money has already been received and it is unclear whether an existing document already covers it, load `flow_invoicing_query` and check (same client, similar amount). If that still leaves it unclear, use `cap_send_to_user` to ask the user.
3. Load the one flow for that document and follow it through to its end. Several documents in one request: handle them one at a time, each through its own flow.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Unload this flow and `flow_invoicing_query`, keeping any that other work still in progress needs.
