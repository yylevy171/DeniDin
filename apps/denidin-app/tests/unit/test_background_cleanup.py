"""
Integration tests for background session cleanup thread.

Tests the full cleanup process managed by background_threads.py:
1. Archive expired sessions to dated folders
2. Transfer conversation to ChromaDB
3. Remove from in-memory index
4. Mark as transferred

These tests verify the cleanup thread behavior that was previously 
part of SessionManager but is now managed externally.
"""
import pytest
import time
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch

from src.managers.session_manager import SessionManager
from src.handlers.ai_handler import AIHandler
from src.services.cleanup_service import (
    MultiTenantSessionCleanupThread,
    SessionCleanupThread,
    run_startup_cleanup_for_tenants,
)
from src.models.config import AppConfiguration


@pytest.fixture
def test_config(tmp_path):
    """Config fixture with test paths."""
    test_data_root = tmp_path / "test_data"
    
    return AppConfiguration(
        green_api_instance_id="test",
        green_api_token="test",
        ai_api_key="test-key",
        ai_model="gpt-4o-mini",
        ai_reply_max_tokens=100,
        log_level="INFO",
        feature_flags={"enable_memory_system": True},
        memory={
            "session": {
                "storage_dir": str(test_data_root / "sessions"),
                "session_timeout_hours": 1 / 3600  # 1 second for testing
            },
            "longterm": {
                "storage_dir": str(test_data_root / "memory"),
                "embedding_model": "text-embedding-3-small",
                "top_k_results": 5,
                "min_similarity": 0.2
            }
        }
    )


