# Implementation Plan: Update "Bot" Terminology to "App/Application"

**Feature ID**: 012-update-bot-terminology-to-app  
**Created**: January 21, 2026  
**Status**: Draft

---

## 1. Implementation Phases

### Phase 0: Research ✓
**Status**: Complete

**Findings:**
- Files containing "bot" terminology (estimated):
  - `README.md` - Project description
  - `specs/**/*.md` - Specification files (~10-15 files)
  - `denidin.py` - Comments and logs
  - `src/**/*.py` - Comments and docstrings (~10 files)
  - `config/config.example.json` - Comments
  - `run_denidin.sh` / `stop_denidin.sh` - Script comments
  - `CONTRIBUTING.md`, `DEPLOYMENT.md` - Documentation

**Search Strategy:**
```bash
# Find files with "bot" references (case-insensitive)
grep -ri "\bbot\b" --include="*.md" --include="*.py" --include="*.json" --include="*.sh" .

# Exclude external libraries and git history
grep -ri "\bbot\b" README.md specs/ denidin-bot/src/ denidin-bot/denidin.py denidin-bot/config/
```

**Categories of Updates:**
1. **High Priority**: README.md, spec files
2. **Medium Priority**: Code comments, docstrings
3. **Low Priority**: Log messages, error messages

---

### Phase 1: Design

#### 1.1 Terminology Replacement Strategy

**Decision Tree** for each "bot" occurrence:

```
Is it referring to DeniDin?
├─ YES → Replace with "application" or "app"
└─ NO → Is it external reference?
    ├─ GreenAPIBot class → KEEP unchanged
    ├─ WhatsApp bot account (setup) → KEEP (industry term)
    ├─ bot.sendMessage() API → KEEP (external API)
    └─ Third-party docs → KEEP unchanged
```

**Replacement Patterns:**

| Context | Old | New |
|---------|-----|-----|
| README title | "DeniDin WhatsApp AI Chatbot" | "DeniDin WhatsApp AI Application" |
| General reference | "the bot" | "the application" |
| Log messages | "Bot starting..." | "Application starting..." |
| Code comments | "Initialize bot" | "Initialize application" |
| Documentation | "bot instance" | "application instance" |
| Spec files | "bot handles message" | "application handles message" |

**Preserved Terms:**
- "WhatsApp bot account" (Green API setup instructions)
- "GreenAPIBot" (external class)
- "bot.sendMessage()" (external API method)

#### 1.2 File-by-File Strategy

**README.md:**
- Title: Add "Application" replace "Chatbot"
- Description: "AI-powered WhatsApp application"
- Features: "Application provides..."
- Setup: "Run the application"

**Spec Files:**
- System descriptions: "application" not "bot"
- Technical details: "app" acceptable in informal contexts
- Keep external references unchanged

**Source Code:**
- Docstrings: """Initialize the application..."""
- Comments: # Application starts here
- Log messages: logger.info("Application starting")

---

### Phase 2: Task Breakdown

**Task Sequence** (can be parallelized):

```
[IMPL-012-001] Update README.md
  └─ [IMPL-012-001a] Replace bot terminology in README

[IMPL-012-002] Update Specification Files
  ├─ [IMPL-012-002a] Update main spec files (001-whatsapp, 002-007-memory)
  ├─ [IMPL-012-002b] Update new enhancement specs (010, 011, 012)
  └─ [IMPL-012-002c] Update METHODOLOGY and CONSTITUTION

[IMPL-012-003] Update Source Code Comments
  ├─ [IMPL-012-003a] Update denidin.py comments and logs
  ├─ [IMPL-012-003b] Update handler comments
  └─ [IMPL-012-003c] Update other source files

[IMPL-012-004] Update Configuration and Scripts
  ├─ [IMPL-012-004a] Update config file comments
  └─ [IMPL-012-004b] Update shell script comments

[IMPL-012-005] Verification
  └─ [IMPL-012-005a] Search for remaining inappropriate "bot" references
```

---

### Phase 3: Implementation Strategy

#### 3.1 Approach
**Strategy**: Manual review with search & replace

**Rationale**:
- Requires human judgment (DeniDin vs. external references)
- Can't automate decision tree
- Low risk (documentation only, no code changes)

