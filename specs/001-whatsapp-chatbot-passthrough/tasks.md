# Tasks: WhatsApp AI Chatbot Passthrough

**Input**: Design documents from `/specs/001-whatsapp-chatbot-passthrough/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Manual end-to-end testing via WhatsApp messages; unit tests optional for Phase 1

**Organization**: Tasks are grouped by user story (P1-P4) to enable independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- All paths relative to `denidin-bot/` project root

## Path Conventions

Single Python project structure:
- `bot.py` - Main entry point
- `src/` - Source code (handlers/, models/, utils/)
- `tests/` - Test suite (unit/, integration/)
- `config/` - Configuration files (.env, settings.py)
- `logs/` - Application logs
- `state/` - Runtime state persistence

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project structure and install dependencies

- [ ] T001 Create project directory `denidin-bot/` with subdirectories: src/{handlers,models,utils}, tests/{unit,integration,fixtures}, config/, logs/, state/
- [ ] T002 [P] Create `__init__.py` files in src/, src/handlers/, src/models/, src/utils/, tests/
- [ ] T003 [P] Create `requirements.txt` with dependencies: whatsapp-chatbot-python>=0.5.1, whatsapp-api-client-python>=0.76.0, whatsapp-chatgpt-python>=0.0.1, openai>=1.12.0, python-dotenv>=1.0.0, PyYAML>=6.0, tenacity>=8.0.0, pytest>=7.0.0
- [ ] T004 [P] Create `.gitignore` to exclude venv/, .env, config/.env, __pycache__/, *.pyc, logs/, state/
- [ ] T005 [P] Create `config/.env.example` template with placeholder credentials (GREEN_API_INSTANCE_ID, GREEN_API_TOKEN, OPENAI_API_KEY, AI_MODEL, SYSTEM_MESSAGE, MAX_TOKENS, TEMPERATURE, LOG_LEVEL, POLL_INTERVAL, MAX_RETRIES)
- [ ] T006 Create `README.md` with setup instructions: Python 3.8+ requirement, virtual environment setup, pip install -r requirements.txt, .env configuration, running the bot
- [ ] T007 Create Python virtual environment: `python -m venv venv`
- [ ] T008 Install dependencies: `pip install -r requirements.txt`

**Checkpoint**: Project structure ready, dependencies installed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models, configuration, and logging infrastructure that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009 [P] Create BotConfiguration model in `src/models/config.py` (dataclass with: green_api_instance_id, green_api_token, openai_api_key, ai_model, system_message, max_tokens, temperature, log_level, poll_interval, max_retries; from_env() classmethod to load from .env; validate() method)
- [ ] T010 [P] Create WhatsAppMessage model in `src/models/message.py` (dataclass with: message_id, chat_id, sender_id, sender_name, text_content, timestamp, message_type, is_group; from_notification() classmethod)
- [ ] T011 [P] Create AIRequest model in `src/models/message.py` (dataclass with: request_id (UUID), prompt, source_message_id, model, timestamp, system_message, max_tokens, temperature; to_openai_payload() method)
- [ ] T012 [P] Create AIResponse model in `src/models/message.py` (dataclass with: response_id, request_id, response_text, model, timestamp, tokens_used, finish_reason; from_openai_response() classmethod; split_for_whatsapp() method to chunk long responses)
- [ ] T013 [P] Create MessageState model in `src/models/state.py` (dataclass with: last_processed_message_id, last_update_timestamp; load() and save() methods for JSON persistence to state/last_message.json; update() method)
- [ ] T014 [P] Create logging utility in `src/utils/logger.py` (configure Python logging with file + console handlers, RotatingFileHandler for logs/denidin.log, 10MB max size, 5 backups, format: timestamp - name - level - message, load LOG_LEVEL from config)
- [ ] T015 [P] Create state persistence utility in `src/utils/state.py` (helper functions: ensure_state_dir(), load_message_state(), save_message_state(); handles state/ directory creation)

**Checkpoint**: Foundation complete - all models, configuration, logging ready

---

## Phase 3: User Story 1 - Run Green API Demo Locally (Priority: P1) 🎯 MVP

**Goal**: Get the Green API ChatGPT integration working locally as proof-of-concept

**Independent Test**: Start bot, send "Hello" via WhatsApp, receive ChatGPT response

### Implementation for User Story 1

- [ ] T016 [US1] Create minimal `bot.py` entry point with: import statements (logging, dotenv, whatsapp_chatbot_python, openai, os), load_dotenv('config/.env'), setup logging (file + console), initialize GreenAPIBot with instance ID and token from env vars, initialize OpenAI client with API key and timeout=30s, log bot startup info (instance ID, model)
- [ ] T017 [US1] Add message handler decorator `@bot.router.message(type_message=["textMessage"])` in `bot.py` with function handle_text_message(notification: Notification)
- [ ] T018 [US1] Implement handle_text_message() in `bot.py`: extract message_text from notification, extract sender_name, log incoming message, call OpenAI chat.completions.create() with system message and user prompt, extract AI response text, log AI response, call notification.answer() to send response back to WhatsApp
- [ ] T019 [US1] Add basic exception handling in handle_text_message(): try/except around AI call, log errors with exc_info=True, send fallback message "Sorry, I encountered an error. Please try again."
- [ ] T020 [US1] Add main block in `bot.py`: `if __name__ == "__main__":` with logger startup messages, bot.run_forever()
- [ ] T021 [US1] Make bot.py executable: `chmod +x bot.py`, add shebang `#!/usr/bin/env python3`
- [ ] T022 [US1] Create actual `config/.env` file (gitignored) with real credentials for testing
- [ ] T023 [US1] Manual test: Start bot with `python bot.py`, verify startup logs, send WhatsApp message, verify bot receives and logs it, verify ChatGPT response appears in WhatsApp within 30 seconds, stop bot with Ctrl+C

