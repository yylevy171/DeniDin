# Contract: `WhatsAppHandler` ↔ Green API `sendFileByUpload`

## Purpose
Delivers a verified `GeneratedDocument`'s `.docx` file directly into the WhatsApp chat as a
document attachment (REQ-083-05), then cleans up the temp file.

## Interface

```python
class WhatsAppHandler:
    def send_document_response(
        self,
        notification: Notification,
        document: GeneratedDocument,
        caption: Optional[str] = None,
    ) -> bool:
        """
        Preconditions: document.verified is True (raises ValueError otherwise - see
        fee-agreement-verification.md contract).

        Calls bot.api.sending.sendFileByUpload(chatId, file=document.temp_path,
        fileName=<derived from variant + client, e.g. "Fee_Agreement_<Client>.docx">,
        caption=caption) - NEEDS CONFIRMATION of exact method/kwarg names against the
        installed whatsapp-api-client-python version, per research.md #1.

        Retry policy: one retry on 5xx/timeout after 1s (CONSTITUTION), never on 4xx.

        On success: deletes document.temp_path, sets document.sent = True, returns True.
        On final failure (after retry exhausted): deletes document.temp_path regardless
        (SC-003 - no leaked files even on failure), logs the technical error, returns
        False so the caller can surface a friendly error message to the user
        ("[emoji] Couldn't send the agreement file. [what to do next]." per CONSTITUTION's
        user-facing-error format) rather than claiming success.
        """
```

## Audit logging
Every outbound document send goes through the existing `utils/whatsapp_audit_log.py`
`log_outbound` call site (no new, separate audit mechanism), same as every other real outbound
send today.

## Integration with the tool-call flow
This is **not** itself exposed as an AI-facing tool — sending is a `denidin.py`/`AIHandler`
finalization-boundary action, the same architectural layer that already turns an `AIResponse`
into an actual WhatsApp send in the existing message flow (`WhatsAppHandler.send_response()`).
The model's role ends at calling `verify_fee_agreement_document` and returning a response that
signals "release this document" (a new `AIResponse` field, e.g. `deliver_document:
Optional[GeneratedDocument]`, parallel to `offer_approval_buttons`); `denidin.py`'s existing
finalization path calls `send_document_response()` when that field is set, exactly the way it
already calls `send_response()`/interactive-buttons sends today. This keeps "an AI tool call
directly hits an external network API with no application-level checkpoint" from being introduced
as a new pattern.

## Live verification requirement
Per research.md #2 (Gate Zero), this contract is not considered fulfilled by unit tests against a
mocked Green API client alone — a real, human-approved live send in `dev` is required before this
path ships to `prod`.
