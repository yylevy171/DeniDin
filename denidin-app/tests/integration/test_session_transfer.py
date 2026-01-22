"""
Integration tests for session expiration and transfer to ChromaDB.

Tests verify that expired sessions are:
1. Archived to expired/ folder
2. Transferred to ChromaDB long-term memory
3. Retrieved correctly when user returns after expiration

TRUE E2E TEST - Uses real app initialization via denidin.py, no direct component access.
"""
import pytest
import time
import json
import shutil
from pathlib import Path
from datetime import datetime
import denidin


@pytest.fixture(scope="module")
def test_config():
    """Load real config for integration tests."""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Override paths to use test_data directory
    test_data_root = Path(__file__).parent.parent.parent / "test_data"
    config['data_root'] = str(test_data_root)
    
    # Configure short expiration for testing
    if 'memory' not in config:
        config['memory'] = {}
    if 'session' not in config['memory']:
        config['memory']['session'] = {}
    
    config['memory']['session']['session_timeout_hours'] = 2 / 3600  # 2 seconds
    config['memory']['session']['cleanup_interval_seconds'] = 1
    config['memory']['session']['storage_dir'] = str(test_data_root / 'sessions')
    
    if 'longterm' not in config['memory']:
        config['memory']['longterm'] = {}
    config['memory']['longterm']['enabled'] = True
    config['memory']['longterm']['storage_dir'] = str(test_data_root / 'memory')
    config['memory']['longterm']['collection_name'] = 'test_memory_transfer'
    config['memory']['longterm']['embedding_model'] = 'text-embedding-3-small'
    config['memory']['longterm']['top_k_results'] = 5
    config['memory']['longterm']['min_similarity'] = 0.2  # Lower threshold for test
    
    return config




def test_session_transfer_and_recall_after_expiration(test_config):
    """
    E2E TEST - Reproduces production bug where expired sessions are archived but NOT transferred to ChromaDB.
    
    Flow:
    1. Initialize app via denidin.py with test config (5s timeout, 1s cleanup interval)
    2. User says "my name is Mike" via denidin API
    3. Wait 6 seconds for expiration + cleanup
    4. ASSERT: Session archived to test_data/sessions/expired/YYYY-MM-DD/ folder
    5. ASSERT: Session transferred to ChromaDB collection test_memory_transfer
    6. User returns and says "What's my name?" via denidin API
    7. ASSERT: System responds with "Mike" (proves memory retrieval works)
    
    Expected with BUG: Step 5 FAILS - ChromaDB is empty
    Expected after FIX: All steps PASS - session transferred atomically with archival
    """
    chat_id = "test_chat_972522968679@c.us"
    
    # Cleanup test_data directories before test
    test_data_root = Path(test_config['data_root'])
    sessions_dir = test_data_root / 'sessions'
    memory_dir = test_data_root / 'memory'
    
    # Clean previous test runs
    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)
    if memory_dir.exists():
        shutil.rmtree(memory_dir)
    
    denidin_app = None
    
    try:
        # ==================== PHASE 1: Initialize app ====================
        print("\n[PHASE 1] Initializing app with test config...")
        denidin_app = denidin.initialize_app(test_config)
        print("✓ App initialized with memory system and cleanup thread")
        
        # ==================== PHASE 2: User introduces themselves ====================
        print("\n[PHASE 2] User introduces themselves...")
        response1 = denidin_app.handle_message(chat_id, "Hello, my name is Mike")
        print(f"✓ Message sent, got response: {response1['response_text'][:100]}...")
        print(f"  Session ID: {response1['session_id']}")
        session_id = response1['session_id']
        
        # ==================== PHASE 3: Wait for expiration ====================
        print("\n[PHASE 3] Waiting for session to expire...")
        time.sleep(9)  # 2s timeout + up to 1s detection + ~4s AI operations + 2s buffer
        print("✓ Wait complete")
        
        # ==================== PHASE 4: Verify archival ====================
        print("\n[PHASE 4] Verifying session was archived...")
        
        expired_dir = sessions_dir / 'expired'
        assert expired_dir.exists(), "Expired directory should exist"
        
        # Find archived session (in dated subfolder YYYY-MM-DD)
        archived_sessions = list(expired_dir.rglob("*/session.json"))
        assert len(archived_sessions) >= 1, "Session should be archived to expired/YYYY-MM-DD/ folder"
        
        # Verify it's our session
        archived_session_path = archived_sessions[0]
        with open(archived_session_path) as f:
            archived_data = json.load(f)
        
        assert archived_data['whatsapp_chat'] == chat_id, "Archived chat ID should match"
        assert archived_data['session_id'] == session_id, "Archived session ID should match"
        print(f"✓ Session {session_id} archived to: {archived_session_path.parent.name}")
        
        # Wait for transfer to complete (check transferred_to_longterm flag)
        print("\n[PHASE 4.5] Waiting for AI transfer to complete...")
        max_wait = 10  # Max 10 seconds
        start_time = time.time()
        transferred = False
        while time.time() - start_time < max_wait:
            with open(archived_session_path) as f:
                session_data = json.load(f)
            if session_data.get('transferred_to_longterm', False):
                transferred = True
                break
            time.sleep(0.5)
        
        assert transferred, f"Transfer did not complete within {max_wait}s"
        print(f"✓ Transfer completed (took {time.time() - start_time:.1f}s)")
        
        # ==================== PHASE 5: Verify ChromaDB transfer ====================
        print("\n[PHASE 5] Verifying session was transferred to ChromaDB...")
        
        # Collection name is dynamic based on chat_id
        expected_collection_name = f"memory_{chat_id.replace('@c.us', '')}"
        
        # Get the memory manager's ChromaDB client
        chroma_client = denidin_app.ai_handler.memory_manager.client
        collection = chroma_client.get_collection(name=expected_collection_name)
        
        # BUG REPRODUCTION: This FAILS because transfer never happened!
        count = collection.count()
        assert count > 0, (
            f"BUG REPRODUCED! Session archived but NOT transferred to ChromaDB. "
            f"Collection 'test_memory_transfer' is EMPTY (count={count}). "
            f"Expected at least 2 messages from session {session_id}."
        )
        
        print(f"✓ ChromaDB has {count} messages from expired session")
        
        # ==================== PHASE 6: User returns and asks about their name ====================
        print("\n[PHASE 6] User returns and asks 'What's my name?'...")
        
        # First, verify memory can be recalled
        recalled = denidin_app.ai_handler.memory_manager.recall(
            query="What's my name?",
            collection_names=[expected_collection_name],
            top_k=5,
            min_similarity=0.0  # Get all results to see what's there
        )
        print(f"  Recalled {len(recalled)} memories: {recalled}")
        
        response2 = denidin_app.handle_message(chat_id, "What's my name?")
        print(f"✓ Got response: {response2['response_text'][:200]}...")
        
        # ==================== PHASE 7: Verify memory recall ====================
        print("\n[PHASE 7] Verifying system remembers 'Mike'...")
        
        # Response should mention Mike (AI retrieved from long-term memory)
        response_text = response2['response_text'].lower()
        assert 'mike' in response_text, (
            f"MEMORY RECALL FAILED! System should remember user's name 'Mike' from expired session. "
            f"Response: {response2['response_text']}"
        )
        
        print(f"✓ System successfully recalled 'Mike' from long-term memory")
        print("\n[SUCCESS] All assertions passed - session transfer and recall working correctly!")
        
    finally:
        # Cleanup
        if denidin_app:
            print("\n[CLEANUP] Shutting down app...")
            denidin_app.shutdown()
            print("✓ App shutdown complete")