**Checkpoint**: P1 Complete - Demo bot working locally, basic passthrough functional

---

## Phase 4: User Story 2 - Basic Message Passthrough (Priority: P2)

**Goal**: Refactor into modular DeniDin bot with proper architecture

**Independent Test**: Send any text message, get AI response; test multiple messages in sequence; test group chat behavior

### Implementation for User Story 2

- [ ] T024 [P] [US2] Create WhatsAppHandler in `src/handlers/whatsapp_handler.py` (class with: process_notification() method to parse notification into WhatsAppMessage model, validate_message_type() to check if textMessage, is_bot_mentioned_in_group() to detect @DeniDin mentions, send_response() to wrap notification.answer())
- [ ] T025 [P] [US2] Create AIHandler in `src/handlers/ai_handler.py` (class with: __init__(openai_client, config), create_request() to build AIRequest from WhatsAppMessage, get_response() to call OpenAI API and return AIResponse, handle_long_response() to split messages >4000 chars)
- [ ] T026 [US2] Refactor `bot.py` to use handlers: import WhatsAppHandler and AIHandler, instantiate handlers in main, update handle_text_message() to call whatsapp_handler.process_notification(), then ai_handler.create_request(), then ai_handler.get_response(), then whatsapp_handler.send_response()
- [ ] T027 [US2] Add group chat detection in WhatsAppHandler: check if WhatsAppMessage.is_group is True, if in group and bot not mentioned (check if "DeniDin" or "@" + bot number in message_text), skip processing and return early
- [ ] T028 [US2] Add message queuing logic in `bot.py`: if multiple messages arrive while processing one, log "Processing message N/M" to indicate queue depth (simple sequential processing, no actual queue data structure in Phase 1)
- [ ] T029 [US2] Add message order preservation: log message timestamp and message_id for each incoming message, verify responses sent in same order as received
- [ ] T030 [US2] Manual test: Send 3 messages quickly ("Test 1", "Test 2", "Test 3"), verify bot responds to all 3 in order; test group chat by adding bot to group, verify it only responds when mentioned; test 1-on-1 chat still works

**Checkpoint**: P2 Complete - Modular architecture, handles groups and sequences correctly

---

## Phase 5: User Story 3 - Error Handling & Resilience (Priority: P3)

**Goal**: Gracefully handle API failures, timeouts, unsupported messages

**Independent Test**: Simulate failures (invalid API key, network timeout, send image), verify fallback messages

### Implementation for User Story 3

