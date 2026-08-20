# Quickstart: Mandatory Client Reference for Invoicing (Feature 027)

Manual verification scenarios once implementation lands, covering all 6 user stories (US1-US6).
Requires: `apps/morning-mcp-app` running (dev, real sandbox) via its own `run_morning_mcp.sh dev`;
`apps/denidin-app` running dev with a godfather WhatsApp number configured. **Starting either
environment always needs explicit approval — nothing below authorizes that on its own.**

## Prerequisites

- `apps/morning-mcp-app/config/config.dev.json` has real Morning sandbox credentials.
- `apps/denidin-app/config/config.dev.json`'s `mcp` block points at the running Morning server's
  status file, and the sender's WhatsApp number resolves to `godfather` or `admin`.
- A sandbox client named "Danny Cohen" exists (create via US2's own flow first, or seed directly).

## US1 — Existing, unambiguous client [Group A]

Send: `"תוציא חשבונית לדני כהן על 500 שקל בעבור ייעוץ"`
Expect: a confirmation question (approval gate, unchanged) → reply "כן" → a Hebrew invoice
confirmation, same shape as today.
Verify: `MorningClient.get_invoice(<returned id>).client.id` equals Danny Cohen's real `client_id`
(look it up via `search_clients({"name": "דני כהן"})` first) — **not** just that a document exists.

## US2 — Unknown client, then created inline [Group A]

Send: `"תוציא חשבונית לרונית לוי על 1000 שקל בעבור שירותי תכנות"` (assuming no such client exists
yet)
Expect turn 1: a friendly "client not found" reply — **no confirmation prompt, no document
created**.
Expect the bot to then ask for phone/email for "Ronit Levi".
Send: phone + email.
Expect turn 2: an `add_client` confirmation question → reply "כן" → client created confirmation.
Expect turn 3 (bot retries automatically, or re-send the original invoice request): an invoice
confirmation question → reply "כן" → invoice created.
Verify: the final invoice's `client.id` equals the newly-created "Ronit Levi"'s real `client_id`.

## US3 — Ambiguous client name [Group A]

Seed a second client "Danny Katz" (shares first name with "Danny Cohen").
Send: `"תוציא חשבונית לדני על 200 שקל"`
Expect: a disambiguation reply listing both "Danny Cohen" and "Danny Katz" — **no document
created**.
Send: `"דני כהן"` (disambiguated).
Expect: proceeds exactly as US1.

## US4 — Group A uniformity across the other 2 tools

Repeat US1's flow verbatim but ask for a `חשבון עסקה` (maps to `create_transaction_account`) and a
`חשבונית מס/קבלה` for an immediate cash sale (maps to `create_combo_document`) instead of a plain
invoice.
Verify: same `client.id`-matches-real-client check as US1 for each.

## US5 — RBAC denial (unchanged)

From a non-godfather/admin (`client`-role) WhatsApp number, send `"תוציא לי חשבונית"`.
Expect: a normal reply with no document created — no MCP tool was available to the model at all.
Verify: no Morning API call appears in logs for that turn.

## US6 — Group B: preserve real id, or refuse [new]

**Preserve path**: using the invoice created in US1 (real `client.id` attached):
Send: `"תעשה זיכוי לחשבונית הזאת"` (referencing that invoice).
Expect: a confirmation question → reply "כן" → a credit-note confirmation.
Verify: the new credit note's `client.id` (via `MorningClient.get_invoice`) equals the **same**
`client_id` as the original invoice's.
Repeat for `"תוציא קבלה על החשבונית הזאת"` (`create_receipt`).

**Refuse path**: seed (via a raw `MorningClient.create_invoice` call, bypassing the tool layer —
see research.md's Outstanding item) a document whose `client` sub-object is `{"name": "Danny
Cohen"}` only, no `id` — simulating a pre-feature document.
Send a request for a credit note / receipt against that document's id.
Expect: **no new document is created**; the reply is a friendly Hebrew refusal (new formatter,
e.g. "לא ניתן להפיק מסמך מקושר עבור חשבונית זו — היא לא מקושרת ללקוח קיים במערכת."), not an error
stack trace and not a bare-name document.
Verify: zero new documents in the sandbox linked to that original.

## Cleanup

Documents/clients created during manual verification are sandbox data — no cleanup mechanism is
required.
