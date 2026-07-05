"""
MemoryManager - ChromaDB-based long-term semantic memory.

Phase 3 of Memory System: Persistent vector database for semantic search.

Architecture:
- Per-entity collection architecture (separate collections per client)
- Collections: memory_{entity}, memory_{entity}_public, memory_{entity}_private
- Global collections: memory_system_context, memory_global_client_context
- Semantic search using OpenAI embeddings (text-embedding-3-small)
- Storage trigger: Batch transfer on session expiration

Error Handling:
- ERR-MEMORY-001: ChromaDB initialization failure → raise exception
- ERR-MEMORY-002: Embedding generation failure → raise exception
- Caller responsibility: Handle retries, set memory_enabled=False on failure
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings
from openai import OpenAI

from src.models.user import MemoryScope


class CollectionWrapper:
    """Wrapper for ChromaDB collection that preserves original name."""

    def __init__(self, collection, original_name: str):
        self._collection = collection
        self.name = original_name  # Override with original unsanitized name

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped collection."""
        return getattr(self._collection, name)


class MemoryManager:
    """Long-term semantic memory using ChromaDB vector database."""

    def __init__(
        self,
        storage_dir: str = "data/memory",
        embedding_model: str = "text-embedding-3-small",
        ai_client: Optional[OpenAI] = None
    ):
        """
        Initialize MemoryManager with ChromaDB and AI clients.

        Args:
            storage_dir: Directory for ChromaDB persistent storage
            embedding_model: OpenAI embedding model to use
            ai_client: OpenAI client instance (required, no environment variables per CONSTITUTION I)

        Raises:
            Exception: If ChromaDB or AI initialization fails (ERR-MEMORY-001)
        """
        self.storage_dir = Path(storage_dir)
        self.embedding_model = embedding_model
        self._collection_cache = {}  # Cache collection objects for test mocking compatibility

        # Initialize ChromaDB persistent client
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.storage_dir),
                settings=Settings(
                    anonymized_telemetry=False
                )
            )
        except Exception as e:
            raise RuntimeError(f"ChromaDB initialization failed: {e}") from e

        # Initialize AI client
        # MUST be provided explicitly (no environment variables per CONSTITUTION I)
        if ai_client is None:
            raise ValueError(
                "ai_client is required. "
                "MemoryManager does not use environment variables. "
                "Pass AI client initialized from config.json."
            )
        self._ai_client = ai_client

    @property
    def ai_client(self):
        """Access AI client (must be initialized in __init__)."""
        if self._ai_client is None:
            raise RuntimeError(
                "AI client not initialized. "
                "This should not happen - client is required in __init__."
            )
        return self._ai_client

    def get_or_create_collection(self, collection_name: str):
        """
        Get existing collection or create new one with cosine similarity.

        Args:
            collection_name: Name of collection (e.g., "memory_1234567890@c.us")

        Returns:
            ChromaDB Collection object (wrapped to preserve original name)
        """
        # Return cached collection if available (for test mocking compatibility)
        if collection_name in self._collection_cache:
            return self._collection_cache[collection_name]

        # Sanitize collection name for ChromaDB (only allows [a-zA-Z0-9._-])
        safe_name = collection_name.replace('@', '_at_').replace(':', '_')

        collection = self.client.get_or_create_collection(
            name=safe_name,
            metadata={"hnsw:space": "cosine"}
        )

        # Wrap collection to preserve original name
        wrapped = CollectionWrapper(collection, collection_name)

        # Cache the wrapped collection object
        self._collection_cache[collection_name] = wrapped
        return wrapped

    def remember(
        self,
        content: str,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store memory in specified collection with embedding.

        Args:
            content: Text content to store
            collection_name: Target collection (e.g., "memory_{chat}_public")
            metadata: Optional metadata dict (type, company, etc.)

        Returns:
            UUID string of stored memory

        Raises:
            Exception: If embedding generation fails (ERR-MEMORY-002)
        """
        # Generate embedding
        embedding = self._create_embedding(content)

        # Prepare metadata with defaults
        if metadata is None:
            metadata = {}

        # Add default metadata
        metadata.setdefault('type', 'fact')
        metadata.setdefault('scope', MemoryScope.PRIVATE.value)  # Default to PRIVATE
        metadata['created_at'] = datetime.now(timezone.utc).isoformat()

        # Generate unique ID
        memory_id = str(uuid.uuid4())

        # Get collection
        collection = self.get_or_create_collection(collection_name)

        # Store in ChromaDB
        collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )

        return memory_id

    def recall(
        self,
        query: str,
        collection_names: List[str],
        top_k: int = 5,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across multiple collections.

        Args:
            query: Search query text
            collection_names: List of collections to search
            top_k: Maximum results to return
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of dicts with keys: content, similarity, collection, metadata
            Sorted by similarity descending (best match first)

        Raises:
            Exception: If embedding generation fails (ERR-MEMORY-002)
        """
        # Generate query embedding
        query_embedding = self._create_embedding(query)

        all_results = []

        # Query each collection
        for collection_name in collection_names:
            try:
                collection = self.get_or_create_collection(collection_name)

                # Check if collection is empty
                count = collection.count()
                if count == 0:
                    continue

                # Query collection
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, count)
                )

                # Process results
                if results['ids'] and results['ids'][0]:
                    for i in range(len(results['ids'][0])):
                        # Calculate similarity from distance (cosine)
                        # ChromaDB returns distance, similarity = 1 - distance
                        distance = results['distances'][0][i]
                        similarity = 1.0 - distance

                        # Filter by minimum similarity
                        if similarity >= min_similarity:
                            all_results.append({
                                'content': results['documents'][0][i],
                                'similarity': similarity,
                                'collection': collection_name,
                                'metadata': results['metadatas'][0][i]
                            })
            except Exception:
                # Skip collections that fail to query
                continue

        # Sort by similarity descending (best first)
        all_results.sort(key=lambda x: x['similarity'], reverse=True)

        # Return top_k results
        return all_results[:top_k]

    def list_memories(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List memories from a collection (for debugging/inspection).

        Args:
            collection_name: Collection to list from
            limit: Maximum number of memories to return (None = all)
            memory_type: Filter by metadata type (e.g., 'location', 'financial')

        Returns:
            List of dicts with keys: id, content, metadata
        """
        collection = self.get_or_create_collection(collection_name)

        # Get all or limited results
        count = collection.count()
        if count == 0:
            return []

        # Determine fetch limit
        fetch_limit = min(limit, count) if limit else count

        # Fetch memories
        results = collection.get(
            limit=fetch_limit,
            include=['documents', 'metadatas']
        )

        # Build result list
        memories = []
        for i in range(len(results['ids'])):
            memory = {
                'id': results['ids'][i],
                'content': results['documents'][i],
                'metadata': results['metadatas'][i]
            }

            # Filter by type if specified
            if memory_type:
                if memory['metadata'].get('type') == memory_type:
                    memories.append(memory)
            else:
                memories.append(memory)

        return memories

    def recall_with_scope_filter(
        self,
        query: str,
        collection_names: List[str],
        allowed_scopes: List[MemoryScope],
        top_k: int = 5,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across collections filtered by allowed scopes.

        Args:
            query: Search query text
            collection_names: List of collections to search
            allowed_scopes: List of allowed MemoryScope values
            top_k: Maximum results to return
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of dicts with keys: content, similarity, collection, metadata
            Filtered to only include memories with allowed scopes
        """
        # Get all results first
        all_results = self.recall(query, collection_names, top_k, min_similarity)

        # Filter by scope
        return self._filter_by_scope(all_results, allowed_scopes)

    def recall_with_rbac_filter(
        self,
        query: str,
        collection_names: List[str],
        user_phone: str,
        allowed_scopes: List[MemoryScope],
        can_see_all_memories: bool,
        top_k: int = 5,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Semantic search with full RBAC filtering (scope + user phone).

        Args:
            query: Search query text
            collection_names: List of collections to search
            user_phone: Phone number of requesting user
            allowed_scopes: List of allowed MemoryScope values
            can_see_all_memories: If True, skip user_phone filter (GODFATHER/ADMIN)
            top_k: Maximum results to return
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of dicts filtered by both scope and user ownership
        """
        # Get all results first
        all_results = self.recall(query, collection_names, top_k, min_similarity)

        # Filter by scope
        filtered_results = self._filter_by_scope(all_results, allowed_scopes)

        # Filter by user phone (unless can see all)
        if not can_see_all_memories:
            filtered_results = self._filter_by_user_phone(filtered_results, user_phone)

        return filtered_results

    def _filter_by_scope(
        self,
        results: List[Dict[str, Any]],
        allowed_scopes: List[MemoryScope]
    ) -> List[Dict[str, Any]]:
        """
        Filter results to only include allowed scopes.

        Args:
            results: List of memory results
            allowed_scopes: List of allowed MemoryScope values

        Returns:
            Filtered list of results
        """
        allowed_scope_values = [scope.value for scope in allowed_scopes]
        return [
            result for result in results
            if result['metadata'].get('scope', MemoryScope.PRIVATE.value) in allowed_scope_values
        ]

    def _filter_by_user_phone(
        self,
        results: List[Dict[str, Any]],
        user_phone: str,
        skip_filter: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter results to only include memories from specific user.
        PUBLIC memories (without user_phone) are always included.

        Args:
            results: List of memory results
            user_phone: Phone number to filter by
            skip_filter: If True, return all results (for GODFATHER/ADMIN)

        Returns:
            Filtered list of results
        """
        if skip_filter:
            return results

        return [
            result for result in results
            if result['metadata'].get('user_phone') == user_phone
            or result['metadata'].get('scope') == MemoryScope.PUBLIC.value  # PUBLIC visible to all
        ]

    def _create_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector using OpenAI API.

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector, 1536 dimensions)

        Raises:
            Exception: If OpenAI API call fails (ERR-MEMORY-002)
        """
        try:
            response = self.ai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}") from e
