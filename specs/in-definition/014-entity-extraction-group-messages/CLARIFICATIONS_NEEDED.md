# Feature 014: Clarifications Needed - Entity Extraction from Group Messages

**Created**: January 22, 2026  
**Status**: PENDING - Awaiting Human Input

---

## Critical Questions (Blocking Plan Creation)

### 1. Entity Extraction Trigger Context
**Question**: Should entity extraction only trigger in GROUP chats, or also in 1:1 Godfather chats?

**Context**: Determines scope of pattern matching.

**Options**:
- A) Only group chats (original use case)
- B) Both group chats and 1:1 with Godfather
- C) Configurable in config.json

**Impact**: 
- Group-only: Simpler logic, clear use case boundary
- Both: More flexible, but may trigger false positives in casual conversation

**Decision**: PENDING

---

### 2. Extraction Pattern Flexibility
**Question**: What patterns should trigger extraction?

**Examples**:
- Full pattern: "Claire from Mizrahi 5000" ✓
- Partial (no company): "Claire 5000" → Extract?
- Minimal: "5000 Shekel" → Extract?
- Reverse order: "5000 from Claire at Mizrahi" → Extract?

**Options**:
- A) Strict: Only "{Name} from {Company} {Amount}" pattern
- B) Flexible: AI detects any transaction-like message
- C) Multiple patterns: Define 3-5 specific patterns to match

**Decision**: PENDING

---

### 3. Currency Detection and Defaults
**Question**: When amount has no currency ("Claire from Mizrahi 5000"), what's the default?

**Options**:
- A) Default to Shekel (Israeli currency, Godfather's locale)
- B) Default to USD (international standard)
- C) Ask Godfather to clarify
- D) Leave currency as null/unspecified until clarified

**Context**: Affects automatic transaction recording accuracy.

**Decision**: PENDING

---

### 4. Transaction Update Strategy
**Question**: When Godfather provides additional info ("Claire's phone is 972509998877, payment due Feb 15"), should DeniDin:

**Options**:
- A) Update existing memory entry's metadata (merge fields in-place)
- B) Create new memory entry and link to original transaction via transaction_id
- C) Both: Create new entry for timeline + update metadata for search

**Context**: Affects memory structure and retrieval patterns.

**Trade-offs**:
- Option A: Simple, but loses timeline of information evolution
- Option B: Full history, but metadata not updated (search issues)
- Option C: Best of both, but more complex and storage overhead

**Decision**: PENDING

---

### 5. Confirmation Reply Behavior
**Question**: Should confirmation reply happen in ALL cases, or only specific contexts?

**Scenarios**:
- Group chat where transaction mentioned → Reply with confirmation?
- 1:1 follow-up with Godfather → Reply with confirmation?
- Godfather says "silent mode" or similar → Skip confirmation?

**Options**:
- A) Always reply with confirmation (consistent behavior)
- B) Only in group chats (where transaction was first mentioned)
- C) Configurable: Godfather can enable/disable confirmations
- D) Smart: Reply in group, silent in 1:1 follow-ups

**Decision**: PENDING

---

### 6. Duplicate Transaction Window
**Question**: How long should the duplicate detection window be?

**Current Spec**: 24 hours

**Options**:
- A) 24 hours (current)
- B) 1 hour (very strict)
- C) 7 days (covers weekly deals)
- D) Configurable per client or globally

**Context**: "Claire from Mizrahi 5000" sent twice - when is it a duplicate vs. new deal?

**Decision**: PENDING - Confirm 24 hours or adjust

---

### 7. Failed Extraction Handling
**Question**: When AI cannot extract entities with confidence, should DeniDin:

**Options**:
- A) Store as general conversation memory (silent fallback)
- B) Ask Godfather: "Did you mean to record a transaction? I couldn't extract details."
- C) Log at DEBUG level, no action
- D) Confidence threshold: Extract if >80% confident, else ask

**Decision**: PENDING

---

### 8. Metadata Schema Validation
**Question**: Should transaction metadata schema be strictly validated?

**Proposed Required Fields**:
- `type`: "client_transaction"
- `client_name`: String
- `amount`: Number

**Proposed Optional Fields**:
- `company`: String
- `currency`: String
- `phone`: String (WhatsApp format)
- `due_date`: ISO 8601 date
- `contract_path`: String (file path)
- `notes`: String

**Confirm**: Is this schema acceptable or needs changes?

**Decision**: PENDING

---

## Research Tasks

1. **AI Entity Extraction Libraries**: Research alternatives to OpenAI (spaCy, Hugging Face NER models)
2. **Pattern Matching Performance**: Test AI vs. regex for extraction accuracy
3. **ChromaDB Metadata Indexing**: Verify metadata fields can be indexed for efficient filtering

---

**Total Questions**: 8 critical questions + 3 research tasks  
**Blocking**: All plan.md creation until resolved  
**Next Step**: Human input required for all decisions
