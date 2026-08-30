# Contract: "Already Done" Journal Delivery to the Merged Turn

**Feature**: `feature/067-realistic-message-handling`
**Components**: `src/models/message.py` (`AIRequest`), `src/handlers/ai_handler.py`
(`instructions` assembly), `src/sources/intake_coordinator.py`, `config/runtime_constitution.md`,
`.github/METHODOLOGY.md`

---

## The field

`AIRequest` gains one field, fully defaulted:

```python
system_note: str = ""
```

- Empty for every existing caller — no behaviour change, no prompt change.
- Set by the live consumer only, when assembling the **merged** turn that follows a cancelled
  turn that had side effects.
- Opaque to `ai_handler` — it is placed verbatim into `instructions`, never parsed.

---

## Assembly point (`ai_handler.py`, `instructions` construction ~lines 363-368)

Current order (unchanged):

```
<constitution text>
<recalled memory context, appended to the constitution string>
---
<today's Israel-local date, computed fresh per call>
```

New: **if `request.system_note` is non-empty**, append after the date line:

```
<today's Israel-local date, computed fresh per call>

<request.system_note>
```

Rationale (D6): the constitution + memory + `---` + date prefix stays byte-identical to today,
so OpenAI's automatic prompt-cache prefix match is preserved. `system_note` is strictly a
suffix, present only on the rare merged-after-cancel turn.

`IT-2` asserts: with a `system_note` set, everything up to and including the date line is
byte-identical to the same request with no `system_note`; the note text appears only after it.

---

## Journal text shape (built by the coordinator/consumer, not the model)

From the `List[SideEffectRecord]` stashed as `carryover[chat_id]`. One header line + one bullet
per record, Hebrew, built from the record's structured `summary_he`:

```
[מערכת: הפעולות הבאות כבר בוצעו בתור קודם שבוטל, ואי אפשר לבטל אותן דרך הצ'אט. התייחס אליהן, ודווח עליהן למשתמש אם רלוונטי. אל תנסה לבצע אותן שוב.]
- נוצרה קבלה מס' 1234 עבור לקוח X על סך ₪500
- נרשם אירוע יומן: הסכם שכ"ט 10% מול Y
```

- Each bullet comes from `SideEffectRecord.summary_he`, which is assembled from
  `tool_name` + parsed `arguments`/`output` fields — **never** from model-authored prose.
- If `carryover[chat_id]` is empty, `system_note` stays `""` and nothing is appended.

---

## Lifecycle of `carryover[chat_id]` (REQ-RMH-015)

| Event | Coordinator action |
|---|---|
| cancelled `AIResponse` returns to the consumer | `record_side_effects(chat_id, response.side_effects_journal)` → `carryover[chat_id] = records` |
| consumer assembles the next merged text `WorkItem` | `WorkItem.carryover = carryover.get(chat_id, [])` → consumer builds `system_note` from it |
| merged turn's reply is **actually sent** (`send_response` succeeds) | `on_turn_finished(chat_id)` clears `carryover[chat_id]` along with `active_turn` / `pending_text` |
| merged turn is **itself** cancelled before its reply | new `record_side_effects` **appends** the newer records to the existing carryover (a burst can be cancelled more than once); the journal accumulates until a reply finally lands |

`carryover` is never persisted; a restart drops it (accepted — matches D3's crash window).

---

## `runtime_constitution.md` — new section (REQ-RMH-014, REQ-RMH-026)

A new section, **"Interrupted / Merged Turns"**, stating:

- The user may send several messages in a row before DeniDin answers. When that happens the
  system merges them and you get **one** combined instruction — treat the whole thing as a
  single request, and answer the **last** point raised (a short/ambiguous trailing message
  still answers the most recently pending question in the same context — cross-reference the
  "Contexts of Operation" general rule).
- You may receive a `[מערכת: ...]` note listing actions **already performed in a previous
  turn that was cancelled**. Those actions are real and cannot be undone from here. Factor
  them into your reply, report them to the user if relevant ("כבר הפקתי את הקבלה לפני
  שביקשת לבטל"), and **never re-attempt them**.
- This is not a tool you invoke and not a topic you can be "asked about" — it is passive
  context. If the merged text is ambiguous, ask; do not guess.

### Cross-references (REQ-RMH-027) — added to each existing tool-bearing section

- **Ledger Event Recognition**: a merged turn's combined text is one instruction; a ledger
  event already listed in a `[מערכת: ...]` note must not be re-captured.
- **Reminder Management**: same — a reminder already listed as done in a system note is not
  re-created; an ambiguous trailing message in a burst answers the pending reminder question,
  it does not start a new reminder action.
- **Invoice Management**: a Morning document listed in a `[מערכת: ...]` note was already
  created server-side in the cancelled turn — report it, never issue it again.

### `.github/METHODOLOGY.md`

Add a short §-reference entry for this feature's constitution section, mirroring the existing
§XXI entry for reminders (REQ-RMH-026).

---

## Immutability

- `AIRequest` gains a defaulted field; no existing construction site changes.
- The `instructions` prefix (constitution → memory → `---` → date) is unchanged byte-for-byte
  when `system_note == ""` — verified by IT-2 and by the existing prompt-cache-oriented tests.
