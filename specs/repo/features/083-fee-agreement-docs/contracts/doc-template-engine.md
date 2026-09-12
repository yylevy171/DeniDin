# Contract: DocTemplateEngine ↔ `generate_fee_agreement` tool

## Purpose
Fills a `.docx` template variant's placeholders with AI-supplied values and writes a temporary
output file, without ever inventing a value the AI did not explicitly provide.

## Interface

```python
class DocTemplateEngine:
    def __init__(self, templates_dir: Path, tmp_dir: Path) -> None: ...

    def list_variants(self) -> list[FeeAgreementVariant]:
        """Loads/returns manifest.json's variants. Read-only; no side effects."""

    def generate(
        self,
        variant_id: str,
        values: dict[str, str],
        components: list[dict[str, str]] | None = None,
    ) -> GeneratedDocument:
        """
        Raises ValueError if:
          - variant_id is unknown
          - values' keys don't exactly match the variant's declared FeeAgreementVariant.placeholders
            (missing OR extra keys are both errors - no silent partial fill)
          - any value (scalar or inside a components entry) is empty/whitespace-only (an empty
            string is not a legitimate answer to "what is the fee amount" - REQ-083-02)
          - the variant HAS a repeating_group (multi_component_agreement) and:
              * components is None/empty, OR
              * len(components) < repeating_group.min_items (2), OR
              * any entry's keys don't exactly match repeating_group.row_placeholders
          - the variant has NO repeating_group and components is not None (extra/unexpected
            argument for a single-fee variant is an error, not silently ignored)

        On success: loads the template via python-docx, replaces every scalar {{PLACEHOLDER}}
        run-by-run in BOTH paragraphs and table cells (preserving surrounding formatting -
        SC-002). For a repeating_group variant, additionally: locates the template's one
        repeatable table row, clones it len(components) times (order preserved), fills each
        clone from its components entry, inserts the clones in place of the original row, and
        discards the original. Writes to tmp_dir/{document_id}.docx, returns a GeneratedDocument
        with verified=False.
        """
```

## Local tool schema (`ai_handler.py`)

```json
{
  "type": "function",
  "name": "generate_fee_agreement",
  "description": "Generates a fee agreement .docx from a template variant, filling in the exact placeholder values provided. Never call this with guessed or default values for any placeholder or inside any component's terms, and never pad or merge fee components to hit a particular count - if any required detail is unknown, ask the user first.",
  "parameters": {
    "type": "object",
    "properties": {
      "variant_id": {"type": "string", "description": "One of the known template variant ids."},
      "values": {
        "type": "object",
        "description": "Exact scalar placeholder name -> value map for the selected variant (excludes any repeating-group placeholders - those go in `components`). Must include every placeholder the variant declares, nothing else.",
        "additionalProperties": {"type": "string"}
      },
      "components": {
        "type": "array",
        "description": "ONLY for variants with a repeating fee-component group (currently multi_component_agreement) - omit entirely for every other variant. One entry per REAL, distinct fee component the user described - any N >= 2, never padded or merged to reach a particular count.",
        "items": {
          "type": "object",
          "properties": {
            "label": {"type": "string", "description": "Short name for this component, e.g. 'Referral Fee', 'Setup Fee', 'Monthly Retainer'."},
            "terms": {"type": "string", "description": "ONE free-text line, fully composed from what the user actually said - the amount, and (only if the user stated them) a percentage/commission, a cost-share split with a named partner, and/or the specific payer entity if different from the main Client. If the component matches one of manifest.json's repeating_group.example_terms patterns, follow that pattern's phrasing/structure filling in the real facts; otherwise compose an equally natural free-text line of your own - the examples are guidance, not a closed set. Never invent any detail not actually discussed, in either case. Example: '15% of the collected amount, split 50/50 with Partner Cohen, payable by the Client upon receipt.'"}
          },
          "required": ["label", "terms"]
        },
        "minItems": 2
      }
    },
    "required": ["variant_id", "values"]
  }
}
```

RBAC: attached only when the acting role is GODFATHER or ADMIN (same gate as reminders/Morning
MCP tools). **Creates a `PendingLocalToolApproval` over the `variant_id`/`values`/`components`
payload before generating anything** (human-confirmed 2026-09-12, research.md §4) — same UX as
`create_reminder`/`modify_reminder`/`delete_reminder`: the AI's proposed values (and, for a
multi-component request, the full itemized component list) are shown to the user for
confirmation, and `DocTemplateEngine.generate()` only actually runs once the human approves
(typed reply or button tap, via the existing `PendingLocalToolApprovalManager` resolution path in
`get_response()`/`resolve_button_tap()`). Once approved and generated, the document's own release
(send) is gated only by `verify_fee_agreement_document` (see `fee-agreement-verification.md`) —
no second human approval on the finished file.

## Error Handling
- Unknown `variant_id` / mismatched `values` or `components` shape / empty value / wrong
  `components` length for the variant → tool-call error result (a message string back to the
  model, not a Python exception surfacing to the user) so the model can ask a clarifying question
  and retry, per REQ-083-02.
- `python-docx` load/write failure (corrupt template, disk full, etc.) → logged (technical detail
  in logs only, per CONSTITUTION retry/error-handling rules) and surfaced to the model as a
  generic "document generation failed" tool error — no user-facing friendly-error text is needed
  at this layer, since the model composes the actual user-facing message.
