# T034: Cross-Tenant Cache/Shared-Mutable-State Audit

**Feature**: 055-multiple-clients-godfathers · **Date**: 2026-08-17 · **Scope**: `apps/denidin-app/src/`

Per `tasks.md` T034: *"review every other module-level/in-memory cache or shared mutable
state in `apps/denidin-app/src/` for the same cross-tenant leak risk flagged in `plan.md`'s
Constitution Check (§XVII)."* This is that finding.

## Method

Searched every `.py` file under `apps/denidin-app/src/` (`capabilities/`, `constants/`,
`handlers/` incl. `extractors/`, `managers/`, `memory/`, `models/`, `services/`, `utils/`) for:
module-level mutable globals, class-level (not instance) mutable attributes,
`functools.lru_cache`/`functools.cache` decorators, `global` statements, singleton
(`_instance = None` + lazy getter) patterns, and any other shared mutable state that could
leak data or behavior from one tenant to another when multiple `Tenant` objects run
concurrently in one process. Every finding was then read in full context to confirm its real
scope, not just pattern-matched.

Already-reviewed-and-known-safe items were excluded from re-flagging: `CapabilityRegistry`
(`src/capabilities/registry.py` — holds only stateless provider implementation instances,
never per-tenant data) and `src/utils/logger.py`'s `_VersionFilter`/`_TenantFilter`/
`threading.local()`-based tenant binding (Phase 8, T031). Both were independently
re-verified during this audit anyway and confirmed genuinely safe.

## Result: no cross-tenant leak risks found beyond the already-known-safe items

### 1. Immutable module-level constants — not flagged (never tenant-varying, never mutated)

- `src/capabilities/registry.py:29-38` — `_MESSAGING_PROVIDERS`, `_INVOICING_PROVIDERS`,
  `_REQUIRED_CAPABILITIES` (already excluded per scope above).
- `src/managers/ledger_event_manager.py:36-73` — `_LETTER_BY_SOURCE_TYPE`, `_HOURS_WORD_MAP`,
  plus several compiled regexes. Static lookup tables/patterns, never mutated.
- `src/handlers/extractors/image_extractor.py:33,37` — `_VALID_DOC_TYPES`, `REQUIRED_FIELDS`.
  Static classification tables.
- `src/handlers/ai_handler.py:44-469` — `MORNING_MCP_AUTHORIZED_ROLES`,
  `APPROVAL_REQUIRED_MCP_TOOLS`, `NO_APPROVAL_MCP_TOOLS`, `_DOCUMENT_TYPE_LABELS`,
  `_GROUP_B_REFERENCE_TOOLS`, `_PAYMENT_METHOD_LABELS`, `_AFFIRMATIVE_REPLIES`,
  `LEDGER_EVENT_TOOL`. All read-only tool schemas/lookup tables — `LEDGER_EVENT_TOOL` in
  particular confirmed only ever read (`.get`, `[...]`), never mutated at any call site.
- `src/managers/media_manager.py:20-24`, `src/managers/media_file_manager.py:23-27` —
  class-level `SUPPORTED_IMAGE_FORMATS`/`SUPPORTED_DOCUMENT_FORMATS`/size-limit constants.
  Plain lists used read-only as membership checks — file-format support isn't tenant-specific
  by design.
- `src/handlers/media_handler.py:328-337` — `_FIELD_LABELS_HE` class attribute, a static
  Hebrew label dict, read-only.
- `src/constants/error_messages.py` — plain string constants.

### 2. Instance-scoped caches that look module/class-level at a glance, but resolve to `self.x` inside an already-constructor-scoped-per-tenant object

- `MemoryManager._collection_cache` (`managers/memory_manager.py:66`) — instance dict;
  `MemoryManager` is one of the 8 constructor-scoped-per-tenant objects.
- `UserManager._user_cache` (`managers/user_manager.py:54`) — instance dict; `UserManager` is
  built fresh inside each `AIHandler.__init__` (`handlers/ai_handler.py:774`).
- `GroupMembershipResolver._cache` (`managers/group_membership_resolver.py:52`) — instance
  dict; one of the constructor-scoped objects, confirmed built fresh per tenant in
  `models/tenant.py`.
- `PendingApprovalManager._pending` (`managers/pending_approval_manager.py:74`) — instance
  dict; confirmed constructed fresh inside each `AIHandler.__init__`
  (`handlers/ai_handler.py:843`), never module-level despite the class living outside
  `AIHandler`.
- `SessionManager.chat_to_session` (`managers/session_manager.py:87`) — instance dict;
  constructor-scoped object, confirmed built fresh per tenant (`handlers/ai_handler.py:790`).
- `TenantManager._tenants_by_id` (`managers/tenant_manager.py:26`) — instance dict, but this
  is *correctly* the one class whose entire job is to hold the multi-tenant registry itself
  (not per-tenant data leaking across tenants — it's the intended cross-tenant lookup table,
  read-only after construction via `get_tenant`/`all_tenants`).
- `AIHandler._constitution_content`/`_constitution_mtime` and `_supplement_content`/
  `_supplement_mtime` (`handlers/ai_handler.py`) — instance-level mtime caches (Phase 7); each
  tenant gets its own `AIHandler` and its own `constitution_supplement_file` path, so no
  cross-tenant bleed.
- `MorningMcpLocator` (`handlers/morning_mcp_locator.py`) — all state (`_status_file`,
  `_max_age_seconds`) is instance-level, constructed per-`AIHandler`/per-tenant from that
  tenant's own `config.mcp`.

## No fix required

- No `functools.lru_cache`/`functools.cache` anywhere in `src/`.
- No `global` statement anywhere in `src/` (all matches were docstring prose, not code).
- No singleton `_instance = None` + lazy-getter pattern anywhere.
- No module-level mutable dict/list/set used as a runtime cache or registry — the only
  module-level dict/set/list literals found are the immutable lookup tables listed above.
- `MultiTenantSessionCleanupThread`/`run_startup_cleanup_for_tenants`
  (`services/cleanup_service.py`, Phase 8/T032) — take a `tenants: List[Any]` reference and
  iterate; hold no shared mutable state of their own, and each tenant's own
  `session_manager`/`ai_handler` (already constructor-scoped) does all the real work, with
  per-tenant exception isolation.
- `TenantAIHandlerFactory.build`/`_build_tenant_config`
  (`managers/tenant_ai_handler_factory.py`) — static methods, no class/module state; every
  credential/path is sourced from the `tenant` argument, with `morning_auth_token` explicitly
  dropped (not silently inherited from `base_config`) when a tenant has no invoicing provider
  (Phase 6/T022's own anti-leak fix).

**Conclusion**: no additional module-level or class-level shared mutable state exists beyond
what was already known-safe. Every cache/dict that superficially resembled shared state
resolves, on inspection, to an instance attribute of an object that is itself constructor-scoped
per tenant. T034 requires no follow-up code fix.
