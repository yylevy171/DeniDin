"""
Unit tests for MemoryManager - ChromaDB long-term semantic memory.

Tests based on Phase 3 requirements:
- Per-entity collection architecture (public/private separation)
- Semantic search across multiple collections
- Memory storage with embeddings
- Collection management
- Error handling

CONSTITUTION I: Tests use config files for OpenAI client (NO env vars)
OpenAI API calls are mocked to avoid actual API usage in unit tests.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import uuid
from openai import OpenAI

from src.managers.memory_manager import MemoryManager
from src.models.config import AppConfiguration


# Load test configuration once for all tests (CONSTITUTION I)
TEST_CONFIG_PATH = 'config/config.test.json'
try:
    test_config = AppConfiguration.from_file(TEST_CONFIG_PATH)
    # Create OpenAI client from config (CONSTITUTION I - config file, not env vars)
    # API calls will be mocked in tests to avoid actual OpenAI charges
    test_ai_client = OpenAI(api_key=test_config.ai_api_key)
except Exception as e:
    raise RuntimeError(
        f"Failed to load test config from {TEST_CONFIG_PATH}. "
        f"Tests require config file (CONSTITUTION I - NO env vars). Error: {e}"
    )


class TestMemoryManagerInitialization(unittest.TestCase):
    """Test MemoryManager initialization and ChromaDB setup."""
    
    def setUp(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        # Use config-based OpenAI client (CONSTITUTION I: NO ENV VARS, NO MOCKS)
        self.ai_client = test_ai_client
    
    def tearDown(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialize_chromadb_client(self):
        """Test ChromaDB client initialization with persistent storage."""
        memory_manager = MemoryManager(storage_dir=self.temp_dir, ai_client=self.ai_client)
        
        # Verify client initialized
        self.assertIsNotNone(memory_manager.client)
        
        # Verify storage directory exists
        self.assertTrue(Path(self.temp_dir).exists())
    
    def test_create_storage_directory_if_missing(self):
        """Test that storage directory is created if it doesn't exist."""
        new_dir = Path(self.temp_dir) / "new_memory_dir"
        self.assertFalse(new_dir.exists())
        
        memory_manager = MemoryManager(storage_dir=str(new_dir), ai_client=self.ai_client)
        
        # ChromaDB should create the directory
        self.assertIsNotNone(memory_manager.client)
    
    def test_custom_embedding_model(self):
        """Test initialization with custom embedding model."""
        memory_manager = MemoryManager(
            storage_dir=self.temp_dir,
            embedding_model="text-embedding-3-large",
            ai_client=self.ai_client
        )
        
        self.assertEqual(memory_manager.embedding_model, "text-embedding-3-large")
    
    @patch('src.managers.memory_manager.chromadb.PersistentClient')
    def test_chromadb_initialization_failure_raises_exception(self, mock_client):
        """Test that ChromaDB init failure raises exception (ERR-MEMORY-001)."""
        # Mock ChromaDB to fail
        mock_client.side_effect = Exception("ChromaDB init failed")
        
        # Should raise exception (caller sets memory_enabled=False)
        with self.assertRaises(Exception) as context:
            MemoryManager(storage_dir=self.temp_dir, ai_client=self.ai_client)
        
        self.assertIn("ChromaDB init failed", str(context.exception))
    
    def test_ai_client_required(self):
        """Test that ai_client parameter is required (CONSTITUTION I: NO ENV VARS)."""
        # Should raise ValueError if ai_client not provided
        with self.assertRaises(ValueError) as context:
            MemoryManager(storage_dir=self.temp_dir, ai_client=None)
        
        self.assertIn("ai_client is required", str(context.exception))
        self.assertIn("config.json", str(context.exception).lower())


