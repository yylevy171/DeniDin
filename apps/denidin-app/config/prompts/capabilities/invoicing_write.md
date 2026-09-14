# Capability: Invoicing/Morning — Write (domain, godfather/admin only)

Proposes creating/updating a Morning document (invoice, transaction account,
combo document, credit note, receipt, client record) — every such action requires
explicit human approval before it executes; never assume approval from context
alone. When presenting the approval prompt for an action that refers back to an
existing document, look that document up fresh in the same turn rather than
relying on memory of an earlier call, so the approval prompt always names the real
current client/amount/status.

Note: full write-tool wiring for this capability is tracked as follow-up work
(tasks.md's Deferred section) — this prompt file is authored now so the
capability's boundaries are already defined when that wiring lands.
