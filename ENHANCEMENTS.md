# Enhancements Backlog

## Deployment & Operations

### Fix run_denidin.sh and stop_denidin.sh Scripts
**Priority:** High  
**Status:** Pending

**Problem:**
The `run_denidin.sh` and `stop_denidin.sh` scripts currently don't work properly:
- Bot process exits immediately when started via script (background execution fails)
- Script reports "Bot failed to start" even though logs show it started
- Process doesn't stay alive when detached from terminal
- Multiple bot instances can be created despite single-instance checks

**Root Causes:**
1. Background process execution with redirected stdin/stdout causes premature exit
2. `disown` alone not sufficient to keep process alive
3. Verification timing (3-second sleep) may be insufficient
4. Bot may be exiting when stdin is closed

**Proposed Solutions:**

1. **Use screen/tmux for process management:**
   - Start bot in detached screen/tmux session
   - More reliable than nohup/disown
   - Allows attaching to view live output
   - Cons: Requires screen/tmux installed

2. **Create proper daemon with double-fork:**
   - Implement proper daemonization in Python or shell
   - Fully detach from terminal session
   - Handle all signal forwarding properly
   - Cons: More complex implementation

3. **Use systemd/launchd for process management:**
   - Rely on OS service manager instead of custom scripts
   - Better for production deployment anyway
   - Cons: Not portable across dev/prod environments

4. **Fix background execution with proper I/O handling:**
   - Investigate why stdin closure causes exit
   - May need to modify bot code to handle detached mode
   - Add `--daemon` flag to denidin.py for proper background mode
   - Cons: Requires bot code changes

**Recommendation:** Option 4 (fix background execution) or Option 1 (use screen/tmux) for simplicity.

**Files to fix:**
- `run_denidin.sh` - Background process startup
- `stop_denidin.sh` - Graceful shutdown
- Possibly `denidin.py` - Add daemon mode support

## Memory System

### Prevent Duplicate Message Storage in Long-Term Memory
**Priority:** Medium  
**Status:** Pending

**Problem:**
Currently, `/reset` command stores the entire conversation history to ChromaDB each time it's called. If a user calls `/reset` multiple times during the same session, the same messages get stored repeatedly with different UUIDs, leading to:
- Redundant storage (messages 1-26 stored, then messages 1-30 including duplicates)
- Duplicate results in semantic search
- Increased storage costs

**Proposed Solutions:**

1. **Message-level hashing approach:**
   - Store each message individually with a deterministic ID (hash of sender + timestamp + content)
   - Before storing, check if message hash already exists in ChromaDB
   - Only store net-new messages on each `/reset`
   - Pros: Granular deduplication, incremental storage
   - Cons: More complex implementation, more ChromaDB operations

2. **Remove `/reset` command, rely on automatic expiration:**
   - Remove manual `/reset` command entirely
   - Only transfer sessions to long-term on 24h expiration
   - Sessions naturally expire once, preventing duplicates
   - Pros: Simple, no duplicate risk
   - Cons: Users can't manually trigger storage

3. **Track last transferred message index:**
   - Add `last_transferred_message_id` to session metadata
   - On `/reset`, only transfer messages after last transferred
   - First `/reset`: stores messages 1-26, marks message 26
   - Second `/reset`: stores only messages 27-30
   - Pros: Incremental, preserves `/reset` functionality
   - Cons: Requires session metadata updates

**Recommendation:** Option 3 (incremental transfer with tracking) provides best balance of functionality and deduplication.

**Files to modify:**
- `src/handlers/ai_handler.py` - `transfer_session_to_long_term_memory()`
- `src/models/state.py` - Add `last_transferred_message_num` to `ChatSession`
- `tests/unit/test_ai_handler_memory.py` - Test incremental transfer
