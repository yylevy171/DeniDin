# Flow: Generate fee agreement docx

Goal: compose a fee agreement (הסכם שכר טרחה) for the user and send it as a .docx file. It is a pre-signing document, so no client needs to exist.

Capabilities: `cap_docx_write`.

Follow these steps in order, to the letter.

1. Load `cap_docx_write`. Gather what the agreement needs from the user. Never invent, guess, or default a missing fact — if something is missing (the client's name, the fee amount, the scope of work), ask for it with `cap_send_to_user` before composing, one question at a time.
2. Compose, check and send the document as `cap_docx_write` directs. This flow needs no approval step and no client lookup.
3. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_docx_write` and this flow, keeping any that other work still in progress needs.
