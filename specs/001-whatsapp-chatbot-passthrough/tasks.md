# Tasks: WhatsApp AI Chatbot Passthrough

**Input**: Design documents from `/specs/001-whatsapp-chatbot-passthrough/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Test-Driven Development (TDD) - ALL tests written and approved BEFORE implementation

**Organization**: Tasks are grouped by user story (P1-P4) to enable independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- **[T###a]**: Write tests (REQUIRES HUMAN APPROVAL before T###b)
- **[T###b]**: Implement code (BLOCKED until T###a approved, tests are IMMUTABLE)
- All paths relative to `denidin-bot/` project root

## TDD Workflow (Per CONSTITUTION Principle I)

1. **Task A (Tests)**: Write comprehensive tests covering acceptance criteria
2. **👤 HUMAN APPROVAL GATE**: Review and approve tests
3. **Task B (Implementation)**: Write code to pass approved tests (tests frozen)
4. **Validation**: Run tests to verify implementation
5. **Next task**: Repeat TDD cycle

### Two-Tier Testing Strategy (Per CONSTITUTION):

**Tier 1: Mocked Tests (Fast, Frequent)**
- Unit tests with mocked external dependencies
- Integration tests with mocked Green API and OpenAI
- Run on every code change, in CI/CD
- Fast execution, no API quota consumption

**Tier 2: Real API Tests (Slow, Critical)**
- Actual Green API connectivity and authentication
- Real OpenAI API calls (consumes quota)
- Complete E2E flow with real network calls
- Run before deployment, after config changes

## Version Control Workflow (Per CONSTITUTION Principle II)

⚠️ **CRITICAL**: Create feature branch BEFORE starting work on each phase!

Each phase includes version control tasks:
- **VC0**: Create feature branch (FIRST STEP - before any work)
- **VC1**: Run tests to validate
- **VC2**: Commit changes
- **VC3**: Push to feature branch
- **VC4**: Create Pull Request
- **VC5**: Review and merge PR
- **NEVER** push directly to master/main

## Path Conventions

Single Python project structure:
- `bot.py` - Main entry point
- `src/` - Source code (handlers/, models/, utils/)
- `tests/` - Test suite (unit/, integration/)
- `config/` - Configuration files (config.json or config.yaml, settings.py)
- `logs/` - Application logs
- `state/` - Runtime state persistence

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project structure and install dependencies

- [ ] T001 Create project directory `denidin-bot/` with subdirectories: src/{handlers,models,utils}, tests/{unit,integration,fixtures}, config/, logs/, state/
- [ ] T002 [P] Create `__init__.py` files in src/, src/handlers/, src/models/, src/utils/, tests/
- [ ] T003 [P] Create `requirements.txt` with dependencies: whatsapp-chatbot-python>=0.5.1, whatsapp-api-client-python>=0.76.0, whatsapp-chatgpt-python>=0.0.1, openai>=1.12.0, PyYAML>=6.0, tenacity>=8.0.0, pytest>=7.0.0
- [ ] T004 [P] Create `.gitignore` to exclude venv/, config/config.json, config/config.yaml, config/*.json, config/*.yaml, __pycache__/, *.pyc, logs/, state/
- [ ] T005 [P] Create `config/config.example.json` template in config/ subfolder with placeholder credentials (green_api_instance_id, green_api_token, openai_api_key, ai_model, system_message, max_tokens, temperature, log_level [INFO/DEBUG], poll_interval_seconds [default: 5], max_retries)
- [ ] T006 Create `README.md` with setup instructions: Python 3.8+ requirement, virtual environment setup, pip install -r requirements.txt, config/config.json setup (copy from config/config.example.json), running the bot
- [ ] T007 Create Python virtual environment: `python -m venv venv`
- [ ] T008 Install dependencies: `pip install -r requirements.txt`

**Checkpoint**: Project structure ready, dependencies installed

### Version Control: Phase 1
- [ ] T008-VC0 **CREATE BRANCH FIRST**: `git checkout -b 001-phase1-infrastructure-setup` (⚠️ MUST be done BEFORE any work)
- [ ] T008-VC1 Commit all Phase 1 changes: `git add .` && `git commit -m "Phase 1: Setup - Project structure and dependencies"`
- [ ] T008-VC2 Push to branch: `git push origin 001-phase1-infrastructure-setup`
- [ ] T008-VC3 Create Pull Request: "Phase 1: Project Setup Complete"
- [ ] T008-VC4 Review, approve, and merge PR to master branch

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models, configuration, and logging infrastructure that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009a [P] Write tests for BotConfiguration in `tests/unit/test_config.py`: Test from_file() loads JSON config correctly, test from_file() loads YAML config correctly, test from_file() with missing required fields raises ValueError, test validate() passes with valid ranges (temperature 0.0-1.0, max_tokens >= 1, poll_interval >= 1), test validate() fails with invalid values, test log_level validates INFO/DEBUG only, test config dataclass attributes exist (including poll_interval_seconds, log_level)
- [ ] T009b [P] Create BotConfiguration model in `src/models/config.py` (BLOCKED until T009a approved)

- [ ] T010a [P] Write tests for WhatsAppMessage in `tests/unit/test_message.py`: Test from_notification() parses textMessage correctly, test from_notification() extracts sender info (id, name), test from_notification() detects group vs 1-on-1 (is_group flag), test dataclass attributes (message_id, chat_id, text_content, timestamp, message_type)
- [ ] T010b [P] Create WhatsAppMessage model in `src/models/message.py` (BLOCKED until T010a approved)

- [ ] T011a [P] Write tests for AIRequest in `tests/unit/test_message.py`: Test AIRequest creation with all required fields, test to_openai_payload() returns correct API format, test UUID generation for request_id, test timestamp auto-population, test system_message/max_tokens/temperature passthrough
- [ ] T011b [P] Create AIRequest model in `src/models/message.py` (BLOCKED until T011a approved)

- [ ] T012a [P] Write tests for AIResponse in `tests/unit/test_message.py`: Test from_openai_response() parses OpenAI response correctly, test truncate_for_whatsapp() truncates messages >4000 chars and appends "...", test truncate_for_whatsapp() preserves messages <=4000 chars, test is_truncated flag set correctly, test tokens_used extraction, test finish_reason handling
- [ ] T012b [P] Create AIResponse model in `src/models/message.py` (BLOCKED until T012a approved)

- [ ] T013a [P] Write tests for MessageState in `tests/unit/test_state.py`: Test load() from non-existent file returns default state, test load() from valid JSON file returns state, test save() persists to state/last_message.json, test update() updates message_id and timestamp, test JSON serialization/deserialization
- [ ] T013b [P] Create MessageState model in `src/models/state.py` (BLOCKED until T013a approved)

- [ ] T014a [P] Write tests for logger in `tests/unit/test_logger.py`: Test logger creates logs/ directory if missing, test file handler writes to logs/denidin.log, test console handler outputs to stderr, test RotatingFileHandler limits file size (mock large logs), test log format includes timestamp/name/level/message, test log_level parameter controls INFO vs DEBUG verbosity, test INFO logs: messages/errors only, test DEBUG logs: parsing/state/API details
- [ ] T014b [P] Create logging utility in `src/utils/logger.py` (BLOCKED until T014a approved)

- [ ] T015a [P] Write tests for state utility in `tests/unit/test_state_utils.py`: Test ensure_state_dir() creates state/ directory, test load_message_state() returns MessageState instance, test save_message_state() writes JSON file, test error handling for corrupted JSON
- [ ] T015b [P] Create state persistence utility in `src/utils/state.py` (BLOCKED until T015a approved)

**Checkpoint**: Foundation complete - all models, configuration, logging ready

### Version Control: Phase 2
- [ ] T015-VC0 **CREATE BRANCH FIRST**: `git checkout -b 001-phase2-foundational` (⚠️ MUST be done BEFORE any work)
- [ ] T015-VC1 Run all tests: `pytest tests/unit/ -v`
- [ ] T015-VC2 Commit Phase 2 changes: `git add .` && `git commit -m "Phase 2: Foundational - Core models and utilities with tests"`
- [ ] T015-VC3 Push to branch: `git push origin 001-phase2-foundational`
- [ ] T015-VC4 Create Pull Request: "Phase 2: Foundational Models & Utilities Complete"
- [ ] T015-VC5 Review, approve, and merge PR to master branch

---

## Phase 3: User Story 1 - Run Green API Demo Locally (Priority: P1) 🎯 MVP

**Goal**: Get the Green API ChatGPT integration working locally as proof-of-concept

**Independent Test**: Start bot, send "Hello" via WhatsApp, receive ChatGPT response

### Implementation for User Story 1

- [ ] T016a [US1] Write tests for bot.py initialization in `tests/integration/test_bot_startup.py`: Test BotConfiguration.from_file() loads config/config.json, test logging setup creates file and console handlers with configured log level, test GreenAPIBot instantiates with valid credentials, test OpenAI client instantiates with API key and 30s timeout, test startup logs contain instance ID, model, and poll interval, test missing config file raises clear error
- [ ] T016b [US1] Create minimal `bot.py` entry point (BLOCKED until T016a approved)

- [ ] T017a [US1] Write tests for message handler registration in `tests/integration/test_bot_startup.py`: Test @bot.router.message decorator exists, test decorator filters textMessage type only, test handle_text_message function signature accepts Notification parameter
- [ ] T017b [US1] Add message handler decorator to `bot.py` (BLOCKED until T017a approved)

- [ ] T018a [US1] Write tests for message processing in `tests/integration/test_message_handler.py`: Test handle_text_message extracts message_text from notification, test sender_name extraction, test incoming message logged, test OpenAI chat.completions.create() called with correct params (system message, user prompt), test AI response extracted from completion object, test AI response logged, test notification.answer() called with response text, mock all external APIs (Green API, OpenAI)
- [ ] T018b [US1] Implement handle_text_message() in `bot.py` (BLOCKED until T018a approved)

- [ ] T019a [US1] Write tests for error handling in `tests/integration/test_message_handler.py`: Test exception during OpenAI call logs error with exc_info=True, test exception sends fallback message "Sorry, I encountered an error. Please try again.", test fallback message sent via notification.answer(), test bot continues running after error (doesn't crash), mock openai.APIError
- [ ] T019b [US1] Add basic exception handling in handle_text_message() (BLOCKED until T019a approved)

- [ ] T020a [US1] Write tests for main block in `tests/integration/test_bot_startup.py`: Test main block only executes when __name__ == "__main__", test startup messages logged before bot.run_forever(), test bot.run_forever() called, mock bot.run_forever to prevent infinite loop
- [ ] T020b [US1] Add main block to `bot.py` (BLOCKED until T020a approved)

- [ ] T021 [US1] Make bot.py executable: `chmod +x bot.py`, add shebang `#!/usr/bin/env python3` (no tests needed - file system operation)

