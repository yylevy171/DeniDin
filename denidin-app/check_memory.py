#!/usr/bin/env python3
"""Quick script to check if memory was stored in ChromaDB."""

import chromadb
from chromadb.config import Settings

# Initialize ChromaDB client
client = chromadb.PersistentClient(
    path="data/memory",
    settings=Settings(anonymized_telemetry=False)
)

# List all collections
collections = client.list_collections()
print(f"Found {len(collections)} collections:")
for coll in collections:
    print(f"  - {coll.name}")
    count = coll.count()
    print(f"    Items: {count}")
    
    if count > 0:
        # Show sample items
        results = coll.get(limit=5, include=['documents', 'metadatas'])
        print(f"    Sample items:")
        for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
            print(f"      {i+1}. {doc[:100]}...")
            print(f"         metadata: {meta}")
