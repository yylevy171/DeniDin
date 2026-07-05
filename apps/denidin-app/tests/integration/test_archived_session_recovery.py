"""
Integration test for archived untransferred session recovery bug.

BUG: Sessions archived to expired/ folder but not yet transferred to ChromaDB
are never found by get_expired_sessions() after app restart.

TEST STRATEGY:
1. Manually create an expired session on disk with transferred_to_longterm=False
2. Start the real DeniDin app (which runs startup cleanup)
3. Wait 5 seconds for cleanup to process
4. Verify session was transferred to ChromaDB
5. Verify transferred_to_longterm flag is now True

This test will FAIL with current code because get_expired_sessions() skips
the expired/ directory.
"""
import pytest
import json
import time
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
import denidin


def test_archived_untransferred_session_transferred_on_startup(tmp_path):
    """
    Test that app startup finds and transfers archived sessions to ChromaDB.
    
    SCENARIO:
    - Session exists in expired/2026-01-22/ folder
    - Session has transferred_to_longterm=False
    - App starts and runs startup cleanup
    - FIX: get_sessions_needing_cleanup() finds archived sessions
    - Session successfully transferred to ChromaDB
    
    VALIDATES: The bug fix for archived untransferred sessions.
    """
    print("\n" + "="*80)
    print("TEST: Archived Untransferred Session Recovery")
    print("="*80)
    
    # Setup test directories
    test_data_root = tmp_path / "test_data"
    sessions_dir = test_data_root / "sessions"
    memory_dir = test_data_root / "memory"
    
    sessions_dir.mkdir(parents=True, exist_ok=True)
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    # ARRANGE: Create expired session with messages
    print("\n[ARRANGE] Creating archived untransferred session on disk...")
    session_id = str(uuid.uuid4())
    chat_id = "test_archived_972522968679@c.us"
    
    # Old timestamp (session expired 25 hours ago)
    last_active = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    created_at = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    
    session_data = {
        "session_id": session_id,
        "whatsapp_chat": chat_id,
        "message_ids": ["msg-001"],
        "message_counter": 1,
        "created_at": created_at,
        "last_active": last_active,
        "total_tokens": 0,
        "transferred_to_longterm": False,  # KEY: Not yet transferred!
        "storage_path": f"expired/2026-01-22/{session_id}"
    }
    
    # Create session in expired/ folder (simulating interrupted cleanup)
    expired_date_dir = sessions_dir / "expired" / "2026-01-22"
    session_dir = expired_date_dir / session_id
    messages_dir = session_dir / "messages"
    messages_dir.mkdir(parents=True, exist_ok=True)
    
    # Write session.json
    with open(session_dir / "session.json", 'w') as f:
        json.dump(session_data, f, indent=2)
    
    # Write test message
    message_data = {
        "message_id": "msg-001",
        "session_id": session_id,
        "role": "user",
        "content": "My name is TestUser and I need this transferred to ChromaDB",
        "sender": chat_id,
        "recipient": "bot@c.us",
        "timestamp": last_active,
        "received_at": last_active,
        "was_received": True,
        "order_num": 1,
        "image_path": None
    }
    
    with open(messages_dir / "msg-001.json", 'w') as f:
        json.dump(message_data, f, indent=2)
    
    print(f"✓ Created session {session_id} in {session_dir.relative_to(test_data_root)}")
    print(f"  - transferred_to_longterm: False")
    print(f"  - 1 message in messages/")
    
    # ARRANGE: Load real config for API key
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
    with open(config_path) as f:
        real_config = json.load(f)
    
    # ARRANGE: Create test config (using real OpenAI API key for embeddings)
    config = {
        "green_api_instance_id": "test_instance",
        "green_api_token": "test_token_12345",
        "ai_api_key": real_config['ai_api_key'],
        "ai_model": "gpt-4o-mini",
        "ai_reply_max_tokens": 1000,
        "temperature": 0.7,
        "log_level": "INFO",
        "data_root": str(test_data_root),
        "feature_flags": {
            "enable_memory_system": True,
            "enable_rbac": False
        },
        "godfather_phone": "972501234567@c.us",
        "memory": {
            "session": {
                "storage_dir": str(sessions_dir),
                "session_timeout_hours": 24,
                "cleanup_interval_seconds": 2  # Fast cleanup for testing
            },
            "longterm": {
                "enabled": True,
                "storage_dir": str(memory_dir),
                "collection_name": "test_archived_recovery",
                "embedding_model": "text-embedding-3-small",
                "top_k_results": 5,
                "min_similarity": 0.2
            }
        }
    }
    
    denidin_app = None
    
    try:
        # ACT: Initialize app (this runs startup cleanup)
        print("\n[ACT] Initializing app (startup cleanup should run)...")
        denidin_app = denidin.initialize_app(config)
        print("✓ App initialized")
        
        # Wait for startup cleanup to complete
        print("\n[WAIT] Waiting 5 seconds for startup cleanup to process session...")
        time.sleep(5)
        print("✓ Wait complete")
        
        # ASSERT 1: Check transferred_to_longterm flag
        print("\n[ASSERT 1] Checking transferred_to_longterm flag...")
        session_file = session_dir / "session.json"
        with open(session_file) as f:
            updated_session = json.load(f)
        
        assert updated_session['transferred_to_longterm'] is True, (
            f"BUG REPRODUCED! Session should be marked as transferred. "
            f"Flag is still False. This means get_expired_sessions() never found "
            f"the session in expired/ folder."
        )
        print(f"✓ Session {session_id} marked as transferred")
        
        # ASSERT 2: Check ChromaDB has the session
        print("\n[ASSERT 2] Checking ChromaDB for transferred data...")
        
        # Get collection name (per-chat collection)
        expected_collection_name = f"memory_{chat_id.replace('@c.us', '')}"
        
        chroma_client = denidin_app.ai_handler.memory_manager.client
        collection = chroma_client.get_collection(name=expected_collection_name)
        count = collection.count()
        
        assert count > 0, (
            f"BUG REPRODUCED! Session archived but NOT transferred to ChromaDB. "
            f"Collection '{expected_collection_name}' is EMPTY (count={count}). "
            f"Expected at least 1 memory from session {session_id}."
        )
        
        print(f"✓ ChromaDB collection '{expected_collection_name}' has {count} memories")
        
        print("\n" + "="*80)
        print("SUCCESS: Archived session was found and transferred!")
        print("="*80)
        
    finally:
        # Cleanup
        if denidin_app:
            print("\n[CLEANUP] Shutting down app...")
            denidin_app.shutdown()
            print("✓ App shutdown complete")