- [ ] T022 [US1] Create actual `config/config.json` file in config/ subfolder with real credentials for manual testing (no tests needed - configuration file, must be gitignored)

- [ ] T022a [US1] Configure Green API bot profile/display name as "DeniDin" via Green API settings or message signature (FR-012 coverage - bot identity)

- [ ] T022b [US1] Write automated E2E test in `tests/integration/test_end_to_end.py`: Test sends real WhatsApp message via Green API to configured phone number, test validates Green API connection (account state "authorized"), test validates OpenAI API key format and connectivity, test provides manual testing instructions in output, test waits for bot processing and checks logs for AI response generation

- [ ] T023 [US1] 👤 **MANUAL APPROVAL GATE**: Start bot with `python bot.py`, verify startup logs, send WhatsApp message "Hello", verify bot receives and logs it, verify ChatGPT response appears in WhatsApp within 30 seconds, stop bot with Ctrl+C - THIS IS YOUR ACCEPTANCE TEST FOR US1

**Checkpoint**: P1 Complete - Demo bot working locally, basic passthrough functional

### Version Control: Phase 3
- [ ] T023-VC0 **CREATE BRANCH FIRST**: `git checkout -b 001-phase3-us1-demo` (⚠️ MUST be done BEFORE any work)
- [ ] T023-VC1 Run all tests including E2E: `pytest tests/ -v`
- [ ] T023-VC2 Commit Phase 3 changes: `git add .` && `git commit -m "Phase 3: US1 - Green API demo bot working with ChatGPT integration and E2E tests"`
- [ ] T023-VC3 Push to branch: `git push origin 001-phase3-us1-demo`
- [ ] T023-VC4 Create Pull Request: "Phase 3: User Story 1 - MVP Demo Bot Complete"
- [ ] T023-VC5 Review, approve, and merge PR to master branch

