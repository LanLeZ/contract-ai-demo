"""
HanLP 依存句法 + 长难句复杂度测试（直接从 Chroma 向量库抽样文档）

说明：
- 只为了拿“向量库中的合同片段文本”做 HanLP 测试，并不需要 embedding
- 直接 collection.get() 抽样即可，不依赖 EMBEDDING_API_KEY / DASHSCOPE_API_KEY

输出：
- problem_test/hanlp_test/results/hanlp_dep_complexity_chroma_*.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]

from complexity_utils import split_sentences, score_sentence_complexity, ComplexityConfig
from hanlp_dep import lazy_load_hanlp_dep, parse_dep


def _fetch_docs_from_chroma(
    *,
    collection_name: str,
    persist_dir: str | None,
    source_type: str | None,
    contract_id: int | None,
    limit: int,
) -> List[Dict[str, Any]]:
    where = None
    if source_type and contract_id is not None:
        where = {"$and": [{"source_type": source_type}, {"contract_id": contract_id}]}
    elif source_type:
        where = {"source_type": source_type}
    elif contract_id is not None:
        where = {"contract_id": contract_id}

    try:
        import chromadb  # type: ignore
    except ImportError as e:
        raise ImportError("缺少依赖 chromadb，请先 pip install chromadb==0.4.22") from e

    client = chromadb.PersistentClient(path=persist_dir or "./chroma_db")
    collection = client.get_collection(name=collection_name)
    got = collection.get(where=where, include=["documents", "metadatas"], limit=int(limit))

    docs = got.get("documents") or []
    metas = got.get("metadatas") or []

    out: List[Dict[str, Any]] = []
    for i, content in enumerate(docs):
        if not content or not str(content).strip():
            continue
        meta = metas[i] if i < len(metas) else {}
        out.append({"content": str(content), "metadata": meta or {}})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", type=str, default="legal_contracts_v2", help="Chroma collection name")
    ap.add_argument(
        "--persist-dir",
        type=str,
        default=os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"),
        help="Chroma persist dir（默认读 CHROMA_PERSIST_DIR 或 ./chroma_db）",
    )
    ap.add_argument("--source-type", type=str, default="contract", help="过滤 source_type（默认 contract）")
    ap.add_argument("--contract-id", type=int, default=-1, help="过滤 contract_id（>=0 才生效）")
    ap.add_argument("--limit", type=int, default=50, help="从库里取多少条 document")
    ap.add_argument("--max-sents", type=int, default=200, help="最多处理多少个句子（避免太慢）")
    ap.add_argument("--threshold", type=float, default=60.0, help="复杂度阈值")
    ap.add_argument(
        "--hanlp-dep-model",
        type=str,
        default="",
        help="可选：指定 HanLP dep 模型名（留空用默认 CTB7）",
    )
    args = ap.parse_args()

    contract_id = args.contract_id if args.contract_id >= 0 else None
    docs = _fetch_docs_from_chroma(
        collection_name=args.collection,
        persist_dir=args.persist_dir,
        source_type=args.source_type or None,
        contract_id=contract_id,
        limit=args.limit,
    )

    if not docs:
        print("没有从 Chroma 取到任何 documents。请检查：persist-dir / collection / 过滤条件。")
        return

    dep = lazy_load_hanlp_dep(args.hanlp_dep_model or None)
    cfg = ComplexityConfig(threshold=float(args.threshold))

    results: List[Dict[str, Any]] = []
    sent_count = 0
    for doc_idx, d in enumerate(docs):
        text = (d.get("content") or "").strip()
        if not text:
            continue
        sents = split_sentences(text)
        for sent_idx, sent in enumerate(sents):
            if sent_count >= args.max_sents:
                break
            parsed = parse_dep(dep, sent)
            scored = score_sentence_complexity(
                sent, parsed["tokens"], parsed["heads"], parsed["deprels"], cfg=cfg
            )
            results.append(
                {
                    "source": "chroma",
                    "collection": args.collection,
                    "persist_dir": args.persist_dir,
                    "doc_index": doc_idx,
                    "sentence_index": sent_idx,
                    "sentence": sent,
                    "tokens": parsed["tokens"],
                    "heads": parsed["heads"],
                    "deprels": parsed["deprels"],
                    **scored,
                    "metadata": d.get("metadata") or {},
                }
            )
            sent_count += 1
        if sent_count >= args.max_sents:
            break

    out_dir = REPO_ROOT / "problem_test" / "hanlp_test" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.collection}_{args.source_type or 'all'}"
    if contract_id is not None:
        tag += f"_contract{contract_id}"
    out_path = out_dir / f"hanlp_dep_complexity_chroma_{tag}.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    top = sorted(results, key=lambda x: float(x.get("score", 0.0)), reverse=True)[:10]
    print(f"输出：{out_path}")
    print(f"总句子数：{len(results)}  阈值：{cfg.threshold}")
    print("\n===== Top 10 (score desc) =====")
    for i, r in enumerate(top, start=1):
        print("-" * 80)
        print(f"#{i} score={r['score']:.2f} is_complex={r['is_complex']} reasons={r.get('reasons')}")
        print(r["sentence"])


if __name__ == "__main__":
    main()


