"""
HanLP 依存句法 + 长难句复杂度测试（本地合同文本）

数据来源（任选其一）：
- A: 直接读取 data/contract/.../*.docx（复用 DocumentParser/ContractTextSplitter）
- B: 读取 problem_test/split_results/*_chunks.json（已切分的 chunk）

输出：
- problem_test/hanlp_results/*.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# 把项目根目录和 backend 加到 sys.path（与 problem_test 其他脚本保持一致风格）
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
for p in (REPO_ROOT, BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backend.app.services.document_parser import DocumentParser  # type: ignore
from backend.app.services.contract_splitter import ContractTextSplitter  # type: ignore

from hanlp_complexity_utils import split_sentences, score_sentence_complexity, ComplexityConfig


def _load_chunks_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("chunks json 结构不正确：期望 list")
    return data


def _iter_text_units_from_docx(docx_path: Path) -> List[Dict[str, Any]]:
    parser = DocumentParser()
    text = parser.parse(str(docx_path), file_type="docx")
    splitter = ContractTextSplitter(chunk_size=200, chunk_overlap=60, min_chunk_size=1)
    chunks = splitter.split_with_metadata(
        text=text,
        source_name=docx_path.name,
        user_id=1,
        contract_id=0,
        contract_type=None,
    )
    return chunks


def _iter_text_units_from_chunks_json(chunks_path: Path) -> List[Dict[str, Any]]:
    chunks = _load_chunks_json(chunks_path)
    # 兼容 demo_split_contract.py 的输出格式：[{content, metadata}, ...]
    normalized: List[Dict[str, Any]] = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        content = (c.get("content") or "").strip()
        if not content:
            continue
        normalized.append({"content": content, "metadata": c.get("metadata") or {}})
    return normalized


def _lazy_load_hanlp_dep():
    """
    延迟加载 HanLP 模型，避免 import 即下载。
    """
    import hanlp  # type: ignore

    # 优先用官方预训练的中文依存句法模型（不同 HanLP 版本名字可能不同）
    # 兼容写法：先尝试 hanlp.pretrained.dep.*，不行就 fallback 到字符串模型名。
    model = None
    try:
        model = hanlp.pretrained.dep.CTB7_BIAFFINE_DEP_ZH  # type: ignore[attr-defined]
    except Exception:
        model = "CTB7_BIAFFINE_DEP_ZH"

    dep = hanlp.load(model)
    return dep


def _parse_dep(dep_model, sentence: str) -> Dict[str, Any]:
    """
    统一成：tokens/heads/deprels 三件套
    """
    out = dep_model(sentence)
    # HanLP dep 常见返回：{'tok': [...], 'pos': [...], 'dep': {'head': [...], 'rel': [...]} }
    tokens = out.get("tok") or out.get("tok/fine") or out.get("token") or []
    dep = out.get("dep") or {}
    heads = dep.get("head") or out.get("dep/head") or []
    deprels = dep.get("rel") or out.get("dep/rel") or []

    if not isinstance(tokens, list):
        tokens = list(tokens)
    if not isinstance(heads, list):
        heads = list(heads)
    if not isinstance(deprels, list):
        deprels = list(deprels)

    return {"tokens": tokens, "heads": heads, "deprels": deprels}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--docx",
        type=str,
        default=str(REPO_ROOT / "data" / "contract" / "internship" / "internship1.docx"),
        help="合同 docx 路径（默认用 data/contract/internship/internship1.docx）",
    )
    ap.add_argument(
        "--chunks-json",
        type=str,
        default="",
        help="已切分 chunk 的 json 文件（例如 problem_test/split_results/internship1_chunks.json）。提供则优先用它。",
    )
    ap.add_argument("--max-chunks", type=int, default=30, help="最多处理多少个 chunk（避免太慢）")
    ap.add_argument("--max-sents", type=int, default=200, help="最多处理多少个句子（避免太慢）")
    ap.add_argument("--threshold", type=float, default=60.0, help="复杂度阈值（越小越容易判为长难句）")
    args = ap.parse_args()

    # 1) 取文本单元（chunk）
    if args.chunks_json:
        units = _iter_text_units_from_chunks_json(Path(args.chunks_json))
        source_tag = Path(args.chunks_json).stem
    else:
        units = _iter_text_units_from_docx(Path(args.docx))
        source_tag = Path(args.docx).stem

    units = units[: max(args.max_chunks, 1)]

    # 2) 加载 HanLP dep 模型
    dep = _lazy_load_hanlp_dep()

    cfg = ComplexityConfig(threshold=float(args.threshold))

    # 3) 跑句法+复杂度
    results: List[Dict[str, Any]] = []
    sent_count = 0
    for chunk_idx, u in enumerate(units):
        text = (u.get("content") or "").strip()
        if not text:
            continue

        sents = split_sentences(text)
        for sent_idx, sent in enumerate(sents):
            if sent_count >= args.max_sents:
                break

            parsed = _parse_dep(dep, sent)
            scored = score_sentence_complexity(
                sent,
                parsed["tokens"],
                parsed["heads"],
                parsed["deprels"],
                cfg=cfg,
            )

            results.append(
                {
                    "source": "docx" if not args.chunks_json else "chunks_json",
                    "source_tag": source_tag,
                    "chunk_index": chunk_idx,
                    "sentence_index": sent_idx,
                    "sentence": sent,
                    "tokens": parsed["tokens"],
                    "heads": parsed["heads"],
                    "deprels": parsed["deprels"],
                    **scored,
                    "metadata": u.get("metadata") or {},
                }
            )
            sent_count += 1

        if sent_count >= args.max_sents:
            break

    # 4) 落地：jsonl（每行一个句子结果）
    out_dir = REPO_ROOT / "problem_test" / "hanlp_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"hanlp_dep_complexity_{source_tag}.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 5) 打印 top 10 长难句（按 score 降序）
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