---

## Phase 4: User Story 2 - Basic Message Passthrough (Priority: P2)

**Goal**: Refactor into modular DeniDin bot with proper architecture

**Independent Test**: Send any text message, get AI response; test multiple messages in sequence; test group chat behavior

### Implementation for User Story 2

- [ ] T024a [P] [US2] Write tests for WhatsAppHandler in `tests/unit/test_whatsapp_handler.py`: Test process_notification() returns WhatsAppMessage, test validate_message_type() accepts textMessage, test validate_message_type() rejects imageMessage/videoMessage, test is_bot_mentioned_in_group() detects "DeniDin" in message, test is_bot_mentioned_in_group() detects "@<bot_number>", test send_response() calls notification.answer() with message text, mock Notification objects
- [ ] T024b [P] [US2] Create WhatsAppHandler in `src/handlers/whatsapp_handler.py` (BLOCKED until T024a approved)

- [ ] T025a [P] [US2] Write tests for AIHandler in `tests/unit/test_ai_handler.py`: Test __init__ stores openai_client and config, test create_request() builds AIRequest from WhatsAppMessage with correct fields, test get_response() calls OpenAI API and returns AIResponse, test get_response() handles long responses (>4000 chars) via split_for_whatsapp(), test handle_long_response() returns list of chunked messages, mock openai.Client
- [ ] T025b [P] [US2] Create AIHandler in `src/handlers/ai_handler.py` (BLOCKED until T025a approved)

- [ ] T026a [US2] Write tests for bot.py refactoring in `tests/integration/test_bot_refactored.py`: Test bot imports WhatsAppHandler and AIHandler, test handlers instantiated in main, test handle_text_message() calls whatsapp_handler.process_notification(), test handle_text_message() calls ai_handler.create_request() with WhatsAppMessage, test handle_text_message() calls ai_handler.get_response(), test handle_text_message() calls whatsapp_handler.send_response() with AIResponse, mock handlers
- [ ] T026b [US2] Refactor `bot.py` to use handlers (BLOCKED until T026a approved)

- [ ] T027a [US2] Write tests for group chat detection in `tests/unit/test_whatsapp_handler.py`: Test WhatsAppHandler.is_bot_mentioned_in_group() returns False if is_group=False, test returns True if is_group=True and "DeniDin" in message_text, test returns True if "@<bot_number>" in message_text, test returns False if is_group=True but no mention, test integration: bot.py skips processing for group messages without mention
- [ ] T027b [US2] Add group chat detection in WhatsAppHandler (BLOCKED until T027a approved)

- [ ] T028a [US2] Write tests for message queuing in `tests/integration/test_message_order.py`: Test sequential processing logs "Processing message 1/3", test multiple messages processed in order, test log contains message_id for tracking, mock rapid message arrival
- [ ] T028b [US2] Add message queuing logic in `bot.py` (BLOCKED until T028a approved)

- [ ] T029a [US2] Write tests for message order preservation in `tests/integration/test_message_order.py`: Test timestamps logged for each incoming message, test message_ids logged, test responses sent in same order as messages received (msg1→resp1, msg2→resp2, msg3→resp3), mock Green API notification stream
- [ ] T029b [US2] Add message order preservation in `bot.py` (BLOCKED until T029a approved)

- [ ] T030 [US2] 👤 **MANUAL APPROVAL GATE**: Send 3 messages quickly ("Test 1", "Test 2", "Test 3"), verify bot responds to all 3 in order; add bot to group, send message without mention (bot ignores), send message with "DeniDin" (bot responds); test 1-on-1 chat still works - THIS IS YOUR ACCEPTANCE TEST FOR US2

**Checkpoint**: P2 Complete - Modular architecture, handles groups and sequences correctly

### Version Control: Phase 4
- [ ] T030-VC0 **CREATE BRANCH FIRST**: `git checkout -b 001-phase4-us2-modular` (⚠️ MUST be done BEFORE any work)
- [ ] T030-VC1 Run all tests: `pytest tests/ -v`
- [ ] T030-VC2 Commit Phase 4 changes: `git add .` && `git commit -m "Phase 4: US2 - Modular architecture with handlers and group chat support"`
- [ ] T030-VC3 Push to branch: `git push origin 001-phase4-us2-modular`
- [ ] T030-VC4 Create Pull Request: "Phase 4: User Story 2 - Modular Architecture Complete"
- [ ] T030-VC5 Review, approve, and merge PR to master branch

---

## Phase 5: User Story 3 - Error Handling & Resilience (Priority: P3)

