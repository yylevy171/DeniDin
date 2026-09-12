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
            (missing OR extra keys are both errors - no silent partial fill)
          - any value is empty/whitespace-only (an empty string is not a legitimate
            answer to "what is the fee amount" - REQ-083-02)

        On success: loads the template via python-docx, replaces every {{PLACEHOLDER}}
        run-by-run (preserving surrounding formatting - SC-002), writes to
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
MCP tools). Dispatches immediately — no `PendingLocalToolApproval` (see research.md §4).

## Error Handling
- Unknown `variant_id` / mismatched `values` keys / empty value → tool-call error result (a
  message string back to the model, not a Python exception surfacing to the user) so the model
  can ask a clarifying question and retry, per REQ-083-02.
- `python-docx` load/write failure (corrupt template, disk full, etc.) → logged (technical detail
  in logs only, per CONSTITUTION retry/error-handling rules) and surfaced to the model as a
  generic "document generation failed" tool error — no user-facing friendly-error text is needed
  at this layer, since the model composes the actual user-facing message.
