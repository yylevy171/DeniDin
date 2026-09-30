# Phase 1 Data Model: The Dynamic Capability Backbone (063)

No new persisted data entities — this is a structural/code refactor. The entities below are the
new *in-process* shapes introduced to make the Backbone-as-orchestrator architecture work; no
database schema, no new files under `data/`, no `LedgerEvent`/`Reminder` field changes.

---

## CapabilityTag (enum-like constant)

The canonical set of capabilities the model can `load_capabilities`. There are no meta
capabilities: the orchestrator is one tool-driven loop (`contracts/capability-resolution-loop.md`).

| Value | Domain | Mode | Prompt file | Tools / backing code |
|---|---|---|---|---|
| `cap_invoicing_write` | Invoicing/Morning | Write | `cap_invoicing_write.md` | Morning MCP tools (shared MCP entry, `require_approval:"never"`) |
| `cap_invoicing_read` | Invoicing/Morning | Read | `cap_invoicing_read.md` | Morning MCP tools |
| `cap_client_write` | Morning clients | Write | `cap_client_write.md` | Morning MCP tools (`add_client`/`update_client`) |
| `cap_client_read` | Morning clients | Read | `cap_client_read.md` | Morning MCP tools |
| `cap_ledger_query` | Ledger Events | Query | `cap_ledger_query.md` | local `query_ledger_events` (`managers/ledger_event_manager.py`, shared, unmodified) |
| `cap_reminders_write` | Reminders | Write | `cap_reminders_write.md` | local create/modify/delete tools (`managers/reminder_manager.py`) |
| `cap_reminders_read` | Reminders | Read | `cap_reminders_read.md` | local `list_reminders` |
| `cap_media_analysis` | Media | Extraction | `cap_media_analysis.md` | local `analyze_media` (`handlers/extractors/*`, shared, unmodified) |
| `cap_docx_write` | Fee agreement docs | Write | `cap_docx_write.md` | local docx tools |

All prompt files live under `config/prompts/capabilities/`. Tool mapping is authored once in
`src/capabilities/toolsets.py`.

**Validation rule**: a capability name passed to `load_capabilities`/`unload_capabilities` (an array) that isn't
one of these tags is rejected with an error result to the model, never silently accepted.

## Loaded-capability set (persisted)

`Session.active_capabilities: List[str]` — the growing set of loaded capability tags for the
chat, persisted via `SessionManager.set_active_capabilities`, surviving turns and restarts.
`load_capabilities` adds, `unload_capabilities` removes, `reset_to_backbone` clears all (and the parallel `Session.active_flows`, managed by `load_flows`/`unload_flows`, see `FlowTag` in `backbone/flow_tags.py`); the
idle sweep (`capabilities_reset_minutes`, `services/capability_reset_service.py`) clears any
session idle longer than the threshold. `instructions` AND `tools` are rebuilt from this set on
every API call (`previous_response_id` retains neither).

## Backbone content (static, not per-turn)

A single loaded string, from the **new** `config/prompts/backbone.md` (not
`runtime_constitution.md`, which is untouched and stays exclusively `AIHandler`'s file). Loaded by
the new orchestrator's own mtime-cache mechanism, structurally mirroring but not sharing code with
`ai_handler.py`'s `_load_constitution`. Contains only the static behavioral constants listed in
`research.md` R4 — no routing/classification logic (the model chooses capabilities itself via
`load_flows`/`load_capabilities`).

## Capability prompt content (per-capability, independently cached)

10 independently mtime-cached strings, loaded from `config/prompts/capabilities/<tag>.md`. Each
round's `instructions` = Backbone content + a `## Loaded capabilities` section (tag list, or
`(none - plain backbone)`) + the prompt of every loaded capability, in canonical order, + memory
context and today's date after that.

## Config additions (`models/config.py`)

`constitution_config` (used by `AIHandler`) is **untouched** — still `{file:
"runtime_constitution.md", base_dir: "config"}`, unmodified. A new, separate config section is
added for the new orchestrator:

```jsonc
{
  "feature_flags": {
    "enable_capability_backbone": false     // NEW — selects AIHandler (false) vs. new orchestrator (true)
  },
  "backbone_config": {                       // NEW — parallel to constitution_config, only read
    "file": "backbone.md",                   //   when the flag is on; AIHandler never reads this
    "base_dir": "config",
    "prompts_dir": "prompts",                // NEW — relative to base_dir: config/prompts/
    "capabilities_dir": "capabilities"       // relative to prompts_dir: config/prompts/capabilities/
  },
  "capabilities_reset_minutes": 60           // NEW — top-level (not a flag): idle minutes before the loaded set clears; 0 = off
}
```

`denidin.py::initialize_app` reads `feature_flags.enable_capability_backbone` once at startup to
decide which handler class to construct, and — when true — also routes media-message dispatch
into the new orchestrator instead of `WhatsAppHandler.handle_media_message` directly (R2a);
`backbone_config` is only ever read by the new orchestrator, so a `dev` config that never sets the
flag needs no `backbone_config` block at all (pure addition, zero effect on the legacy path
either way).
