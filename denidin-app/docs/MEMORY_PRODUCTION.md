# Memory System - Production Enablement Guide

## Overview

This guide provides step-by-step instructions for enabling the memory system in production environments. The memory system is deployed behind a feature flag for safe, incremental rollout.

**Current Status**: Memory system code is merged to master, feature flag **DISABLED** by default.

---

## Prerequisites

Before enabling the memory system:

1. ✅ Bot running successfully in production (v1.0)
2. ✅ All 212 tests passing
3. ✅ Memory system code merged (PR #20)
4. ✅ ChromaDB dependency installed
5. ✅ Data directories created (`data/sessions/`, `data/memory/`)

---

## Rollout Strategy

### Phase 1: Test Environment (Week 1)

**Goal**: Validate memory system in isolated test environment

**Steps:**

1. **Enable in test config**
   ```bash
   cd /path/to/denidin-bot
   cp config/config.json config/config.prod.backup.json  # Backup
   ```

   Edit `config/config.json`:
   ```json
   {
     "feature_flags": {
       "enable_memory_system": true
     },
     "godfather_phone": "TEST_PHONE@c.us",
     "data_root": "data_test"
   }
   ```

2. **Start bot in test mode**
   ```bash
   ./run_denidin.sh
   ```

3. **Validation checklist**
   - [ ] Bot starts without errors
   - [ ] Session files created in `data_test/sessions/`
   - [ ] ChromaDB database created in `data_test/memory/`
   - [ ] Conversation history persists across messages
   - [ ] `/reset` command works
   - [ ] Session expiration triggers after 24h
   - [ ] Memory recall includes relevant context
   - [ ] No performance degradation (<500ms response time)

4. **Check logs**
   ```bash
   tail -f logs/denidin.log | grep -E "(session|memory|recall)"
   ```

   **Expected log patterns:**
   - `Session created: {session_id}`
   - `Added message to session: {message_id}`
   - `Recalled {count} memories`
   - `Session expired, transferring to long-term memory`

5. **Monitor metrics**
   - Response time: Should be <500ms (memory adds ~50-100ms)
   - Session count: `ls data_test/sessions/ | wc -l`
   - Memory count: Check ChromaDB collection size
   - Error rate: `grep ERROR logs/denidin.log | wc -l`

**Success Criteria:**
- ✅ All validation checks pass
- ✅ No errors in logs for 7 days
- ✅ Session/memory operations working as expected

### Phase 2: Godfather Only (Week 2)

**Goal**: Enable for admin user only in production

**Steps:**

1. **Update production config**
   ```json
   {
     "feature_flags": {
       "enable_memory_system": true
     },
     "godfather_phone": "ACTUAL_ADMIN_PHONE@c.us",
     "data_root": "data",
     "memory": {
       "session": {
         "max_tokens_by_role": {
           "client": 4000,
           "godfather": 100000
         }
       }
     }
   }
   ```

2. **Deploy update**
   ```bash
   git pull origin master
   ./stop_denidin.sh
   ./run_denidin.sh
   ```

3. **Godfather testing**
   - Send test messages from godfather phone
   - Verify 100K token limit vs client's 4K
   - Test `/reset` command
   - Check memory recall quality

4. **Monitor for 7 days**
   ```bash
   # Check session counts
   ls data/sessions/ | wc -l
   
   # Check memory database size
   du -h data/memory/
   
   # Monitor errors
   grep ERROR logs/denidin.log
   ```

**Success Criteria:**
- ✅ Godfather can access extended history (100K tokens)
- ✅ Memory recall relevant and accurate
- ✅ No impact on client users (still using stateless mode)
- ✅ No errors or performance issues

### Phase 3: Full Production Rollout (Week 3+)

**Goal**: Enable for all users

**Steps:**

1. **Final config validation**
   ```json
   {
     "feature_flags": {
       "enable_memory_system": true
     },
     "godfather_phone": "ADMIN_PHONE@c.us",
     "memory": {
       "session": {
         "max_tokens_by_role": {
           "client": 4000,
           "godfather": 100000
         },
         "session_timeout_hours": 24
       },
       "longterm": {
         "enabled": true,
         "top_k_results": 5,
         "min_similarity": 0.7
       }
     }
   }
   ```

2. **Gradual user enablement** (optional)
   - Monitor first 10 users for 24 hours
   - Expand to 50 users for 48 hours
   - Full rollout if no issues

3. **Post-deployment monitoring**
   ```bash
   # Session growth rate
   watch -n 60 'ls data/sessions/ | wc -l'
   
   # Memory database growth
   watch -n 300 'du -h data/memory/'
   
   # Active sessions
   find data/sessions/ -name "session.json" -mtime -1 | wc -l
   ```

**Success Criteria:**
- ✅ All users have working memory
- ✅ Session cleanup working (expired → long-term)
- ✅ No spike in errors or API costs
- ✅ User feedback positive

---

## Monitoring & Maintenance

### Daily Checks

```bash
# Check bot is running
ps aux | grep "[p]ython3 denidin.py"

# Check recent errors
tail -100 logs/denidin.log | grep ERROR

# Check session count
ls data/sessions/ | wc -l

# Check memory database size
du -h data/memory/
```

### Weekly Maintenance

```bash
# Clean up expired sessions (automatic, but verify)
find data/sessions/expired/ -mtime +30 -delete

# Check ChromaDB integrity
python3 -c "
from src.memory.memory_manager import MemoryManager
import json
with open('config/config.json') as f:
    config = json.load(f)
mgr = MemoryManager(
    storage_dir=config['memory']['longterm']['storage_dir'],
    collection_name=config['memory']['longterm']['collection_name'],
    embedding_model=config['memory']['longterm']['embedding_model'],
    openai_api_key=config['openai_api_key']
)
print(f'Memory count: {mgr.collection.count()}')
"

# Backup data
tar -czf backup_$(date +%Y%m%d).tar.gz data/
```

### Metrics to Track

| Metric | Target | Alert If |
|--------|--------|----------|
| Response time | <500ms | >1000ms |
| Session count | <1000 | >5000 |
| Memory database size | <500MB | >2GB |
| Error rate | <1% | >5% |
| Session expiration rate | ~95% auto-expire | <50% |

---

## Troubleshooting

### Issue: Memory not persisting

**Symptoms**: Sessions reset on bot restart

**Diagnosis:**
```bash
ls data/sessions/
# Should show session directories

cat data/sessions/{session_id}/session.json
# Should show message history
```

**Solutions:**
1. Check `data_root` config points to correct directory
2. Verify write permissions: `ls -la data/`
3. Check logs for save errors: `grep "save.*session" logs/denidin.log`

### Issue: ChromaDB errors

**Symptoms**: "Collection not found" or embedding errors

**Diagnosis:**
```bash
ls data/memory/
# Should show chroma.sqlite3

python3 -m pytest tests/integration/test_memory_integration.py -v
```

**Solutions:**
1. Delete and recreate: `rm -rf data/memory/ && mkdir -p data/memory/`
2. Check OpenAI API key for embeddings
3. Verify ChromaDB version: `pip show chromadb`

### Issue: High API costs

**Symptoms**: OpenAI bill increased significantly

**Diagnosis:**
```bash
# Count embedding calls
grep "embedding" logs/denidin.log | wc -l

# Check recall frequency
grep "recall" logs/denidin.log | wc -l
```

**Solutions:**
1. Reduce `top_k_results` from 5 to 3
2. Increase `min_similarity` from 0.7 to 0.8
3. Disable long-term memory: `"longterm": {"enabled": false}`

### Issue: Sessions not expiring

**Symptoms**: Old sessions accumulating

**Diagnosis:**
```bash
# Find old sessions
find data/sessions/ -name "session.json" -mtime +2

# Check cleanup logs
grep "cleanup" logs/denidin.log
```

**Solutions:**
1. Manually trigger cleanup: `session_mgr.cleanup_expired_sessions()`
2. Reduce `session_timeout_hours` from 24 to 12
3. Run cleanup cron job:
   ```bash
   # Add to crontab -e
   0 2 * * * cd /path/to/denidin-bot && python3 -c "from src.memory.session_manager import SessionManager; import json; config = json.load(open('config/config.json')); mgr = SessionManager(**config['memory']['session']); mgr.cleanup_expired_sessions()"
   ```

---

## Rollback Procedure

If critical issues arise:

### Quick Disable (No Code Changes)

1. **Disable feature flag**
   ```json
   {
     "feature_flags": {
       "enable_memory_system": false
     }
   }
   ```

2. **Restart bot**
   ```bash
   ./stop_denidin.sh
   ./run_denidin.sh
   ```

3. **Verify stateless operation**
   - Bot should work without memory
   - No session files created
   - No ChromaDB queries

### Full Rollback (Code Revert)

```bash
# Revert to v1.0 (pre-memory)
git checkout v1.0.0
pip install -r requirements.txt
./stop_denidin.sh
./run_denidin.sh
```

### Data Preservation

```bash
# Backup memory data before rollback
tar -czf memory_backup_$(date +%Y%m%d).tar.gz data/sessions/ data/memory/

# Can restore later when re-enabling
tar -xzf memory_backup_YYYYMMDD.tar.gz
```

---

## Performance Tuning

### Optimize Token Limits

**Problem**: Hitting OpenAI token limits or high costs

**Solution**: Adjust role-based limits
```json
{
  "memory": {
    "session": {
      "max_tokens_by_role": {
        "client": 2000,      // Reduce from 4000
        "godfather": 50000   // Reduce from 100000
      }
    }
  }
}
```

### Optimize Memory Recall

**Problem**: Irrelevant memories being recalled

**Solution**: Increase similarity threshold
```json
{
  "memory": {
    "longterm": {
      "min_similarity": 0.8,  // Increase from 0.7
      "top_k_results": 3      // Reduce from 5
    }
  }
}
```

### Optimize Session Expiration

**Problem**: Too many active sessions

**Solution**: Shorter timeout
```json
{
  "memory": {
    "session": {
      "session_timeout_hours": 12  // Reduce from 24
    }
  }
}
```

---

## Security Considerations

### Data Privacy

1. **Session Data**: Contains conversation history
   - Stored locally in `data/sessions/`
   - Not transmitted except to OpenAI API
   - Git-ignored by default

2. **Long-term Memory**: Contains embedded summaries
   - Stored locally in ChromaDB
   - Embeddings sent to OpenAI
   - Not accessible externally

3. **Encryption**:
   ```bash
   # Encrypt data directory at rest (optional)
   # macOS FileVault or Linux dm-crypt recommended
   ```

### Access Control

- **Godfather Role**: Full memory access (100K tokens)
- **Client Role**: Limited memory (4K tokens)
- **Phone Number Validation**: Verify `godfather_phone` is correct admin

### Backup Strategy

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf /backup/denidin_${DATE}.tar.gz \
  data/sessions/ \
  data/memory/ \
  config/config.json \
  logs/denidin.log

# Keep 30 days
find /backup/ -name "denidin_*.tar.gz" -mtime +30 -delete
```

---

## Success Metrics

After full production rollout, monitor:

| Metric | Week 1 | Week 2 | Week 4 |
|--------|--------|--------|--------|
| Active sessions | Baseline | +20% | +50% |
| Memory recall accuracy | >80% | >85% | >90% |
| User satisfaction | Survey | Survey | Survey |
| Error rate | <1% | <0.5% | <0.1% |
| Response time | <500ms | <450ms | <400ms |

---

## Next Steps

After successful memory system deployment:

1. **Phase 7-10 Complete** ✅
2. **Monitor for 30 days**
3. **Gather user feedback**
4. **Plan next features**:
   - Feature 006: RBAC User Roles
   - Feature 003: Media Processing
   - Feature 004: MCP WhatsApp Server

---

## Support & Resources

- **Documentation**: `/Users/yaronl/personal/DeniDin/denidin-bot/docs/MEMORY_API.md`
- **Specification**: `/Users/yaronl/personal/DeniDin/specs/002-007-memory-system/spec.md`
- **Tests**: `python3 -m pytest tests/integration/test_memory_integration.py -v`
- **Logs**: `tail -f logs/denidin.log`

---

## Changelog

- **2026-01-21**: Initial production enablement guide (Phase 7-10)
- **2026-01-20**: Memory system phases 1-6 merged to master
- **2026-01-18**: v1.0.0 production deployment
