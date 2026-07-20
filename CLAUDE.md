# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This repo is split into two independently deployable apps under `apps/`, plus SpecKit governance docs:

- **`apps/denidin-app/`** — the production WhatsApp AI assistant (main application). All app development happens here; it has its own `.pylintrc`, `mypy.ini`, `pytest.ini`, `requirements.txt`, `Dockerfile`, and virtualenv expectations.
- **`apps/morning-mcp-app/`** — a standalone app for the Morning/Green Invoice API (Israeli invoicing): a client library (`MorningClient`, `MorningAuth` under its own `src/denidin_mcp_morning/`), a FastMCP server (`server.py`, 7 invoice-management tools, streamable-HTTP, bearer-auth, `/health` endpoint) exposed to `apps/denidin-app` over a real ngrok tunnel, plus its sandbox-backed integration test suite. It has its own `requirements.txt`, `pytest.ini`, `Makefile`, `Dockerfile`, and config files — fully independent of `apps/denidin-app/` (`denidin-app` reaches it only over HTTP via the tunnel, never by importing its code). Remaining polish work (audit logging, run-both-apps docs) tracked under `specs/in-definition/018-denidin-morning-mcp-integration/`.
- **`specs/`** — SpecKit-style feature specifications, organized by status: `in-definition/`, `P1/`, `P2/`, `done/`, `not-doing/`, `bugfixes/`, `checklists/`. See "Spec-Driven Workflow" below.
- **`.github/`** — the project's constitution/methodology docs (see "Governance Docs" below) — these are binding rules for how work is done here, not just background reading.
- **`docker-compose.yml`** (repo root) — local-dev convenience for running both apps together; each app also builds/runs standalone via its own `Dockerfile` (`docker build`/`docker run` from within the app's own directory, no dependency on the other app or on compose).

**Almost all day-to-day commands below assume `cd apps/denidin-app` first**, unless working on the morning app (`cd apps/morning-mcp-app`).

## Commands

### Setup
```bash
cd apps/denidin-app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config/config.example.json config/config.json  # then fill in real credentials
```

### Run
```bash
cd apps/denidin-app
./run_denidin.sh      # start (enforces single instance via PID file)
./stop_denidin.sh      # graceful SIGTERM shutdown
python3 denidin.py     # run directly (foreground)
docker build -t denidin-app . && docker run --rm -v "$(pwd)/config:/app/config" -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" denidin-app   # containerized
```

### Test
```bash
cd apps/denidin-app
python3 -m pytest tests/ -v --tb=short          # full suite (expensive tests skipped by default)
python3 -m pytest tests/unit/ -v                # unit only
python3 -m pytest tests/integration/ -v         # integration only
python3 -m pytest tests/unit/test_session_manager.py::test_function -xvs   # single test
python3 -m pytest tests/ --cov=src --cov-report=html   # coverage (htmlcov/index.html)
```
Also runnable from repo root via `make test` (wraps the same pytest invocation from `apps/denidin-app/`).

Expensive tests (`tests/expensive/`, marked `@pytest.mark.expensive`) hit real OpenAI APIs and cost money — they are excluded by default (`pytest.ini` sets `addopts = -m "not expensive"`). Don't run them repeatedly — read `logs/test_logs/` for a prior run's output before re-running, and only re-run after a code change you're confident fixes the issue.

**Expensive test rules (strict):**
- **User approval is required before running any expensive test, every single time** — no exceptions, even for a single test, even as part of a larger approved task.
- **Never run expensive tests all together.** Go one at a time (`pytest tests/expensive/test_X.py::test_name -v -m expensive`), never a bare `-m expensive` sweep.
- **Read existing logs in `logs/test_logs/` before re-running anything.** A prior run's log may already answer the question.
- **Only re-run a previously-failed expensive test once you're confident a fix addresses the failure** — don't re-run speculatively to "see what happens."
- **Never re-run an expensive test yourself once it has been billed** (i.e. it actually reached OpenAI, whether it passed or failed) — that always requires a fresh, explicit approval from the user for that specific run, no exceptions, including "just to double-check" or "just to read the output." Re-running an *unbilled* failure (one that errored before reaching OpenAI) is fine without re-asking.
- **`apps/morning-mcp-app` runs as a separate long-lived process for these cross-app tests** (`./run_morning_mcp.sh` / `./stop_morning_mcp.sh`), not something pytest starts. Python does not hot-reload: any code or config change in `apps/morning-mcp-app` (tools, formatters, server, config.json) has **no effect on a running process**. Whenever you edit anything in `apps/morning-mcp-app` for the sake of a denidin-app E2E test, you **must** `./stop_morning_mcp.sh` then `./run_morning_mcp.sh` (verify the new tunnel URL lands in `running_status.json` with `"status": "running"`) **before** retrying the test — otherwise the test silently exercises stale code and any observed failure/pass is not meaningful.

**Never redirect test output to `/tmp` or other ad-hoc log files.** Each app's `conftest.py` already writes per-test-file logs to `logs/test_logs/{test_file}.log` automatically (see `pytest_runtest_setup` in `apps/denidin-app/conftest.py`); read from there instead of teeing to a custom path. This applies to both apps under `apps/`.

### Lint & Type-check
```bash
cd apps/denidin-app
python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc   # or: make lint (from repo root)
python3 -m mypy src/ --config-file=mypy.ini
```

### morning-mcp-app (self-contained, own Makefile)
```bash
cd apps/morning-mcp-app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config/config.example.json config/config.json  # then fill in real Morning API credentials
make test            # or: python3 -m pytest tests/ -v --tb=short
make docker-build && make docker-run
```

## Governance Docs — Read Before Non-Trivial Work

This project enforces its workflow through docs in `.github/`, which are authoritative and take precedence over generic conventions:

- **`.github/CONSTITUTION.md`** — binding coding standards (config handling, UTC timestamps, git workflow, no monkey-patching, logging format, retry/error-handling rules, file formats, exit codes). This is "WHAT we enforce."
- **`.github/METHODOLOGY.md`** — binding process (spec-first development, TDD with human approval gates, Bug-Driven Development for bug fixes, folder movement rules for `specs/`). This is "HOW we work."
- **`.github/quick-ref-constitution.md`** — condensed cheat-sheet of the two docs above; read this first if short on time.
- **`.github/agents/*.agent.md`** and **`.github/prompts/*.prompt.md`** — SpecKit agent definitions (`speckit.specify`, `speckit.plan`, `speckit.tasks`, `speckit.implement`, `speckit.analyze`, `speckit.clarify`, `speckit.constitution`, `speckit.checklist`, `speckit.taskstoissues`).

Note: `CONSTITUTION.md` opens with an absolute "ZERO MOCKING POLICY" banner claiming it overrides every other section, but later sections in the same file (§I, §V) explicitly permit mocking external services (OpenAI, Green API) in tests while forbidding mocking of *internal* application components (routers, handlers, managers, models). In practice, follow the more detailed §I/§V rule: real internal code paths always, mocks only for third-party network services, and never `unittest.mock` inside `tests/integration/` — use real sandbox endpoints, local HTTP fixture servers, or `@pytest.mark.expensive` for real API calls instead.

### Rules that matter most for code changes here
- **Never work on `master` directly.** Check `git branch --show-current`; if on master, create `feature/###-description` or `bugfix/###-description` first.
- **No environment variables** — `os.getenv()`/`os.environ` are forbidden. All config comes from `config/config.json` (or `config/config.test.json` in tests), loaded via `AppConfiguration` and passed by dependency injection.
- **UTC everywhere** — always `datetime.now(timezone.utc)`, never bare `datetime.now()`.
- **No monkey-patching** — no runtime method replacement or dynamic attribute injection; use dependency injection, strategy, template-method, or observer patterns instead (see CONSTITUTION §XVII for the canonical examples).
- **`pathlib.Path`**, not string concatenation or `os.path`.
- **Feature flags** for new behavior, under `config.feature_flags`, default `false`; when disabled, code path must be byte-for-byte identical to before. Unit tests may set flags; integration tests must never set flags (they test default production behavior).
- **Integration tests** simulate a real external entry point (e.g. a Green API webhook JSON dispatched through `bot.router`), not direct method calls into internal components — see CONSTITUTION §V for the distinction between true "integration" and "component integration" tests, and why routing/dispatcher coverage matters (a real production bug — missing `imageMessage` router — is the running example in these docs).
- **Tests are immutable once approved** — new phases add tests, they don't rewrite existing ones, without explicit human sign-off.
- Retry policy: retry once on 5xx/timeout after 1s; never retry 4xx. User-facing errors are friendly (`"[emoji] [what happened]. [what to do next]."`); technical detail goes to logs only.

## Architecture (`apps/denidin-app/`)

DeniDin is a WhatsApp bot (Green API) that forwards messages to OpenAI (GPT-4o-mini) with a two-tier memory system, RBAC, and media processing. Full diagrammed architecture: `.github/ARCHITECTURE.md`.

### Message flow
```
Green API webhook → denidin.py @bot.router.message(type_message=...) handlers
  → WhatsAppHandler (validate/parse notification, group-mention filtering)
  → UserManager (role: admin/godfather/client/blocked → token limit + memory scope)
  → SessionManager (load/create session, append message, prune to token budget)
  → AIHandler
      → MemoryManager.recall() (ChromaDB semantic search, only if enable_memory_system)
      → builds system prompt (constitution + role context + memories + history)
      → OpenAI call (retry: 3 attempts, 2s wait; rate-limit: 3 attempts, 5s wait)
  → SessionManager (store response, update token count)
  → WhatsAppHandler.send_response() (truncates >4000 chars)
```
Non-text messages (`imageMessage`, `documentMessage`, `videoMessage`, `audioMessage`) route through the same dispatcher pattern in `denidin.py` to `WhatsAppHandler.handle_media_message()` → `MediaHandler` → the extractor pipeline below. There is also a catch-all `@bot.router.message()` handler so no message type is silently dropped.

### Key components (`apps/denidin-app/src/`)
- **`denidin.py`** (repo root of the app, not under `src/`) — entry point; owns the global `bot` (GreenAPIBot) and `denidin_app` (a `DeniDin` instance holding `ai_handler`, `config`, `whatsapp_handler`, `cleanup_thread`); registers all `@bot.router.message(...)` handlers; `initialize_app(config_dict)` is the shared bootstrap used by both `__main__` and integration tests (constructs `AIHandler` → `WhatsAppHandler` → `MediaHandler`, wires memory startup recovery + cleanup thread if `enable_memory_system`).
- **`handlers/whatsapp_handler.py`** — Green API integration, message-type validation, group-mention detection, response sending/truncation.
- **`handlers/ai_handler.py`** — OpenAI integration via the Responses API, system-prompt construction, memory recall integration, session-to-long-term-memory transfer, RBAC-aware token limits, current-date injection into `instructions`, and Morning MCP remote-tool attachment for godfather/admin roles (see "Morning MCP integration" below).
- **`handlers/media_handler.py`** + **`handlers/extractors/`** — `MediaExtractor` abstract base with `ImageExtractor` (vision model per `config.ai_vision_model`, default `gpt-4o-mini`, single call for text+analysis), `PDFExtractor` (PyMuPDF page-to-image, delegates to `ImageExtractor`, aggregates per-page analysis, max 10 pages), `DOCXExtractor` (python-docx + optional AI analysis via `config.ai_model`). All extractors return a common contract: `extracted_text`, `document_analysis` (`document_type`/`summary`/`key_points`), `extraction_quality`, `warnings`, `model_used`.
- **`managers/session_manager.py`** — Tier-1 (short-term) memory: UUID sessions, JSON persistence under `data/sessions/`, per-role token limits, 24h expiration, archival to `data/sessions/expired/YYYY-MM-DD/`.
- **`managers/memory_manager.py`** — Tier-2 (long-term) memory: ChromaDB collections (`memory_{entity_id}`, `_public`, `_private`, `memory_system_context`), OpenAI embeddings per `config.ai_embedding_model` (default `text-embedding-3-large`), scope-filtered semantic recall.
- **`managers/user_manager.py`** — RBAC: role resolution (Admin > Godfather > Client > Blocked) from phone number, permission/token-limit/memory-scope lookups.
- **`managers/media_file_manager.py`**, **`managers/media_manager.py`** — media file lifecycle and orchestration supporting `MediaHandler`.
- **`services/cleanup_service.py`** — `SessionCleanupThread` (hourly background sweep) and `run_startup_cleanup` (recovers orphaned sessions on boot). 4-step cleanup per expired session: archive → transfer to ChromaDB → remove from active index → mark `transferred_to_longterm`.
- **`models/config.py`** — `AppConfiguration` dataclass; `from_file()`/`from_dict()` loading + `validate()`; this is the single source of truth for all runtime config (no env vars).
- **`models/`** (message, user, media, media_attachment, document, green_api, state) — typed data models for messages, media attachments, document analysis, RBAC users.
- **`constants/error_messages.py`** — centralized user-facing error strings (friendly, no stack traces).

### Data & config
- `config/config.json` (gitignored, real secrets) vs `config/config.example.json` (safe placeholders, committed) vs `config/config.test.json` (used by tests, loaded via `AppConfiguration.from_file`, no env vars).
- `data/sessions/`, `data/memory/` (ChromaDB), `data/constitution/` — all gitignored runtime state, isolated from test data via the `data_root` config field.
- `logs/denidin.log` (production) and `logs/test_logs/{test_file}.log` (per-test-file, auto-configured by `conftest.py`) — check these logs instead of re-running expensive tests to get more diagnostic detail.

### Morning MCP integration (`apps/denidin-app` ↔ `apps/morning-mcp-app`)
Godfather/admin users manage invoices in natural Hebrew: `AIHandler` calls OpenAI's **Responses API** with the Morning server attached as a **remote MCP tool** (`type: "mcp"`, bearer-auth header), reached over a real ngrok tunnel — no local import of `denidin_mcp_morning` code, no mocking of the MCP round-trip. The tunnel URL is discovered via a shared status file (`apps/morning-mcp-app/running_status.json`, must show `"status": "running"`); `apps/denidin-app`'s own `config.mcp.morning_status_file` points at it. RBAC-gated: only godfather/admin roles get the tool attached. Current date is injected into `instructions` at reply time (UTC, computed per call — not templated into the constitution file) so the model resolves relative dates correctly instead of guessing a wrong year.

### `apps/morning-mcp-app/` (separate app, own package/tests/config/Docker)
Standalone `MorningClient`/`MorningAuth` for the Morning (Green Invoice) sandbox API — token-managed HTTP client with retry/backoff (`requests` + urllib3 `Retry`). Own package at `apps/morning-mcp-app/src/denidin_mcp_morning/`, imported as `from denidin_mcp_morning.morning_client import MorningClient` (its `conftest.py` puts its own `src/` on `sys.path` — no cross-app imports, no `sys.path` reach-through into `apps/denidin-app/`). `server.py` builds a FastMCP server exposing 7 tools (`create_invoice`, `list_invoices`, `get_invoice_details`, `update_invoice_status`, `add_client`, `get_financial_summary`, `download_invoice_pdf`) over streamable-HTTP, wrapped in `BearerTokenMiddleware` (single shared secret, not OAuth) plus an unauthenticated `/health` liveness route. `./run_morning_mcp.sh` / `./stop_morning_mcp.sh` run it as a standalone long-lived process (single-instance PID-file enforced) with an ngrok tunnel, writing `running_status.json` for `apps/denidin-app` (and its own expensive tests, via `discover_running_server()` in `tests/expensive/e2e_helpers.py`) to discover the live URL — reusing an already-warm tunnel instead of spinning up a fresh one avoids an ngrok cold-start flake (`424 Failed Dependency` on the first request). Exercised by `apps/morning-mcp-app/tests/integration/test_morning_sandbox_*.py`, which hit the real Morning sandbox (constitution: no mocking). Config lives in its own `config/{config.example.json,config.test.json,config.json}` (flat shape: `api_key_id`/`api_key_secret`/`api_url`, plus an `mcp` block: `auth_token`/`ngrok_authtoken`/`status_file`) — no longer shares config files with `apps/denidin-app/`. `config.test.json` holds real sandbox secrets (plus `openai_api_key`/`mcp.ngrok_authtoken` for the OpenAI/ngrok-driven tests) and, like `config.json`, is gitignored rather than committed (changed 2026-07-09 — only `config.example.json` is tracked).

## Spec-Driven Workflow

Non-trivial features and bugfixes follow a SpecKit pipeline (full detail in `.github/METHODOLOGY.md`):
```
speckit.specify → spec.md (+ MANDATORY user-stories.md, Given-When-Then, BLOCKING gate)
  → speckit.clarify (resolve ambiguities)
  → speckit.plan → plan.md, research.md, data-model.md, contracts/, quickstart.md
  → speckit.tasks → tasks.md (Task A = tests, Task B = implementation, B blocked until A approved)
  → speckit.analyze (cross-artifact consistency check)
  → speckit.implement → incremental delivery, one user story at a time
```
- New/updated specs belong under `specs/in-definition/` (pre-clarification) or the priority folders `specs/P0/`/`P1/`/`P2/` (post-clarification); `specs/done/` and `specs/not-doing/` are historical archives — never delete from them. Bugfix specs go in `specs/bugfixes/bugfix-###-description.md`.
- Bug fixes follow Bug-Driven Development instead: root cause → human approval → test-gap analysis → failing test → human approval → minimal fix → verify. See `.github/METHODOLOGY.md` §VII.
- Branch naming: `feature/###-description`, `bugfix/###-description`, or `docs/`/`chore/` prefixes.
