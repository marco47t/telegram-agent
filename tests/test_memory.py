import pytest
from unittest.mock import MagicMock
import memory

def test_retrieve_memories(mocker):
    # Mock chroma DB client and collection
    mock_collection = MagicMock()
    mock_collection.count.return_value = 1

    # Set up mock query return.
    # Distances for cosine space in Chroma: lower = more similar, [0, 2]
    # We want to test filtering by similarity: similarity = 1 - (dist / 2)
    # Threshold is 0.5.
    # If dist = 0.5 -> similarity = 1 - 0.25 = 0.75 >= 0.5 (keep)
    # If dist = 1.0 -> similarity = 1 - 0.5 = 0.5 >= 0.5 (keep)
    # If dist = 1.5 -> similarity = 1 - 0.75 = 0.25 < 0.5 (drop)

    mock_collection.query.return_value = {
        "documents": [["doc1", "doc2", "doc3"]],
        "distances": [[0.5, 1.0, 1.5]]
    }

    # Patch the global _collection in memory.py
    mocker.patch("memory._collection", mock_collection)

    results = memory.retrieve_memories(user_id=1, query="test", k=3, similarity_threshold=0.5)

    # Expect "doc1" and "doc2" but not "doc3"
    assert results == ["doc1", "doc2"]

    mock_collection.query.assert_called_once_with(
        query_texts=["test"],
        n_results=3,
        where={"user_id": 1}
    )

def test_retrieve_memories_empty(mocker):
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    mocker.patch("memory._collection", mock_collection)

    results = memory.retrieve_memories(user_id=1, query="test", k=3)
    assert results == []
    mock_collection.query.assert_not_called()