**Process**:
1. Search for all "bot" occurrences
2. Review each in context
3. Replace if referring to DeniDin
4. Preserve if external reference
5. Document ambiguous cases

#### 3.2 Testing Strategy

**Validation**:
- Visual review of updated files
- Check that external references preserved
- Verify no broken links or formatting
- Application still runs (no accidental code changes)

**No automated tests needed**: Pure documentation updates.

---

## 2. Risk Analysis

### High Risk Items
None - documentation-only changes.

### Medium Risk Items
**Risk**: Accidentally change external library references  
**Mitigation**: 
- Careful review of each occurrence
- Grep for `GreenAPIBot` after changes to ensure unchanged
- Test application startup

### Low Risk Items
**Risk**: Miss some "bot" references  
**Mitigation**: Comprehensive grep search at end

---

## 3. Technical Decisions

### TD-012-01: Manual Review Required
**Decision**: Manually review each "bot" occurrence

**Rationale**:
- Context-dependent (DeniDin vs. external)
- Can't safely automate
- Low volume of changes (~50-100 occurrences)

**Alternatives Considered**:
- Automated find/replace - **Rejected** (would break external references)

---

### TD-012-02: Preserve Industry Terms
**Decision**: Keep "WhatsApp bot account" in setup instructions

**Rationale**:
- Industry standard terminology
- Green API documentation uses "bot account"
- Changing would confuse users following setup guides

---

### TD-012-03: Update All Specs (Including New Ones)
**Decision**: Update terminology in specs 010, 011, 012 even though just created

**Rationale**:
- Maintain consistency
- These specs will be long-term documentation
- Better to fix now than later

---

## 4. Success Metrics

### Completion Criteria
- ✅ README uses "application" terminology
- ✅ All spec files use "application" for DeniDin references
- ✅ Code comments use "app"/"application"
- ✅ Log messages use "application"
- ✅ `GreenAPIBot` and external references unchanged
- ✅ Application starts and runs correctly

**Verification Commands**:
```bash
# Search for remaining DeniDin "bot" references (expect external only)
grep -ri "\bbot\b" README.md specs/ denidin-bot/src/ denidin-bot/denidin.py | grep -v "GreenAPIBot" | grep -v "WhatsApp bot account" | grep -v "bot.sendMessage"
# Expect: No inappropriate references

# Verify external references preserved
grep -r "GreenAPIBot" denidin-bot/
# Expect: Unchanged occurrences

# Application still works
cd denidin-bot && timeout 5 python3 denidin.py 2>&1 | head -20
# Expect: Clean startup (no code changes)
```

---

## 5. Timeline Estimate

**Total Estimated Duration**: 2-3 hours

**Breakdown**:
- README update: 15 minutes
- Spec files update: 60 minutes (~10-15 files)
- Source code comments: 45 minutes
- Config/scripts: 15 minutes
- Verification: 30 minutes

---

## 6. METHODOLOGY Compliance Checklist

- [x] **Integration Contracts**: N/A - documentation only
- [x] **Terminology Glossary**: Standardizing on "application" terminology
- [x] **Technology Choices**: No technology changes
- [x] **Requirement IDs**: US-012-01 through US-012-05 defined
- [x] **Phase Checkpoints**: Phase 0 complete, Phase 1 documented
- [x] **Task ID Format**: Tasks use [IMPL-012-###] format
- [x] **Path Conventions**: Absolute paths from project root
- [x] **Clarifications Tracking**: All decisions documented
- [x] **Estimated Duration**: 2-3 hours documented
- [x] **Templates**: Following plan-template.md structure

---

## 7. CONSTITUTION Compliance Review

**Principle I (Configuration & Testing)**:
- ✅ No configuration changes
- ✅ No test changes needed (documentation only)

**Principle III (Version Control)**:
- ✅ Feature branch: `012-update-bot-terminology-to-app`
- ✅ PR required before merge

**Principle IV (Testing)**:
- ✅ Manual verification (no automated tests needed)
- ✅ Application startup validates no code damage

---

## 8. Open Issues

None - all design decisions finalized.

---

## 9. Approval

**Plan Approved By**: [Pending]  
**Date**: [Pending]  
**Approved to Proceed to Task Generation**: [ ] Yes [ ] No
