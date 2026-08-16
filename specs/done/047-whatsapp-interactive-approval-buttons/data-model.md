# Data Model: WhatsApp Interactive Buttons for the Approval Gate

**Feature**: 047-whatsapp-interactive-approval-buttons

All changes are to existing in-memory entities — no new persisted storage, no migration.

## `PendingApproval` (extended)

`src/managers/pending_approval_manager.py` — existing dataclass, one new field:

| Field | Type | Existing/New | Notes |
|---|---|---|---|
| `response_id` | `str` | existing | unchanged |
| `approval_request_id` | `str` | existing | unchanged |
| `tool_name` | `str` | existing | unchanged |
| `arguments` | `str` | existing | unchanged |
| `server_label` | `str` | existing | unchanged |
| `created_at` | `str` | existing | unchanged |
| `sent_message_id` | `Optional[str]` | **NEW**, default `None` | The WhatsApp `idMessage` returned by `sendInteractiveButtons` for the buttons message presenting *this* pending approval. `None` from creation until `PendingApprovalManager.attach_sent_message_id` is called after a successful send (see contracts/whatsapp-buttons-send.md for why creation and send are two separate steps). A tap whose `stanzaId` doesn't equal this field is stale by definition — including the case where it's still `None` (send hasn't completed/attached yet, so no tap for it could legitimately exist). |

## `PendingApprovalManager` (extended)

One new method, alongside the existing `get`/`set`/`clear`:

```python
def attach_sent_message_id(self, chat_id: str, id_message: str) -> None:
    """Records the WhatsApp idMessage of the just-sent buttons message for chat_id's
    currently pending approval, if one still exists. No-op (logged) if the pending
    approval was already resolved/cleared/replaced before this call landed - that's a
    real possible race (e.g. a very fast text-based decline arriving before the send's
    own response returns), not an error; the attach is simply irrelevant at that point."""
```

- Does **not** raise if there's no pending approval for `chat_id`, or if the one present is a
  *different* approval than the one this `id_message` belongs to (can't be distinguished from
  the outside anyway — the caller only has one pending approval per chat to attach to, by
  construction). Logs at `info` either way, matching the existing `get`/`set`/`clear` logging
  style (`[022]`-prefixed).

## New module-level constants (`pending_approval_manager.py`)

```python
BUTTON_ID_APPROVE = "denidin_approve"
BUTTON_ID_DECLINE = "denidin_decline"
```

Stable identifiers sent as `buttonId` and matched against `selectedId` on the tap reply — never
the display label (`"כן"`/`"לא"`, per spec.md Clarifications), which is presentation only and
confirmed (Gate Zero) to live in a separate field (`selectedDisplayText`).

## `AIResponse` (extended)

`src/models/message.py` — one new field, same style as the existing `should_reply` (Feature
039):

| Field | Type | Default | Notes |
|---|---|---|---|
| `offer_approval_buttons` | `bool` | `False` | Set `True` by `AIHandler` exactly when this turn's response just created a new pending approval (same point `PendingApproval` is first `set()`, existing `ai_handler.py` ~line 1591) — signals `WhatsAppHandler` to send via `sendInteractiveButtons` instead of plain text. Never `True` at the same time as `should_reply=False` (a turn that owes no reply can't simultaneously be offering approval buttons for one — not a real code path, not enforced as a new invariant beyond what `__post_init__` already checks for `should_reply`/text). |

## New `AIHandler` method: `resolve_button_tap`

Not a new persisted entity, but the new resolution path alongside `_resolve_pending_approval`.
**Implementation note (as-built, 2026-08-14)**: rather than reimplementing approve/decline
resolution, this does its own `stanza_id` staleness check and then *delegates* to the existing
`get_response`/`_resolve_pending_approval` pipeline via a synthetic `"כן"`/`"לא"` `AIRequest` —
see contracts/button-tap-resolution.md for the full rationale (genuinely zero duplicated
approve/decline logic, and a button decline inherits the exact same fresh-turn fallthrough
behavior a typed `לא` already has today).

```python
def resolve_button_tap(
    self, chat_id: str, selected_id: str, stanza_id: str, message_id: str,
    user_phone: Optional[str], sender: Optional[str],
) -> Optional[AIResponse]:
    """Resolves a button tap against chat_id's pending approval, if the tap's stanza_id
    matches the message it was actually sent as. Returns None (caller sends nothing -
    clarify: silent) if there's no pending approval, or its sent_message_id doesn't equal
    stanza_id (stale/superseded tap). Otherwise synthesizes a "כן"/"לא" AIRequest and
    delegates to get_response/_resolve_pending_approval verbatim, driven by
    selected_id == BUTTON_ID_APPROVE rather than parsed free text."""
```

## State transitions (unchanged shape, one new dimension)

The existing Feature 022 state machine (per-`chat_id`: no pending → pending → resolved
[approved/declined] → no pending) is unchanged. What's new is purely about *which* replies are
eligible to resolve a pending approval:

```
                    ┌─────────────────────────────┐
                    │  no pending approval         │
                    └──────────────┬───────────────┘
                                    │ mcp_approval_request in OpenAI response
                                    ▼
                    ┌─────────────────────────────┐
                    │  pending, sent_message_id=None │  (buttons not yet sent/attached)
                    └──────────────┬───────────────┘
                                    │ sendInteractiveButtons succeeds
                                    ▼
                    ┌─────────────────────────────┐
                    │  pending, sent_message_id=X  │
                    └──┬───────────────────────┬───┘
       tap: stanzaId==X │                       │ typed "כן"/"לא"/etc. (unchanged, always works)
                        ▼                       ▼
              resolve (approve/decline)   resolve (approve/decline)
                        │                       │
                        └───────────┬───────────┘
                                    ▼
                    ┌─────────────────────────────┐
                    │  no pending approval          │  (cleared)
                    └─────────────────────────────┘

  tap: stanzaId != X, or no pending approval at all → silently ignored, no state change
```
