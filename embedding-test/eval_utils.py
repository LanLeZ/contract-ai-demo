"""
评测工具函数：
- 加载 chunks 与 embeddings
- 计算余弦相似度
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import json

import numpy as np

from .config import CHUNKS_PATH


def load_chunks_with_ids(
    chunks_path: Path | None = None,
) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    """
    从 JSONL 中加载 chunk id、文本和元数据。

    返回:
        ids: List[str]
        contents: List[str]
        metadatas: List[dict]
    """
    if chunks_path is None:
        chunks_path = CHUNKS_PATH

    ids: List[str] = []
    contents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    with Path(chunks_path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            ids.append(obj.get("id"))
            contents.append(obj["content"])
            metadatas.append(obj.get("metadata", {}))

    return ids, contents, metadatas


def load_embeddings(npz_path: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    """
    从 .npz 文件中加载 embeddings 与 metadatas。

    返回:
        embeddings: np.ndarray [num_chunks, dim]
        metadatas: np.ndarray[object]  # 每个元素为 {"id": ..., "metadata": {...}}
        model_name: str
    """
    data = np.load(npz_path, allow_pickle=True)
    embeddings = data["embeddings"]
    metadatas = data["metadatas"]
    model_name = str(data["model"])
    return embeddings, metadatas, model_name


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """对向量进行 L2 归一化，用于计算余弦相似度"""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return embeddings / norms


def cosine_similarities(
    query_vec: np.ndarray,
    docs_emb: np.ndarray,
) -> np.ndarray:
    """
    计算单个查询向量与所有文档向量的余弦相似度。

    要求:
        - query_vec: shape [dim]
        - docs_emb: shape [num_docs, dim]，已归一化
    """
    q = query_vec / (np.linalg.norm(query_vec) + 1e-12)
    return docs_emb @ q

































