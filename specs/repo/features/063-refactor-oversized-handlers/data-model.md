# Phase 1 Data Model: The Dynamic Capability Backbone (063)

No new persisted data entities — this is a structural/code refactor. The entities below are the
new *in-process* shapes introduced to make the Backbone+Plugins architecture work; no database
schema, no new files under `data/`, no `LedgerEvent`/`Reminder` field changes.

---

## CapabilityTag (enum-like constant)

The canonical set of gated capability plugins, fixing both the routing vocabulary (R2) and the
constitution-append order (R3, REQ-063-06).

| Value | Domain | Mode | Constitution file | Manager |
|---|---|---|---|---|
| `invoicing_write` | Invoicing/Morning | Write | `config/capabilities/invoicing_write.md` | none (remote MCP) |
| `invoicing_read` | Invoicing/Morning | Read | `config/capabilities/invoicing_read.md` | none (remote MCP) |
| `ledger_capture` | Ledger Events | Capture | `config/capabilities/ledger_capture.md` | `capabilities/ledger_events/manager.py` |
| `ledger_query` | Ledger Events | Query | `config/capabilities/ledger_query.md` | `capabilities/ledger_events/manager.py` (shared) |
| `reminders_write` | Reminders | Write | `config/capabilities/reminders_write.md` | `capabilities/reminders/manager.py` |
| `reminders_read` | Reminders | Read | `config/capabilities/reminders_read.md` | `capabilities/reminders/manager.py` (shared) |

Canonical order (the table's row order above) is the fixed append order for REQ-063-06 — never
alphabetical or request-order, so that identical matched-sets across turns produce byte-identical
appended blocks regardless of what order the classifier happened to list them in.

**Validation rule**: a `CapabilityTag` value the classifier returns that isn't one of these 6 is
dropped (logged as a warning), never attached — an unrecognized tag must not silently expand what
prompt/tools a turn receives.

## ClassificationResult (pre-classifier call output, R2)

```json
{"capabilities": ["reminders_write", "ledger_query"]}
```

- `capabilities`: `List[CapabilityTag]`, may be empty (Backbone-only turn, AS-1's case), never
  `null`. Order as returned by the model is irrelevant — R3's canonical order governs assembly
  regardless.
- Not persisted. Exists only for the duration of one turn's processing (analogous to today's
  in-memory `tools` list built by `_assemble_tools`).
- On a classifier call failure (timeout, malformed JSON after retry): **fail open to the full
  legacy behavior for that turn** — attach all 6 plugins (equivalent to today's always-everything
  constitution) rather than fail closed to Backbone-only, since silently dropping a capability the
  user actually needs (e.g. an invoicing request landing with no Invoicing plugin attached) is a
  worse failure mode than a temporarily-oversized prompt. Logged as an ERROR either way.

## RBAC-filtered capability set

`effective_capabilities = ClassificationResult.capabilities ∩ role_allowed_capabilities(user.role)`

`role_allowed_capabilities` mirrors today's `_assemble_tools` RBAC checks: `client`/`blocked`
roles never receive `invoicing_*`/`ledger_*`/`reminders_*` (those tools are godfather/admin-only
today); `godfather`/`admin` receive the full 6. This intersection happens *after* classification,
so the classifier itself doesn't need to know about RBAC — same separation of concerns as today's
tool-assembly step.

## Backbone content (static, not per-turn)

A single loaded string, from the **new** `config/backbone.md` (not `runtime_constitution.md`,
which is untouched and stays exclusively `AIHandler`'s file). Loaded by the new orchestrator's own
mtime-cache mechanism, structurally mirroring but not sharing code with `ai_handler.py`'s
`_load_constitution`. Contains the always-on sections listed in research.md R4, plus the
pre-classifier's own routing instructions.

## Capability plugin content (per-plugin, independently cached)

6 independently mtime-cached strings, one per `CapabilityTag`, loaded from
`config/capabilities/<tag>.md` by the new orchestrator. Each is appended to the Backbone content,
in canonical order, only for the `effective_capabilities` set computed for that turn.

## Config additions (`models/config.py`)

`constitution_config` (used by `AIHandler`) is **untouched** — still `{file: "runtime_constitution.md",
base_dir: "config"}`, unmodified. A new, separate config section is added for the new orchestrator:

```jsonc
{
  "feature_flags": {
    "enable_capability_backbone": false     // NEW — selects AIHandler (false) vs. new orchestrator (true)
  },
  "backbone_config": {                       // NEW — parallel to constitution_config, only read
    "file": "backbone.md",                   //   when the flag is on; AIHandler never reads this
    "base_dir": "config",
    "capabilities_dir": "capabilities"       // relative to base_dir, e.g. config/capabilities/
  }
}
```

`denidin.py::initialize_app` reads `feature_flags.enable_capability_backbone` once at startup to
decide which handler class to construct; `backbone_config` is only ever read by the new
orchestrator, so a `dev` config that never sets the flag needs no `backbone_config` block at all
(pure addition, zero effect on the legacy path either way).
