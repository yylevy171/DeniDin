# Contract: `memory_collections.collection_name_for_chat`

**Module (new)**: `apps/denidin-app/src/managers/memory_collections.py`
**Consumers**: `daily_summary_roll_service`, `AIHandler` (recall path), `apps/rolling-memory-backfill`.

The **single source of truth** for a chat's ChromaDB collection name. Fixes bugfix-035 H1
structurally: today the name is constructed ad-hoc in 3 places in `ai_handler.py`
(`f"memory_{chat.replace('@c.us','')}"`), one of which (`~4002`) then does a raw
`client.get_collection()` with the *unsanitized* name and throws `NotFoundError` for `@g.us`.

---

## `collection_name_for_chat(whatsapp_chat: str) -> str`

MUST reproduce the **existing prod collection names byte-for-byte** (verified live 2026-09-02):

| `whatsapp_chat` | returns |
|---|---|
| `972522968679@c.us` | `memory_972522968679` |
| `120363210094632983@g.us` | `memory_120363210094632983_at_g.us` |

Algorithm (matches how the names got created — `memory_{chat.replace('@c.us','')}` then
`MemoryManager.get_or_create_collection`'s inline sanitizer
`.replace('@','_at_').replace(':','_')`):

```
base = f"memory_{whatsapp_chat.replace('@c.us', '')}"
name = base.replace('@', '_at_').replace(':', '_')
return name
```

- `@c.us` chats: `@c.us` stripped, nothing left to sanitize → `memory_<number>`.
- `@g.us` chats: `@c.us` not present, so `@g.us` survives the strip, then `@` → `_at_` →
  `memory_<id>_at_g.us`.
- Any other shape: the two `.replace` calls make it collection-name-safe; never raises.

**Requirements**: this helper is used on **every** path that needs the name — the roll write, the
recall read, the backfill — and **no** caller may derive the name any other way or call
`client.get_collection()` with a raw chat id (REQ-MEM-022). A unit test
(`test_collection_name_helper.py`) pins the two prod names and the no-raise property; a static test
(`test_retired_paths_removed.py`) asserts 0 remaining ad-hoc `f"memory_{...}"` constructions and 0
raw `get_collection` calls in the roll/recall paths.