**Goal**: Gracefully handle API failures, timeouts, unsupported messages

**Independent Test**: Simulate failures (invalid API key, network timeout, send image), verify fallback messages

### Implementation for User Story 3

- [ ] T031a [P] [US3] Write tests for retry logic in AIHandler in `tests/unit/test_ai_handler_retry.py`: Test get_response() retries 3 times on RateLimitError, test exponential backoff timing (1s, 2s, 4s), test get_response() retries on APITimeoutError, test get_response() retries on APIError, test get_response() fails after 3 attempts, mock openai exceptions with tenacity
- [ ] T031b [P] [US3] Add retry logic to AIHandler.get_response() with tenacity decorator (BLOCKED until T031a approved)

- [ ] T032a [P] [US3] Write tests for retry logic in WhatsAppHandler in `tests/unit/test_whatsapp_handler_retry.py`: Test send_response() retries 3 times on requests.RequestException, test exponential backoff for Green API sendMessage, test send_response() fails after 3 attempts with clear error, mock requests exceptions
- [ ] T032b [P] [US3] Add retry logic to WhatsAppHandler.send_response() with tenacity (BLOCKED until T032a approved)

- [ ] T033a [US3] Write tests for timeout handling in `tests/unit/test_ai_handler.py`: Test get_response() catches openai.APITimeoutError, test timeout logged with timestamp and error details, test fallback AIResponse returned with message "Sorry, I'm having trouble connecting to my AI service. Please try again later.", test fallback sent via WhatsAppHandler.send_response(), mock APITimeoutError
- [ ] T033b [US3] Add timeout handling in AIHandler (BLOCKED until T033a approved)

- [ ] T034a [US3] Write tests for rate limit handling in `tests/unit/test_ai_handler.py`: Test get_response() catches openai.RateLimitError, test rate limit logged with timestamp, test fallback message "I'm currently at capacity. Please try again in a minute.", test user receives fallback via notification.answer(), mock RateLimitError
- [ ] T034b [US3] Add rate limit handling in AIHandler (BLOCKED until T034a approved)

- [ ] T035a [US3] Write tests for Green API errors in `tests/unit/test_whatsapp_handler.py`: Test send_response() catches requests.HTTPError, test 400 error logged with status code, test 401 error logged (authentication), test 429 error logged (rate limit), test 500 error logged (server error), test fallback message varies by error type, mock HTTPError with different status codes
- [ ] T035b [US3] Add Green API error handling in WhatsAppHandler (BLOCKED until T035a approved)

- [ ] T036a [US3] Write tests for unsupported message types in `tests/unit/test_whatsapp_handler.py`: Test validate_message_type() rejects "imageMessage", test validate_message_type() rejects "audioMessage", test validate_message_type() rejects "videoMessage", test auto-reply sent "I currently only support text messages.", test bot skips processing and continues, test warning logged
- [ ] T036b [US3] Add unsupported message type handling in WhatsAppHandler (BLOCKED until T036a approved)

- [ ] T037a [US3] Write tests for global exception handler in `tests/integration/test_bot_exception_handling.py`: Test handle_text_message() catches any Exception, test full traceback logged, test generic fallback sent "Sorry, I encountered an error processing your message. Please try again.", test bot continues running after exception (doesn't crash), mock unexpected exceptions (KeyError, ValueError)
- [ ] T037b [US3] Add global exception handler in bot.py handle_text_message() (BLOCKED until T037a approved)

- [ ] T038a [US3] Write tests for message length validation in `tests/unit/test_ai_handler.py`: Test prompt >10000 chars triggers warning log, test long prompt truncated to 10000 chars OR fallback message sent, test fallback message "Your message is too long. Please send a shorter message (max 10,000 characters).", test short messages (<10000) pass through unchanged
- [ ] T038b [US3] Add message length validation in AIHandler (BLOCKED until T038a approved)

- [ ] T039 [US3] 👤 **MANUAL APPROVAL GATE**: 1) Set invalid openai_api_key in config.json, restart bot, send message, verify fallback; 2) Send image/voice note via WhatsApp, verify "I only support text" auto-reply; 3) Send 10,001 character message, verify length validation handling; 4) Check logs/denidin.log for proper error logging with timestamps and error codes - THIS IS YOUR ACCEPTANCE TEST FOR US3

**Checkpoint**: P3 Complete - Robust error handling, bot doesn't crash on failures

### Version Control: Phase 5
- [ ] T039-VC0 **CREATE BRANCH FIRST**: `git checkout -b 001-phase5-us3-error-handling` (⚠️ MUST be done BEFORE any work)
- [ ] T039-VC1 Run all tests: `pytest tests/ -v`
- [ ] T039-VC2 Commit Phase 5 changes: `git add .` && `git commit -m "Phase 5: US3 - Comprehensive error handling and resilience"`
- [ ] T039-VC3 Push to branch: `git push origin 001-phase5-us3-error-handling`
- [ ] T039-VC4 Create Pull Request: "Phase 5: User Story 3 - Error Handling & Resilience Complete"
- [ ] T039-VC5 Review, approve, and merge PR to master branch

---

## Phase 6: User Story 4 - Configuration & Deployment (Priority: P4)

**Goal**: Externalize all config, add deployment readiness (logging, state persistence)

**Independent Test**: Change config values, restart bot, verify new config applied; simulate restart to test state persistence

### Implementation for User Story 4

- [ ] T040a [P] [US4] Write tests for enhanced config validation in `tests/unit/test_config.py`: Test from_env() raises ValueError listing missing GREEN_API_INSTANCE_ID, test from_env() raises ValueError for missing GREEN_API_TOKEN, test from_env() raises ValueError for missing OPENAI_API_KEY, test error message clearly lists ALL missing variables, test from_env() succeeds with all required vars present
- [ ] T040b [P] [US4] Enhance BotConfiguration.from_env() to validate required env vars (BLOCKED until T040a approved)

