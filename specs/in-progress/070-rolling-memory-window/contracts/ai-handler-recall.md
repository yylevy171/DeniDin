# Contract: `AIHandler` recall path — daily-summary `top_k`

**Module**: `apps/denidin-app/src/handlers/ai_handler.py` (`create_request` → the memory recall
call → `_build_instructions`).
**Resolves**: analyze finding U1 — how `memory.longterm.daily_summary_top_k` (10) coexists with
the global `memory.longterm.top_k_results` (5).

---

## Current state (verified 2026-09-02)

- Recall happens **once per turn**, inside `AIHandler.create_request` (`ai_handler.py:~1597-1709`),
  not `get_response`.
- It is a single `MemoryManager.recall_with_rbac_filter(query, collection_names=[<the one per-chat
  collection>], top_k=<...>, min_similarity=<...>)` call. The per-chat collection
  (`collection_name_for_chat(chat)`) holds **both** legacy `session_summary` records **and**, after
  this feature, `daily_summary` records — they rank together in that one call.
- `top_k` for that call today comes from `config.memory['longterm']['top_k_results']` (5).
- The results are formatted into the `RECALLED MEMORIES` block appended to `instructions`
  (`_build_instructions`, `ai_handler.py:~1815-1873`).

## Contract

There is **no second recall call**. The change is minimal:

1. **The per-turn conversational recall call's `top_k` becomes
   `config.memory['longterm'].get('daily_summary_top_k', 10)`.** This is the call over the chat's
   own collection — the one that now surfaces daily summaries. Renaming intent: it is "the `top_k`
   for recalling this chat's own long-term memory (daily + session summaries)", and 5 is too small
   once each hit is a single day and a question can span weeks.
2. **`memory.longterm.top_k_results` (5) is left as the default for `MemoryManager.recall` /
   `recall_with_rbac_filter`** (the parameter default) and for **any other** recall call site.
   Grep confirms the conversational `create_request` recall is the only call site in
   `ai_handler.py` that feeds the `RECALLED MEMORIES` block; if a future call site recalls for a
   different purpose it keeps the 5 default unless it opts in.
3. `min_similarity` is unchanged (`config.memory['longterm']['min_similarity']`, 0.15 in real
   configs).
4. **RECALLED MEMORIES block placement** is a separate, Phase-0-gated question (plan-mode C,
   `research.md` D12) — this contract does not change the block's *format* or its content rules,
   only the `top_k` feeding it. If Phase 0's A/B moves the block from `instructions` into the
   first `input` item for prompt-cache reasons, that relocation is applied here too, verified by
   the Phase-0 functional-regression check; the `top_k` rule above is independent of where the
   block ends up.

## Config

`config.py` `memory_defaults['longterm']` gains `'daily_summary_top_k': 10` (already listed in
`data-model.md` §7). `config/config.*.json` add it under `memory.longterm`.

## Test

`test_recall_surfaces_daily_summary.py` (Phase 2, integration): seed 12+ `daily_summary` records
across 3 weeks for a chat + a couple of legacy `session_summary` records; ask (through
`bot.router`) a question whose answer is in the oldest daily summary; assert it appears in the
`RECALLED MEMORIES` block — which requires `top_k >= ` its rank, i.e. proves 5 would have dropped
it and 10 keeps it. A unit assertion pins that the recall call receives `top_k=10` from config and
that the `MemoryManager.recall` default parameter is still 5.
