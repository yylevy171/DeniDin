# Contract: `react_to_message` AI tool

**Location**: `apps/denidin-app/src/handlers/ai_handler.py`, alongside the other local
`type: "function"` tool constants (`CREATE_REMINDER_TOOL` etc.).

## Schema (OpenAI Responses API `type: "function"` shape)

```python
REACT_TO_MESSAGE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "react_to_message",
    "description": (
        "Attach or replace a native WhatsApp emoji reaction on a message. Pass an empty string "
        "for emoji to clear an existing reaction. Omit message_id (pass null) to react to the "
        "CURRENT user turn's incoming message; pass a known earlier message id to flip a "
        "reaction you or the system set earlier in this workflow (e.g. flipping a document's "
        "in-flight emoji to a final checkmark once its ledger capture is complete). This is "
        "purely cosmetic and reversible — a failure here is logged and never blocks your reply."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "emoji": {
                "type": "string",
                "description": "A single unicode emoji, or \"\" to clear the reaction.",
            },
            "message_id": {
                "type": ["string", "null"],
                "description": (
                    "The target message's id. Pass null to default to the current turn's "
                    "incoming message, or to the active document/action workflow's originating "
                    "message if one is open."
                ),
            },
        },
        "required": ["emoji", "message_id"],
        "additionalProperties": False,
    },
}
```

## Attachment (RBAC)

Attached **unconditionally, to every role** (client, godfather, admin) — unlike reminder/ledger
tools, this is not privileged: reacting to a message carries no financial, data-integrity, or
disclosure risk. (Group-chat scoping is enforced separately, at the fast-path/etiquette layer —
see `contracts/group-discretion-gating.md` — not via RBAC.)

## Dispatch

**No approval gate.** Unlike `create_reminder`/`modify_reminder`/`delete_reminder`
(`PendingLocalToolApprovalManager`), `react_to_message` dispatches **immediately** on
`function_call`, the same way `list_reminders`/`query_ledger_events` (read-only tools) dispatch
immediately — the spec explicitly frames reactions as cosmetic/reversible, so there is no
"the model might act on my behalf on something irreversible" concern an approval gate exists to
guard against.

Dispatch logic:
1. Resolve `message_id`, if `null`, via the fallback chain documented once in `data-model.md`:
   explicit arg → `Session.active_document_message_id` → current turn's
   `Message.whatsapp_id_message`.
2. Resolve `chat_id` from the active turn's context (same as every other local tool already does).
3. Call `send_reaction(bot, chat_id, resolved_message_id, emoji)` (see
   `contracts/green-api-reaction-client.md`) — never raises.
4. Return a `function_call_output` reporting `{"status": "ok"}` or `{"status": "failed"}` back to
   the model, so it can still phrase a normal reply either way (mirrors how
   `_run_local_tool_dispatch_loop` already reports outcomes for read-only tools) — the model is
   never blocked or made to retry the reaction call itself.

## Runtime constitution guidance (see `contracts/group-discretion-gating.md` for the full section)

The tool's own JSON-schema description is deliberately **not** treated as sufficient scoping, per
the CLAUDE.md "every new tool-bearing feature needs explicit constitution boundaries" rule — the
`## Reaction Management` section defines when to call this tool (document receipt, action
commands, warm sentiment) and when NOT to (trivial 1:1 acknowledgments, any message in a group chat
DeniDin isn't actually engaging with), independent of this schema.

## Testing

Unit: fallback-chain resolution logic in isolation (given various combinations of explicit arg /
`active_document_message_id` set-or-not / current-turn id, confirm the right one wins), against a
stubbed `send_reaction`.

Billed: a real conversational turn where the model is offered the tool and calls it — both the
"react to current message" (`message_id: null`) and "flip an earlier one" (`message_id` explicitly
set) shapes, confirming the correct id and emoji are passed through end to end.
