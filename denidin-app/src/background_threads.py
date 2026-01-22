"""
Background threads for application-level tasks.

App-level cleanup thread with access to global context (SessionManager, MemoryManager, AIHandler).
Ensures atomic transfer + archival operations.
"""

import threading
import time
from src.utils.logger import get_logger

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
        self._thread = None

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

    def _cleanup_expired_sessions(self):
        """
        Clean up expired sessions with atomic 4-step process.

        For each expired session:
        1. Archive to expired/YYYY-MM-DD/ (update storage_path, keep in index)
        2. Transfer to ChromaDB (if not already transferred)
        3. Remove from index (session no longer accessible)
        4. Update transferred_to_longterm flag
        """
        try:
            # Get all expired sessions
            expired_sessions = self.global_context.session_manager.get_expired_sessions()

            if not expired_sessions:
                logger.debug("No expired sessions to clean up")
                return

            logger.info(f"Found {len(expired_sessions)} expired session(s) to process")

            for session in expired_sessions:
                try:
                    session_start_time = time.time()

                    # STEP 1: Archive session files (updates storage_path, keeps in index)
                    step1_start = time.time()
                    logger.info(f"[STEP 1/4] Starting archive for session {session.session_id}")
                    self.global_context.session_manager.archive_session(session)
                    logger.info(f"[STEP 1/4] Archive completed in {time.time() - step1_start:.2f}s")

                    # STEP 2: Transfer to ChromaDB (if not already done)
                    if not session.transferred_to_longterm:
                        step2_start = time.time()
                        logger.info(
                            f"[STEP 2/4] Starting AI transfer for session {session.session_id} "
                            f"(chat: {session.whatsapp_chat})"
                        )

                        result = self.global_context.ai_handler.transfer_session_to_long_term_memory(
                            chat_id=session.whatsapp_chat,
                            session_id=session.session_id
                        )

                        logger.info(f"[STEP 2/4] AI transfer completed in {time.time() - step2_start:.2f}s")

                        if result.get('success'):
                            logger.info(
                                f"Successfully transferred session {session.session_id}: "
                                f"memory_id={result.get('memory_id')}"
                            )

                            # STEP 3: Remove from index (transfer complete)
                            step3_start = time.time()
                            logger.info(f"[STEP 3/4] Removing session {session.session_id} from index")
                            self.global_context.session_manager.remove_from_index(session)
                            logger.info(f"[STEP 3/4] Index removal completed in {time.time() - step3_start:.2f}s")

                            # STEP 4: Mark as transferred and save to archived location
                            step4_start = time.time()
                            logger.info(f"[STEP 4/4] Saving transferred flag for session {session.session_id}")
                            session.transferred_to_longterm = True
                            self.global_context.session_manager._save_session(session)
                            logger.info(f"[STEP 4/4] Flag save completed in {time.time() - step4_start:.2f}s")
                        else:
                            logger.error(
                                f"Failed to transfer session {session.session_id}: "
                                f"{result.get('reason')}"
                            )
                            # Remove from index anyway - will retry on lazy load
                            step3_start = time.time()
                            logger.info(f"[STEP 3/4] Removing failed session {session.session_id} from index")
                            self.global_context.session_manager.remove_from_index(session)
                            logger.info(f"[STEP 3/4] Index removal completed in {time.time() - step3_start:.2f}s")
                    else:
                        logger.debug(
                            f"Session {session.session_id} already transferred "
                            f"(transferred_to_longterm=True)"
                        )
                        # Remove from index
                        step3_start = time.time()
                        logger.info(f"[STEP 3/4] Removing already-transferred session {session.session_id} from index")
                        self.global_context.session_manager.remove_from_index(session)
                        logger.info(f"[STEP 3/4] Index removal completed in {time.time() - step3_start:.2f}s")

                    total_time = time.time() - session_start_time
                    logger.info(f"Session {session.session_id} cleanup completed in {total_time:.2f}s")

                except Exception as session_error:
                    logger.error(
                        f"Failed to process expired session {session.session_id}: {session_error}",
                        exc_info=True
                    )

        except Exception as e:
            logger.error(f"Error during session cleanup: {e}", exc_info=True)


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
            try:
                # Same 3-step process as periodic cleanup: archive, transfer, set flag
                # Step 1: Archive first
                logger.info(f"Startup: Archiving session {session.session_id}")
                global_context.session_manager.archive_session(session)

                # Step 2: Transfer to long-term memory
                if not session.transferred_to_longterm:
                    logger.info(
                        f"Startup: Transferring session {session.session_id} to long-term memory"
                    )

                    result = global_context.ai_handler.transfer_session_to_long_term_memory(
                        chat_id=session.whatsapp_chat,
                        session_id=session.session_id
                    )

                    # Step 3: Set flag after successful transfer
                    if result.get('success'):
                        logger.info(f"Startup: Transferred session {session.session_id}")
                        session.transferred_to_longterm = True
                        global_context.session_manager._save_session(session)
                    else:
                        logger.warning(f"Startup: Failed to transfer session {session.session_id}")

            except Exception as e:
                logger.error(f"Startup cleanup failed for session {session.session_id}: {e}")

        logger.info("Startup session cleanup complete")

    except Exception as e:
        logger.error(f"Startup cleanup error: {e}", exc_info=True)
