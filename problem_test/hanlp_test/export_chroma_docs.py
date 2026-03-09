"""
从 Chroma collection 抽样导出 documents → chunks.json（供 HanLP 脚本离线分析）

用途：
- 避免在同一个环境里同时安装 HanLP[full](TF) 与 chromadb/后端依赖导致版本冲突
- 推荐：在你的后端环境（已安装 chromadb）里先运行本脚本导出，再用 HanLP 环境跑 run_from_docx_or_chunks.py --chunks-json

输出格式与 split_results 的 chunks.json 兼容：[{content, metadata}, ...]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]


def _export(
    *,
    collection_name: str,
    persist_dir: str,
    source_type: str | None,
    contract_id: int | None,
    limit: int,
) -> List[Dict[str, Any]]:
    import chromadb  # type: ignore

    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_collection(name=collection_name)

    where = None
    if source_type and contract_id is not None:
        where = {"$and": [{"source_type": source_type}, {"contract_id": contract_id}]}
    elif source_type:
        where = {"source_type": source_type}
    elif contract_id is not None:
        where = {"contract_id": contract_id}

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
        default=os.getenv("CHROMA_PERSIST_DIR", str(REPO_ROOT / "backend" / "chroma_db")),
        help="Chroma persist dir（默认 CHROMA_PERSIST_DIR，否则 backend/chroma_db）",
    )
    ap.add_argument("--source-type", type=str, default="contract", help="过滤 source_type（默认 contract）")
    ap.add_argument("--contract-id", type=int, default=-1, help="过滤 contract_id（>=0 才生效）")
    ap.add_argument("--limit", type=int, default=50, help="导出多少条 document")
    ap.add_argument(
        "--out",
        type=str,
        default=str(REPO_ROOT / "problem_test" / "hanlp_test" / "results" / "chroma_export_chunks.json"),
        help="输出 chunks.json 路径",
    )
    args = ap.parse_args()

    contract_id = args.contract_id if args.contract_id >= 0 else None
    items = _export(
        collection_name=args.collection,
        persist_dir=args.persist_dir,
        source_type=args.source_type or None,
        contract_id=contract_id,
        limit=args.limit,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"导出完成：{out_path}  条数={len(items)}")


if __name__ == "__main__":
    main()


