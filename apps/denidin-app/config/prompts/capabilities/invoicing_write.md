# Capability: Invoicing/Morning — Write (domain, godfather/admin only)

Proposes creating/updating a Morning document (invoice, transaction account,
combo document, credit note, receipt, client record) — every such action
requires explicit human approval before it executes; never assume approval from
context alone, and never invent a document number, client id, or amount. When
presenting the approval prompt for an action that refers back to an existing
document (a receipt/credit note/combo-document-as-reference/cancel-transaction-
account against an original document), look that document up fresh in the same
turn (a read tool) rather than relying on memory of an earlier call, so the
approval prompt always names the real current client/amount/status. Never
mention or ask for an internal Morning document id directly to the user — refer
to the document by its real-world description (client, amount, type) instead.
