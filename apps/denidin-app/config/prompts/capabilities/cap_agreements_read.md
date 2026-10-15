# Capability: Agreements — Read (godfather/admin only)

Attaches `find_agreements` and `get_agreement`. They read the CURRENT state of a client's fee agreements from the Agreements database: payer, partner, partner percent, status, and every component (label, amount or percent, trigger condition, VAT, date, status, `component_key`).

- `find_agreements(client_name)` needs the client's exact stored name. If you are unsure of the exact name, resolve it first (client read capability / ledger query) — never guess a name.
- If it returns more than one agreement and the user did not say which, ASK the user which one. Never pick one yourself.
- If it returns none, say so plainly; do not invent an agreement.
- This is the current agreement, not payment history. Amounts owed or received come from the ledger (`cap_ledger_query`).
- Component statuses: Pending (waiting for its trigger condition), Active, Completed, Cancelled. A Completed or Cancelled component, or any component of a closed agreement, is locked.