- [ ] T041a [P] [US4] Write tests for config.validate() in `tests/unit/test_config.py`: Test validate() passes with temperature=0.7 (valid range 0.0-1.0), test validate() raises ValueError if temperature=-0.1, test validate() raises ValueError if temperature=1.5, test validate() raises ValueError if max_tokens=0, test validate() raises ValueError if poll_interval=0, test error message includes specific field name
- [ ] T041b [P] [US4] Add BotConfiguration.validate() logic (BLOCKED until T041a approved)

- [ ] T042a [US4] Write tests for config validation integration in `tests/integration/test_bot_startup.py`: Test bot.py calls config.validate() after from_env(), test ValueError caught and logged, test sys.exit(1) called on invalid config, test bot doesn't start with invalid config, mock sys.exit
- [ ] T042b [US4] Call config.validate() in bot.py after loading config (BLOCKED until T042a approved)

- [ ] T043a [US4] Write tests for config logging in `tests/integration/test_bot_startup.py`: Test startup logs all config values, test API keys masked (show first 10 chars + "..."), test model logged, test temperature logged, test max_tokens logged, test poll_interval logged, test logs are DEBUG level or INFO
- [ ] T043b [US4] Add config logging in bot.py startup (BLOCKED until T043a approved)

- [ ] T044a [P] [US4] Write tests for MessageState integration in `tests/integration/test_bot_state.py`: Test bot loads state on startup, test incoming message_id compared to last_processed_message_id, test duplicate message skipped (not processed twice), test state.update(message_id) called after successful processing, test state persisted to state/last_message.json, test bot restart preserves state
- [ ] T044b [P] [US4] Integrate MessageState into bot.py (BLOCKED until T044a approved)

- [ ] T045a [US4] Write tests for log rotation in `tests/unit/test_logger.py`: Test RotatingFileHandler maxBytes=10MB, test backupCount=5 (creates .1, .2, .3, .4, .5 files), test logs/ directory created if missing, test old logs rotated when size limit reached, mock large log writes
- [ ] T045b [US4] Add log rotation configuration in logger.py (BLOCKED until T045a approved)

- [ ] T046 [US4] Create deployment guide in `DEPLOYMENT.md` (no tests needed - documentation): systemd service file example, environment variable setup for production, log monitoring with `tail -f logs/denidin.log`, recommended cloud VM specs (1 CPU, 1GB RAM), Green API webhook setup for production

- [ ] T047a [US4] Write tests for graceful shutdown in `tests/integration/test_bot_shutdown.py`: Test SIGINT signal handler registered, test SIGTERM signal handler registered, test "Shutting down gracefully..." logged on signal, test current message processing completes before exit, test bot.run_forever() exits cleanly, mock signal handlers
- [ ] T047b [US4] Add graceful shutdown handling in bot.py (BLOCKED until T047a approved)

- [ ] T048 [US4] 👤 **MANUAL APPROVAL GATE**: 1) Remove openai_api_key from config.json, start bot, verify clear error and exit; 2) Set temperature to 2.0, start bot, verify validation error; 3) Set ai_model to "gpt-4o-mini", restart, send message, verify model change in logs; 4) Start bot, send message, Ctrl+C, restart bot, send new message, verify no duplicate processing via state persistence - THIS IS YOUR ACCEPTANCE TEST FOR US4

**Checkpoint**: P4 Complete - Production-ready config, deployment guide, state persistence working

### Version Control: Phase 6
- [ ] T048-VC0 **CREATE BRANCH FIRST**: `git checkout -b 001-phase6-us4-deployment` (⚠️ MUST be done BEFORE any work)
- [ ] T048-VC1 Run all tests: `pytest tests/ -v`
- [ ] T048-VC2 Commit Phase 6 changes: `git add .` && `git commit -m "Phase 6: US4 - Production-ready configuration and deployment"`
- [ ] T048-VC3 Push to branch: `git push origin 001-phase6-us4-deployment`
- [ ] T048-VC4 Create Pull Request: "Phase 6: User Story 4 - Configuration & Deployment Complete"
- [ ] T048-VC5 Review, approve, and merge PR to master branch

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final refinements, documentation, code cleanup

**Note**: Phase 2 already created foundational tests; Phase 7 adds polish and validates all tests pass

- [ ] T049 [P] Add comprehensive docstrings to all classes and methods in src/models/, src/handlers/, src/utils/ (Google-style docstrings with Args, Returns, Raises sections) - no additional tests needed, documentation only

- [ ] T050 [P] Run pytest on all existing unit tests (created in Phase 2-6): `pytest tests/unit/ -v` - verify all unit tests pass

- [ ] T051 [P] Run pytest on all existing integration tests (created in Phase 2-6): `pytest tests/integration/ -v` - verify all integration tests pass

- [ ] T052a [P] Write additional test fixtures in `tests/fixtures/sample_messages.json`: Create realistic Green API notification examples (textMessage with emoji, long textMessage >4000 chars, imageMessage, audioMessage, videoMessage, group message with mention, group message without mention, 1-on-1 message), include timestamps and sender info
- [ ] T052b [P] Create test fixtures file `tests/fixtures/sample_messages.json` (BLOCKED until T052a approved)

- [ ] T053 [P] Run full test suite: `pytest tests/ -v --cov=src --cov-report=html` - verify 100% of tests pass, generate coverage report

- [ ] T053a [P] Performance validation test (NFR-007): Simulate 100 messages/hour load to validate sequential processing capacity meets throughput requirement (optional: can be manual testing or automated load test script)

