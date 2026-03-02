"""
评估不同配置的检索性能
"""
import json
import sys
from pathlib import Path
import numpy as np

from .config import (
    PROJECT_ROOT, EMBEDDING_DIR, RESULTS_DIR, 
    TEST_CONFIGS, EVAL_TOP_K, QUERIES_PATH
)


def add_backend_to_path():
    backend_path = PROJECT_ROOT / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


def load_embeddings(npz_path: Path):
    """加载向量文件"""
    data = np.load(npz_path, allow_pickle=True)
    embeddings = data["embeddings"]
    ids = data["ids"]
    metadatas = data["metadatas"]
    model_name = str(data.get("model_name", "unknown"))
    chunk_size = int(data.get("chunk_size", 0))
    overlap = int(data.get("overlap", 0))
    return embeddings, ids, metadatas, model_name, chunk_size, overlap


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """归一化向量"""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return embeddings / norms


def cosine_similarities(query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    """计算余弦相似度"""
    return np.dot(doc_vecs, query_vec)


def create_embedder_from_model_name(model_name: str):
    """
    根据模型名称自动识别模型类型并创建对应的 embedder 实例
    """
    # 将 embedding-test 目录添加到 sys.path
    embedding_test_path = PROJECT_ROOT / "embedding-test"
    if str(embedding_test_path) not in sys.path:
        sys.path.insert(0, str(embedding_test_path))
    
    model_name_lower = model_name.lower()
    
    # 识别 DashScope 模型
    if "text-embedding-v" in model_name_lower or "qwen3-embedding" in model_name_lower:
        import embedders
        return embedders.DashScopeEmbedder(model=model_name)
    
    # 识别 BGE 模型
    elif "bge" in model_name_lower:
        import embedders
        return embedders.BGEEmbedder(model_name=model_name)
    
    # 识别 Text2Vec 模型
    elif "text2vec" in model_name_lower:
        import embedders
        return embedders.Text2VecEmbedder(model_name=model_name)
    
    else:
        raise ValueError(
            f"无法识别模型类型: {model_name}。"
            f"支持的模型类型：DashScope (text-embedding-v*, qwen3-embedding*), BGE (bge-*), Text2Vec (text2vec-*)"
        )


def evaluate_config(chunk_size: int, overlap: int):
    """评估指定配置"""
    add_backend_to_path()
    
    # 加载向量
    npz_file = EMBEDDING_DIR / f"chunks_{chunk_size}_{overlap}.npz"
    if not npz_file.exists():
        print(f"❌ 向量文件不存在: {npz_file}")
        return None
    
    embeddings, ids, metadatas, model_name, _, _ = load_embeddings(npz_file)
    doc_emb = normalize_embeddings(embeddings)
    
    # 加载查询数据集
    queries = []
    if not QUERIES_PATH.exists():
        print(f"❌ 查询数据集不存在: {QUERIES_PATH}")
        return None
    
    with QUERIES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            queries.append(json.loads(line.strip()))
    
    print(f"📊 评估配置: chunk_size={chunk_size}, overlap={overlap}")
    print(f"   模型: {model_name}")
    print(f"   文档数: {len(embeddings)}")
    print(f"   查询数: {len(queries)}")
    
    # 创建embedder
    embedder = create_embedder_from_model_name(model_name)
    
    # 评估
    results = {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "model": model_name,
        "total_chunks": len(embeddings),
        "total_queries": len(queries),
        "metrics": {},
        "sample_results": [],
    }
    
    for k in EVAL_TOP_K:
        hit_count = 0
        mrr_sum = 0.0
        
        for query in queries:
            q_vec = embedder.embed_query(query["query"])
            q_vec_norm = normalize_embeddings(np.array([q_vec], dtype="float32"))[0]
            
            sims = cosine_similarities(q_vec_norm, doc_emb)
            ranked_indices = sims.argsort()[::-1]
            
            hit_rank = None
            for rank, idx in enumerate(ranked_indices[:k], 1):
                chunk_id = ids[idx]
                if chunk_id in query.get("relevant_chunk_ids", []):
                    hit_rank = rank
                    break
            
            if hit_rank:
                hit_count += 1
                mrr_sum += 1.0 / hit_rank
        
        recall_at_k = hit_count / len(queries) if queries else 0.0
        mrr = mrr_sum / len(queries) if queries else 0.0
        
        results["metrics"][f"recall@{k}"] = recall_at_k
        results["metrics"][f"mrr@{k}"] = mrr
        
        print(f"   Recall@{k}: {recall_at_k:.4f}, MRR@{k}: {mrr:.4f}")
    
    # 保存结果
    output_file = RESULTS_DIR / f"eval_{chunk_size}_{overlap}.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 评估完成: {output_file}")
    return results


def main():
    print("=" * 60)
    print("评估不同配置的检索性能")
    print("=" * 60)
    
    all_results = []
    for config in TEST_CONFIGS:
        result = evaluate_config(
            chunk_size=config["chunk_size"],
            overlap=config["overlap"]
        )
        if result:
            all_results.append(result)
        print()
    
    # 打印对比
    if all_results:
        print("\n" + "=" * 80)
        print("检索性能对比")
        print("=" * 80)
        print(f"{'配置':<15} {'Recall@3':<12} {'Recall@5':<12} {'Recall@10':<12} {'MRR@5':<12}")
        print("-" * 80)
        for result in all_results:
            config_name = f"{result['chunk_size']}_{result['overlap']}"
            metrics = result["metrics"]
            print(f"{config_name:<15} {metrics['recall@3']:<12.4f} {metrics['recall@5']:<12.4f} "
                  f"{metrics['recall@10']:<12.4f} {metrics['mrr@5']:<12.4f}")


if __name__ == "__main__":
    main()