class TestCollectionManagement(unittest.TestCase):
    """Test collection creation and management (per-entity architecture)."""
    
    def setUp(self):
        """Create temporary directory and memory manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_manager = MemoryManager(storage_dir=self.temp_dir, ai_client=test_ai_client)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_or_create_collection_creates_new(self):
        """Test creating a new collection."""
        collection_name = "memory_1234567890@c.us"
        
        collection = self.memory_manager.get_or_create_collection(collection_name)
        
        self.assertIsNotNone(collection)
        self.assertEqual(collection.name, collection_name)
    
    def test_get_or_create_collection_returns_existing(self):
        """Test that getting existing collection doesn't create duplicate."""
        collection_name = "memory_test@c.us"
        
        # Create first time
        collection1 = self.memory_manager.get_or_create_collection(collection_name)
        
        # Get second time (should return same collection)
        collection2 = self.memory_manager.get_or_create_collection(collection_name)
        
        self.assertEqual(collection1.name, collection2.name)
    
    def test_create_per_client_collections(self):
        """Test creating per-client collection set (main, public, private)."""
        client_chat = "1234567890@c.us"
        
        # Create all three collections
        main_collection = self.memory_manager.get_or_create_collection(f"memory_{client_chat}")
        public_collection = self.memory_manager.get_or_create_collection(f"memory_{client_chat}_public")
        private_collection = self.memory_manager.get_or_create_collection(f"memory_{client_chat}_private")
        
        # Verify all created
        self.assertEqual(main_collection.name, f"memory_{client_chat}")
        self.assertEqual(public_collection.name, f"memory_{client_chat}_public")
        self.assertEqual(private_collection.name, f"memory_{client_chat}_private")
    
    def test_create_global_collections(self):
        """Test creating global collections (system, client context)."""
        system_collection = self.memory_manager.get_or_create_collection("memory_system_context")
        global_collection = self.memory_manager.get_or_create_collection("memory_global_client_context")
        
        self.assertEqual(system_collection.name, "memory_system_context")
        self.assertEqual(global_collection.name, "memory_global_client_context")


class TestMemoryStorage(unittest.TestCase):
    """Test memory storage (remember functionality)."""
    
    def setUp(self):
        """Create temporary directory and memory manager."""
        self.temp_dir = tempfile.mkdtemp()
        # Create mock OpenAI client for tests (avoid real API calls)
        self.mock_ai_client = Mock()
        self.memory_manager = MemoryManager(storage_dir=self.temp_dir, ai_client=self.mock_ai_client)
        
        # Setup default mock embedding response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        self.mock_ai_client.embeddings.create.return_value = mock_response
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_remember_stores_memory_in_collection(self):
        """Test storing memory with embedding in specific collection."""
        
        collection_name = "memory_1234567890@c.us"
        content = "Invoice INV-001 for ₪5000 sent on Jan 1"
        
        memory_id = self.memory_manager.remember(
            content=content,
            collection_name=collection_name
        )
        
        # Verify memory_id is UUID
        self.assertIsNotNone(memory_id)
        uuid.UUID(memory_id)  # Should not raise
        
        # Verify embedding was created
        self.mock_ai_client.embeddings.create.assert_called_once()
    
    def test_remember_with_custom_metadata(self):
        """Test storing memory with custom metadata."""
        
        collection_name = "memory_test@c.us"
        content = "TestCorp is in Tel Aviv"
        metadata = {
            'type': 'location',
            'company': 'TestCorp'
        }
        
        memory_id = self.memory_manager.remember(
            content=content,
            collection_name=collection_name,
            metadata=metadata
        )
        
        # Retrieve and verify metadata
        collection = self.memory_manager.get_or_create_collection(collection_name)
        results = collection.get(ids=[memory_id])
        stored_metadata = results['metadatas'][0]
        
        self.assertEqual(stored_metadata['type'], 'location')
        self.assertEqual(stored_metadata['company'], 'TestCorp')
        self.assertIn('created_at', stored_metadata)
    
    def test_remember_default_metadata_added(self):
        """Test that default metadata (created_at, type) is added automatically."""
        
        collection_name = "memory_test@c.us"
        memory_id = self.memory_manager.remember("Some fact", collection_name)
        
        # Retrieve and check metadata
        collection = self.memory_manager.get_or_create_collection(collection_name)
        results = collection.get(ids=[memory_id])
        metadata = results['metadatas'][0]
        
        self.assertIn('created_at', metadata)
        self.assertEqual(metadata['type'], 'fact')
    
    def test_remember_in_public_collection(self):
        """Test storing memory in client's public collection."""
        
        client_chat = "1234567890@c.us"
        public_collection = f"memory_{client_chat}_public"
        content = "Payment terms: Net 30"
        
        memory_id = self.memory_manager.remember(content, public_collection)
        
        # Verify stored in correct collection
        collection = self.memory_manager.get_or_create_collection(public_collection)
        results = collection.get(ids=[memory_id])
        
        self.assertEqual(len(results['ids']), 1)
        self.assertEqual(results['documents'][0], content)
    
    def test_remember_in_private_collection(self):
        """Test storing memory in client's private collection."""
        
        client_chat = "1234567890@c.us"
        private_collection = f"memory_{client_chat}_private"
        content = "Always pays late, be firm"
        
        memory_id = self.memory_manager.remember(content, private_collection)
        
        # Verify stored in correct collection
        collection = self.memory_manager.get_or_create_collection(private_collection)
        results = collection.get(ids=[memory_id])
        
        self.assertEqual(len(results['ids']), 1)
        self.assertEqual(results['documents'][0], content)
    
    def test_remember_embedding_failure_raises_exception(self):
        """Test that embedding generation failure raises exception (ERR-MEMORY-002)."""
        # Mock OpenAI to fail
        self.mock_ai_client.embeddings.create.side_effect = Exception("API Error")
        
        # Should raise exception (caller handles retry)
        with self.assertRaises(Exception) as context:
            self.memory_manager.remember("Test", "memory_test@c.us")
        
        self.assertIn("API Error", str(context.exception))


