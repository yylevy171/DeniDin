# Implementation Tasks: Update "Bot" Terminology to "App/Application"

**Feature ID**: 012-update-bot-terminology-to-app  
**Created**: January 21, 2026  
**Status**: Ready for Implementation

---

## Task Overview

**Total Tasks**: 6 implementation tasks (no separate test tasks - documentation only)  
**Estimated Duration**: 2-3 hours  
**Dependency**: Should be done AFTER 011-rename-botconfiguration-to-appconfiguration

---

## Git Workflow

### Branch Setup
```bash
git checkout master
git pull origin master
git checkout -b 012-update-bot-terminology-to-app
```

### Commit Strategy
- Commit after each major section (README, specs, source code)
- Use descriptive commit messages
- Final commit encompasses all changes

### PR Creation
```bash
git push origin 012-update-bot-terminology-to-app
gh pr create --base master --head 012-update-bot-terminology-to-app \
  --title "Docs: Update 'bot' terminology to 'app/application'" \
  --body "See specs/012-update-bot-terminology-to-app/spec.md"
```

### Important Rules
- **NEVER** push directly to master
- Manual review of all changes
- Squash merge PR
- Delete branch after merge

---

## Task List

### [IMPL-012-001] Update README.md
**User Story**: US-012-01  
**Priority**: P1  
**Estimated Duration**: 15 minutes  
**Blocked By**: None

**Acceptance Criteria**:
- [ ] Title uses "Application" instead of "Chatbot"
- [ ] Description references "application"
- [ ] Feature list uses "application" terminology
- [ ] Setup instructions reference "the application"
- [ ] External references preserved (e.g., "WhatsApp bot account" setup)

**Files to Modify**:
- `/Users/yaronl/personal/DeniDin/README.md`

**Implementation Steps**:

1. Open README.md
2. Update title:
   ```markdown
   # BEFORE
   # DeniDin WhatsApp AI Chatbot
   
   # AFTER
   # DeniDin WhatsApp AI Application
   ```

3. Update description section:
   ```markdown
   # Replace references like:
   "DeniDin is a WhatsApp chatbot..." → "DeniDin is a WhatsApp application..."
   "the bot provides..." → "the application provides..."
   "bot features include..." → "application features include..."
   ```

4. Review setup instructions:
   - Keep "WhatsApp bot account" (Green API term)
   - Update "run the bot" → "run the application"
   - Update "bot starts" → "application starts"

5. Verify external references unchanged:
   - "Create bot on Green API" → Keep (external service setup)
   - "GreenAPIBot" → Keep (library reference)

**Validation**:
```bash
# Check for inappropriate "bot" references
grep -i "\bbot\b" README.md | grep -v "WhatsApp bot account" | grep -v "Green API bot"
# Review output - should be minimal/none

# Verify "application" added
grep -i "application" README.md
# Expect: Multiple occurrences
```

**Commit**:
```bash
git add README.md
git commit -m "docs: update README to use 'application' terminology

- Changed title from 'Chatbot' to 'Application'
- Updated descriptions to reference 'application'
- Preserved external references (WhatsApp bot account, Green API)"
```

---

### [IMPL-012-002] Update Specification Files
**User Story**: US-012-02  
**Priority**: P1  
**Estimated Duration**: 60 minutes  
**Blocked By**: None

**Acceptance Criteria**:
- [ ] All spec files use "application" for DeniDin references
- [ ] External library references preserved
- [ ] Consistent terminology across all specs
- [ ] No misleading "bot" references remain

**Files to Modify**:
- `specs/001-whatsapp-chatbot-passthrough/spec.md`
- `specs/001-whatsapp-chatbot-passthrough/plan.md`
- `specs/001-whatsapp-chatbot-passthrough/tasks.md`
- `specs/002-007-memory-system/spec.md`
- `specs/002-007-memory-system/plan.md`
- `specs/002-007-memory-system/tasks.md`
- `specs/010-rename-openai-to-ai/*.md` (just created)
- `specs/011-rename-botconfiguration-to-appconfiguration/*.md` (just created)
- `specs/012-update-bot-terminology-to-app/*.md` (current spec)
- `specs/METHODOLOGY.md`
- `specs/CONSTITUTION.md`
- `specs/ROADMAP.md`
- Any other spec files

