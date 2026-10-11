# Feature Specification: Update "Bot" Terminology to "App/Application"

**Feature ID**: 012-update-bot-terminology-to-app  
**Created**: January 21, 2026  
**Status**: Draft  
**Priority**: Medium

---

## 1. Overview

### 1.1 Purpose
Update all documentation, comments, and user-facing messages to use "app" or "application" terminology instead of "bot" or "chatbot", accurately reflecting that DeniDin is an AI-powered application, not merely a bot.

### 1.2 Background
Throughout the codebase and documentation, DeniDin is referred to as a "bot" or "chatbot":
- README describes it as "DeniDin WhatsApp AI Chatbot"
- Comments reference "the bot"
- Log messages mention "bot started"
- Spec documents use "bot" terminology

This terminology is inaccurate because:
- DeniDin is a full application with memory, session management, and AI capabilities
- "Bot" diminishes the sophistication of the system
- Inconsistent with professional software terminology

### 1.3 Scope
**In Scope:**
- README.md title and descriptions
- All specification files (`specs/**/*.md`)
- Code comments and docstrings
- Log messages
- Error messages
- Configuration file comments
- User-facing documentation

**Out of Scope:**
- Code identifiers (class names, variable names) - handled in 011
- External library references (e.g., `GreenAPIBot` class)
- WhatsApp "bot account" references (industry standard term)
- Historical git commit messages (don't rewrite history)
- Third-party library documentation

### 1.4 Success Criteria
- ✅ README describes DeniDin as an "application"
- ✅ Spec files use "application" terminology
- ✅ Code comments reference "app" or "application"
- ✅ Log messages use "application" terminology
- ✅ No inappropriate "bot" references remain
- ✅ External library references preserved (GreenAPIBot, etc.)

---

## 2. User Stories

### US-012-01: Developer Updates README (P1)
**As a** project stakeholder  
**I want** the README to describe DeniDin as an application  
**So that** the project is accurately represented to external audiences

**Acceptance Criteria:**
- Title references "DeniDin WhatsApp AI Application" (not "Chatbot")
- Description uses "application" terminology
- Feature list describes application capabilities
- Setup instructions reference "the application"

**Priority**: P1 (First impression for external audiences)

---

### US-012-02: Developer Updates Specification Files (P1)
**As a** developer reading specs  
**I want** specifications to use "application" terminology  
**So that** technical documentation is accurate and professional

**Acceptance Criteria:**
- All spec files (`specs/**/*.md`) use "application" terminology
- "Bot" only appears when referencing external libraries
- Consistent terminology across all feature specs

**Priority**: P1 (Core technical documentation)

---

### US-012-03: Developer Updates Code Comments (P2)
**As a** developer reading code  
**I want** comments to reference "app" or "application"  
**So that** code is self-documenting with accurate terminology

**Acceptance Criteria:**
- Docstrings use "application" terminology
- Inline comments reference "app" where appropriate
- Function descriptions accurate
- No misleading "bot" references in comments

**Priority**: P2 (Code quality and maintainability)

---

### US-012-04: Developer Updates Log Messages (P2)
**As a** system operator  
**I want** log messages to reference "application"  
**So that** logs are professional and clear

**Acceptance Criteria:**
- Startup logs: "Application starting" (not "Bot starting")
- Status logs: "Application initialized" 
- Error logs: "Application error"
- Shutdown logs: "Application stopped"

**Priority**: P2 (Operational clarity)

---

### US-012-05: Developer Preserves External References (P1)
**As a** developer  
**I want** external library references unchanged  
**So that** code continues to work with WhatsApp Green API

**Acceptance Criteria:**
- `GreenAPIBot` class name unchanged
- "WhatsApp bot account" terminology preserved (industry standard)
- Third-party documentation references unchanged
- Only DeniDin-specific references updated

**Priority**: P1 (Correctness requirement)

---

## 3. Functional Requirements

### FR-012-01: README Updates
**Requirement**: README MUST use "application" terminology

**Acceptance Criteria:**
- Given the README.md file is opened
- When reviewing the title and description
- Then "application" terminology is used consistently
- And "bot" only appears in historical context or external references

---

### FR-012-02: Specification Updates
**Requirement**: All spec files MUST use "application" terminology

**Acceptance Criteria:**
- Given any spec file in `specs/` is opened
- When reviewing terminology
- Then "application" is used for DeniDin references
- And "bot" only appears when referencing external systems

---

### FR-012-03: Code Comment Updates
**Requirement**: Code comments MUST use accurate terminology

**Acceptance Criteria:**
- Given any source file is reviewed
- When reading comments and docstrings
- Then "app" or "application" terminology is used
- And "bot" only appears in external library contexts

---

### FR-012-04: Log Message Updates
**Requirement**: Log messages MUST use professional terminology

**Acceptance Criteria:**
- Given the application is running
- When log messages are emitted
- Then messages reference "application" not "bot"
- And logs remain clear and informative

---

### FR-012-05: External Reference Preservation
**Requirement**: External library references MUST remain unchanged

**Acceptance Criteria:**
- Given external library code is reviewed
- When checking class/method names
- Then `GreenAPIBot` and similar remain unchanged
- And only internal DeniDin terminology is updated

---

## 4. Non-Functional Requirements

### NFR-012-01: Documentation Quality
**Requirement**: Updated documentation must maintain high quality
- Clear and professional language
- Consistent terminology across all files
- No ambiguity about what is being referenced

### NFR-012-02: Backward Compatibility
**Requirement**: No breaking changes
- Application behavior unchanged
- Configuration format unchanged
- API contracts unchanged
- Only documentation and comments updated

---

## 5. Edge Cases & Error Scenarios

### EC-012-01: Ambiguous "Bot" References
**Scenario**: Some "bot" references may be ambiguous (DeniDin vs. WhatsApp bot account)

**Resolution Strategy:**
- "WhatsApp bot account" → Keep (industry term)
- "the bot starts" → "the application starts"
- "bot instance" → "application instance"
- "GreenAPIBot" → Keep (external library)

**Guideline**: If referring to DeniDin, use "application". If referring to external systems, preserve original terminology.

---

### EC-012-02: Historical References
**Scenario**: Old documentation may have historical "bot" references

**Expected Behavior:**
- Update to current terminology
- Don't rewrite git history
- Add notes about evolution if helpful

---

## 6. Technical Constraints

### TC-012-01: No Code Changes
- Only documentation and comments updated
- No class names, variables, or function names changed (handled in 011)
- No runtime behavior changes

### TC-012-02: External Libraries Unchanged
- `GreenAPIBot` class usage unchanged
- Third-party library references preserved
- Only DeniDin-specific terminology updated

---

## 7. Terminology Mapping

### Update These Terms:
| Old | New | Context |
|-----|-----|---------|
| "DeniDin bot" | "DeniDin application" | General references |
| "the bot" | "the application" | System references |
| "bot starts" | "application starts" | Log messages |
| "bot instance" | "application instance" | Technical docs |
| "chatbot" | "AI application" | Descriptions |
| "WhatsApp AI Chatbot" | "WhatsApp AI Application" | README title |

### Preserve These Terms:
| Term | Reason |
|------|--------|
| "WhatsApp bot account" | Industry standard term |
| "GreenAPIBot" | External library class |
| "bot.sendMessage()" | External API method |
| "Create bot on Green API" | Setup instructions for external service |

---

## 8. Dependencies

### Internal Dependencies
- Should be done AFTER 011-rename-botconfiguration-to-appconfiguration
- Should be done ALONGSIDE or AFTER 010-rename-openai-to-ai
- Can be done independently of code refactors

### External Dependencies
- None

---

## 9. Open Questions

**Q1**: Should we update "bot" in setup instructions for Green API?  
**A1**: No - "WhatsApp bot account" is industry terminology for Green API setup.

**Q2**: Should we update historical changelog entries?  
**A2**: No - preserve historical accuracy. Only update current/forward-looking documentation.

**Q3**: What about "BotConfiguration" in old specs?  
**A3**: Update to "AppConfiguration" since these are current technical docs, not historical records.

---

## 10. Out of Scope

- Renaming Python classes/variables (handled in 011)
- Rewriting git commit history
- Updating third-party library names
- Changing external API method names
- Updating WhatsApp Green API setup terminology

---

## 11. Approval

**Specification Approved By**: [Pending]  
**Date**: [Pending]  
**Approved to Proceed to Planning**: [ ] Yes [ ] No
