# Flow: Deposit provided by the user

Goal: the user reported or forwarded a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Make sure its client exists in Morning, and get a Morning document for it only when the user asks for one.

Capabilities: `cap_media_analysis`, `cap_client_read`.
Flows it may load: `flow_add_client`, `flow_morning_document_write`.

Follow these steps in order, to the letter.

1. If the deposit came as an image or document (a bank slip, a payment screenshot), it must have been read with `cap_media_analysis`'s `analyze_media` (load it and read it now if it was not). Use `cap_send_to_user` to report what it contains so the user can see what you understood. If it is not a bank slip or payment confirmation, stop using this flow and decide what it is from its content.
2. Load `cap_client_read` and resolve the client by the client name the user gave, or, failing that, the name on the slip - even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. If the user asks for a Morning document for this money - an invoice, a combo invoice/receipt, a receipt or a transaction account, or a cancellation of any of these - load `flow_morning_document_write` and follow it through to its end. If it is unclear whether the user wants a Morning document at all, or which one, use `cap_send_to_user` to ask. If they want none, do not create one.
4. Recording the deposit in the ledger happens automatically after the turn, from what is in the conversation. There is nothing to load or call for it, so do not try.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `cap_client_read` and this flow, keeping any that other work still in progress needs.
