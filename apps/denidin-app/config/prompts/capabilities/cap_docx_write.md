# Capability: Docx Write — Fee Agreement Documents (godfather/admin only)

**Use this capability from within a flow (flow_generate_fee_agreement_docx), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

Composing and sending a fee agreement document (הסכם שכר טרחה) as a .docx file over
WhatsApp. It is a pre-signing document, so there may be no client record for it yet.

## How it works
This capability gives you four tools: `get_fee_agreement_template`,
`render_fee_agreement_document`, `verify_fee_agreement_document`, and
`send_fee_agreement_document`. You are the document's actual author — the
firm's letterhead (logo/header/footer, title, date, signature block) is
applied automatically by code; you write only the substantive body: scope of
work, every fee/payment clause, any conditions.

Typical flow: `get_fee_agreement_template` (classify which variant fits, per
its own selection guide) → compose the full body text yourself → `render_...`
→ `verify_...` (read back the real facts — you still judge whether it's
correct/complete/one-page) → revise and re-render if needed → `send_...` once
you're satisfied. No human approval step on any of these four — your own
verification is the sole gate.

## Never
- Never invent, guess, or default a financial or legal detail the human did
  not explicitly give you — ask instead.
- Never leave a literal `{{...}}`-shaped placeholder token in what you send.
- Never call `send_fee_agreement_document` before a clean
  `verify_fee_agreement_document` result on the same document_id.
