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

    def generate(self, variant_id: str, values: dict[str, str]) -> GeneratedDocument:
        """
        Raises ValueError if:
          - variant_id is unknown
          - values' keys don't exactly match the variant's declared placeholders
            (missing OR extra keys are both errors - no silent partial fill), EXCEPT
            for multi_component_agreement's optional COMPONENT_2_*/COMPONENT_3_* groups
            (see data-model.md "Variable-length component rows") - those may be omitted
            as a complete group, but a partial group (e.g. COMPONENT_2_NAME without
            COMPONENT_2_FEE) is still a validation error
          - any value is empty/whitespace-only (an empty string is not a legitimate
            answer to "what is the fee amount" - REQ-083-02)

        On success: loads the template via python-docx, replaces every {{PLACEHOLDER}}
        run-by-run in BOTH paragraphs and table cells (preserving surrounding
        formatting - SC-002), deletes any multi_component_agreement table row whose
        COMPONENT_N_* group was omitted from values, writes to
        tmp_dir/{document_id}.docx, returns a GeneratedDocument with verified=False.
        """
```

## Local tool schema (`ai_handler.py`)

```json
{
  "type": "function",
  "name": "generate_fee_agreement",
  "description": "Generates a fee agreement .docx from a template variant, filling in the exact placeholder values provided. Never call this with guessed or default values for any placeholder - if any required detail is unknown, ask the user first.",
  "parameters": {
    "type": "object",
    "properties": {
      "variant_id": {"type": "string", "description": "One of the known template variant ids."},
      "values": {
        "type": "object",
        "description": "Exact placeholder name -> value map for the selected variant. Must include every placeholder the variant declares, nothing else.",
        "additionalProperties": {"type": "string"}
      }
    },
    "required": ["variant_id", "values"]
  }
}
```

RBAC: attached only when the acting role is GODFATHER or ADMIN (same gate as reminders/Morning
MCP tools). **Creates a `PendingLocalToolApproval` over the `variant_id`/`values` payload before
generating anything** (human-confirmed 2026-09-12, research.md §4) — same UX as
`create_reminder`/`modify_reminder`/`delete_reminder`: the AI's proposed values are shown to the
user for confirmation, and `DocTemplateEngine.generate()` only actually runs once the human
approves (typed reply or button tap, via the existing `PendingLocalToolApprovalManager` resolution
path in `get_response()`/`resolve_button_tap()`). Once approved and generated, the document's own
release (send) is gated only by `verify_fee_agreement_document` (see
`fee-agreement-verification.md`) — no second human approval on the finished file.

## Error Handling
- Unknown `variant_id` / mismatched `values` keys / empty value → tool-call error result (a
  message string back to the model, not a Python exception surfacing to the user) so the model
  can ask a clarifying question and retry, per REQ-083-02.
- `python-docx` load/write failure (corrupt template, disk full, etc.) → logged (technical detail
  in logs only, per CONSTITUTION retry/error-handling rules) and surfaced to the model as a
  generic "document generation failed" tool error — no user-facing friendly-error text is needed
  at this layer, since the model composes the actual user-facing message.
