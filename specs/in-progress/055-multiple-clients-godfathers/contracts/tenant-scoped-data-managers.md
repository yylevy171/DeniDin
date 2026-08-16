# Integration Contracts: Tenant-Scoped Data Managers

**Feature**: 055-multiple-clients-godfathers · Per METHODOLOGY.md §VII format.

Added during `speckit.analyze` remediation (finding G3) — the underlying work was already
covered by `tasks.md` T009-T011, but METHODOLOGY §VII requires the contract itself to be
written down, not just implied by task descriptions. Covers the three managers whose data
roots become `tenant_id`-partitioned (`data-model.md`).

---

### Core Conversation Pipeline ↔ `SessionManager` Contract (extension)

**Callers (`denidin.py`, `AIHandler`) MUST**:
- Pass `tenant_id` to every `SessionManager` call that today takes only `chat_id`/`user_phone`
  — `get_session`, `add_message`, and friends all gain this parameter.

**`SessionManager` PROVIDES**:
- Session files rooted at `{environment_data_root}/{tenant_id}/sessions/...` instead of
  `{environment_data_root}/sessions/...` — same file format/naming beneath that root, unchanged.
- Two tenants' sessions for the same `chat_id` value (should not normally collide, since
  `chat_id`s are Green-API-instance-scoped, but not guaranteed impossible across two different
  instances) never read/write each other's files.

**`SessionManager` EXPECTS**: `tenant_id` is always present and valid (same standing
expectation as every other tenant-scoped component, `research.md` §2).

---

### Core Conversation Pipeline / `MemoryManager` Contract (extension)

**Callers MUST**:
- Pass `tenant_id` to `MemoryManager.recall`/write-path calls.

**`MemoryManager` PROVIDES**:
- ChromaDB collection names/paths partitioned by `tenant_id` (e.g.
  `{tenant_id}_memory_{entity_id}`/`_public`/`_private`, exact naming a `speckit.implement`
  decision) — a recall for tenant A's entity never surfaces tenant B's memories even for
  semantically similar content or a colliding `entity_id`.

**`MemoryManager` EXPECTS**: `tenant_id` always present and valid.

---

### `AIHandler`'s `capture_ledger_event` tool ↔ `ledger_event_manager` Contract (extension)

**`AIHandler` MUST**:
- Pass `tenant_id` when invoking `ledger_event_manager`'s write path.

**`ledger_event_manager` PROVIDES**:
- Events written under `{environment_data_root}/{tenant_id}/events/{event_id}.json` instead of
  `{environment_data_root}/events/{event_id}.json` — `event_id` format itself (source-type
  letter + `DDMMYY` + `HHMM` + sequence digit) is unchanged; uniqueness is still guaranteed
  within one tenant's own event stream (cross-tenant `event_id` collisions are possible in
  principle but harmless, since the two events live under different tenant directories).

**`ledger_event_manager` EXPECTS**: `tenant_id` always present and valid.
