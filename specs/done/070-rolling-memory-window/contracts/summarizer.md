# Contract: `summarizer.summarize_conversation`

**Module (new)**: `apps/denidin-app/src/handlers/summarizer.py`
**Consumers**: `daily_summary_roll_service`, `apps/rolling-memory-backfill`.

Lifts the call shape of the (deleted) `AIHandler.transfer_session_to_long_term_memory`
(`ai_handler.py:~3915-4017`) into a module-level function usable without an `AIHandler` instance.

---

## `summarize_conversation(client, model: str, messages: List[Dict]) -> str`

| Param | Contract |
|---|---|
| `client` | An OpenAI client (`openai.OpenAI(...)`). The caller owns construction / `max_retries`. |
| `model` | `config.ai_model` (`gpt-5.6-luna`). |
| `messages` | Oldest-first list in the shape `get_messages_for_local_date` / `get_rolling_window` return (has at least `role` and `content`; group items may carry the `[sender_name]` prefix already). Never empty (the caller skips empty days before calling). |

**Behavior**:

1. Render `messages` to a transcript string `conv_text` (`f"{role}: {content}"` per line, the same
   rendering the retired method used).
2. `resp = client.responses.create(model=model, instructions=<the existing summarizer instruction
   string, lifted verbatim>, input=f"Summarize this conversation...\n\n{conv_text}",
   max_output_tokens=1000)`.
3. On success → return `resp.output_text.strip()`.
4. On any exception from the call → log `WARNING` and return the **raw transcript** `conv_text`
   (the existing `used_fallback=True` degradation). This function therefore does **not** raise for
   an ordinary OpenAI failure.
   - *Exception*: if the caller needs to distinguish "summary failed, retry the day later" from
     "fallback used", the roll service treats a returned fallback the same as a real summary
     (it is still a durable, useful record) — REQ-MEM-025's "retry" case is reserved for the
     summary call raising **before** any string is produced (network down, auth error), which the
     fallback path also catches. To keep REQ-MEM-025 semantics, `summarize_conversation` MAY accept
     an optional `raise_on_failure: bool = False`; the roll service passes `False` (fallback is
     fine), and a future stricter caller can pass `True`. Implementer's call — keep it simple;
     `False`-only is acceptable for this feature since a fallback transcript is a valid daily
     record.

**No side effects.** Does not embed, does not write ChromaDB, does not touch roll markers — the
caller does all persistence.

**No new prompt.** The instruction string is the existing session-summary one, unchanged (D13,
Out of Scope forbids prompt-format churn).
