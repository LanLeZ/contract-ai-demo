import json
import math
from pathlib import Path
from typing import Dict, Any, List


def compute_metrics_for_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    samples: List[Dict[str, Any]] = data.get("samples", [])
    sample_count = data.get("sample_count", len(samples))
    top_k = data.get("top_k", None)

    ranks_hit: List[int] = []
    ndcg_sum = 0.0

    for s in samples:
        r = s.get("hit_rank")
        if r is None:
            continue
        # 记录 rank 统计
        ranks_hit.append(int(r))
        # NDCG@K：只在前 top_k 内贡献
        if top_k is not None and r <= top_k:
            ndcg_sum += 1.0 / math.log2(r + 1)

    # 由于每个样本只有一个相关条目，IDCG = 1/log2(1+1) = 1
    ndcg_at_k = ndcg_sum / sample_count if sample_count > 0 else 0.0

    metrics: Dict[str, Any] = {
        "model": data.get("model"),
        "dataset": data.get("dataset"),
        "top_k": top_k,
        "sample_count": sample_count,
        "recall_at_k": data.get("recall_at_k"),
        "mrr": data.get("mrr"),
        "hit_count_topk": data.get("hit_count_topk"),
        "ndcg_at_k": ndcg_at_k,
    }

    if ranks_hit:
        ranks_hit_sorted = sorted(ranks_hit)
        hit_count = len(ranks_hit)
        mean_rank = sum(ranks_hit) / hit_count
        median_rank = (
            ranks_hit_sorted[hit_count // 2]
            if hit_count % 2 == 1
            else (ranks_hit_sorted[hit_count // 2 - 1] + ranks_hit_sorted[hit_count // 2]) / 2
        )
        metrics.update(
            {
                "hit_count_any_rank": hit_count,
                "hit_rate_any_rank": hit_count / sample_count if sample_count > 0 else 0.0,
                "mean_hit_rank": mean_rank,
                "median_hit_rank": median_rank,
                "min_hit_rank": ranks_hit_sorted[0],
                "max_hit_rank": ranks_hit_sorted[-1],
            }
        )
    else:
        metrics.update(
            {
                "hit_count_any_rank": 0,
                "hit_rate_any_rank": 0.0,
                "mean_hit_rank": None,
                "median_hit_rank": None,
                "min_hit_rank": None,
                "max_hit_rank": None,
            }
        )

    return metrics


def collect_all_metrics(root: Path) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []

    for chunk_dir in ["chunkSize200_embeddings", "chunkSize800_embeddings"]:
        dir_path = root / chunk_dir
        if not dir_path.is_dir():
            continue

        chunk_size = int("".join(filter(str.isdigit, chunk_dir)))  # 200 / 800

        for eval_file in dir_path.glob("eval_retrieval_*.json"):
            metrics = compute_metrics_for_file(eval_file)
            metrics["chunk_size"] = chunk_size
            metrics["eval_file"] = str(eval_file)
            results.append(metrics)

    # 整体结构：按 (model, chunk_size) 聚合在一个列表中即可
    summary: Dict[str, Any] = {
        "root": str(root),
        "results": results,
    }
    return summary


def main() -> None:
    root = Path(__file__).resolve().parent
    summary = collect_all_metrics(root)

    out_path = root / "eval_retrieval_metrics_summary.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Metrics summary written to: {out_path}")


if __name__ == "__main__":
    main()




