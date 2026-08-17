"""
Session cleanup service for application-level tasks.

App-level cleanup thread with access to global context (SessionManager, MemoryManager, AIHandler).
Ensures atomic transfer + archival operations.

Feature 055 (Multi-Tenancy) Phase 8, REQ-BG-001: `MultiTenantSessionCleanupThread`/
`run_startup_cleanup_for_tenants` extend this to sweep every tenant's own data root in
one unified background thread (not one thread per tenant - matches the "shared,
multi-tenant-native services" architecture this feature settled on throughout), with
per-tenant exception isolation so one tenant's failure never skips any other tenant's
cleanup. `Tenant` (src/models/tenant.py) itself duck-types as a `global_context` (its
own `.ai_handler` attribute, plus a `session_manager` property aliasing
`ai_handler.session_manager` - the same shape `denidin.py`'s single-tenant `DeniDin`
class already has), so every existing function/class below is reused UNCHANGED for the
multi-tenant case - no parity risk to the single-tenant path.
"""

import threading
import time
from typing import Any, List, Optional
from src.utils.logger import bind_tenant_context, get_logger
from src.managers.session_manager import Session

logger = get_logger(__name__)


class SessionCleanupThread:
    """
    Application-level cleanup thread with access to global context.

    Performs atomic 4-step cleanup:
    1. Archive session files to expired/YYYY-MM-DD/ (update storage_path, keep in index)
    2. Transfer session to ChromaDB (via AIHandler)
    3. Remove from index (session no longer accessible via get_session)
    4. Set transferred_to_longterm=True flag
    """

    def __init__(self, global_context, cleanup_interval_seconds: int = 3600):
        """
        Initialize cleanup thread.

        Args:
            global_context: Object with session_manager, memory_manager, ai_handler refs
            cleanup_interval_seconds: Interval between cleanup runs
        """
        self.global_context = global_context
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(f"SessionCleanupThread initialized: interval={cleanup_interval_seconds}s")

    def start(self):
        """Start the background cleanup thread."""
        if self._running:
            logger.warning("Cleanup thread already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._thread.start()
        logger.info("Session cleanup thread started")

    def stop(self):
        """Stop the background cleanup thread."""
        if not self._running:
            return

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Session cleanup thread stopped")

    def _cleanup_loop(self):
        """Main cleanup loop - runs periodically."""
        while self._running:
            if self._running:
                logger.debug("Running scheduled session cleanup")
                self._cleanup_expired_sessions()
            time.sleep(self.cleanup_interval_seconds)

    def _process_single_session(self, session: Session, log_prefix: str = ""):
        """
        Process a single session through cleanup workflow.
        
        Delegates to module-level _process_session_cleanup function.
        """
        _process_session_cleanup(self.global_context, session, log_prefix)

    def _cleanup_expired_sessions(self):
        """
        Clean up expired sessions with atomic 4-step process.

        For each expired session:
        1. Archive to expired/YYYY-MM-DD/ (update storage_path, keep in index)
        2. Transfer to ChromaDB (if not already transferred)
        3. Remove from index (session no longer accessible)
        4. Update transferred_to_longterm flag
        """
        _cleanup_expired_sessions_for_context(self.global_context)


def _cleanup_expired_sessions_for_context(global_context: Any, log_context: str = "") -> None:
    """One periodic-sweep pass for ONE context (a single-tenant `DeniDin` instance, or -
    Feature 055 Phase 8 - one `Tenant` among several in a multi-tenant sweep). Shared by
    `SessionCleanupThread._cleanup_expired_sessions` (single-tenant, `log_context=""` -
    REQ-PARITY-001: byte-identical log lines to before this function was extracted) and
    `MultiTenantSessionCleanupThread` (one call per tenant). Catches its own top-level
    exception (unchanged pre-055 behavior) so a failure here never propagates to a caller
    iterating multiple contexts (REQ-BG-001).
    """
    try:
        # Get all expired sessions
        expired_sessions = global_context.session_manager.get_expired_sessions()

        if not expired_sessions:
            logger.debug(f"{log_context}No expired sessions to clean up")
            return

        logger.info(f"{log_context}Found {len(expired_sessions)} expired session(s) to process")

        for session in expired_sessions:
            _process_session_cleanup(global_context, session, log_context)

    except Exception as cleanup_error:  # pylint: disable=broad-except
        logger.error(f"{log_context}Error during session cleanup: {cleanup_error}", exc_info=True)


def run_startup_cleanup(global_context):
    """
    Run cleanup once at startup to catch any missed sessions.

    This handles sessions that expired while the app was down or crashed
    before cleanup could run.

    Args:
        global_context: Object with session_manager, memory_manager, ai_handler refs
    """
    logger.info("Running startup session cleanup...")

    try:
        expired_sessions = global_context.session_manager.get_expired_sessions()

        if not expired_sessions:
            logger.info("Startup cleanup: No expired sessions found")
            return

        logger.info(f"Startup cleanup: Found {len(expired_sessions)} expired session(s)")

        for session in expired_sessions:
            _process_session_cleanup(global_context, session, "[STARTUP] ")

        logger.info("Startup session cleanup complete")

    except Exception as e:
        logger.error(f"Startup cleanup error: {e}", exc_info=True)


def run_startup_cleanup_for_tenants(tenants: List[Any]) -> None:
    """Feature 055 Phase 8 (REQ-BG-001): run startup cleanup once per tenant, in turn.
    `run_startup_cleanup` already catches its own top-level exception (unchanged, see
    above), so one tenant's failure can never skip any other tenant's startup cleanup -
    no additional try/except needed here to get that guarantee."""
    for tenant in tenants:
        bind_tenant_context(getattr(tenant, "bot_name", "-"))
        run_startup_cleanup(tenant)


class MultiTenantSessionCleanupThread:
    """Feature 055 Phase 8 (REQ-BG-001): ONE unified background thread sweeping every
    tenant's own data root in turn - not one `SessionCleanupThread` per tenant (matches
    this feature's "shared, multi-tenant-native services, not N processes/threads"
    architecture throughout, e.g. `research.md` §6's background-thread-policy decision).

    Each tenant's own sweep already self-isolates its exception
    (`_cleanup_expired_sessions_for_context`); this class adds an OUTER per-tenant
    try/except too, so even a structurally broken tenant (e.g. missing `.ai_handler`
    entirely, raising before that inner try block is even reached) can't take down the
    sweep for the rest.
    """

    def __init__(self, tenants: List[Any], cleanup_interval_seconds: int = 3600):
        """
        Args:
            tenants: every tenant to sweep each cycle - each one duck-types as a
                `global_context` (`.session_manager`, `.ai_handler`; `Tenant` provides
                both). Read fresh from this list reference each sweep, so a caller that
                mutates the underlying list (a tenant added/removed) is picked up on
                the next cycle without restarting the thread.
            cleanup_interval_seconds: interval between sweeps, same meaning as
                `SessionCleanupThread`'s own parameter.
        """
        self.tenants = tenants
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(
            f"MultiTenantSessionCleanupThread initialized: {len(tenants)} tenant(s), "
            f"interval={cleanup_interval_seconds}s"
        )

    def start(self):
        """Start the background cleanup thread."""
        if self._running:
            logger.warning("Multi-tenant cleanup thread already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._thread.start()
        logger.info("Multi-tenant session cleanup thread started")

    def stop(self):
        """Stop the background cleanup thread."""
        if not self._running:
            return

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Multi-tenant session cleanup thread stopped")

    def _cleanup_loop(self):
        """Main cleanup loop - runs periodically, same immediate-first-pass shape as
        `SessionCleanupThread._cleanup_loop` (cleanup runs before the first sleep, not
        only after - critical for catching sessions that expired while the app was
        down, same rationale as that class's own version)."""
        while self._running:
            if self._running:
                self._cleanup_all_tenants()
            time.sleep(self.cleanup_interval_seconds)

    def _cleanup_all_tenants(self) -> None:
        """One sweep across every tenant, in turn. A given tenant's failure is logged
        and skipped - never aborts the sweep for the tenants after it."""
        for tenant in self.tenants:
            bot_name = getattr(tenant, "bot_name", "?")
            try:
                bind_tenant_context(bot_name)
                _cleanup_expired_sessions_for_context(tenant, log_context=f"[{bot_name}] ")
            except Exception as sweep_error:  # pylint: disable=broad-except
                logger.error(
                    f"[{bot_name}] Cleanup sweep failed for this tenant - "
                    f"continuing with the remaining tenants: {sweep_error}",
                    exc_info=True,
                )
                continue


def _process_session_cleanup(global_context, session: Session, log_prefix: str = ""):
    """
    Process a single session through the 4-step cleanup workflow.
    
    Shared implementation used by both periodic and startup cleanup.
    
    Steps:
    1. Archive to expired/YYYY-MM-DD/ (if not already archived)
    2. Transfer to ChromaDB (if not already transferred)
    3. Remove from index
    4. Set transferred_to_longterm flag
    
    Args:
        global_context: Object with session_manager, memory_manager, ai_handler refs
        session: Session object to process
        log_prefix: Prefix for log messages (e.g., "[STARTUP] " or "")
    """
    try:
        session_start_time = time.time()

        # STEP 1: Archive session files (only if not already archived)
        if session.storage_path and session.storage_path.startswith("expired/"):
            logger.debug(
                f"{log_prefix}[STEP 1/4] Session {session.session_id} already archived "
                f"at {session.storage_path}, skipping archive"
            )
        else:
            step1_start = time.time()
            logger.info(f"{log_prefix}[STEP 1/4] Starting archive for session {session.session_id}")
            global_context.session_manager.archive_session(session)
            logger.info(f"{log_prefix}[STEP 1/4] Archive completed in {time.time() - step1_start:.2f}s")

        # STEP 2: Transfer to ChromaDB (if not already done)
        if not session.transferred_to_longterm:
            step2_start = time.time()
            logger.info(
                f"{log_prefix}[STEP 2/4] Starting AI transfer for session {session.session_id} "
                f"(chat: {session.whatsapp_chat})"
            )

            result = global_context.ai_handler.transfer_session_to_long_term_memory(
                session=session
            )

            logger.info(f"{log_prefix}[STEP 2/4] AI transfer completed in {time.time() - step2_start:.2f}s")

            if result.get('success'):
                logger.info(
                    f"Successfully transferred session {session.session_id}: "
                    f"memory_id={result.get('memory_id')}"
                )

                # STEP 3: Remove from index (transfer complete)
                step3_start = time.time()
                was_removed = global_context.session_manager.remove_from_index(session)
                if was_removed:
                    logger.info(f"{log_prefix}[STEP 3/4] Removed session {session.session_id} from index")
                else:
                    logger.info(
                        f"{log_prefix}[STEP 3/4] Session {session.session_id} was not in index "
                        f"(already removed or archived session)"
                    )
                logger.info(f"{log_prefix}[STEP 3/4] Index removal completed in {time.time() - step3_start:.2f}s")

                # STEP 4: Mark as transferred and save to archived location
                step4_start = time.time()
                logger.info(f"{log_prefix}[STEP 4/4] Saving transferred flag for session {session.session_id}")
                session.transferred_to_longterm = True
                global_context.session_manager._save_session(session)
                logger.info(f"{log_prefix}[STEP 4/4] Flag save completed in {time.time() - step4_start:.2f}s")
            else:
                logger.error(
                    f"Failed to transfer session {session.session_id}: "
                    f"{result.get('reason')}"
                )
                # Remove from index anyway - will retry on lazy load
                step3_start = time.time()
                was_removed = global_context.session_manager.remove_from_index(session)
                if was_removed:
                    logger.info(f"{log_prefix}[STEP 3/4] Removed failed session {session.session_id} from index")
                else:
                    logger.info(
                        f"{log_prefix}[STEP 3/4] Failed session {session.session_id} was not in index "
                        f"(already removed or archived session)"
                    )
                logger.info(f"{log_prefix}[STEP 3/4] Index removal completed in {time.time() - step3_start:.2f}s")
        else:
            logger.debug(
                f"Session {session.session_id} already transferred "
                f"(transferred_to_longterm=True)"
            )
            # Remove from index
            step3_start = time.time()
            was_removed = global_context.session_manager.remove_from_index(session)
            if was_removed:
                logger.info(f"{log_prefix}[STEP 3/4] Removed already-transferred session {session.session_id} from index")
            else:
                logger.info(
                    f"{log_prefix}[STEP 3/4] Already-transferred session {session.session_id} was not in index "
                    f"(already removed or archived session)"
                )
            logger.info(f"{log_prefix}[STEP 3/4] Index removal completed in {time.time() - step3_start:.2f}s")

        total_time = time.time() - session_start_time
        logger.info(f"Session {session.session_id} cleanup completed in {total_time:.2f}s")

    except Exception as session_error:
        logger.error(f"Failed to process session {session.session_id}: {session_error}", exc_info=True)
