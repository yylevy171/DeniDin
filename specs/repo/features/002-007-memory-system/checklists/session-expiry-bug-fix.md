# Session Expiry & Memory Transfer Bug Fix Checklist

**Purpose**: Validate requirements quality for fixing the session expiry bug where 2-day-old sessions are not transferred to long-term memory.

**Created**: 2026-01-22  
**Bug Context**: Sessions older than 24h (`session_timeout_hours: 24`) remain in active storage instead of being moved to `expired/` and transferred to ChromaDB long-term memory.

**Observed Evidence**:
- Session `a162e1eb-d585-4812-8811-28cfddc5806e` created 2026-01-20 14:41:35 (48+ hours old)
- `data/sessions/expired/` folder is empty
- Expected: Session moved to `expired/{YYYY-MM-DD}/` → transferred to ChromaDB
- Actual: Session remains in active storage

---

## Requirement Completeness

- [ ] CHK001 - Are requirements defined for when the cleanup thread should start? [Gap, Thread Lifecycle]
- [ ] CHK002 - Are requirements specified for cleanup thread initialization logging? [Gap, Observability]
- [ ] CHK003 - Are error handling requirements defined for cleanup thread failures? [Gap, Exception Flow]
- [ ] CHK004 - Are requirements documented for what happens if cleanup thread crashes? [Gap, Recovery]
- [ ] CHK005 - Are session expiry detection requirements clearly specified? [Completeness, Session Lifecycle]
- [ ] CHK006 - Are timestamp comparison requirements defined (timezone handling, format validation)? [Gap, Data Quality]
- [ ] CHK007 - Are requirements specified for the cleanup interval configuration? [Completeness, Config §session.cleanup_interval_seconds]
- [ ] CHK008 - Is the default cleanup interval value justified in requirements? [Gap, Config Defaults]
- [ ] CHK009 - Are requirements defined for expired session directory structure (e.g., `{YYYY-MM-DD}/` subdirectories)? [Completeness, Storage]
- [ ] CHK010 - Are requirements specified for session archival atomicity (move vs copy+delete)? [Gap, Data Integrity]
- [ ] CHK011 - Are long-term memory transfer requirements documented? [Completeness, Memory Integration]
- [ ] CHK012 - Are requirements defined for when transfer to ChromaDB should occur (cleanup vs startup)? [Gap, Timing]
- [ ] CHK013 - Are requirements specified for AI summarization of expired sessions? [Completeness, AI Integration]
- [ ] CHK014 - Are requirements documented for ChromaDB metadata storage? [Completeness, Data Model]
- [ ] CHK015 - Are startup recovery requirements clearly defined? [Completeness, Bootstrap]

## Requirement Clarity

- [ ] CHK016 - Is "session expiry" precisely defined with measurable criteria? [Clarity, Terminology]
- [ ] CHK017 - Is the expiry threshold calculation formula specified? [Clarity, Algorithm]
- [ ] CHK018 - Is "cleanup interval" distinguished from "session timeout"? [Clarity, Terminology]
- [ ] CHK019 - Are the units for timeout configuration unambiguous (hours vs seconds)? [Clarity, Config §session_timeout_hours]
- [ ] CHK020 - Is the relationship between `last_active` timestamp updates and expiry clear? [Clarity, State Management]
- [ ] CHK021 - Is "background thread" lifecycle (start, run, stop) explicitly defined? [Clarity, Concurrency]
- [ ] CHK022 - Are the conditions for session cleanup execution clearly stated? [Clarity, Control Flow]
- [ ] CHK023 - Is the archival directory naming convention (`{YYYY-MM-DD}/`) documented? [Clarity, File System]
- [ ] CHK024 - Are the steps for "orphaned session recovery" precisely defined? [Clarity, Recovery Flow]
- [ ] CHK025 - Is the term "orphaned session" clearly defined and distinguished from "expired session"? [Ambiguity, Terminology]

## Requirement Consistency

- [ ] CHK026 - Are session timeout requirements consistent between config and code? [Consistency, Config §session_timeout_hours]
- [ ] CHK027 - Are cleanup interval requirements consistent across SessionManager and AIHandler initialization? [Consistency, Integration]
- [ ] CHK028 - Are timestamp format requirements consistent (ISO 8601 UTC) across all session operations? [Consistency, §CONST-II Time Handling]
- [ ] CHK029 - Are storage directory path requirements consistent between session and memory modules? [Consistency, File System]
- [ ] CHK030 - Are requirements for "expired" state consistent across cleanup, transfer, and recovery flows? [Consistency, State Machine]
- [ ] CHK031 - Are error handling requirements consistent between cleanup thread and main thread? [Consistency, Exception Handling]
- [ ] CHK032 - Are logging requirements consistent for session lifecycle events? [Consistency, Observability]

