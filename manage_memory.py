# 记忆管理工具：查看、添加、删除 chromadb 中的记忆条目
from datetime import date
from memory.vector_store import _get_collection

def list_all():
    collection = _get_collection()
    results = collection.get(include=["documents", "metadatas"])
    total = len(results["ids"])
    print(f"共 {total} 条记忆\n")
    for i, (id_, doc, meta) in enumerate(
        zip(results["ids"], results["documents"], results["metadatas"]), 1
    ):
        print(f"[{i}] id={id_[:8]}...  日期：{meta.get('date', '未知')}")
        print(f"     {doc}\n")
    return results["ids"]

def delete_by_index(index: int):
    collection = _get_collection()
    results = collection.get()
    ids = results["ids"]
    if index < 1 or index > len(ids):
        print(f"序号无效，请输入 1 ~ {len(ids)}")
        return
    target_id = ids[index - 1]
    collection.delete(ids=[target_id])
    print(f"已删除第 {index} 条（id={target_id[:8]}...）")

def add_manually(text: str):
    from memory.vector_store import add_memory
    today = date.today().isoformat()
    add_memory(text, today)
    print(f"已添加：{text}")

# 直接在这里操作，改完运行即可
if __name__ == "__main__":
    # 查看所有
    list_all()

    # 删除第 2 条，取消注释使用：
    # delete_by_index(2)

    # 手动添加一条，取消注释使用：
    # add_manually("这是一条手动添加的记忆")