"""
Integration tests for RBAC (Role-Based Access Control) system.

Tests verify that all RBAC components work together correctly:
- User model + UserManager + MemoryManager + SessionManager + AIHandler
- End-to-end flows with different user roles
- Memory isolation and token limit enforcement
- Multi-user scenarios

NOTE: Per CONSTITUTION.md - Integration tests load configuration from config.test.json.
Feature flags (like enable_rbac) are set in that config file, NOT in test code.
This ensures tests run with production-like configuration loading.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
from openai import OpenAI

from src.models.config import AppConfiguration
from src.models.user import Role, MemoryScope
from src.models.message import WhatsAppMessage, AIRequest
from src.handlers.ai_handler import AIHandler
from src.managers.user_manager import UserManager
from src.managers.memory_manager import MemoryManager
from src.managers.session_manager import SessionManager


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def rbac_config(temp_data_dir):
    """Load AppConfiguration from config.test.json with RBAC enabled."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "config.test.json"
    config = AppConfiguration.from_file(str(config_path))
    
    # Override storage directories to use temp_data_dir
    config.memory['session']['storage_dir'] = f'{temp_data_dir}/sessions'
    config.memory['longterm']['storage_dir'] = f'{temp_data_dir}/memory'
    
    return config


@pytest.fixture
def mock_ai_client():
    """Create mock OpenAI client."""
    client = MagicMock()
    
    # Mock embeddings
    mock_embedding = Mock()
    mock_embedding.embedding = [0.1] * 1536  # Mock embedding vector
    client.embeddings.create.return_value = Mock(data=[mock_embedding])
    
    # Mock Responses API call
    mock_response = Mock()
    mock_response.output_text = "Test AI response"
    mock_response.output = []
    mock_response.incomplete_details = None
    mock_response.usage = Mock(
        total_tokens=150,
        input_tokens=100,
        output_tokens=50
    )
    mock_response.model = "gpt-4o-mini"
    client.responses.create.return_value = mock_response
    
    return client