class TestBackgroundCleanupThread:
    """Test background cleanup thread executes immediately at startup."""
    
    def test_cleanup_runs_immediately_at_startup(self, test_config, tmp_path):
        """
        Verify cleanup runs IMMEDIATELY at initialization, before first sleep interval.
        
        This is CRITICAL for preventing orphaned sessions after restarts.
        """
        # Create SessionManager and add an expired session
        session_manager = SessionManager(
            storage_dir=test_config.memory["session"]["storage_dir"],
            session_timeout_hours=test_config.memory["session"]["session_timeout_hours"]
        )
        
        chat_id = "test_user@c.us"
        session_manager.add_message(chat_id, "user", "Old message", "client")
        session = session_manager.get_session(chat_id)
        session_id = session.session_id
        
        # Manually expire the session
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        session.last_active = old_time.isoformat()
        session_manager._save_session(session)
        
        # Mock AIHandler to avoid actual AI calls
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Summary"))]
        )
        
        ai_handler = AIHandler(mock_client, test_config)
        ai_handler.session_manager = session_manager
        ai_handler.memory_manager.remember = Mock(return_value="memory_id_123")
        
        # Mock collection for ChromaDB verification
        mock_collection = Mock()
        mock_collection.count.return_value = 1
        ai_handler.memory_manager.client.get_collection = Mock(return_value=mock_collection)
        
        # Create global context for SessionCleanupThread
        class GlobalContext:
            pass
        
        global_context = GlobalContext()
        global_context.session_manager = session_manager
        global_context.ai_handler = ai_handler
        
        # Start background cleanup thread (cleanup should run immediately)
        cleanup_thread = SessionCleanupThread(
            global_context=global_context,
            cleanup_interval_seconds=3600  # 1 hour - realistic interval
        )
        cleanup_thread.start()
        
        try:
            # Wait briefly for immediate cleanup to complete
            time.sleep(2)  # Should be enough for immediate cleanup
            
            # Verify session was archived immediately (not after 1 hour wait)
            storage_dir = Path(test_config.memory["session"]["storage_dir"])
            active_dir = storage_dir / session_id
            expected_date = old_time.strftime("%Y-%m-%d")
            expired_dir = storage_dir / "expired" / expected_date / session_id
            
            # This should PASS - cleanup ran at startup, not after interval
            assert not active_dir.exists(), "Expired session should be moved immediately at startup"
            assert expired_dir.exists(), "Expired session should be in expired/ folder"
            
        finally:
            cleanup_thread.stop()
    
    def test_active_sessions_not_moved_during_cleanup(self, test_config, tmp_path):
        """
        Verify active sessions remain untouched during cleanup.
        
        Only expired sessions should be archived/transferred.
        """
        # Create SessionManager with active session (10 second timeout)
        session_manager = SessionManager(
            storage_dir=test_config.memory["session"]["storage_dir"],
            session_timeout_hours=10 / 3600  # 10 seconds for testing
        )
        
        chat_id = "active_user@c.us"
        session_manager.add_message(chat_id, "user", "Recent message", "client")
        session = session_manager.get_session(chat_id)
        session_id = session.session_id
        
        # Session is active (recent timestamp) - should NOT be cleaned up
        assert session_id in session_manager.chat_to_session.values()
        
        # Mock AIHandler
        mock_client = MagicMock()
        ai_handler = AIHandler(mock_client, test_config)
        ai_handler.session_manager = session_manager
        
        # Create global context for SessionCleanupThread
        class GlobalContext:
            pass
        
        global_context = GlobalContext()
        global_context.session_manager = session_manager
        global_context.ai_handler = ai_handler
        
        # Start cleanup thread
        cleanup_thread = SessionCleanupThread(
            global_context=global_context,
            cleanup_interval_seconds=0.5
        )
        cleanup_thread.start()
        
        try:
            # Wait for at least one cleanup cycle
            time.sleep(1.5)
            
            # Verify active session is still in active directory
            storage_dir = Path(test_config.memory["session"]["storage_dir"])
            active_dir = storage_dir / session_id
            assert active_dir.exists(), "Active session should remain in place"
            
            # Verify still in index
            assert chat_id in session_manager.chat_to_session
            assert session_manager.chat_to_session[chat_id] == session_id
            
        finally:
            cleanup_thread.stop()
    
    def test_cleanup_full_cycle_archive_transfer_remove(self, test_config, tmp_path):
        """
        Verify complete cleanup cycle:
        1. Archive session to expired/YYYY-MM-DD/
        2. Transfer to ChromaDB
        3. Remove from in-memory index
        4. Mark as transferred_to_longterm=True
        """
        # Create SessionManager with session
        session_manager = SessionManager(
            storage_dir=test_config.memory["session"]["storage_dir"],
            session_timeout_hours=test_config.memory["session"]["session_timeout_hours"]
        )
        
        chat_id = "cleanup_test@c.us"
        session_manager.add_message(chat_id, "user", "Message 1", "client")
        session_manager.add_message(chat_id, "assistant", "Response 1", "client")
        session = session_manager.get_session(chat_id)
        session_id = session.session_id
        
        # Expire the session
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        session.last_active = old_time.isoformat()
        session_manager._save_session(session)
        
        # Mock AIHandler
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Test summary"))]
        )
        
        ai_handler = AIHandler(mock_client, test_config)
        ai_handler.session_manager = session_manager
        ai_handler.memory_manager.remember = Mock(return_value="memory_xyz")
        
        # Mock collection
        mock_collection = Mock()
        mock_collection.count.return_value = 1
        ai_handler.memory_manager.client.get_collection = Mock(return_value=mock_collection)
        
        # Create global context for SessionCleanupThread
        class GlobalContext:
            pass
        
        global_context = GlobalContext()
        global_context.session_manager = session_manager
        global_context.ai_handler = ai_handler
        
        # Start cleanup
        cleanup_thread = SessionCleanupThread(
            global_context=global_context,
            cleanup_interval_seconds=0.5
        )
        cleanup_thread.start()
        
        try:
            # Wait for cleanup to complete (allow time for all 4 steps)
            time.sleep(3)
            
            storage_dir = Path(test_config.memory["session"]["storage_dir"])
            expected_date = old_time.strftime("%Y-%m-%d")
            expired_dir = storage_dir / "expired" / expected_date / session_id
            
            # STEP 1: Verify archived
            assert expired_dir.exists(), "Session should be archived"
            
            # STEP 2: Verify transferred to ChromaDB
            ai_handler.memory_manager.remember.assert_called()
            
            # STEP 3: Verify removed from index
            assert chat_id not in session_manager.chat_to_session, "Session should be removed from index"
            
            # STEP 4: Verify transferred flag set
            archived_session_file = expired_dir / "session.json"
            with open(archived_session_file) as f:
                archived_data = json.load(f)
            assert archived_data.get("transferred_to_longterm", False) is True, "Should be marked as transferred"

        finally:
            cleanup_thread.stop()


class _FakeTenantContext:
    """Minimal duck-typed `global_context` for these tests - real SessionManager
    (real, fast file I/O), Mock() ai_handler (no real ChromaDB/OpenAI needed to
    exercise the cross-tenant SWEEP logic under test here, distinct from
    TestBackgroundCleanupThread above which already covers the full real
    per-session mechanics)."""

    def __init__(self, bot_name: str, storage_dir):
        self.bot_name = bot_name
        self.session_manager = SessionManager(storage_dir=str(storage_dir), session_timeout_hours=1 / 3600)
        self.ai_handler = MagicMock()
        self.ai_handler.transfer_session_to_long_term_memory = Mock(
            return_value={"success": True, "memory_id": f"memory-{bot_name}"}
        )


