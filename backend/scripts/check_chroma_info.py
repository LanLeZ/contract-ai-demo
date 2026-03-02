# 保存为 check_chroma_info.py 并在 backend 目录下运行：python check_chroma_info.py
from app.services.vector_store import VectorStore

vs = VectorStore()  # 会自动连到当前的 chroma_db
info = vs.get_collection_info()
print("集合名称:", info["name"])
print("文档数量:", info["count"])
print("集合元数据:", info["metadata"])