**Implementation Steps**:

1. Search for all "bot" references in specs:
   ```bash
   cd /Users/yaronl/personal/DeniDin
   grep -ri "\bbot\b" specs/ --include="*.md" > /tmp/spec_bot_refs.txt
   cat /tmp/spec_bot_refs.txt
   ```

2. For each spec file, apply replacements:
   ```
   "the bot" → "the application"
   "bot handles" → "application handles"
   "bot receives" → "application receives"
   "bot responds" → "application responds"
   "bot instance" → "application instance"
   "bot starts" → "application starts"
   "chatbot" → "AI application"
   ```

3. **Preserve these** (don't change):
   - "WhatsApp bot account" (industry term)
   - "GreenAPIBot" (external library)
   - "bot.sendMessage()" (external API)
   - References to "bot" in context of Green API setup

4. Review feature spec titles:
   ```markdown
   # Example: specs/001-whatsapp-chatbot-passthrough/spec.md
   # BEFORE
   "WhatsApp Chatbot Passthrough"
   
   # AFTER (if appropriate)
   "WhatsApp Integration" or keep if "passthrough" makes sense
   # Note: Changing feature titles may not be necessary if they're historical
   ```

5. Update each file manually (review each occurrence)

**Validation**:
```bash
# Search for remaining "bot" in specs (expect only external references)
grep -ri "\bbot\b" specs/ --include="*.md" | grep -v "WhatsApp bot account" | grep -v "GreenAPIBot" | grep -v "Green API bot"
# Review output - should be minimal (setup instructions, external refs)
```

**Commit**:
```bash
git add specs/
git commit -m "docs: update spec files to use 'application' terminology

- Updated all spec files to reference 'application' instead of 'bot'
- Preserved external references (GreenAPIBot, WhatsApp bot account)
- Maintained consistency across all feature documentation"
```

---

### [IMPL-012-003] Update Main Application Code Comments
**User Story**: US-012-03, US-012-04  
**Priority**: P2  
**Estimated Duration**: 30 minutes  
**Blocked By**: None

**Acceptance Criteria**:
- [ ] `denidin.py` comments use "application" terminology
- [ ] Docstrings updated
- [ ] Log messages use "application" terminology
- [ ] Error messages updated

**Files to Modify**:
- `denidin-bot/denidin.py`

**Implementation Steps**:

1. Open `denidin.py`

2. Update module docstring:
   ```python
   # BEFORE
   """
   DeniDin WhatsApp Bot - Main Entry Point
   ...
   """
   
   # AFTER
   """
   DeniDin WhatsApp Application - Main Entry Point
   ...
   """
   ```

3. Update log messages:
   ```python
   # BEFORE
   logger.info("Bot starting...")
   logger.info("Bot initialized successfully")
   logger.error("Bot configuration error")
   
   # AFTER
   logger.info("Application starting...")
   logger.info("Application initialized successfully")
   logger.error("Application configuration error")
   ```

4. Update comments:
   ```python
   # BEFORE
   # Initialize bot components
   # Start bot main loop
   
   # AFTER
   # Initialize application components
   # Start application main loop
   ```

5. **Preserve**:
   - `GreenAPIBot` class instantiation (external library)
   - References to "WhatsApp bot account" in comments

**Validation**:
```bash
# Check for "bot" in denidin.py (expect only external refs)
grep -i "\bbot\b" denidin-bot/denidin.py | grep -v "GreenAPIBot" | grep -v "bot account"
# Review output

# Verify "application" added
grep -i "application" denidin-bot/denidin.py
# Expect: Multiple occurrences
```

---

### [IMPL-012-004] Update Source Code Handler Comments
**User Story**: US-012-03  
**Priority**: P2  
**Estimated Duration**: 30 minutes  
**Blocked By**: None

**Acceptance Criteria**:
- [ ] Handler docstrings use "application" terminology
- [ ] Inline comments updated
- [ ] No misleading "bot" references in handlers

**Files to Modify**:
- `denidin-bot/src/handlers/ai_handler.py`
- `denidin-bot/src/handlers/whatsapp_handler.py`
- `denidin-bot/src/memory/memory_manager.py`
- `denidin-bot/src/memory/session_manager.py`

**Implementation Steps**:

1. For each source file:
   ```bash
   grep -i "\bbot\b" denidin-bot/src/handlers/ai_handler.py
   grep -i "\bbot\b" denidin-bot/src/handlers/whatsapp_handler.py
   grep -i "\bbot\b" denidin-bot/src/memory/memory_manager.py
   grep -i "\bbot\b" denidin-bot/src/memory/session_manager.py
   ```

2. Update docstrings:
   ```python
   # BEFORE
   """Handler for bot AI interactions."""
   
   # AFTER
   """Handler for application AI interactions."""
   ```

3. Update comments:
   ```python
   # BEFORE
   # Bot processes user message
   # Return bot response
   
   # AFTER
   # Application processes user message
   # Return application response
   ```

4. **Preserve**:
   - `GreenAPIBot` references
   - External API method calls

**Validation**:
```bash
# Check all source files for "bot" references
grep -ri "\bbot\b" denidin-bot/src/ --include="*.py" | grep -v "GreenAPIBot"
# Review output - should be minimal/external only
```

**Commit**:
```bash
git add denidin-bot/
git commit -m "docs: update code comments to use 'application' terminology

- Updated denidin.py docstrings and log messages
- Updated handler and memory module comments
- Preserved external library references (GreenAPIBot)"
```

---

### [IMPL-012-005] Update Configuration and Script Files
**User Story**: US-012-03  
**Priority**: P3  
**Estimated Duration**: 15 minutes  
**Blocked By**: None

**Acceptance Criteria**:
- [ ] Config file comments use "application" terminology
- [ ] Shell script comments updated
- [ ] No misleading references

**Files to Modify**:
- `denidin-bot/config/config.example.json`
- `denidin-bot/run_denidin.sh`
- `denidin-bot/stop_denidin.sh`
- `denidin-bot/DEPLOYMENT.md` (if exists)
- `denidin-bot/CONTRIBUTING.md` (if exists)

**Implementation Steps**:

1. Update `config.example.json` comments (if any):
   ```json
   // BEFORE
   {
     "// Comment": "Bot configuration example"
   }
   
   // AFTER
   {
     "// Comment": "Application configuration example"
   }
   ```

2. Update `run_denidin.sh`:
   ```bash
   # BEFORE
   # Start the DeniDin bot
   echo "Starting bot..."
   
   # AFTER
   # Start the DeniDin application
   echo "Starting application..."
   ```

3. Update `stop_denidin.sh`:
   ```bash
   # BEFORE
   # Stop the DeniDin bot
   echo "Stopping bot..."
   
   # AFTER
   # Stop the DeniDin application
   echo "Stopping application..."
   ```

4. Update DEPLOYMENT.md and CONTRIBUTING.md if they exist

**Validation**:
```bash
# Check script files
grep -i "\bbot\b" denidin-bot/*.sh denidin-bot/*.md denidin-bot/config/*.json
# Review output
```

**Commit**:
```bash
git add denidin-bot/config/ denidin-bot/*.sh denidin-bot/*.md
git commit -m "docs: update config and script comments to use 'application'

- Updated shell script comments
- Updated configuration file comments
- Updated deployment/contributing docs if present"
```

---

### [IMPL-012-006] Final Verification
**Priority**: P1  
**Estimated Duration**: 30 minutes  
**Blocked By**: IMPL-012-001 through IMPL-012-005

**Acceptance Criteria**:
- [ ] No inappropriate "bot" references remain
- [ ] External library references preserved
- [ ] Application starts successfully
- [ ] No accidental code changes

**Validation Steps**:

1. **Comprehensive search for "bot" references**:
   ```bash
   cd /Users/yaronl/personal/DeniDin
   
   # Search all markdown files
   grep -ri "\bbot\b" README.md specs/ denidin-bot/*.md --include="*.md" | \
     grep -v "WhatsApp bot account" | \
     grep -v "Green API bot" | \
     grep -v "bot account setup"
   # Review each occurrence - should be minimal/acceptable
   
   # Search all Python files
   grep -ri "\bbot\b" denidin-bot/src/ denidin-bot/denidin.py --include="*.py" | \
     grep -v "GreenAPIBot" | \
     grep -v "bot.sendMessage" | \
     grep -v "from.*bot import"
   # Review - should be external references only
   
   # Search config and scripts
   grep -ri "\bbot\b" denidin-bot/*.sh denidin-bot/config/ --include="*.sh" --include="*.json"
   # Review
   ```

2. **Verify external references preserved**:
   ```bash
   # Check GreenAPIBot still referenced correctly
   grep -r "GreenAPIBot" denidin-bot/
   # Expect: Unchanged from before
   
   # Check WhatsApp bot account references preserved
   grep -r "WhatsApp bot account" .
   # Expect: In setup/README sections
   ```

3. **Verify "application" terminology added**:
   ```bash
   # Check README
   grep -i "application" README.md
   # Expect: Multiple occurrences
   
   # Check specs
   grep -ri "application" specs/ --include="*.md" | wc -l
   # Expect: Significant number (50+)
   
   # Check source code
   grep -ri "application" denidin-bot/denidin.py denidin-bot/src/
   # Expect: In comments and logs
   ```

4. **Test application startup** (ensure no accidental code changes):
   ```bash
   cd /Users/yaronl/personal/DeniDin/denidin-bot
   timeout 5 python3 denidin.py 2>&1 | head -20
   
   # Expected:
   # - Application starts successfully
   # - New log messages: "Application starting..." etc.
   # - No errors
   # - Application initializes correctly
   ```

5. **Visual review of key files**:
   - Open and scan README.md
   - Spot-check 2-3 spec files
   - Review denidin.py changes
   - Verify no unintended changes

**Final Checklist**:
- [ ] README uses "application" terminology
- [ ] Specs use "application" for DeniDin
- [ ] Code comments/logs use "application"
- [ ] External references preserved (GreenAPIBot, WhatsApp bot account)
- [ ] Application starts without errors
- [ ] No accidental code logic changes

---

## Final Commit and Push

```bash
# If any final fixes needed, make them, then:
git add .
git commit -m "docs: finalize application terminology updates

- All documentation updated from 'bot' to 'application'
- Code comments and logs updated
- External library references preserved
- Application terminology now consistent across entire codebase"

# Push to remote
git push origin 012-update-bot-terminology-to-app

# Create PR
gh pr create --base master --head 012-update-bot-terminology-to-app \
  --title "Docs: Update 'bot' terminology to 'app/application'" \
  --body "## Summary
Updates all documentation, comments, and user-facing messages to use 'application' instead of 'bot' terminology.

## Changes
- README: 'Chatbot' → 'Application'
- Specs: All references updated to 'application'
- Code comments: Updated to 'app'/'application'
- Log messages: 'Application starting' etc.
- External references preserved (GreenAPIBot, WhatsApp bot account)

## Rationale
DeniDin is a full AI-powered application with memory, session management, and sophisticated capabilities - not just a simple 'bot'. This terminology better reflects the system's sophistication.

## Validation
✅ Application starts successfully
✅ External library references preserved
✅ Terminology consistent across codebase

See \`specs/012-update-bot-terminology-to-app/spec.md\` for details."
```

---

## Post-Merge Cleanup

```bash
# After PR merged
git checkout master
git pull origin master
# Branch auto-deleted by gh pr merge --delete-branch
```

---

## Notes

- **Documentation-only changes** - no code logic affected
- **Manual review required** for each "bot" occurrence
- **Context-sensitive** - preserve external references
- **Low risk** - application behavior unchanged
- Estimated time: 2-3 hours
- Should be done AFTER code refactors (010, 011) for consistency