def _expire_session(session_manager, chat_id: str) -> str:
    session_manager.add_message(chat_id, "user", "Old message", "client")
    session = session_manager.get_session(chat_id)
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    session.last_active = old_time.isoformat()
    session_manager._save_session(session)
    return session.session_id


class TestMultiTenantSessionCleanupThread:
    """Feature 055 Phase 8, T032a (REQ-BG-001): one unified sweep iterates every
    tenant's own data root in turn; one tenant's cleanup error doesn't abort the
    sweep for other tenants."""

    def test_sweep_processes_expired_sessions_across_multiple_tenants(self, tmp_path):
        tenant_a = _FakeTenantContext("DeniDin", tmp_path / "tenant_a")
        tenant_b = _FakeTenantContext("Jabaloola", tmp_path / "tenant_b")
        chat_a = "client_a@c.us"
        chat_b = "client_b@c.us"
        _expire_session(tenant_a.session_manager, chat_a)
        _expire_session(tenant_b.session_manager, chat_b)

        cleanup_thread = MultiTenantSessionCleanupThread(
            tenants=[tenant_a, tenant_b], cleanup_interval_seconds=3600
        )
        cleanup_thread.start()
        try:
            time.sleep(2)

            assert chat_a not in tenant_a.session_manager.chat_to_session
            assert chat_b not in tenant_b.session_manager.chat_to_session
            tenant_a.ai_handler.transfer_session_to_long_term_memory.assert_called()
            tenant_b.ai_handler.transfer_session_to_long_term_memory.assert_called()
        finally:
            cleanup_thread.stop()

    def test_one_tenants_cleanup_error_does_not_abort_the_sweep_for_others(self, tmp_path):
        """The actual point of REQ-BG-001: tenant A is structurally broken
        (get_expired_sessions raises) but tenant B still gets cleaned up in
        the same sweep."""
        tenant_a = _FakeTenantContext("Broken", tmp_path / "tenant_a")
        tenant_a.session_manager.get_expired_sessions = Mock(side_effect=RuntimeError("boom"))
        tenant_b = _FakeTenantContext("Healthy", tmp_path / "tenant_b")
        chat_b = "client_b@c.us"
        _expire_session(tenant_b.session_manager, chat_b)

        cleanup_thread = MultiTenantSessionCleanupThread(
            tenants=[tenant_a, tenant_b], cleanup_interval_seconds=3600
        )
        cleanup_thread.start()
        try:
            time.sleep(2)

            assert chat_b not in tenant_b.session_manager.chat_to_session
            tenant_b.ai_handler.transfer_session_to_long_term_memory.assert_called()
        finally:
            cleanup_thread.stop()

    def test_no_tenants_configured_does_not_crash_the_loop(self, tmp_path):
        cleanup_thread = MultiTenantSessionCleanupThread(tenants=[], cleanup_interval_seconds=3600)
        cleanup_thread.start()
        try:
            time.sleep(1)
            assert cleanup_thread._thread.is_alive()  # pylint: disable=protected-access
        finally:
            cleanup_thread.stop()


class TestRunStartupCleanupForTenants:
    """Feature 055 Phase 8, T032a (REQ-BG-001): same isolation guarantee, for the
    one-time startup sweep."""

    def test_processes_expired_sessions_for_every_tenant(self, tmp_path):
        tenant_a = _FakeTenantContext("DeniDin", tmp_path / "tenant_a")
        tenant_b = _FakeTenantContext("Jabaloola", tmp_path / "tenant_b")
        chat_a = "client_a@c.us"
        chat_b = "client_b@c.us"
        _expire_session(tenant_a.session_manager, chat_a)
        _expire_session(tenant_b.session_manager, chat_b)

        run_startup_cleanup_for_tenants([tenant_a, tenant_b])

        assert chat_a not in tenant_a.session_manager.chat_to_session
        assert chat_b not in tenant_b.session_manager.chat_to_session

    def test_one_tenants_startup_failure_does_not_abort_the_others(self, tmp_path):
        tenant_a = _FakeTenantContext("Broken", tmp_path / "tenant_a")
        tenant_a.session_manager.get_expired_sessions = Mock(side_effect=RuntimeError("boom"))
        tenant_b = _FakeTenantContext("Healthy", tmp_path / "tenant_b")
        chat_b = "client_b@c.us"
        _expire_session(tenant_b.session_manager, chat_b)

        # Must not raise - tenant_a's failure is caught internally.
        run_startup_cleanup_for_tenants([tenant_a, tenant_b])

        assert chat_b not in tenant_b.session_manager.chat_to_session