class TestEndToEndRBACEnforcement:
    """Test complete RBAC enforcement across all components."""
    
    def test_client_user_flow(self, rbac_config, mock_ai_client):
        """CLIENT user: filtered memories, 4K token limit."""
        # Arrange
        handler = AIHandler(mock_ai_client, rbac_config)
        client_phone = "+972501111111"
        
        # Act: Create request
        message = WhatsAppMessage(
            message_id="msg-1",
            chat_id="client@c.us",
            sender_name="Client User",
            sender_id=client_phone,
            text_content="Hello, what can you help me with?",
            timestamp=1234567890,
            message_type="text"
        )
        
        request = handler.create_request(message, user_phone=client_phone)
        
        # Act: Get response (stores in session with token limit)
        response = handler.get_response(
            request,
            user_phone=client_phone,
            sender=client_phone,
            recipient="AI"
        )
        
        # Assert
        assert response.response_text == "Test AI response"
        assert handler.user_manager.get_user(client_phone).role == Role.CLIENT
        assert handler.user_manager.get_user(client_phone).token_limit == 4000
    
    def test_godfather_user_flow(self, rbac_config, mock_ai_client):
        """GODFATHER user: sees all private memories, 100K token limit.

        Reality check (bugfix/010): a real Green API webhook's sender is a
        WhatsApp JID like "+972501234567@c.us" (see WhatsAppMessage.from_notification
        and its pinned test in test_message.py), not the bare phone number
        config.test.json's godfather_phone is expressed as. This test previously
        hardcoded sender_id as the bare phone AND passed an explicit user_phone=
        override to create_request()/get_response() - a test-only convenience
        parameter denidin.py's real webhook handler never passes (it only ever
        passes sender=message.sender_id). That combination let this test pass
        while production silently resolved real godfather messages to CLIENT.
        """
        # Arrange
        handler = AIHandler(mock_ai_client, rbac_config)
        godfather_phone = "+972501234567"
        godfather_whatsapp_id = f"{godfather_phone}@c.us"

        # Act
        message = WhatsAppMessage(
            message_id="msg-2",
            chat_id="godfather@c.us",
            sender_name="Godfather",
            sender_id=godfather_whatsapp_id,
            text_content="Show me everything",
            timestamp=1234567890,
            message_type="text"
        )

        # No user_phone= override - matches denidin.py's real call shape exactly
        # (get_response(ai_request, sender=message.sender_id, recipient="AI")).
        request = handler.create_request(message)
        response = handler.get_response(
            request,
            sender=godfather_whatsapp_id,
            recipient="AI"
        )

        # Assert
        user = handler.user_manager.get_user(godfather_whatsapp_id)
        assert user.role == Role.GODFATHER
        assert user.token_limit == 100000
        assert user.can_see_all_memories is True
    
    def test_admin_user_flow(self, rbac_config, mock_ai_client):
        """ADMIN user: full access including SYSTEM scope."""
        # Arrange
        handler = AIHandler(mock_ai_client, rbac_config)
        admin_phone = "+972509999999"
        
        # Act
        user = handler.user_manager.get_user(admin_phone)
        
        # Assert
        assert user.role == Role.ADMIN
        assert user.can_access_system is True
        assert MemoryScope.SYSTEM in user.allowed_memory_scopes
        assert user.token_limit == 100000
    
    def test_blocked_user_rejected(self, rbac_config, mock_ai_client):
        """BLOCKED user: rejected at all entry points."""
        # Arrange
        handler = AIHandler(mock_ai_client, rbac_config)
        blocked_phone = "+972505555555"
        
        message = WhatsAppMessage(
            message_id="msg-3",
            chat_id="blocked@c.us",
            sender_name="Blocked User",
            sender_id=blocked_phone,
            text_content="Let me in!",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Act & Assert: create_request rejects
        with pytest.raises(PermissionError, match="User is blocked"):
            handler.create_request(message, user_phone=blocked_phone)
        
        # Act & Assert: get_response rejects
        request = AIRequest(
            user_prompt="Test",
            constitution="Test",
            max_tokens=500,
            model="gpt-4o-mini",
            chat_id="blocked@c.us",
            message_id="msg-3"
        )
        
        with pytest.raises(PermissionError, match="User is blocked"):
            handler.get_response(request, user_phone=blocked_phone, sender=blocked_phone)



class TestMemoryScopeFiltering:
    """Test memory filtering based on user roles and scopes."""
    
    def test_client_sees_public_and_own_private(self, rbac_config, mock_ai_client, temp_data_dir):
        """CLIENT can recall PUBLIC memories and their own PRIVATE memories."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "test_collection"
        client_phone = "+972501111111"
        
        # Store PUBLIC memory
        memory_manager.remember(
            content="Public announcement",
            collection_name=collection,
            metadata={"scope": MemoryScope.PUBLIC.value}
        )
        
        # Store PRIVATE memory for client
        memory_manager.remember(
            content="Client private note",
            collection_name=collection,
            metadata={"scope": MemoryScope.PRIVATE.value, "user_phone": client_phone}
        )
        
        # Store PRIVATE memory for different user
        memory_manager.remember(
            content="Other user private note",
            collection_name=collection,
            metadata={"scope": MemoryScope.PRIVATE.value, "user_phone": "+972502222222"}
        )
        
        # Act: CLIENT recalls
        results = memory_manager.recall_with_rbac_filter(
            query="note",
            collection_names=[collection],
            user_phone=client_phone,
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
            can_see_all_memories=False,
            top_k=10,
            min_similarity=0.0
        )
        
        # Assert: Should see PUBLIC + own PRIVATE (2 memories)
        contents = [r['content'] for r in results]
        assert "Public announcement" in contents
        assert "Client private note" in contents
        assert "Other user private note" not in contents
    
    def test_godfather_sees_all_private_memories(self, rbac_config, mock_ai_client, temp_data_dir):
        """GODFATHER sees PUBLIC + ALL PRIVATE memories (not SYSTEM)."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "test_collection"
        godfather_phone = "+972501234567"
        
        # Store memories
        memory_manager.remember("Public", collection, {"scope": MemoryScope.PUBLIC.value})
        memory_manager.remember("Private User A", collection, {"scope": MemoryScope.PRIVATE.value, "user_phone": "+972501111111"})
        memory_manager.remember("Private User B", collection, {"scope": MemoryScope.PRIVATE.value, "user_phone": "+972502222222"})
        memory_manager.remember("System config", collection, {"scope": MemoryScope.SYSTEM.value})
        
        # Act: GODFATHER recalls
        results = memory_manager.recall_with_rbac_filter(
            query="test",
            collection_names=[collection],
            user_phone=godfather_phone,
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
            can_see_all_memories=True,  # GODFATHER sees all
            top_k=10,
            min_similarity=0.0
        )
        
        # Assert: Should see PUBLIC + all PRIVATE (3 memories), not SYSTEM
        contents = [r['content'] for r in results]
        assert len(contents) == 3
        assert "Public" in contents
        assert "Private User A" in contents
        assert "Private User B" in contents
        assert "System config" not in contents
    
    def test_admin_sees_everything_including_system(self, rbac_config, mock_ai_client, temp_data_dir):
        """ADMIN sees all scopes including SYSTEM."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "test_collection"
        admin_phone = "+972509999999"
        
        # Store memories
        memory_manager.remember("Public", collection, {"scope": MemoryScope.PUBLIC.value})
        memory_manager.remember("Private", collection, {"scope": MemoryScope.PRIVATE.value, "user_phone": "+972501111111"})
        memory_manager.remember("System", collection, {"scope": MemoryScope.SYSTEM.value})
        
        # Act: ADMIN recalls
        results = memory_manager.recall_with_rbac_filter(
            query="test",
            collection_names=[collection],
            user_phone=admin_phone,
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE, MemoryScope.SYSTEM],
            can_see_all_memories=True,
            top_k=10,
            min_similarity=0.0
        )
        
        # Assert: Should see all 3 memories
        contents = [r['content'] for r in results]
        assert len(contents) == 3
        assert "Public" in contents
        assert "Private" in contents
        assert "System" in contents


class TestMultiUserMemoryIsolation:
    """Test memory isolation between users."""
    
    def test_private_memories_isolated_between_clients(self, rbac_config, mock_ai_client, temp_data_dir):
        """User A's PRIVATE memories not visible to User B (both CLIENTs)."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "shared_collection"
        user_a = "+972501111111"
        user_b = "+972502222222"
        
        # User A stores private memory
        memory_manager.remember(
            "User A secret",
            collection,
            {"scope": MemoryScope.PRIVATE.value, "user_phone": user_a}
        )
        
        # User B stores private memory
        memory_manager.remember(
            "User B secret",
            collection,
            {"scope": MemoryScope.PRIVATE.value, "user_phone": user_b}
        )
        
        # Act: User A recalls
        results_a = memory_manager.recall_with_rbac_filter(
            query="secret",
            collection_names=[collection],
            user_phone=user_a,
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
            can_see_all_memories=False,
            top_k=10,
            min_similarity=0.0
        )
        
        # Act: User B recalls
        results_b = memory_manager.recall_with_rbac_filter(
            query="secret",
            collection_names=[collection],
            user_phone=user_b,
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
            can_see_all_memories=False,
            top_k=10,
            min_similarity=0.0
        )
        
        # Assert: Each user sees only their own memory
        assert len(results_a) == 1
        assert results_a[0]['content'] == "User A secret"
        
        assert len(results_b) == 1
        assert results_b[0]['content'] == "User B secret"
    
    def test_public_memory_visible_to_all_users(self, rbac_config, mock_ai_client, temp_data_dir):
        """PUBLIC memories visible to all user roles."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "public_collection"
        
        # Store PUBLIC memory
        memory_manager.remember(
            "Important announcement for everyone",
            collection,
            {"scope": MemoryScope.PUBLIC.value}
        )
        
        # Act: Different users recall
        client_results = memory_manager.recall_with_rbac_filter(
            query="announcement",
            collection_names=[collection],
            user_phone="+972501111111",
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
            can_see_all_memories=False,
            top_k=10,
            min_similarity=0.0
        )
        
        godfather_results = memory_manager.recall_with_rbac_filter(
            query="announcement",
            collection_names=[collection],
            user_phone="+972501234567",
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
            can_see_all_memories=True,
            top_k=10,
            min_similarity=0.0
        )
        
        # Assert: Both see the public memory
        assert len(client_results) == 1
        assert client_results[0]['content'] == "Important announcement for everyone"
        
        assert len(godfather_results) == 1
        assert godfather_results[0]['content'] == "Important announcement for everyone"


class TestConfigLoadingAndRoleAssignment:
    """Test configuration loading and role precedence."""
    
    def test_role_precedence_admin_over_godfather(self):
        """ADMIN role takes precedence over GODFATHER."""
        # Arrange: Phone number in both godfather AND admin list
        # Create custom config with same phone in both roles
        user_manager = UserManager(
            godfather_phone="+972501234567",
            admin_phones=["+972501234567"],  # Same number!
            blocked_phones=[]
        )
        
        # Act
        user = user_manager.get_user("+972501234567")
        
        # Assert: Should be ADMIN (precedence)
        assert user.role == Role.ADMIN
    
    def test_role_precedence_blocked_over_client(self):
        """BLOCKED role takes precedence over default CLIENT."""
        # Arrange
        user_manager = UserManager(
            godfather_phone="+972501234567",
            admin_phones=[],
            blocked_phones=["+972505555555"]
        )
        
        # Act
        user = user_manager.get_user("+972505555555")
        
        # Assert
        assert user.role == Role.BLOCKED
    
    def test_unknown_phone_defaults_to_client(self):
        """Unknown phone number defaults to CLIENT role."""
        # Arrange
        user_manager = UserManager(
            godfather_phone="+972501234567",
            admin_phones=["+972509999999"],
            blocked_phones=["+972505555555"]
        )
        
        # Act
        unknown_user = user_manager.get_user("+972508888888")
        
        # Assert
        assert unknown_user.role == Role.CLIENT


class TestErrorHandling:
    """Test error handling for edge cases and invalid inputs."""
    
    def test_blocked_user_create_request_raises_permission_error(self, rbac_config, mock_ai_client):
        """create_request() raises PermissionError for blocked users."""
        # Arrange
        handler = AIHandler(mock_ai_client, rbac_config)
        blocked_phone = "+972505555555"
        
        message = WhatsAppMessage(
            message_id="msg-blocked",
            chat_id="blocked@c.us",
            sender_name="Blocked User",
            sender_id=blocked_phone,
            text_content="Let me in!",
            timestamp=1234567890,
            message_type="text"
        )
        
        # Act & Assert
        with pytest.raises(PermissionError) as exc_info:
            handler.create_request(message, user_phone=blocked_phone)
        
        assert "User is blocked" in str(exc_info.value)
    
    def test_blocked_user_get_response_raises_permission_error(self, rbac_config, mock_ai_client):
        """get_response() raises PermissionError for blocked users."""
        # Arrange
        handler = AIHandler(mock_ai_client, rbac_config)
        blocked_phone = "+972505555555"
        
        request = AIRequest(
            user_prompt="Test",
            constitution="Test",
            max_tokens=500,
            model="gpt-4o-mini",
            chat_id="blocked@c.us",
            message_id="msg-blocked"
        )
        
        # Act & Assert
        with pytest.raises(PermissionError) as exc_info:
            handler.get_response(request, user_phone=blocked_phone, sender=blocked_phone)
        
        assert "User is blocked" in str(exc_info.value)
    
    def test_recall_with_empty_allowed_scopes(self, rbac_config, mock_ai_client, temp_data_dir):
        """Recall with empty allowed_scopes returns nothing."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "test_collection"
        memory_manager.remember("Test memory", collection, {"scope": MemoryScope.PUBLIC.value})
        
        # Act: Recall with empty scopes
        results = memory_manager.recall_with_rbac_filter(
            query="test",
            collection_names=[collection],
            user_phone="+972501111111",
            allowed_scopes=[],  # Empty!
            can_see_all_memories=False,
            top_k=10,
            min_similarity=0.0
        )
        
        # Assert: No results
        assert len(results) == 0
    


class TestConcurrentUserScenarios:
    """Test concurrent user operations (simulated)."""
    
    def test_multiple_users_same_collection_isolated(self, rbac_config, mock_ai_client, temp_data_dir):
        """Multiple users storing memories in same collection remain isolated."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "shared_collection"
        user_phones = ["+972501111111", "+972502222222", "+972503333333"]
        
        # Act: Each user stores a private memory
        for i, phone in enumerate(user_phones):
            memory_manager.remember(
                f"User {i} private data",
                collection,
                {"scope": MemoryScope.PRIVATE.value, "user_phone": phone}
            )
        
        # Act: Each user recalls
        for i, phone in enumerate(user_phones):
            results = memory_manager.recall_with_rbac_filter(
                query="data",
                collection_names=[collection],
                user_phone=phone,
                allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
                can_see_all_memories=False,
                top_k=10,
                min_similarity=0.0
            )
            
            # Assert: Each user sees only their own memory
            assert len(results) == 1
            assert results[0]['content'] == f"User {i} private data"
    
    def test_godfather_sees_all_concurrent_users_memories(self, rbac_config, mock_ai_client, temp_data_dir):
        """GODFATHER can see memories from all concurrent users."""
        # Arrange
        memory_manager = MemoryManager(
            storage_dir=f'{temp_data_dir}/memory',
            embedding_model='text-embedding-3-small',
            ai_client=mock_ai_client
        )
        
        collection = "concurrent_collection"
        godfather_phone = "+972501234567"
        
        # Act: Multiple users store private memories
        user_phones = ["+972501111111", "+972502222222", "+972503333333"]
        for phone in user_phones:
            memory_manager.remember(
                f"Memory from {phone}",
                collection,
                {"scope": MemoryScope.PRIVATE.value, "user_phone": phone}
            )
        
        # Act: GODFATHER recalls
        results = memory_manager.recall_with_rbac_filter(
            query="Memory",
            collection_names=[collection],
            user_phone=godfather_phone,
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE],
            can_see_all_memories=True,  # GODFATHER sees all
            top_k=10,
            min_similarity=0.0
        )
        
        # Assert: GODFATHER sees all 3 memories
        assert len(results) == 3
        contents = [r['content'] for r in results]
        for phone in user_phones:
            assert f"Memory from {phone}" in contents
    
    def test_session_isolation_between_concurrent_users(self, rbac_config, temp_data_dir):
        """Multiple users' sessions remain isolated."""
        # Arrange
        session_manager = SessionManager(
            storage_dir=f'{temp_data_dir}/sessions',
        )
        
        # Act: Multiple users create sessions
        chat_ids = ["user1@c.us", "user2@c.us", "user3@c.us"]
        for i, chat_id in enumerate(chat_ids):
            session_manager.add_message_with_tokens(
                chat_id=chat_id,
                role="user",
                content=f"Message from {chat_id}",
                user_role=Role.CLIENT,
                sender=f"+97250{i}111111",
                recipient="AI"
            )
        
        # Assert: Each session has only its own messages
        for i, chat_id in enumerate(chat_ids):
            session = session_manager.get_session(chat_id)
            assert len(session.message_ids) == 1
            # Message isolation verified by message_ids count
