# Contract: Capability Resolution Loop (supersedes tool-driven-loop.md's use_capability/note)

Status: implemented 2026-09-24; flows level added 2026-09-25.

## Model-facing tools
- `load_flows(flows[])` / `unload_flows(flows[])` — always plural (one item is fine; several flows may be combined). A flow is a blueprint (`config/prompts/flows/<tag>.md`): which capabilities to load, in what order, how they connect — flow level only. Loading a flow attaches its blueprint text, NOT its capabilities; the model loads those itself. Idempotent.
- `load_capabilities(capabilities[])` / `unload_capabilities(capabilities[])` — always plural. From the NEXT round, each capability's prompt (in `instructions`) and real tools are attached. Idempotent. (Replaces the singular `load_capability`/`unload_capability`.)
- `reset_to_backbone()` — clears BOTH sets.
- Unknown names are reported back in the tool result (never silently dropped).
- **No default/fallback flow**: the backbone tells the model that if no flow fits it loads capabilities at its own discretion.
- Resolve/lookup mechanics (client resolution, fresh document lookup, download link, reminder identification) live in flows and the backbone, never in write-capability prompts — write capabilities only write.
- `record_planning_status(...)`, `approval_with_yes_no_buttons(text)`, `send_to_user(text)`, plus `send_progress_update` / `react_to_message`.
- There is no `use_capability`, no `note`, no "initial call" concept.

## State
- `Session.active_capabilities: List[str]` and `Session.active_flows: List[str]`, persisted (`SessionManager.set_active_capabilities` / `set_active_flows`), survive turns and restarts.
- `instructions` AND `tools` are rebuilt from that set on every API call (`previous_response_id` retains neither).
- `last_active` is refreshed by any message sent or received.

## Idle reset
- Top-level config `capabilities_reset_minutes` (int, 0 = off; not a feature flag).
- `services/capability_reset_service.py`: own BackgroundScheduler, 1-minute IntervalTrigger; clears both sets of any session idle longer than the threshold. No user notice.

## Toolsets (`capabilities/toolsets.py`)
- Local function tools (reminders, ledger query, media analysis, docx): dispatched by the backbone via each capability's `dispatch_direct_tool_call`.
- Morning MCP tools (invoicing/client read+write): one MCP entry per loaded capability - same server URL/token, its own `server_label` (`<morning_server_label>-<capability>`, e.g. `morning-invoices-invoicing-read`) and its own fixed `allowed_tools`, `require_approval: "never"`, executed by OpenAI. Never one shared, widening entry: OpenAI lists a label's tools only once per `previous_response_id` chain, so tools added to an existing label mid-turn are never seen (T1, 2026-10-01, verified against the real API). Write approval is the plain `approval_with_yes_no_buttons` tool, never an MCP handshake.
- Ledger capture is not a capability: it is `denidin.py`'s shared post-turn recognition.
- Tool-name collisions across capabilities are out of scope.

## Flows (`backbone/flow_tags.py`, `config/prompts/flows/`)
`FlowTag`: `document_for_client`, `document_on_existing_document`, `new_client`, `update_client`, `agreement_mentioned`, `fee_agreement_document`, `ledger_question`, `media_received`, `change_or_cancel_reminder`. Each has a few-sentence description (`FLOW_INFO`) rendered as the `## Flows` catalog in the instructions (capabilities likewise, `## Capabilities`), then each loaded flow's blueprint, then each loaded capability's prompt, then `## Loaded flows` / `## Loaded capabilities` lines. Ledger capture is neither a capability nor a flow (`agreement_mentioned` only states that recording happens automatically after the turn).

## Audit and debug logging (flows are the model's routing decisions — the most important thing to be able to reconstruct)
- Every load/unload/reset of flows or capabilities: INFO `[FLOW-AUDIT]` line (`utils/capability_audit_log.py::log_loading_action`) with action, kind, exactly what the model requested, the full resulting flow and capability sets, and the model's latest `record_planning_status` text (its stated reasoning); plus a DEBUG `[FLOW-DEBUG]` line with the same sets and counts.
- Idle-sweep resets are logged with the flows and capabilities that were cleared.
- Domain tool calls logged via `log_capability_action`; wire logs show `flows=` and `capabilities=` (from the Loaded lines) instead of full instructions (full text at DEBUG via `debug_wire`).

## Approvals and button taps (no regression from the legacy path)
- Which actions require approval, and which details the approval text must state, live in each write capability's prompt (cap_invoicing_write, cap_client_write, cap_reminders_write); the generic rules (real data only, missing detail = ask first, closing question `אישור — כן/לא?`, once, affirmative only) live in `backbone.md`. Code no longer builds the approval block.
- Write capabilities carry only write tools. Read capabilities are loaded by the model itself when it needs a lookup (backbone.md says so once, generically).
- Feature 047's stale-tap guard is preserved: `Session.approval_message_id` holds the idMessage of the outstanding approval-buttons message (recorded by denidin.py right after the send). `resolve_button_tap` treats a tap as live only if `stanzaId` equals it; a live tap is consumed and resolved as an ordinary "כן"/"לא" turn; anything else returns None (nothing sent). Any new turn clears it.
- `session_manager` is a required backbone dependency (no in-memory fallback).