class TestSemanticRecall(unittest.TestCase):
    """Test semantic memory recall across multiple collections."""
    
    def setUp(self):
        """Create temporary directory and memory manager."""
        self.temp_dir = tempfile.mkdtemp()
        # Create mock OpenAI client for tests (avoid real API calls)
        self.mock_ai_client = Mock()
        self.memory_manager = MemoryManager(storage_dir=self.temp_dir, ai_client=self.mock_ai_client)
        
        # Setup default mock embedding response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        self.mock_ai_client.embeddings.create.return_value = mock_response
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_recall_from_single_collection(self):
        """Test recalling memories from a single collection."""
        
        collection_name = "memory_test@c.us"
        content = "TestCorp owes ₪5000"
        
        # Store memory
        self.memory_manager.remember(content, collection_name)
        
        # Recall memories
        results = self.memory_manager.recall(
            query="What does TestCorp owe?",
            collection_names=[collection_name]
        )
        
        # Should return stored memory
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIn('content', results[0])
        self.assertIn('similarity', results[0])
        self.assertIn('collection', results[0])
    
    def test_recall_from_multiple_collections(self):
        """Test recalling memories from multiple collections simultaneously."""
        
        client_chat = "1234567890@c.us"
        main_collection = f"memory_{client_chat}"
        public_collection = f"memory_{client_chat}_public"
        global_collection = "memory_global_client_context"
        
        # Store memories in different collections
        self.memory_manager.remember("Client history", main_collection)
        self.memory_manager.remember("Payment terms", public_collection)
        self.memory_manager.remember("General rule", global_collection)
        
        # Recall from all three
        results = self.memory_manager.recall(
            query="payment",
            collection_names=[main_collection, public_collection, global_collection]
        )
        
        # Should return results from multiple collections
        self.assertIsInstance(results, list)
    
    def test_recall_respects_top_k_limit(self):
        """Test that recall respects top_k parameter."""
        
        collection_name = "memory_test@c.us"
        
        # Store multiple memories
        for i in range(10):
            self.memory_manager.remember(f"Fact number {i}", collection_name)
        
        # Recall with top_k=3
        results = self.memory_manager.recall(
            query="Fact",
            collection_names=[collection_name],
            top_k=3
        )
        
        # Should return at most 3 results
        self.assertLessEqual(len(results), 3)
    
    def test_recall_filters_by_min_similarity(self):
        """Test that recall filters results by minimum similarity score."""
        
        collection_name = "memory_test@c.us"
        self.memory_manager.remember("TestCorp data", collection_name)
        
        # Mock collection.query to return low similarity
        collection = self.memory_manager.get_or_create_collection(collection_name)
        original_query = collection.query
        
        def mock_query(*args, **kwargs):
            result = original_query(*args, **kwargs)
            # Force low similarity (high distance)
            result['distances'] = [[0.5]]  # Distance 0.5 = similarity 0.5
            return result
        
        collection.query = mock_query
        
        # Recall with min_similarity=0.7 (should filter out)
        results = self.memory_manager.recall(
            query="query",
            collection_names=[collection_name],
            min_similarity=0.7
        )
        
        # Should be empty due to low similarity
        self.assertEqual(len(results), 0)
    
    def test_recall_empty_collections_returns_empty_list(self):
        """Test recalling from empty collections returns empty list."""
        
        # Don't store anything, just query
        results = self.memory_manager.recall(
            query="some query",
            collection_names=["memory_empty@c.us"]
        )
        
        # Should return empty list
        self.assertEqual(results, [])
    
    def test_recall_results_sorted_by_similarity_descending(self):
        """Test that recall results are sorted by similarity (best first)."""
        
        collection_name = "memory_test@c.us"
        collection = self.memory_manager.get_or_create_collection(collection_name)
        
        # Store memories
        self.memory_manager.remember("doc1", collection_name)
        self.memory_manager.remember("doc2", collection_name)
        self.memory_manager.remember("doc3", collection_name)
        
        # Mock query results with different similarities
        def mock_query(*args, **kwargs):
            return {
                'ids': [['mem1', 'mem2', 'mem3']],
                'documents': [['doc1', 'doc2', 'doc3']],
                'metadatas': [[{'type': 'fact'}] * 3],
                'distances': [[0.1, 0.3, 0.2]]  # Similarities: 0.9, 0.7, 0.8
            }
        
        collection.query = mock_query
        
        results = self.memory_manager.recall(
            query="query",
            collection_names=[collection_name],
            min_similarity=0.0
        )
        
        # Should be sorted by similarity descending (0.9, 0.8, 0.7)
        self.assertEqual(len(results), 3)
        self.assertGreaterEqual(results[0]['similarity'], results[1]['similarity'])
        self.assertGreaterEqual(results[1]['similarity'], results[2]['similarity'])
    
    def test_recall_includes_collection_name_in_results(self):
        """Test that recall results include collection name for multi-collection queries."""
        
        collection1 = "memory_client1@c.us"
        collection2 = "memory_client2@c.us"
        
        # Store in different collections
        self.memory_manager.remember("Client 1 data", collection1)
        self.memory_manager.remember("Client 2 data", collection2)
        
        # Recall from both
        results = self.memory_manager.recall(
            query="data",
            collection_names=[collection1, collection2]
        )
        
        # Each result should have collection name
        for result in results:
            self.assertIn('collection', result)
            self.assertIn(result['collection'], [collection1, collection2])
    
    def test_recall_embedding_failure_raises_exception(self):
        """Test that embedding failure during recall raises exception (ERR-MEMORY-002)."""
        # Mock OpenAI to fail on query
        self.mock_ai_client.embeddings.create.side_effect = Exception("API Error")
        
        # Should raise exception (caller handles retry/fallback)
        with self.assertRaises(Exception):
            self.memory_manager.recall("query", ["memory_test@c.us"])


