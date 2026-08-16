"""
Semantic memory: local embeddings (no API calls, no cost, runs fine on CPU)
+ ChromaDB for storage/retrieval. Postgres (see db.py) stays the source of
truth; this module keeps a mirrored, embedded copy for similarity search.
"""
import os
import uuid
import chromadb
from chromadb.utils import embedding_functions

_client = None
_collection = None

_embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"  # ~90MB, CPU-only, milliseconds per call
)


def init_memory():
    global _client, _collection
    _client = chromadb.PersistentClient(path=os.environ.get("CHROMA_PATH", "./chroma_data"))
    _collection = _client.get_or_create_collection(
        name="user_memories", embedding_function=_embedder
    )


def store_memory(user_id: int, content: str, category: str) -> str:
    """Embeds and stores one distilled fact. Returns the vector id (also save this in Postgres)."""
    vector_id = str(uuid.uuid4())
    _collection.add(
        ids=[vector_id],
        documents=[content],
        metadatas=[{"user_id": user_id, "category": category}],
    )
    return vector_id


def retrieve_memories(user_id: int, query: str, k: int = 5, similarity_threshold: float = 0.5) -> list[str]:
    """
    Returns relevant memory strings for this user, filtered by similarity.
    Chroma returns *distances* (lower = more similar) for cosine space by
    default in [0, 2]; we convert to a 0-1 similarity score for the threshold.
    """
    if _collection.count() == 0:
        return []

    results = _collection.query(
        query_texts=[query],
        n_results=k,
        where={"user_id": user_id},
    )

    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]

    kept = []
    for doc, dist in zip(docs, distances):
        similarity = 1 - (dist / 2)  # cosine distance -> similarity
        if similarity >= similarity_threshold:
            kept.append(doc)
    return kept
