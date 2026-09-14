# Phase 1 Data Model: The Dynamic Capability Backbone (063)

No new persisted data entities — this is a structural/code refactor. The entities below are the
new *in-process* shapes introduced to make the Backbone-as-orchestrator architecture work; no
database schema, no new files under `data/`, no `LedgerEvent`/`Reminder` field changes.

---

## CapabilityTag (enum-like constant)

The canonical set of capabilities, fixing both the routing vocabulary and the per-step prompt
file lookup (R2/R3, REQ-063-06). Two kinds: **meta** (about orchestration itself) and **domain**
(business logic).

| Value | Kind | Domain | Mode | Prompt file | Manager/backing code |
|---|---|---|---|---|---|
| `intent_identification` | Meta | — | — | `config/prompts/capabilities/intent_identification.md` | none |
| `planning` | Meta | — | — | `config/prompts/capabilities/planning.md` | none |
| `invoicing_write` | Domain | Invoicing/Morning | Write | `config/prompts/capabilities/invoicing_write.md` | none (remote MCP) |
| `invoicing_read` | Domain | Invoicing/Morning | Read | `config/prompts/capabilities/invoicing_read.md` | none (remote MCP) |
| `ledger_capture` | Domain | Ledger Events | Capture | `config/prompts/capabilities/ledger_capture.md` | `managers/ledger_event_manager.py` (unmodified, shared with `AIHandler`) |
| `ledger_query` | Domain | Ledger Events | Query | `config/prompts/capabilities/ledger_query.md` | `managers/ledger_event_manager.py` (shared) |
| `reminders_write` | Domain | Reminders | Write | `config/prompts/capabilities/reminders_write.md` | `managers/reminder_manager.py` (unmodified, shared) |
| `reminders_read` | Domain | Reminders | Read | `config/prompts/capabilities/reminders_read.md` | `managers/reminder_manager.py` (shared) |
| `media_analysis` | Domain | Media | Extraction | `config/prompts/capabilities/media_analysis.md` | `handlers/extractors/{image,pdf,docx}_extractor.py` (unmodified, shared) |

Canonical order (the table's row order above) is the fixed reference order for REQ-063-06, though
under R2's step-by-step execution model each call carries at most one active `CapabilityTag`'s
content at a time (see `Backbone content` below) — canonical order now matters for cache-hit
*consistency of individual capability prompts*, not for concatenation order of a multi-capability
union (the original, superseded design).

**Validation rule**: a `CapabilityTag` value a Planning step names that isn't one of these 9 is
dropped (logged as a warning), never executed — an unrecognized tag must not silently expand what
prompt/tools a turn receives.

## Plan (Planning capability's output, R2)

```json
{"steps": [
  {"capability": "media_analysis", "note": "extract the incoming image"},
  {"capability": "ledger_capture", "note": "check if the extracted text describes a fee agreement or deposit"}
]}
```

- `steps`: `List[{capability: CapabilityTag, note: str}]`, may be empty (Backbone-only turn,
  AS-1's small-talk case — Intent Identification determined nothing further is needed), never
  `null`. Order is the actual execution order (unlike the old `ClassificationResult`, which had no
  ordering semantics) — a step may depend on a prior step's result (e.g. `ledger_capture` above
  needs `media_analysis`'s extracted text).
- Only ever contains **domain** `CapabilityTag`s — Intent Identification and Planning are
  themselves always the first two steps of *every* turn (implicit, not part of the `Plan` object
  they jointly produce) and are never named inside a `Plan`.
- Not persisted. Exists only for the duration of one turn's processing.
- On a Planning call failure (timeout, malformed JSON after retry): **fail open** — execute every
  domain capability the role has access to, in canonical order (equivalent to today's
  always-everything constitution), rather than fail closed to an empty plan. Silently dropping a
  capability the user actually needs is a worse failure mode than a temporarily larger set of
  calls. Logged as an ERROR either way.
- A step whose named capability the executing role isn't allowed (see RBAC below) is dropped
  before execution, logged as a WARNING — Planning is only ever told about the role's allowed
  capabilities in the first place (R2), so this should be rare, but the check is defense in depth.

## RBAC-filtered capability set (computed before Planning runs, not after)

`available_capabilities_for_planning = role_allowed_capabilities(user.role)`

`role_allowed_capabilities` mirrors today's `_assemble_tools` RBAC checks: `client`/`blocked`
roles never receive `invoicing_*`/`ledger_*`/`reminders_*` (those are godfather/admin-only today);
`media_analysis` follows the same media-message RBAC any role already has today (no new
restriction). `godfather`/`admin` receive the full domain set. Unlike the original (classifier)
design, this filtering happens **before** Planning is even invoked (R2) — Planning is told which
capabilities exist for this role, so it never proposes one the turn can't execute in the first
place, rather than proposing freely and being filtered after the fact.

## Backbone content (static, not per-turn)

A single loaded string, from the **new** `config/prompts/backbone.md` (not
`runtime_constitution.md`, which is untouched and stays exclusively `AIHandler`'s file). Loaded by
the new orchestrator's own mtime-cache mechanism, structurally mirroring but not sharing code with
`ai_handler.py`'s `_load_constitution`. Contains only the static behavioral constants listed in
`research.md` R4 — no routing/classification logic (that's Intent Identification/Planning's own
prompt content, loaded per-step like any other capability).

## Capability prompt content (per-capability, independently cached)

9 independently mtime-cached strings (2 meta + 7 domain), loaded from
`config/prompts/capabilities/<tag>.md` by the new orchestrator. For a given call in the plan
execution loop, exactly one capability's content is active — appended to the Backbone content for
that call only (R3) — plus the accumulated results of prior steps in the same plan, appended after
that (analogous to how `_build_instructions` appends memory context today).

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
  }
}
```

`denidin.py::initialize_app` reads `feature_flags.enable_capability_backbone` once at startup to
decide which handler class to construct, and — when true — also routes media-message dispatch
into the new orchestrator instead of `WhatsAppHandler.handle_media_message` directly (R2a);
`backbone_config` is only ever read by the new orchestrator, so a `dev` config that never sets the
flag needs no `backbone_config` block at all (pure addition, zero effect on the legacy path
either way).