class TestMemoryListing(unittest.TestCase):
    """Test memory listing functionality."""
    
    def setUp(self):
        """Create temporary directory and memory manager."""
        self.temp_dir = tempfile.mkdtemp()
        # Create mock OpenAI client for tests (avoid real API calls)
        self.mock_ai_client = Mock()
        self.memory_manager = MemoryManager(storage_dir=self.temp_dir, ai_client=self.mock_ai_client)
        
        # Setup default mock embedding response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        self.mock_ai_client.embeddings.create.return_value = mock_response
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_list_all_memories_in_collection(self):
        """Test listing all memories in a specific collection."""
        
        collection_name = "memory_test@c.us"
        
        # Store multiple memories
        self.memory_manager.remember("Fact 1", collection_name)
        self.memory_manager.remember("Fact 2", collection_name)
        self.memory_manager.remember("Fact 3", collection_name)
        
        # List all
        memories = self.memory_manager.list_memories(collection_name)
        
        self.assertEqual(len(memories), 3)
        self.assertIn('id', memories[0])
        self.assertIn('content', memories[0])
        self.assertIn('metadata', memories[0])
    
    def test_list_memories_with_limit(self):
        """Test listing with limit parameter."""
        
        collection_name = "memory_test@c.us"
        
        # Store 5 memories
        for i in range(5):
            self.memory_manager.remember(f"Fact {i}", collection_name)
        
        # List with limit=2
        memories = self.memory_manager.list_memories(collection_name, limit=2)
        
        self.assertLessEqual(len(memories), 2)
    
    def test_list_memories_filtered_by_type(self):
        """Test filtering memories by metadata type."""
        
        collection_name = "memory_test@c.us"
        
        # Store different types
        self.memory_manager.remember(
            "Location fact",
            collection_name,
            metadata={'type': 'location'}
        )
        self.memory_manager.remember(
            "Financial fact",
            collection_name,
            metadata={'type': 'financial'}
        )
        self.memory_manager.remember(
            "Another location",
            collection_name,
            metadata={'type': 'location'}
        )
        
        # Filter by type
        locations = self.memory_manager.list_memories(
            collection_name,
            memory_type='location'
        )
        
        self.assertEqual(len(locations), 2)
        for mem in locations:
            self.assertEqual(mem['metadata']['type'], 'location')


