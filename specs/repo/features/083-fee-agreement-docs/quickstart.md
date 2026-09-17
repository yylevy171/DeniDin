# Quickstart: Fee Agreement Document Generation (manual verification)

Prerequisite: `config.feature_flags.fee_agreement_docs = true` in `config.dev.json`, godfather/
admin phone number configured, `config/fee_agreement_templates/manifest.json` + at least one real
`.docx` variant present (see research.md #5 — these are human-curated, not auto-generated).

## Stage 1 — Template selection
1. As a godfather/admin, WhatsApp DeniDin: *"Create a retainer agreement for NewCo Ltd."*
2. **Expect**: the AI's next turn (internally) selects `variant_id: "retainer_agreement"` — check
   `logs/denidin.log` for the `generate_fee_agreement` tool call's `variant_id` argument once you
   reach Stage 2/3 (Stage 1 alone has no user-visible confirmation of the selected variant unless
   the model chooses to state it).

## Stage 2 — Clarification (anti-hallucination)
1. WhatsApp: *"Draft an agreement for Yossi."* (a known client, no financial terms given)
2. **Expect**: the AI's reply is a clarifying question (e.g. fee amount + scope) — NOT a
   generated document, and NOT a guessed/default amount.
3. Reply: *"The fee is 5,000 NIS for tax consultation."*
4. **Expect**: the AI proceeds without asking again for anything you just supplied.

## Stage 3 — Self-verification
1. Check `logs/denidin.log` for the turn's tool-call sequence: `generate_fee_agreement` MUST be
   followed by a `verify_fee_agreement_document` call before any document is sent.
2. **Expect**: the verification tool's result (in the log) shows `remaining_placeholders: []` and
   every `values_found` entry `true` before the send happens.

## Stage 4 — Delivery
1. **Expect**: an actual `.docx` file arrives in the WhatsApp chat as a document attachment
   (not a text message, not a link).
2. Open it: formatting (fonts, logos, bullet points) must be intact, and every placeholder must
   be replaced with the real values from the conversation (no `{{...}}` tokens visible).
3. Check `{data_root}/tmp/fee_agreements/` — it must be empty (or not contain this run's file)
   after the send completes (SC-003).

## Rollback / troubleshooting
- If `sendFileByUpload` fails: confirm research.md #1's blocking task (client library method
  confirmation) was actually completed — a wrong method/kwarg name would fail every send.
- If a `.docx` is left behind in `tmp/fee_agreements/`: check `send_document_response()`'s failure
  path actually ran (both success and final-failure branches must delete the temp file — see
  `contracts/whatsapp-file-delivery.md`).
