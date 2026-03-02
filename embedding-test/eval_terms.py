"""
术语理解评测脚本

数据格式（JSONL），每行一个术语样本，例如：
    {
        "id": "term_1",
        "query": "什么是合同相对性？",
        "relevant_chunk_ids": ["3-民法典/民法典（2021-01-01）.md#114"]
    }

说明：
- query：实际用于向量检索的查询句子（可以是术语名称或问句）
- relevant_chunk_ids：认为"正确答案"的 chunk_id 列表，
  与 chunks JSONL 文件中的 "id" 字段对应（例如 "3-民法典/民法典（2021-01-01）.md#114"）
- 在多法律统一语料下（例如 LawBench 涉及多部法律），评测时会先按法律文件前缀过滤，
  仅在对应法律内部判断是否命中正确条文，避免跨法混淆（如不同法律中的“第一百四十条”）。

用法示例：
    python -m embedding-test.eval_terms \\
        --model-npz embedding-test/embeddings/law_book_text-embedding-v3.npz \\
        --dataset embedding-test/eval/terms.jsonl \\
        --top-k 5
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

from .config import PROJECT_ROOT, EVAL_DIR
from .eval_utils import (
    load_embeddings,
    load_chunks_with_ids,
    normalize_embeddings,
    cosine_similarities,
)


def create_embedder_from_model_name(model_name: str):
    """
    根据模型名称自动识别模型类型并创建对应的 embedder 实例。
    
    业务逻辑：
    - 评测时需要确保查询向量化使用的模型与文档向量化使用的模型一致
    - 从 .npz 文件中读取的 model_name 可能包含完整模型标识
    - 目前仅支持通义千问 DashScope 系列 embedding 模型

    技术实现：
    - DashScope 模型：包含 "text-embedding-v" 或 "qwen3-embedding" 关键字
    
    Args:
        model_name: 模型名称，例如：
            - "text-embedding-v3" (DashScope)
            - "qwen3-embedding-8b" (DashScope)
            - "BAAI/bge-large-zh-v1.5" (BGE)
            - "shibing624/text2vec-base-chinese" (Text2Vec)
    
    Returns:
        BaseEmbedder 实例
    
    Raises:
        ValueError: 如果无法识别模型类型
    """
    model_name_lower = model_name.lower()

    # 仅支持 DashScope 模型（包括 text-embedding-v* 和 qwen3-embedding*）
    if "text-embedding-v" in model_name_lower or "qwen3-embedding" in model_name_lower:
        # 使用 embedding-test 模块中的 DashScopeEmbedder（支持 HTTP API 和 SDK）
        from .embedders import DashScopeEmbedder

        return DashScopeEmbedder(model=model_name)

    raise ValueError(
        f"当前评测脚本仅支持 DashScope embedding 模型，无法识别模型类型: {model_name}。"
        f"支持的模型前缀：text-embedding-v*, qwen3-embedding*"
    )


@dataclass
class TermSample:
    id: str
    query: str
    relevant_chunk_ids: List[str]


def load_term_dataset(path: Path) -> List[TermSample]:
    samples: List[TermSample] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            samples.append(
                TermSample(
                    id=obj["id"],
                    query=obj["query"],
                    relevant_chunk_ids=obj.get("relevant_chunk_ids", []),
                )
            )
    return samples


def evaluate_terms(
    model_npz: Path,
    dataset_path: Path,
    top_k: int = 5,
    output_path: Path | None = None,
) -> dict:
    """
    术语理解评测主函数。
    
    业务逻辑：
    - 评测 embedding 模型在术语理解任务上的表现，使用 Recall@k 和 MRR 指标
    - 术语理解是检索任务的特例，查询通常是术语定义或概念解释
    - 确保查询向量化使用的模型与文档向量化使用的模型一致（通过模型识别自动匹配）
    - 通过 relevant_chunk_ids 标注判断检索结果是否正确
    
    技术实现：
    - 加载预计算的文档向量（.npz 格式）和术语数据集（JSONL 格式）
    - 对术语查询进行向量化，计算与所有文档的余弦相似度
    - 按相似度排序，找到第一个命中 relevant_chunk_ids 的排名
    - 计算 Recall@k（前 k 个结果中是否包含正确答案）和 MRR（平均倒数排名）
    
    评测指标说明：
    - Recall@k: 前 k 个检索结果中包含正确答案的术语比例（默认 k=5，术语理解通常需要更精确）
    - MRR (Mean Reciprocal Rank): 所有术语的倒数排名平均值，反映首次命中位置
    
    Args:
        model_npz: 预计算的文档向量文件路径（.npz 格式）
        dataset_path: 术语评测数据集路径（JSONL 格式）
        top_k: 计算 Recall@k 中的 k 值（默认 5，术语理解通常需要更精确的检索）
    """
    # 1. 加载语料 embeddings 与 metadata
    embeddings, meta_arr, model_name = load_embeddings(model_npz)
    print(f"📥 已加载向量文件: {model_npz} (模型: {model_name})")
    print(f"   文档向量数: {embeddings.shape[0]}, 维度: {embeddings.shape[1]}")

    # 归一化文档向量
    doc_emb = normalize_embeddings(embeddings)

    # 2. 加载 chunks 对应的 metadata（用于 chunk_id）
    _, _, chunk_metadatas = load_chunks_with_ids()
    if len(chunk_metadatas) != embeddings.shape[0]:
        print("⚠️ 警告: chunks 数量与向量数量不一致，评测结果可能不准确")

    # 3. 加载术语数据集
    samples = load_term_dataset(dataset_path)
    print(f"📚 术语样本数: {len(samples)}")

    # 4. 根据模型名称自动识别并创建对应的 embedder
    # 业务逻辑：确保查询向量化使用的模型与文档向量化使用的模型一致
    # 技术实现：通过 model_name 特征自动推断模型类型并创建对应实例
    print(f"🔍 识别模型类型: {model_name}")
    embedder = create_embedder_from_model_name(model_name)
    print(f"✅ 已创建 embedder: {type(embedder).__name__}")

    # 5. 预计算每个文档所属的「法律文件前缀」（基于 chunk_id 中的 # 之前部分）
    # 说明：
    # - chunk_id 一般形如 "<相对路径>.md#<chunk_index>"
    # - 在 LawBench 这类多法律统一语料中，相对路径即可视为「法律文件」标识
    doc_law_prefixes: list[str | None] = []
    for meta in meta_arr:
        chunk_id = meta.get("id")
        if isinstance(chunk_id, str) and "#" in chunk_id:
            law_prefix = chunk_id.split("#", 1)[0]
        else:
            law_prefix = None
        doc_law_prefixes.append(law_prefix)

    # 6. 逐个样本评测
    hit_count_topk = 0
    mrr_sum = 0.0
    sample_results = []

    for idx, sample in enumerate(samples, 1):
        print(f"\n[{idx}/{len(samples)}] 术语: {sample.id} - {sample.query}")
        if not sample.relevant_chunk_ids:
            print("  ⚠️ 无标注的 relevant_chunk_ids，跳过")
            sample_results.append(
                {
                    "id": sample.id,
                    "query": sample.query,
                    "hit_rank": None,
                    "hit": False,
                }
            )
            continue

        # 6.1 计算该术语对应的「目标法律文件前缀」集合
        # 说明：
        # - LawBench / 多法律场景下，relevant_chunk_ids 已被转换为真实 chunk_id
        #   形如 "某路径/某法（日期）.md#123"，我们只在这些法律文件内部评测命中情况
        # - 旧数据（仍使用 "民法典.md#40" 或 "第七十条" 等形式）将自动退化为「不按法律过滤」
        law_prefixes: set[str] = set()
        for rel_id in sample.relevant_chunk_ids:
            if isinstance(rel_id, str) and "#" in rel_id:
                law_prefixes.add(rel_id.split("#", 1)[0])
        # 如果无法解析出任何法律前缀（老格式或仅条款编号），则不做法律过滤
        enable_law_filter = len(law_prefixes) > 0

        # 向量化 query
        q_vec = embedder.embed_query(sample.query)
        q_vec_arr = normalize_embeddings(
            embeddings=np.array([q_vec], dtype="float32")
        )[0]

        # 计算与所有文档的相似度
        sims = cosine_similarities(q_vec_arr, doc_emb)
        # 按相似度从高到低排序
        ranked_indices = sims.argsort()[::-1]

        # 找到第一个「同一法律文件且命中 relevant_chunk_ids」的排名
        hit_rank = None
        for rank, doc_idx in enumerate(ranked_indices, 1):
            meta = meta_arr[doc_idx]
            chunk_id = meta.get("id")  # 从 metadata 中获取 chunk_id
            if not isinstance(chunk_id, str):
                continue

            # 先按法律文件前缀过滤（多法律统一语料场景）
            if enable_law_filter:
                doc_law = doc_law_prefixes[doc_idx]
                if doc_law not in law_prefixes:
                    # 不属于本术语对应的法律，直接跳过
                    continue

            # 再判断是否命中「该法律内部」的标注条文
            if chunk_id in sample.relevant_chunk_ids:
                hit_rank = rank
                break

        if hit_rank is not None:
            print(f"  ✅ 命中，首次命中排名: {hit_rank}")
            if hit_rank <= top_k:
                hit_count_topk += 1
            mrr_sum += 1.0 / hit_rank
            sample_results.append(
                {
                    "id": sample.id,
                    "query": sample.query,
                    "hit_rank": hit_rank,
                    "hit": True,
                }
            )
        else:
            print("  ❌ 未在语料中命中标注的 chunk_id（或命中在其他法律中）")
            sample_results.append(
                {
                    "id": sample.id,
                    "query": sample.query,
                    "hit_rank": None,
                    "hit": False,
                }
            )

    # 6. 汇总指标
    n = len(samples)
    if n == 0:
        print("\n❌ 无有效术语样本，无法计算指标")
        return

    recall_at_k = hit_count_topk / n
    mrr = mrr_sum / n

    # 构建评测结果
    results = {
        "model": model_name,
        "dataset": str(dataset_path),
        "top_k": top_k,
        "sample_count": n,
        "recall_at_k": recall_at_k,
        "mrr": mrr,
        "hit_count_topk": hit_count_topk,
        "samples": sample_results,
    }

    print("\n" + "=" * 60)
    print("📊 术语理解评测结果")
    print("=" * 60)
    print(f"模型: {model_name}")
    print(f"样本数: {n}")
    print(f"Recall@{top_k}: {recall_at_k:.4f}")
    print(f"MRR: {mrr:.4f}")
    print("=" * 60)

    # 保存结果到文件
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 评测结果已保存到: {output_path}")
    else:
        # 默认保存到 embeddings 目录，文件名包含样本量标注
        default_output = model_npz.parent / f"eval_terms_{model_name.replace('/', '_')}_n{n}.json"
        default_output.parent.mkdir(parents=True, exist_ok=True)
        with default_output.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 评测结果已保存到: {default_output}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="术语理解评测脚本")
    parser.add_argument(
        "--model-npz",
        type=str,
        required=True,
        help="embedding-test/embed_model.py 生成的 .npz 向量文件路径",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(EVAL_DIR / "terms.jsonl"),
        help="术语评测数据集 JSONL 路径（默认 embedding-test/eval/terms.jsonl）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="计算 Recall@k 中的 k（默认 5）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="评测结果保存路径（JSON格式，默认保存到 embeddings 目录）",
    )

    args = parser.parse_args()
    model_npz = Path(args.model_npz).resolve()
    dataset_path = Path(args.dataset).resolve()

    if not model_npz.exists():
        print(f"❌ 模型向量文件不存在: {model_npz}")
        return
    if not dataset_path.exists():
        print(f"❌ 术语数据集不存在: {dataset_path}")
        return

    output_path = Path(args.output).resolve() if args.output else None

    evaluate_terms(
        model_npz=model_npz,
        dataset_path=dataset_path,
        top_k=args.top_k,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()


