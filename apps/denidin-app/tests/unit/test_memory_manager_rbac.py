"""Unit tests for MemoryManager RBAC filtering."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.managers.memory_manager import MemoryManager
from src.models.user import MemoryScope


class TestMemoryManagerRBACFiltering:
    """Test memory filtering based on user roles and scopes."""
    
    @pytest.fixture
    def mock_ai_client(self):
        """Create mock AI client."""
        client = Mock()
        client.embeddings = Mock()
        client.embeddings.create = Mock(return_value=Mock(
            data=[Mock(embedding=[0.1] * 1536)]
        ))
        return client
    
    @pytest.fixture
    def memory_manager(self, mock_ai_client, tmp_path):
        """Create MemoryManager with mock AI client."""
        return MemoryManager(
            storage_dir=str(tmp_path / "memory"),
            ai_client=mock_ai_client
        )
    
    def test_remember_with_scope_metadata(self, memory_manager):
        """Test that memories can be stored with scope in metadata."""
        memory_id = memory_manager.remember(
            content="Test memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.PRIVATE.value}
        )
        assert memory_id is not None
        assert isinstance(memory_id, str)
    
    def test_remember_with_user_phone_metadata(self, memory_manager):
        """Test that memories can be stored with user_phone in metadata."""
        memory_id = memory_manager.remember(
            content="Test memory",
            collection_name="memory_test",
            metadata={
                "user_phone": "+972501234567",
                "scope": MemoryScope.PRIVATE.value
            }
        )
        assert memory_id is not None
    
    def test_remember_defaults_to_private_scope_when_not_specified(self, memory_manager):
        """Test that scope defaults to PRIVATE when not specified."""
        memory_id = memory_manager.remember(
            content="Test memory",
            collection_name="memory_test",
            metadata={"user_phone": "+972501234567"}
        )
        
        # Retrieve and verify default scope
        collection = memory_manager.get_or_create_collection("memory_test")
        result = collection.get(ids=[memory_id])
        assert result['metadatas'][0].get('scope', MemoryScope.PRIVATE.value) == MemoryScope.PRIVATE.value
    
    def test_recall_with_scope_filter(self, memory_manager):
        """Test recalling memories filtered by allowed scopes."""
        # Store memories with different scopes
        memory_manager.remember(
            content="Public memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.PUBLIC.value}
        )
        memory_manager.remember(
            content="Private memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.PRIVATE.value}
        )
        memory_manager.remember(
            content="System memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.SYSTEM.value}
        )
        
        # Recall with scope filter (e.g., CLIENT can only see PRIVATE)
        results = memory_manager.recall_with_scope_filter(
            query="memory",
            collection_names=["memory_test"],
            allowed_scopes=[MemoryScope.PRIVATE],
            top_k=10
        )
        
        # Should only get PRIVATE scope memories
        assert len(results) == 1
        assert "Private" in results[0]['content']
    
    def test_recall_with_multiple_allowed_scopes(self, memory_manager):
        """Test recalling memories with multiple allowed scopes."""
        # Store memories
        memory_manager.remember(
            content="Public memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.PUBLIC.value}
        )
        memory_manager.remember(
            content="Private memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.PRIVATE.value}
        )
        memory_manager.remember(
            content="System memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.SYSTEM.value}
        )
        
        # Recall with ADMIN scopes (all)
        results = memory_manager.recall_with_scope_filter(
            query="memory",
            collection_names=["memory_test"],
            allowed_scopes=[MemoryScope.PUBLIC, MemoryScope.PRIVATE, MemoryScope.SYSTEM],
            top_k=10
        )
        
        # Should get all memories
        assert len(results) == 3
    
    def test_recall_with_user_phone_filter_for_client(self, memory_manager):
        """Test that CLIENT users only see their own memories."""
        # Store memories from different users
        memory_manager.remember(
            content="User1 memory",
            collection_name="memory_test",
            metadata={
                "user_phone": "+972501234567",
                "scope": MemoryScope.PRIVATE.value
            }
        )
        memory_manager.remember(
            content="User2 memory",
            collection_name="memory_test",
            metadata={
                "user_phone": "+972507654321",
                "scope": MemoryScope.PRIVATE.value
            }
        )
        
        # Recall as CLIENT user1 (can only see own memories)
        results = memory_manager.recall_with_rbac_filter(
            query="memory",
            collection_names=["memory_test"],
            user_phone="+972501234567",
            allowed_scopes=[MemoryScope.PRIVATE],
            can_see_all_memories=False,
            top_k=10
        )
        
        # Should only see own memory
        assert len(results) == 1
        assert "User1" in results[0]['content']
    
    def test_recall_with_user_phone_filter_for_godfather(self, memory_manager):
        """Test that GODFATHER users see all memories."""
        # Store memories from different users
        memory_manager.remember(
            content="User1 memory",
            collection_name="memory_test",
            metadata={
                "user_phone": "+972501234567",
                "scope": MemoryScope.PRIVATE.value
            }
        )
        memory_manager.remember(
            content="User2 memory",
            collection_name="memory_test",
            metadata={
                "user_phone": "+972509999999",
                "scope": MemoryScope.PRIVATE.value
            }
        )
        
        # Recall as GODFATHER (can see all memories)
        results = memory_manager.recall_with_rbac_filter(
            query="memory",
            collection_names=["memory_test"],
            user_phone="+972507654321",  # Godfather phone
            allowed_scopes=[MemoryScope.PRIVATE],
            can_see_all_memories=True,
            top_k=10
        )
        
        # Should see all memories
        assert len(results) == 2
    
    def test_recall_filters_by_both_scope_and_user_phone(self, memory_manager):
        """Test that recall filters by both scope AND user_phone for CLIENT."""
        # Store various memories
        memory_manager.remember(
            content="User1 private",
            collection_name="memory_test",
            metadata={
                "user_phone": "+972501234567",
                "scope": MemoryScope.PRIVATE.value
            }
        )
        memory_manager.remember(
            content="User1 system",  # Wrong scope for CLIENT
            collection_name="memory_test",
            metadata={
                "user_phone": "+972501234567",
                "scope": MemoryScope.SYSTEM.value
            }
        )
        memory_manager.remember(
            content="User2 private",  # Wrong user
            collection_name="memory_test",
            metadata={
                "user_phone": "+972507654321",
                "scope": MemoryScope.PRIVATE.value
            }
        )
        
        # Recall as CLIENT user1
        results = memory_manager.recall_with_rbac_filter(
            query="private",
            collection_names=["memory_test"],
            user_phone="+972501234567",
            allowed_scopes=[MemoryScope.PRIVATE],
            can_see_all_memories=False,
            top_k=10
        )
        
        # Should only see user1's private memory
        assert len(results) == 1
        assert "User1 private" in results[0]['content']
    
    def test_recall_with_empty_collection_returns_empty_list(self, memory_manager):
        """Test that recalling from empty collection returns empty list."""
        results = memory_manager.recall_with_rbac_filter(
            query="test",
            collection_names=["empty_collection"],
            user_phone="+972501234567",
            allowed_scopes=[MemoryScope.PRIVATE],
            can_see_all_memories=False,
            top_k=10
        )
        assert results == []
    
    def test_recall_with_no_matching_scope_returns_empty_list(self, memory_manager):
        """Test that no results returned when scope doesn't match."""
        # Store SYSTEM scope memory
        memory_manager.remember(
            content="System memory",
            collection_name="memory_test",
            metadata={"scope": MemoryScope.SYSTEM.value}
        )
        
        # Try to recall with CLIENT scopes (PRIVATE only)
        results = memory_manager.recall_with_scope_filter(
            query="memory",
            collection_names=["memory_test"],
            allowed_scopes=[MemoryScope.PRIVATE],
            top_k=10
        )
        
        assert results == []