class TestEmbeddingGeneration(unittest.TestCase):
    """Test embedding generation with OpenAI."""
    
    def setUp(self):
        """Create temporary directory and memory manager."""
        self.temp_dir = tempfile.mkdtemp()
        # Create mock OpenAI client for tests (avoid real API calls)
        self.mock_ai_client = Mock()
        self.memory_manager = MemoryManager(storage_dir=self.temp_dir, ai_client=self.mock_ai_client)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_embedding_calls_openai_api(self):
        """Test embedding creation with OpenAI API."""
        # Mock OpenAI response
        mock_response = Mock()
        expected_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
        mock_response.data = [Mock(embedding=expected_embedding)]
        self.mock_ai_client.embeddings.create.return_value = mock_response
        
        # Create embedding
        embedding = self.memory_manager._create_embedding("Test text")
        
        # Verify
        self.assertEqual(embedding, expected_embedding)
        self.mock_ai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="Test text"
        )
    
    def test_create_embedding_with_custom_model(self):
        """Test embedding with custom model."""
        # Create mock client for this test
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response
        
        # Create manager with custom model
        memory_manager = MemoryManager(
            storage_dir=self.temp_dir,
            embedding_model="text-embedding-3-large",
            ai_client=mock_client
        )
        
        # Create embedding
        memory_manager._create_embedding("Test")
        
        # Verify correct model used
        mock_client.embeddings.create.assert_called_with(
            model="text-embedding-3-large",
            input="Test"
        )
    
    def test_create_embedding_api_failure_raises_exception(self):
        """Test that OpenAI API failure raises exception."""
        # Mock OpenAI to fail
        self.mock_ai_client.embeddings.create.side_effect = Exception("API Error")
        
        # Should raise exception
        with self.assertRaises(Exception) as context:
            self.memory_manager._create_embedding("Test")
        
        self.assertIn("API Error", str(context.exception))


if __name__ == '__main__':
    unittest.main()
