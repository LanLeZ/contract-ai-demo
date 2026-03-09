"""
HanLP 依存句法 + 长难句复杂度测试（本地合同文本）

数据来源（任选其一）：
- A: 直接读取 docx 并按「条款编号」扁平切分为 chunk（不依赖后端代码）
- B: 读取 problem_test/split_results/*_chunks.json（已切分的 chunk）

输出：
- problem_test/hanlp_test/results/*.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from complexity_utils import split_sentences, score_sentence_complexity, ComplexityConfig
from hanlp_dep import lazy_load_hanlp_dep, parse_dep

import re


REPO_ROOT = Path(__file__).resolve().parents[2]

# 与 backend/app/services/contract_splitter.py 对齐的条款编号模式（扁平切分）
_CLAUSE_MARK_PATTERNS = [
    r"^第[一二三四五六七八九十百千万〇零两]+条",
    r"^[一二三四五六七八九十]+、",
    r"^[（(]\d+[)）]",
    r"^[（(][一二三四五六七八九十]+[)）]",
    r"^\d+([.,，]\d+)*[、.)]?",
    r"^[①②③④⑤⑥⑦⑧⑨]",
    r"^[a-zA-Z][\.\)、)]",
]


def _parse_docx_to_text(docx_path: Path) -> str:
    try:
        from docx import Document  # type: ignore
    except ImportError as e:
        raise ImportError("缺少依赖 python-docx，请先 pip install python-docx") from e

    doc = Document(str(docx_path))
    lines: List[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            lines.append(t)
    return "\n".join(lines).strip()


def _is_page_separator(line: str) -> bool:
    return bool(re.match(r"^\s*---\s*Page\s+\d+\s*---\s*$", line))


def _match_clause_marker(line: str) -> str | None:
    s = (line or "").strip()
    if not s:
        return None
    for p in _CLAUSE_MARK_PATTERNS:
        m = re.match(p, s)
        if m:
            return m.group(0)
    return None


def _split_contract_to_units_flat(
    text: str, *, source_name: str, min_chunk_size: int = 50
) -> List[Dict[str, Any]]:
    """
    扁平条款切分：一条款≈一个 chunk。
    输出结构与 split_results 的 chunks.json 对齐：[{content, metadata}, ...]
    """
    if not text or not text.strip():
        return []

    lines = [ln.rstrip() for ln in text.splitlines()]
    units: List[Dict[str, Any]] = []
    current_marker: str = ""
    current_text: List[str] = []
    clause_index = 0

    def flush():
        nonlocal current_text, current_marker, clause_index
        clause = "\n".join(current_text).strip()
        current_text = []
        if not clause:
            return
        if len(clause) < min_chunk_size:
            return
        units.append(
            {
                "content": clause,
                "metadata": {
                    "source_name": source_name,
                    "source_type": "contract",
                    "chunk_index": len(units),
                    "clause_index": clause_index,
                    "clause_marker": current_marker,
                },
            }
        )

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current_text:
                current_text.append("")  # 保留换行
            continue
        if _is_page_separator(raw_line):
            continue

        marker = _match_clause_marker(line)
        if marker:
            if current_text:
                flush()
            clause_index += 1
            current_marker = marker
            rest = line[len(marker) :].strip()
            current_text = [rest] if rest else []
        else:
            # 续行：拼到当前条款；若开头无编号，视为前言单独一条
            if clause_index == 0:
                clause_index = 1
                current_marker = ""
                current_text = [raw_line]
            else:
                current_text.append(raw_line)

    if current_text:
        flush()

    return units


def _load_chunks_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("chunks json 结构不正确：期望 list")
    return data


def _iter_text_units_from_docx(docx_path: Path) -> List[Dict[str, Any]]:
    text = _parse_docx_to_text(docx_path)
    return _split_contract_to_units_flat(text, source_name=docx_path.name, min_chunk_size=50)


def _iter_text_units_from_chunks_json(chunks_path: Path) -> List[Dict[str, Any]]:
    chunks = _load_chunks_json(chunks_path)
    normalized: List[Dict[str, Any]] = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        content = (c.get("content") or "").strip()
        if not content:
            continue
        normalized.append({"content": content, "metadata": c.get("metadata") or {}})
    return normalized


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--docx",
        type=str,
        default=str(REPO_ROOT / "backend" / "data" / "contract" / "internship" / "internship1.docx"),
        help="合同 docx 路径（默认用 backend/data/contract/internship/internship1.docx）",
    )
    ap.add_argument(
        "--chunks-json",
        type=str,
        default="",
        help="已切分 chunk 的 json 文件（提供则优先用它）。",
    )
    ap.add_argument("--max-chunks", type=int, default=30, help="最多处理多少个 chunk（避免太慢）")
    ap.add_argument("--max-sents", type=int, default=200, help="最多处理多少个句子（避免太慢）")
    ap.add_argument("--threshold", type=float, default=100.0, help="复杂度阈值（越小越容易判为长难句）")
    ap.add_argument(
        "--skip-clause-marker-regex",
        type=str,
        default=r"^[A-Za-z]\d+(?:[A-Za-z]\d+)*$",
        help="跳过匹配该正则的 metadata.clause_marker（例如 a1、a1a2）。留空则不跳过。",
    )
    ap.add_argument(
        "--hanlp-dep-model",
        type=str,
        default="",
        help="可选：指定 HanLP dep 模型名（留空用默认 CTB7）",
    )
    args = ap.parse_args()
    skip_marker_re = re.compile(args.skip_clause_marker_regex) if args.skip_clause_marker_regex else None

    # 1) 取文本单元（chunk）
    if args.chunks_json:
        units = _iter_text_units_from_chunks_json(Path(args.chunks_json))
        source_tag = Path(args.chunks_json).stem
        source = "chunks_json"
    else:
        units = _iter_text_units_from_docx(Path(args.docx))
        source_tag = Path(args.docx).stem
        source = "docx"

    units = units[: max(args.max_chunks, 1)]

    # 2) 加载 HanLP dep 模型
    dep = lazy_load_hanlp_dep(args.hanlp_dep_model or None)
    cfg = ComplexityConfig(threshold=float(args.threshold))

    # 3) 跑句法+复杂度
    results: List[Dict[str, Any]] = []
    sent_count = 0
    for chunk_idx, u in enumerate(units):
        text = (u.get("content") or "").strip()
        if not text:
            continue
        if skip_marker_re:
            meta = u.get("metadata") or {}
            marker = str(meta.get("clause_marker") or "").strip()
            if marker and skip_marker_re.match(marker):
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
                    "source": source,
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

    # 4) 落地：jsonl
    out_dir = REPO_ROOT / "problem_test" / "hanlp_test" / "results"
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