class TestMemoryManagerRBACHelpers:
    """Test helper methods for RBAC filtering."""
    
    @pytest.fixture
    def mock_ai_client(self):
        """Create mock AI client."""
        client = Mock()
        client.embeddings = Mock()
        client.embeddings.create = Mock(return_value=Mock(
            data=[Mock(embedding=[0.1] * 1536)]
        ))
        return client
    
    @pytest.fixture
    def memory_manager(self, mock_ai_client, tmp_path):
        """Create MemoryManager with mock AI client."""
        return MemoryManager(
            storage_dir=str(tmp_path / "memory"),
            ai_client=mock_ai_client
        )
    
    def test_filter_results_by_scope(self, memory_manager):
        """Test filtering results by allowed scopes."""
        results = [
            {'content': 'Public', 'metadata': {'scope': MemoryScope.PUBLIC.value}},
            {'content': 'Private', 'metadata': {'scope': MemoryScope.PRIVATE.value}},
            {'content': 'System', 'metadata': {'scope': MemoryScope.SYSTEM.value}}
        ]
        
        filtered = memory_manager._filter_by_scope(
            results,
            allowed_scopes=[MemoryScope.PRIVATE]
        )
        
        assert len(filtered) == 1
        assert filtered[0]['content'] == 'Private'
    
    def test_filter_results_by_user_phone(self, memory_manager):
        """Test filtering results by user_phone."""
        results = [
            {'content': 'User1', 'metadata': {'user_phone': '+972501234567'}},
            {'content': 'User2', 'metadata': {'user_phone': '+972507654321'}}
        ]
        
        filtered = memory_manager._filter_by_user_phone(
            results,
            user_phone='+972501234567'
        )
        
        assert len(filtered) == 1
        assert filtered[0]['content'] == 'User1'
    
    def test_filter_by_user_phone_skipped_when_can_see_all(self, memory_manager):
        """Test that user_phone filter is skipped when can_see_all_memories=True."""
        results = [
            {'content': 'User1', 'metadata': {'user_phone': '+972501234567'}},
            {'content': 'User2', 'metadata': {'user_phone': '+972507654321'}}
        ]
        
        # When can_see_all_memories=True, should not filter by user_phone
        filtered = memory_manager._filter_by_user_phone(
            results,
            user_phone='+972501234567',
            skip_filter=True
        )
        
        assert len(filtered) == 2
