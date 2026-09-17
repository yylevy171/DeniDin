# Contract: `verify_fee_agreement_document` tool

## Purpose
Gives the model the means to fulfil REQ-083-04 — the AI, not code, makes the final "is this
document correct and ready to send" determination, but the *evidence* it verifies against
(the generated document's actual extracted content) must come from a real read of the real file,
not from the model's memory of what it asked for.

## Interface

```python
class DocTemplateEngine:
    def verify(self, document_id: str) -> DocumentVerificationResult: ...

@dataclass
class DocumentVerificationResult:
    extracted_text: str            # full text content of the generated .docx (python-docx read)
    remaining_placeholders: list[str]  # any "{{...}}" tokens still present - should be empty
    values_found: dict[str, bool]      # each expected value -> whether it appears verbatim in the text
```

## Local tool schema (`ai_handler.py`)

```json
{
  "type": "function",
  "name": "verify_fee_agreement_document",
  "description": "Reads back a just-generated fee agreement document and reports its full text plus whether any template placeholders remain unfilled. You MUST call this after generate_fee_agreement and confirm the result is clean before ever sending the document to the user.",
  "parameters": {
    "type": "object",
    "properties": {
      "document_id": {"type": "string", "description": "The document_id returned by generate_fee_agreement."}
    },
    "required": ["document_id"]
  }
}
```

RBAC: same gate as `generate_fee_agreement`. Dispatches immediately, read-only, no
`PendingLocalToolApproval`.

## Contract with `send_document_response()`

`WhatsAppHandler`'s document-send path (see `whatsapp-file-delivery.md`) MUST check
`GeneratedDocument.verified is True` before calling Green API — this is a code-level guard, not
solely a prompt instruction, so that a model that skips the verify step (or ignores a
failed-verification result and tries to send anyway) cannot cause a bad document to reach the
client. `verified` is set to `True` only by a call to `verify()` that returned
`remaining_placeholders == []` and every entry in `values_found` `True`.

## Failure mode
If `remaining_placeholders` is non-empty, or any `values_found` entry is `False`, the tool result
tells the model exactly which placeholder(s)/value(s) failed, and the model is expected (per
`runtime_constitution.md`'s new section) to either retry `generate_fee_agreement` with corrected
values or ask the user for the missing/wrong detail — never to send a document that failed its
own verification.
