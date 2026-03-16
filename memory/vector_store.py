# 向量记忆存储：ChromaDB 封装，支持去重和标签
import uuid
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
CHROMA_DIR = WORKSPACE_DIR / "memory" / "chroma"
COLLECTION_NAME = "memories"
EMBEDDING_FUNCTION = DefaultEmbeddingFunction()

# 相似度阈值：ChromaDB 默认用 L2 距离，越小越相似；低于此值视为重复
DEDUP_DISTANCE_THRESHOLD = 0.3


def _get_collection():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=EMBEDDING_FUNCTION,
    )


def _is_duplicate(collection, text: str) -> bool:
    """检查是否已存在高度相似的记忆"""
    total = collection.count()
    if total == 0:
        return False

    result = collection.query(
        query_texts=[text],
        n_results=1,
    )

    distances = result.get("distances", [[]])
    if distances and distances[0]:
        closest_distance = distances[0][0]
        if closest_distance < DEDUP_DISTANCE_THRESHOLD:
            dup_doc = result["documents"][0][0] if result.get("documents") else "?"
            print(f"[记忆去重] 已存在相似记忆（距离={closest_distance:.3f}），跳过写入")
            print(f"  已有: {dup_doc[:80]}")
            print(f"  新增: {text[:80]}")
            return True
    return False


def add_memory(text: str, date: str, tag: str = "") -> str:
    """写入记忆，自动去重。返回状态信息。"""
    collection = _get_collection()

    if _is_duplicate(collection, text):
        return "跳过：已存在相似记忆"

    metadata = {"date": date}
    if tag:
        metadata["tag"] = tag

    collection.add(
        ids=[str(uuid.uuid4())],
        documents=[text],
        metadatas=[metadata],
    )
    print(f"[记忆写入] {text[:60]}")
    return "已记录"


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


def get_stats() -> dict:
    """返回记忆库统计信息"""
    collection = _get_collection()
    total = collection.count()
    results = collection.get(include=["metadatas"])
    tags = {}
    dates = set()
    for meta in results.get("metadatas", []):
        if meta:
            tag = meta.get("tag", "无标签")
            tags[tag] = tags.get(tag, 0) + 1
            if meta.get("date"):
                dates.add(meta["date"])
    return {
        "total": total,
        "tags": tags,
        "date_range": f"{min(dates)} ~ {max(dates)}" if dates else "无",
    }
