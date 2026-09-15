# Fee agreement curated examples (Feature 083 follow-up, 2026-09-14)

One `<variant_id>.json` file per template variant: `{"variant_id", "directive",
"examples": [...]}`. `directive` is a short instruction telling the AI what to
do with the examples + the reference template body (`get_fee_agreement_template`
returns both together - see `DocTemplateEngine.get_reference_materials`).
`examples` is a curated list of REAL fee-agreement excerpts this firm has
actually sent to real clients, obfuscated before being committed here.

## Provenance

Source material: ~22 real fee-agreement screenshots pulled from prod (godfather
WhatsApp media), OCR'd once each via a real OpenAI vision call into sibling
`.txt` files under `media_from_prod/` (gitignored - real client names/amounts,
never committed). Each was manually classified into one of the (now 3) template
variants, then the best few per variant were selected for diversity of
structure/register (staged litigation fees, contingency percentages, hourly
add-ons, joint clients, formal-letter register, VAT-inclusive vs
VAT-exclusive phrasing, etc.) and hand-obfuscated: every client name and
adversary/company name was replaced with a fictitious-but-plausible stand-in,
and every exact monetary figure was shifted, before being committed here. The
phrasing, clause structure, and professional register are real; the specific
facts are not.

## Coverage gap (explicit human decision, 2026-09-14)

The real corpus turned out to be dominated by staged/cumulative litigation fee
structures - no real example existed for a genuinely single-flat-fee
engagement (the old, now-removed `fixed_price_project` variant) or an ongoing
monthly retainer (the old, now-removed `retainer_agreement` variant). Per
explicit human decision:
- `fixed_price_project` was folded into `multi_component_agreement` - a
  single flat fee is now just `multi_component_agreement` with one component
  (unlettered, or lettered only if there's a real second item to letter
  alongside it).
- `retainer_agreement` was removed entirely (no real example, no template).

This leaves 3 variants: `hourly_consultation`, `multi_component_agreement`,
`alternative_tracks`.

## Adding more examples later

If real `fixed_price_project`/`retainer_agreement`-shaped documents (or just
more diversity for any existing variant) become available, add a JSON file
here following the same shape - no code changes needed, `get_reference_materials`
picks up any `<variant_id>.json` under this directory automatically, and its
absence for a given variant degrades gracefully (falls back to the reference
template body alone, no error).
