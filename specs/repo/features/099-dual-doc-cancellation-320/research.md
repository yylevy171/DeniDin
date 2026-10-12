# Research: Feature 099 - verified against the real Morning sandbox (2026-10-09)

Procedure (probe scripts, session scratchpad): seed client -> `create_combo_document` 320 for 1000 (bank transfer + bank details) -> `create_credit_note` 330 -> raw `POST /documents` type 400.

- Morning **accepts** a type-400 with `linkedDocumentIds=[<320 id>]` and a payment line with a **negative `price`** (-1000, same `type`/bank details as the 320's payment).
- Stored: `amount: -1000`, `vat: 0`, description as sent, payment rendered "העברה בנקאית / בנק … / סניף … / חשבון …", `linkedDocuments` -> the 320. The 320's own `linkedDocuments` then lists **both** the 330 and the negative 400 (amount -1000).
- Link list on the 400 holds only the 320 (the 330 is not linked on it).
- "Already cancelled" signal: the 320's `linkedDocuments` containing a type 330 (or a negative 400).
- Today `create_receipt` rejects any original that is not type 305 -> extended per design.
- Sandbox now contains the probe client/documents (no cleanup needed; sandbox).