## Acceptance Criteria Quality

- [ ] CHK033 - Can "session has expired" be objectively verified? [Measurability, Acceptance Criteria]
- [ ] CHK034 - Can "cleanup thread is running" be objectively tested? [Measurability, Testing]
- [ ] CHK035 - Can "session successfully moved to expired/" be objectively verified? [Measurability, File System]
- [ ] CHK036 - Can "session transferred to long-term memory" be objectively validated? [Measurability, ChromaDB]
- [ ] CHK037 - Are success criteria defined for cleanup execution? [Acceptance Criteria, Gap]
- [ ] CHK038 - Are success criteria defined for memory transfer completion? [Acceptance Criteria, Gap]
- [ ] CHK039 - Are performance criteria specified for cleanup operations? [Measurability, Non-Functional]
- [ ] CHK040 - Are success criteria defined for startup recovery? [Acceptance Criteria, Bootstrap]

## Scenario Coverage

- [ ] CHK041 - Are requirements defined for the primary flow: cleanup detects expired session → moves to expired/ → transfers to ChromaDB? [Coverage, Primary Flow]
- [ ] CHK042 - Are requirements specified for cleanup running but finding no expired sessions? [Coverage, Alternate Flow]
- [ ] CHK043 - Are requirements defined for multiple expired sessions in one cleanup cycle? [Coverage, Batch Processing]
- [ ] CHK044 - Are requirements specified for cleanup thread starting at application boot? [Coverage, Initialization]
- [ ] CHK045 - Are requirements defined for cleanup thread graceful shutdown? [Coverage, Teardown]
- [ ] CHK046 - Are requirements specified for orphaned session recovery at startup? [Coverage, Recovery Flow]
- [ ] CHK047 - Are requirements defined for sessions that become active again before cleanup? [Coverage, Race Condition]
- [ ] CHK048 - Are requirements specified for concurrent session updates during cleanup? [Coverage, Concurrency]

## Edge Case Coverage

- [ ] CHK049 - Are requirements defined for empty expired/ directory at startup? [Edge Case, Bootstrap]
- [ ] CHK050 - Are requirements specified for cleanup thread failure/crash scenarios? [Edge Case, Exception Flow]
- [ ] CHK051 - Are requirements defined for filesystem errors during session move? [Edge Case, I/O Errors]
- [ ] CHK052 - Are requirements specified for ChromaDB connection failures during transfer? [Edge Case, Integration Failure]
- [ ] CHK053 - Are requirements defined for AI summarization failures? [Edge Case, AI Integration]
- [ ] CHK054 - Are requirements specified for sessions with invalid `last_active` timestamps? [Edge Case, Data Quality]
- [ ] CHK055 - Are requirements defined for sessions with missing `last_active` field? [Edge Case, Schema Validation]
- [ ] CHK056 - Are requirements specified for zero cleanup interval configuration? [Edge Case, Config Validation]
- [ ] CHK057 - Are requirements defined for negative timeout values? [Edge Case, Config Validation]
- [ ] CHK058 - Are requirements specified for expired/ directory already containing a session with same ID? [Edge Case, Collision]
- [ ] CHK059 - Are requirements defined for disk space exhaustion scenarios? [Edge Case, Resource Limits]
- [ ] CHK060 - Are requirements specified for cleanup running exactly at session expiry moment? [Edge Case, Timing]

## Non-Functional Requirements

### Performance
- [ ] CHK061 - Are cleanup execution time requirements specified? [Gap, Performance]
- [ ] CHK062 - Are requirements defined for cleanup impact on main thread? [Gap, Performance]
- [ ] CHK063 - Are memory usage requirements specified for cleanup operations? [Gap, Resource Management]
- [ ] CHK064 - Are requirements defined for cleanup scalability (100s of sessions)? [Gap, Scalability]

### Observability
- [ ] CHK065 - Are logging requirements defined for cleanup thread start/stop? [Gap, Observability]
- [ ] CHK066 - Are logging requirements specified for each cleanup cycle execution? [Gap, Observability]
- [ ] CHK067 - Are logging requirements defined for session expiry detection? [Gap, Observability]
- [ ] CHK068 - Are logging requirements specified for successful session archival? [Gap, Observability]
- [ ] CHK069 - Are logging requirements defined for memory transfer operations? [Gap, Observability]
- [ ] CHK070 - Are logging requirements specified for cleanup errors? [Gap, Error Handling]
- [ ] CHK071 - Are metrics requirements defined for cleanup monitoring? [Gap, Monitoring]