- [ ] T031 [P] [US3] Add retry logic to AIHandler.get_response(): use tenacity @retry decorator with stop_after_attempt(3), wait_exponential(multiplier=1, min=1, max=10), retry_if_exception_type(RateLimitError, APITimeoutError, APIError)
- [ ] T032 [P] [US3] Add retry logic to WhatsAppHandler.send_response(): use tenacity @retry for Green API sendMessage with stop_after_attempt(3), wait_exponential, retry on requests.exceptions.RequestException
- [ ] T033 [US3] Add timeout handling in AIHandler: catch openai.APITimeoutError, log timeout, return fallback AIResponse with message "Sorry, I'm having trouble connecting to my AI service. Please try again later."
- [ ] T034 [US3] Add rate limit handling in AIHandler: catch openai.RateLimitError, log rate limit hit, return fallback message "I'm currently at capacity. Please try again in a minute."
- [ ] T035 [US3] Add Green API error handling in WhatsAppHandler: catch requests.HTTPError for 400/401/429/500 status codes, log with status code and error message, send fallback based on error type
- [ ] T036 [US3] Add unsupported message type handling in WhatsAppHandler.validate_message_type(): if message_type not in ["textMessage"], log warning, send auto-reply "I currently only support text messages.", return False to skip processing
- [ ] T037 [US3] Add global exception handler in bot.py handle_text_message(): outer try/except for any Exception, log full traceback, send generic fallback "Sorry, I encountered an error processing your message. Please try again."
- [ ] T038 [US3] Add message length validation in AIHandler: if prompt > 10000 chars (OpenAI limit), log warning, truncate prompt or send fallback "Your message is too long. Please send a shorter message (max 10,000 characters)."
- [ ] T039 [US3] Manual test error scenarios: 1) Temporarily set invalid OPENAI_API_KEY in .env, restart bot, send message, verify fallback; 2) Send image/voice note, verify "I only support text" message; 3) Send very long message (>10k chars), verify handling; 4) Monitor logs for proper error logging with timestamps and error codes

**Checkpoint**: P3 Complete - Robust error handling, bot doesn't crash on failures

---

## Phase 6: User Story 4 - Configuration & Deployment (Priority: P4)

**Goal**: Externalize all config, add deployment readiness (logging, state persistence)

**Independent Test**: Change config values, restart bot, verify new config applied; simulate restart to test state persistence

### Implementation for User Story 4

- [ ] T040 [P] [US4] Enhance BotConfiguration.from_env() to validate required env vars: raise ValueError with clear message listing missing variables if GREEN_API_INSTANCE_ID, GREEN_API_TOKEN, or OPENAI_API_KEY are missing
- [ ] T041 [P] [US4] Add BotConfiguration.validate() logic: check temperature in range 0.0-1.0, max_tokens >= 1, poll_interval >= 1, raise ValueError with specific field name if validation fails
- [ ] T042 [US4] Call config.validate() in bot.py after loading config, catch ValueError and log error with sys.exit(1) if config invalid
- [ ] T043 [US4] Add config logging in bot.py startup: log all config values (mask API keys - show only first 10 chars + "..."), log model, temperature, max_tokens, poll_interval for troubleshooting
- [ ] T044 [P] [US4] Integrate MessageState into bot.py: load state on startup with state_util.load_message_state(), check if incoming message_id == last_processed_message_id (skip duplicates), update state after successful processing with state.update(message_id)
- [ ] T045 [US4] Add log rotation configuration in logger.py: use logging.handlers.RotatingFileHandler with maxBytes=10*1024*1024 (10MB), backupCount=5, ensure logs/ directory exists before creating handler
- [ ] T046 [US4] Create deployment guide in `DEPLOYMENT.md`: systemd service file example for Linux, environment variable setup for production, log monitoring with `tail -f logs/denidin.log`, recommended cloud VM specs (1 CPU, 1GB RAM), Green API webhook setup for production (replace polling)
- [ ] T047 [US4] Add graceful shutdown handling in bot.py: register signal handler for SIGINT/SIGTERM, log "Shutting down gracefully...", finish processing current message before exit
- [ ] T048 [US4] Manual test config scenarios: 1) Remove OPENAI_API_KEY from .env, start bot, verify clear error message and exit; 2) Set TEMPERATURE=2.0 (invalid), start bot, verify validation error; 3) Change AI_MODEL to "gpt-4o-mini", restart, send message, verify model change in logs; 4) Start bot, send message, stop bot (Ctrl+C), restart bot, send new message, verify no duplicate processing of old message

