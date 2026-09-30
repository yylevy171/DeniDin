# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.
