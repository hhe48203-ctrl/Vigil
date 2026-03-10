import uuid
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
CHROMA_DIR = WORKSPACE_DIR / "memory" / "chroma"
COLLECTION_NAME = "memories"
EMBEDDING_FUNCTION = DefaultEmbeddingFunction()


def _get_collection():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=EMBEDDING_FUNCTION,
    )


def add_memory(text: str, date: str) -> None:
    collection = _get_collection()
    collection.add(
        ids=[str(uuid.uuid4())],
        documents=[text],
        metadatas=[{"date": date}],
    )


def search_memory(query: str, n_results: int = 8) -> list[str]:
    if not query.strip():
        return []

    collection = _get_collection()
    total = collection.count()
    if total == 0:
        print("[记忆检索] 向量库为空，跳过检索")
        return []

    result = collection.query(
        query_texts=[query],
        n_results=min(n_results, total),
    )

    documents = result.get("documents", [])
    hits = [doc for doc in documents[0] if doc] if documents else []
    print(f"[记忆检索] query={query[:40]!r}  库中共 {total} 条，命中 {len(hits)} 条")
    for i, doc in enumerate(hits, 1):
        print(f"  [{i}] {doc[:80]}")
    return hits