**Checkpoint**: P4 Complete - Production-ready config, deployment guide, state persistence working

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final refinements, documentation, code cleanup

- [ ] T049 [P] Add comprehensive docstrings to all classes and methods in src/models/, src/handlers/, src/utils/ (Google-style docstrings with Args, Returns, Raises sections)
- [ ] T050 [P] Create unit tests in tests/unit/: test_models.py (test WhatsAppMessage.from_notification(), AIResponse.split_for_whatsapp()), test_config.py (test BotConfiguration.from_env() with mock env vars, test validate())
- [ ] T051 [P] Create integration tests in tests/integration/: test_green_api.py (mock Green API responses, test WhatsAppHandler), test_openai.py (mock OpenAI responses, test AIHandler)
- [ ] T052 [P] Create test fixtures in tests/fixtures/: sample_messages.json with example Green API notifications (textMessage, imageMessage, group message, 1-on-1 message)
- [ ] T053 [P] Run pytest to verify all unit and integration tests pass: `pytest tests/`
- [ ] T054 [P] Add type hints to all function signatures using Python typing module (str, int, bool, Optional, List, Dict)
- [ ] T055 [P] Run linter (pylint or flake8) on all source code: `pylint src/ bot.py`, fix any warnings
- [ ] T056 Update README.md with: architecture diagram (ASCII art showing WhatsApp → GreenAPI → DeniDin → OpenAI → ChatGPT flow), troubleshooting section, FAQ (What if bot doesn't respond? How to change AI model? Cost estimation)
- [ ] T057 Add cost monitoring helper in `src/utils/cost_tracker.py`: log total_tokens from each AIResponse, calculate monthly cost estimate (tokens * model_cost_per_million / 1M), log daily summary
- [ ] T058 Create `CONTRIBUTING.md` with: code style guide (PEP 8), how to add new features, how to run tests, PR process

**Checkpoint**: All polish tasks complete, code production-ready

---

## Dependency Graph

**Legend**: A → B means "A must be completed before B can start"

### Setup Dependencies
```
T001 → T002, T007
T003 → T008
T005 → T022
```

### Foundational Dependencies
```
T008 → T009, T010, T011, T012, T013, T014, T015
(All Phase 2 tasks are parallelizable with [P] marker)
Phase 2 complete → Phase 3 can start
```

### User Story Dependencies
```
T009 → T016 (config needed for bot.py)
T014 → T016 (logging needed for bot.py)
T010, T011, T012 → T018 (models needed for message handling)

T016, T017, T018, T019, T020, T021 → T022 (bot.py must exist before .env testing)
T022 → T023 (credentials needed for manual test)

T023 complete (P1 working) → T024, T025 can start (P2)
T024, T025 → T026 (handlers needed before refactoring bot.py)
T026 → T027, T028, T029 (refactored bot needed for group/queue logic)
T029 → T030 (implementation before testing)

T030 complete (P2 working) → T031-T038 can start (P3)
T031, T032, T033, T034, T035, T036, T037, T038 → T039 (all error handling before testing)

T039 complete (P3 working) → T040-T047 can start (P4)
T040, T041 → T042 (validation logic before integration)
T044 → T013, T015 (state integration needs state models/utils)
T042, T043, T044, T045, T046, T047 → T048 (all config/deploy before testing)

T048 complete (P4 working) → T049-T058 can start (Polish)
(All Phase 7 tasks are parallelizable with [P] marker except T053 which needs T050, T051, T052)
```

### Critical Path (Longest Dependency Chain)
```
T001 → T002 → T008 → T009 → T016 → T017 → T018 → T022 → T023 → T024 → T026 → T027 → T030 → T031 → T039 → T040 → T042 → T044 → T048 → T053 → T057
```

---

## Parallel Execution Recommendations

### Maximum Parallelism by Phase

**Phase 1 (Setup)**: 
- Can parallelize: T002, T003, T004, T005, T006 (5 tasks)
- After T001 completes

**Phase 2 (Foundational)**:
- Can parallelize: T009, T010, T011, T012, T013, T014, T015 (7 tasks)
- All models, config, and utils can be built simultaneously

**Phase 3 (US1)**:
- Sequential: T016 → T017 → T018 → T019 → T020 → T021 → T022 → T023
- No parallelization (building single bot.py file iteratively)

**Phase 4 (US2)**:
- Can parallelize: T024, T025 (2 tasks - different handler files)
- Then sequential: T026 → T027 → T028 → T029 → T030

**Phase 5 (US3)**:
- Can parallelize: T031, T032, T033, T034, T035, T036 (6 tasks - different error scenarios)
- Then sequential: T037 → T038 → T039

**Phase 6 (US4)**:
- Can parallelize: T040, T041, T045, T046 (4 tasks)
- Then sequential: T042 → T043 → T044 → T047 → T048

**Phase 7 (Polish)**:
- Can parallelize: T049, T050, T051, T052, T054, T055, T056, T057, T058 (9 tasks)
- Then: T053 (depends on T050, T051, T052)

**Estimated Time to Complete** (with parallelization):
- Phase 1: 1 hour
- Phase 2: 2 hours (models + config)
- Phase 3: 3 hours (iterative bot.py development + testing)
- Phase 4: 3 hours (refactoring + manual testing)
- Phase 5: 2 hours (error handling + testing)
- Phase 6: 2 hours (config enhancement + deployment guide)
- Phase 7: 3 hours (docs, tests, polish)
**Total**: ~16 hours of focused development time

---

## Testing Strategy

### Manual Testing Requirements (End-to-End)

Each user story has a manual test checkpoint (T023, T030, T039, T048). Required tests:

**P1 (T023)**: Start bot, send "Hello" via WhatsApp, receive ChatGPT response, stop bot
**P2 (T030)**: Send 3 messages quickly, verify order; test group chat behavior
**P3 (T039)**: Test error scenarios (invalid API key, unsupported media, long message)
**P4 (T048)**: Test config validation, model switching, state persistence across restarts

### Automated Testing (Optional - Phase 7)

**Unit Tests** (T050):
- `test_models.py`: WhatsAppMessage.from_notification(), AIResponse.split_for_whatsapp()
- `test_config.py`: BotConfiguration.from_env(), validate()

**Integration Tests** (T051):
- `test_green_api.py`: Mock Green API responses, test WhatsAppHandler
- `test_openai.py`: Mock OpenAI responses, test AIHandler

**Run Tests**: `pytest tests/ -v`

### Acceptance Criteria Validation

Map each acceptance scenario from spec.md to tasks:

**US1, Scenario 1** (Demo runs): T016-T023  
**US1, Scenario 2** (Receives message, sends response): T018, T023  
**US1, Scenario 3** (Graceful shutdown): T020, T047  
**US2, Scenario 1** (AI response): T026, T030  
**US2, Scenario 2** (Full response sent): T012, T025  
**US2, Scenario 3** (Multiple messages in order): T028, T029, T030  
**US2, Scenario 4** (Group chat only when mentioned): T027, T030  
**US3, Scenario 1** (AI timeout fallback): T033, T039  
**US3, Scenario 2** (Rate limit retry): T034, T039  
**US3, Scenario 3** (Unsupported media): T036, T039  
**US3, Scenario 4** (Exception doesn't crash): T037, T039  
**US4, Scenario 1** (Loads config from .env): T040, T048  
**US4, Scenario 2** (Configurable AI endpoint): T040, T041, T048  
**US4, Scenario 3** (Config validation error): T042, T048  
**US4, Scenario 4** (Background service, auto-restart): T046, T047  

---

## Notes

- **Phase 1 Focus**: P1 (Run Green API Demo Locally) is the absolute minimum viable product - get this working first
- **Incremental Delivery**: After P1 works, each subsequent user story (P2, P3, P4) adds value independently
- **No Tests in Phase 1-6**: Manual testing sufficient for MVP; automated tests are Phase 7 polish
- **Parallelization**: Use [P] markers to identify tasks that can run simultaneously
- **State Management**: MessageState (T013, T044) prevents duplicate processing on bot restart
- **Error Handling**: P3 tasks (T031-T039) are critical for production but can be implemented after P1 and P2 prove the concept
- **Configuration**: P4 tasks (T040-T048) externalize all secrets and prepare for deployment
- **Cost Tracking**: T057 adds cost monitoring for OpenAI API usage

**Ready for Implementation**: Start with Phase 1 (T001-T008), then Phase 2 (T009-T015), then execute user stories in priority order (P1 → P2 → P3 → P4)