### Reliability
- [ ] CHK072 - Are retry requirements specified for transient cleanup failures? [Gap, Resilience]
- [ ] CHK073 - Are requirements defined for cleanup thread automatic restart? [Gap, Self-Healing]
- [ ] CHK074 - Are data integrity requirements specified for session archival? [Gap, Data Integrity]
- [ ] CHK075 - Are atomicity requirements defined for memory transfer operations? [Gap, Transaction Semantics]

### Security
- [ ] CHK076 - Are access control requirements specified for expired/ directory? [Gap, Security]
- [ ] CHK077 - Are requirements defined for sensitive data in archived sessions? [Gap, Privacy]

## Dependencies & Assumptions

- [ ] CHK078 - Are threading library dependencies documented? [Dependency, threading module]
- [ ] CHK079 - Are filesystem operation dependencies specified? [Dependency, os/pathlib]
- [ ] CHK080 - Are ChromaDB integration dependencies documented? [Dependency, MemoryManager]
- [ ] CHK081 - Are AI handler dependencies specified? [Dependency, AIHandler]
- [ ] CHK082 - Is the assumption of UTC timestamps validated? [Assumption, §CONST-II]
- [ ] CHK083 - Is the assumption of thread-safe file operations validated? [Assumption, Concurrency]
- [ ] CHK084 - Is the assumption of daemon thread behavior documented? [Assumption, Thread Lifecycle]
- [ ] CHK085 - Are session.json schema assumptions validated? [Assumption, Data Model]

## Ambiguities & Conflicts

- [ ] CHK086 - Is the relationship between cleanup_interval_seconds (code) and session_timeout_hours (config) unambiguous? [Ambiguity, Configuration]
- [ ] CHK087 - Is it clear whether cleanup runs immediately at startup or after first interval? [Ambiguity, Initialization]
- [ ] CHK088 - Is the race condition between cleanup and active session updates addressed? [Conflict, Concurrency]
- [ ] CHK089 - Is the ownership of memory transfer (SessionManager vs AIHandler) clearly defined? [Ambiguity, Responsibility]
- [ ] CHK090 - Are the different expiry detection points (cleanup vs startup recovery) clearly distinguished? [Ambiguity, Control Flow]
- [ ] CHK091 - Is the term "expired session" vs "orphaned session" consistently used? [Ambiguity, Terminology]
- [ ] CHK092 - Is the behavior when both cleanup and recovery detect the same session defined? [Conflict, Concurrency]

## Traceability

- [ ] CHK093 - Is a requirement ID scheme established for this bug fix? [Traceability, Gap]
- [ ] CHK094 - Are config parameter requirements traceable to code? [Traceability, Config §memory.session]
- [ ] CHK095 - Are cleanup thread requirements traceable to implementation? [Traceability, SessionManager]
- [ ] CHK096 - Are memory transfer requirements traceable to integration contract? [Traceability, AIHandler↔SessionManager]
- [ ] CHK097 - Are timestamp handling requirements traceable to CONSTITUTION §II? [Traceability, §CONST-II]

## Root Cause Analysis Requirements

- [ ] CHK098 - Are diagnostic requirements defined to identify why cleanup thread isn't running? [Gap, Debugging]
- [ ] CHK099 - Are requirements specified for verifying thread startup? [Gap, Diagnostics]
- [ ] CHK100 - Are requirements defined for checking cleanup interval configuration? [Gap, Diagnostics]
- [ ] CHK101 - Are requirements specified for validating timestamp comparisons? [Gap, Diagnostics]
- [ ] CHK102 - Are logging requirements sufficient to debug cleanup failures? [Gap, Observability]
- [ ] CHK103 - Are requirements defined for reproducing the bug in test environment? [Gap, Testing]

---

**Checklist Summary**: 103 requirements quality validation items  
**Focus Areas**: Completeness (15), Clarity (10), Consistency (7), Acceptance Criteria (8), Scenario Coverage (8), Edge Cases (12), Non-Functional (17), Dependencies (8), Ambiguities (7), Traceability (5), Root Cause (6)

**Next Steps**:
1. Review each checklist item to validate bug fix requirements
2. Document missing requirements identified through checklist
3. Create formal bug fix specification if requirements gaps are significant
4. Proceed with root cause diagnosis using validated requirements