- [ ] T054a [P] Add type hints validation: Create `tests/type_check.py` to verify type hints using mypy (test all function signatures have type hints, test return types specified, test Optional/List/Dict used correctly)
- [ ] T054b [P] Add type hints to all function signatures in src/ and bot.py using Python typing module (str, int, bool, Optional, List, Dict) (BLOCKED until T054a approved)

- [ ] T055a [P] Create linter config `.pylintrc` with project-specific rules: max-line-length=120, ignore=venv,tests, enable=all
- [ ] T055b [P] Run linter and fix all warnings: `pylint src/ bot.py` - fix code style issues, ensure pylint score >= 9.0/10

- [ ] T056 [P] Update README.md with: architecture diagram (ASCII art: WhatsApp → GreenAPI → DeniDin → OpenAI → ChatGPT), troubleshooting section (bot doesn't respond, API errors, rate limits), FAQ (change AI model, cost estimation, webhook vs polling)

- [ ] T057a [P] Write tests for cost tracking in `tests/unit/test_cost_tracker.py`: Test log_token_usage() records total_tokens from AIResponse, test calculate_cost() computes cost per model (gpt-4o, gpt-4o-mini), test daily_summary() aggregates tokens and cost, test monthly_estimate() projects costs
- [ ] T057b [P] Add cost monitoring helper in `src/utils/cost_tracker.py` (BLOCKED until T057a approved)

- [ ] T058 [P] Create `CONTRIBUTING.md` (no tests needed - documentation): code style guide (PEP 8, 120 char lines), how to add new features, how to run tests, PR process, TDD workflow (write tests first, get approval, implement)

**Checkpoint**: All polish tasks complete, code production-ready

### Version Control: Phase 7
- [ ] T058-VC0 **CREATE BRANCH FIRST**: `git checkout -b 001-phase7-polish` (⚠️ MUST be done BEFORE any work)
- [ ] T058-VC1 Run full test suite: `pytest tests/ -v --cov=src --cov-report=html`
- [ ] T058-VC2 Run linter: `pylint src/ denidin.py`
- [ ] T058-VC3 Commit Phase 7 changes: `git add .` && `git commit -m "Phase 7: Polish - Documentation, tests, and code quality"`
- [ ] T058-VC4 Push to branch: `git push origin 001-phase7-polish`
- [ ] T058-VC5 Create Pull Request: "Phase 7: Polish & Documentation Complete - Project Ready"
- [ ] T058-VC6 Review, approve, and merge PR to master branch
- [ ] T058-VC7 Tag release: `git tag v1.0.0` && `git push origin v1.0.0`

---

## Dependency Graph (TDD Pattern)

**Legend**: 
- A → B means "A must be completed before B can start"
- T###a → 👤 APPROVAL → T###b (every implementation task)

### Setup Dependencies
```
T001 → T002, T007
T003 → T008
T005 → T022 (in Phase 3)
```

### Foundational Dependencies (TDD Pairs)
```
T008 → All Phase 2 test tasks (T009a, T010a, T011a, T012a, T013a, T014a, T015a)

TDD Pairs (each requires human approval):
T009a → 👤 APPROVAL → T009b (BotConfiguration)
T010a → 👤 APPROVAL → T010b (WhatsAppMessage)
T011a → 👤 APPROVAL → T011b (AIRequest)
T012a → 👤 APPROVAL → T012b (AIResponse)
T013a → 👤 APPROVAL → T013b (MessageState)
T014a → 👤 APPROVAL → T014b (Logger)
T015a → 👤 APPROVAL → T015b (State utils)

(All Phase 2 "a" test tasks are parallelizable with [P] marker)
Phase 2 complete (all "b" tasks done) → Phase 3 can start
```

### User Story Dependencies (TDD Pairs)
```
Foundation (Phase 2):
T009b → T016a (config needed for bot.py tests)
T014b → T016a (logging needed for bot.py tests)
T010b, T011b, T012b → T018a (models needed for message handling tests)

User Story 1 (Phase 3):
T016a → 👤 APPROVAL → T016b
T016b, T017a → 👤 APPROVAL → T017b
T017b, T018a → 👤 APPROVAL → T018b
T018b, T019a → 👤 APPROVAL → T019b
T019b, T020a → 👤 APPROVAL → T020b
T020b → T021, T022 → T023 (manual approval gate)

User Story 2 (Phase 4):
T023 complete → T024a, T025a can start
T024a → 👤 APPROVAL → T024b
T025a → 👤 APPROVAL → T025b
T024b, T025b, T026a → 👤 APPROVAL → T026b
T026b, T027a → 👤 APPROVAL → T027b
T027b, T028a → 👤 APPROVAL → T028b
T028b, T029a → 👤 APPROVAL → T029b
T029b → T030 (manual approval gate)

User Story 3 (Phase 5):
T030 complete → T031a-T038a can start (all "a" test tasks parallelizable)
T031a → 👤 APPROVAL → T031b
T032a → 👤 APPROVAL → T032b
T033a → 👤 APPROVAL → T033b
T034a → 👤 APPROVAL → T034b
T035a → 👤 APPROVAL → T035b
T036a → 👤 APPROVAL → T036b
T037a → 👤 APPROVAL → T037b
T038a → 👤 APPROVAL → T038b
All T03Xb complete → T039 (manual approval gate)

User Story 4 (Phase 6):
T039 complete → T040a-T041a can start
T040a → 👤 APPROVAL → T040b
T041a → 👤 APPROVAL → T041b
T040b, T041b, T042a → 👤 APPROVAL → T042b
T042b, T043a → 👤 APPROVAL → T043b
T044a → 👤 APPROVAL → T044b (depends on T013b, T015b)
T045a → 👤 APPROVAL → T045b
T046 (docs only), T047a → 👤 APPROVAL → T047b
All T04Xb complete → T048 (manual approval gate)

Polish (Phase 7):
T048 complete → T049-T058 can start
T052a → 👤 APPROVAL → T052b
T054a → 👤 APPROVAL → T054b
T057a → 👤 APPROVAL → T057b
All tests written → T050, T051, T053 (run test suites)
```

### Critical Path (Longest TDD Chain)
```
T001 → T002 → T008 → T009a → 👤 → T009b → T016a → 👤 → T016b → T017a → 👤 → T017b → T018a → 👤 → T018b → T022 → T023 → T024a → 👤 → T024b → T026a → 👤 → T026b → T027a → 👤 → T027b → T030 → T031a → 👤 → T031b → T039 → T040a → 👤 → T040b → T042a → 👤 → T042b → T044a → 👤 → T044b → T048 → T053 → T057b
```

**👤 = Human Approval Gate** (every "a" task requires your approval before "b" can start)

---

## Parallel Execution Recommendations (TDD-Aware)

### Maximum Parallelism by Phase

**Phase 1 (Setup)**: 
- Can parallelize: T002, T003, T004, T005, T006 (5 tasks)
- After T001 completes
- No TDD pairs (infrastructure only)

**Phase 2 (Foundational)**:
- **Test tasks** (parallelizable): T009a, T010a, T011a, T012a, T013a, T014a, T015a (7 tasks)
- **👤 APPROVAL GATE**: Review all 7 test files before proceeding
- **Implementation tasks** (parallelizable): T009b, T010b, T011b, T012b, T013b, T014b, T015b (7 tasks)
- **Time estimate**: 2 hours tests + approval + 2 hours implementation = ~4 hours

**Phase 3 (US1)**:
- **Sequential TDD pairs**: T016a→👤→T016b → T017a→👤→T017b → T018a→👤→T018b → T019a→👤→T019b → T020a→👤→T020b
- Each pair: ~30 min (15 min write test, approval, 15 min implement)
- **Time estimate**: 5 pairs × 30min = 2.5 hours + T021-T023 = ~3 hours

**Phase 4 (US2)**:
- **Parallel test tasks**: T024a, T025a (2 tasks) - 30 min
- **👤 APPROVAL GATE**: Review handler tests
- **Parallel implementation**: T024b, T025b (2 tasks) - 30 min
- **Sequential pairs**: T026a→👤→T026b → T027a→👤→T027b → T028a→👤→T028b → T029a→👤→T029b
- **Time estimate**: ~3 hours

**Phase 5 (US3)**:
- **Parallel test tasks**: T031a, T032a, T033a, T034a, T035a, T036a (6 tasks) - 1 hour
- **👤 APPROVAL GATE**: Review all error handling tests
- **Parallel implementation**: T031b-T036b (6 tasks) - 1 hour
- **Sequential**: T037a→👤→T037b → T038a→👤→T038b - 30 min
- **Time estimate**: ~2.5 hours

**Phase 6 (US4)**:
- **Parallel test tasks**: T040a, T041a, T045a (3 tasks) - 30 min
- **👤 APPROVAL GATE**: Review config validation tests
- **Parallel implementation**: T040b, T041b, T045b (3 tasks) - 30 min
- **Sequential pairs**: T042a→👤→T042b → T043a→👤→T043b → T044a→👤→T044b → T047a→👤→T047b
- **Docs**: T046 (no tests needed)
- **Time estimate**: ~2.5 hours

**Phase 7 (Polish)**:
- **Parallel test tasks**: T052a, T054a, T057a (3 tasks) - 30 min
- **👤 APPROVAL GATE**: Review fixture/type/cost tests
- **Parallel docs/implementation**: T049 (docs), T052b, T054b, T055a, T055b, T056, T057b, T058 - 1.5 hours
- **Run test suites**: T050 (unit), T051 (integration), T053 (full suite) - 30 min
- **Time estimate**: ~2.5 hours

**Estimated Time to Complete** (with TDD parallelization + approval gates):
- Phase 1: 1 hour (infrastructure setup)
- Phase 2: 4 hours (tests + approval + implementation for 7 models)
- Phase 3: 3 hours (sequential TDD pairs for bot.py + manual test)
- Phase 4: 3 hours (handler tests + refactoring + manual test)
- Phase 5: 2.5 hours (error handling tests + manual test)
- Phase 6: 2.5 hours (config tests + deployment + manual test)
- Phase 7: 2.5 hours (polish + full test suite)
**Total**: ~18.5 hours of focused development time (includes human review time)

**Human Review Time Estimate**: ~3 hours (approving ~40 test files)

---

## Testing Strategy (TDD-Based)

### Test-First Workflow (Principle VI)

**Every implementation follows this pattern**:
1. Write comprehensive tests (T###a) covering:
   - Happy path (expected functionality)
   - Edge cases (boundary conditions)
   - Error scenarios (exceptions, invalid input)
   - Integration points (mocked external APIs)

2. **👤 HUMAN APPROVAL GATE**: You review tests for:
   - Coverage of all acceptance criteria from spec.md
   - Correct mocking of external dependencies
   - Realistic test data and assertions
   - Clear test names describing behavior

3. Implement code (T###b) to pass approved tests
4. Run tests to validate implementation
5. Tests are FROZEN (no changes without re-approval)

### Manual Testing Requirements (Acceptance Gates)

Each user story has a manual acceptance test (T023, T030, T039, T048):

**P1 (T023)** - 👤 **YOU TEST**: Start bot, send "Hello" via WhatsApp, receive ChatGPT response, stop bot
**P2 (T030)** - 👤 **YOU TEST**: Send 3 messages quickly, verify order; test group chat behavior
**P3 (T039)** - 👤 **YOU TEST**: Test error scenarios (invalid API key, unsupported media, long message)
**P4 (T048)** - 👤 **YOU TEST**: Test config validation, model switching, state persistence across restarts

### Automated Testing (Built Throughout Phases 2-6)

**Unit Tests** (created in Phase 2-6 "a" tasks):
- `tests/unit/test_config.py` - T009a, T040a, T041a: BotConfiguration.from_env(), validate()
- `tests/unit/test_message.py` - T010a, T011a, T012a: WhatsAppMessage, AIRequest, AIResponse models
- `tests/unit/test_state.py` - T013a: MessageState load/save/update
- `tests/unit/test_logger.py` - T014a, T045a: Logger setup, rotation
- `tests/unit/test_state_utils.py` - T015a: State persistence utilities
- `tests/unit/test_whatsapp_handler.py` - T024a, T027a, T035a, T036a: WhatsAppHandler methods
- `tests/unit/test_ai_handler.py` - T025a, T033a, T034a, T038a: AIHandler methods
- `tests/unit/test_ai_handler_retry.py` - T031a: Retry logic with tenacity
- `tests/unit/test_whatsapp_handler_retry.py` - T032a: Green API retry logic
- `tests/unit/test_cost_tracker.py` - T057a: Cost monitoring

**Integration Tests** (created in Phase 3-6 "a" tasks):
- `tests/integration/test_bot_startup.py` - T016a, T017a, T020a, T042a, T043a: Bot initialization, config loading
- `tests/integration/test_message_handler.py` - T018a, T019a: Message processing, error handling
- `tests/integration/test_bot_refactored.py` - T026a: Handler integration
- `tests/integration/test_message_order.py` - T028a, T029a: Queuing, order preservation
- `tests/integration/test_bot_exception_handling.py` - T037a: Global exception handler
- `tests/integration/test_bot_state.py` - T044a: State persistence integration
- `tests/integration/test_bot_shutdown.py` - T047a: Graceful shutdown

**Test Fixtures**:
- `tests/fixtures/sample_messages.json` - T052a: Realistic Green API notifications

**Run Tests** (Phase 7):
- T050: `pytest tests/unit/ -v` (unit tests only)
- T051: `pytest tests/integration/ -v` (integration tests only)
- T053: `pytest tests/ -v --cov=src --cov-report=html` (full suite with coverage)

### Acceptance Criteria Validation (TDD Mapping)

Map each acceptance scenario from spec.md to TDD task pairs:

**US1, Scenario 1** (Demo runs): T016a/b-T020a/b → T023 manual test  
**US1, Scenario 2** (Receives message, sends response): T018a/b → T023 manual test  
**US1, Scenario 3** (Graceful shutdown): T020a/b, T047a/b  
**US2, Scenario 1** (AI response): T025a/b, T026a/b → T030 manual test  
**US2, Scenario 2** (Full response sent): T012a/b, T025a/b → T030 manual test  
**US2, Scenario 3** (Multiple messages in order): T028a/b, T029a/b → T030 manual test  
**US2, Scenario 4** (Group chat only when mentioned): T027a/b → T030 manual test  
**US3, Scenario 1** (AI timeout fallback): T033a/b → T039 manual test  
**US3, Scenario 2** (Rate limit retry): T031a/b, T034a/b → T039 manual test  
**US3, Scenario 3** (Unsupported media): T036a/b → T039 manual test  
**US3, Scenario 4** (Exception doesn't crash): T037a/b → T039 manual test  
**US4, Scenario 1** (Loads config from file): T040a/b → T048 manual test  
**US4, Scenario 2** (Configurable AI endpoint): T040a/b, T041a/b → T048 manual test  
**US4, Scenario 3** (Config validation error): T042a/b → T048 manual test  
**US4, Scenario 4** (Background service, auto-restart): T046, T047a/b → T048 manual test  

---

## Notes (TDD Updated)

- **Phase 1 Focus**: Setup infrastructure (no TDD needed - file system operations)
- **Phase 2 Foundation**: FIRST set of tests written - establishes testing patterns for all future work
- **Phase 3-6 User Stories**: Every feature implemented via TDD (test first, approve, implement)
- **Phase 7 Polish**: Run all accumulated tests, add final coverage
- **Incremental Delivery**: After each manual approval gate (T023, T030, T039, T048), user story is independently testable and deliverable
- **Test Immutability**: Once you approve a test (T###a), it CANNOT change during T###b implementation without your re-approval
- **Approval Parallelization**: You can approve multiple test files in batch (e.g., approve all Phase 2 tests together), then all implementations can run in parallel
- **Cost Tracking**: T057a/b adds OpenAI API cost monitoring
- **State Management**: T013a/b, T044a/b prevents duplicate processing on bot restart
- **Error Handling**: P3 tasks (T031a/b-T038a/b) are critical for production reliability
- **Configuration**: P4 tasks (T040a/b-T047a/b) externalize all secrets and prepare for deployment

**Ready for Implementation**: 
1. Start with Phase 1 (T001-T008) - infrastructure setup
2. Phase 2 (T009a-T015a) - write ALL foundation tests - **SUBMIT FOR YOUR APPROVAL**
3. After approval → Phase 2 (T009b-T015b) - implement all models
4. Phase 3-6 - repeat TDD cycle for each user story
5. Phase 7 - polish and validate

**Total Task Count**: 
- Infrastructure: 8 tasks (Phase 1)
- Foundation: 14 tasks (7 TDD pairs in Phase 2)
- User Story 1: 13 tasks (5 TDD pairs + 3 misc in Phase 3)
- User Story 2: 13 tasks (6 TDD pairs + 1 manual in Phase 4)
- User Story 3: 17 tasks (8 TDD pairs + 1 manual in Phase 5)
- User Story 4: 17 tasks (8 TDD pairs + 1 manual in Phase 6)
- Polish: 12 tasks (3 TDD pairs + 6 misc in Phase 7)
**Total**: ~94 tasks (was 58 before TDD split), ~18.5 hours estimate
