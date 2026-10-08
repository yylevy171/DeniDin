# Feature 100: Stateless Client Resolution Caching

## 1. Background & The Problem
The Backbone architecture dictates that the LLM operates in a strictly stateless manner across turns. When a user workflow spans multiple turns (e.g., querying a client, receiving 5 candidates, selecting one via a lazy shorthand like "רביבו", and then requesting to generate a document), each interim update or interaction ends a turn and drops the working context.

Because the system forgets the client candidates between turns, the LLM relies purely on conversational inference to recover its state. This leads to **redundant global searches**:
1. The user asks for a client (e.g., "יהושע").
2. `resolve_client_name` returns 5 candidates.
3. The LLM asks the user to clarify.
4. The user says "רביבו".
5. The LLM infers this means "יהושע רביבו" and performs a **redundant** `resolve_client_name` lookup on "יהושע רביבו" to get the exact match.
6. The user then asks to generate a document. The LLM drops context again, infers the client from the history, and performs **another redundant** `resolve_client_name` lookup on "יהושע רביבו".

*Why not just save the active client in the session state?*
As demonstrated in the "הדס" vs "נועה" test: If the system maintains a stateful `active_client` (e.g., setting it to "נועה" from the last query) and the user blindly uploads an image meant for "הדס", the stateful backend would blindly attribute the document to "נועה" without confirmation. The system MUST remain stateless to prevent cross-turn misattribution.

## 2. Evidence from Production Logs
(See attached `dev_trace_yehoshua.md` and `dev_trace_yossi.md` in this directory for exact LLM reasoning traces).

In the logs from 2026-10-06, we see the LLM repeatedly guessing the full name from user shorthand and re-running `resolve_client_name`. It is forced to do this because it has no deterministic way to link the user's shorthand directly to the previously retrieved candidates without re-running the global search tool.

## 3. The Solution: Prompt-Injected Resolution Cache
Instead of forcing the backend to track the active client for downstream tools (which breaks the stateless architecture), we provide the LLM with a highly reliable lookup table of exact names it has already resolved.

### A. The Backend Cache (Session State)
When the `resolve_client_name` tool returns a definitive, exact match (e.g., successful resolution to a single client), the backend intercepts this and appends a record to a short-term cache in the `Session` object:
```json
{
  "input": "מור פלומבו", 
  "resolved": "מור פלימבו"
}
```

### B. Prompt Injection
The Backbone (or Session Manager) injects this list directly into the LLM's system prompt (e.g., via the active capabilities or planning notes):
```markdown
# Cached Resolved Clients
- Input: "מור פלומבו" -> Exact Name: "מור פלימבו"
- Input: "רביבו" -> Exact Name: "יהושע רביבו"
```

### C. LLM Instruction
A strict rule is added to the system prompt:
> "If a client name requested by the user is an EXACT verbatim match to either the `input` or the `resolved` value in the Cached Resolved Clients table, you MUST use the `resolved` value directly in all subsequent tools (such as `create_invoice` with `client_name="מור פלימבו", name_resolved=True`), and you MUST NOT call `resolve_client_name` again."

## 4. Why this works
- **No ID Leaks:** The backend tools (like `create_invoice` in the Morning MCP) only require the exact `client_name` as a string (they fetch the internal `client_id` silently during execution). The LLM never needs to see Morning IDs.
- **Statelessness Preserved:** The LLM retains its stateless architecture. If the user mentions a new name, it resolves it normally.
- **Redundancy Eliminated:** If the user uses a shorthand that perfectly matches a cached `input` or `resolved` string, the LLM skips the redundant `resolve_client_name` call and proceeds straight to the target tool.
- **Safety First:** Cross-turn misattribution is prevented because the short-circuit only occurs if the user explicitly provides an exact verbatim match to the cached input/output.
