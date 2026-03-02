#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 LawBench 查询文件中的 relevant_chunk_ids（目前为“第X条”等条文编号）
映射为实际的 chunk_id（例如 "1-宪法/宪法.md#12"），并输出到新的 JSONL 文件。

设计说明
--------
- 输入：
  - queries_file: 默认 embedding-test/eval/queries_lawbench_3-2_matched.jsonl
    - 字段：
      - id: 查询 ID
      - query: 查询文本
      - source_name: 法律名称（如 "宪法"、"公司法"）
      - relevant_chunk_ids: ["第五十六条", ...]  —— 当前是“条文编号”
  - chunks_file: 默认 config.CHUNKS_PATH（embedding-test/data/lawbench_laws_chunks.jsonl）
    - 字段：
      - id: chunk_id，例如 "1-宪法/宪法.md#12"
      - content: 文本内容
      - metadata: 至少包含 "source_name"（如 "1-宪法/宪法.md"）

- 映射逻辑：
  1) 先从 queries 文件收集所有需要用到的 (标准化法律名, 条文编号) 对。
     - 对法律名使用 filter_queries_by_law_book.normalize_law_name 标准化。
  2) 扫描 chunks_file：
     - 根据 metadata["source_name"]（相对路径）与 Law-Book-lawbench 目录推断出原始 .md 文件路径，
       再用 extract_law_name_from_file 得到“标准化法律名”。
     - 对于该法律下每一个“需要用到的条文编号”，如果该条文编号字符串出现在 chunk.content 中，
       则认为该 chunk 覆盖该条文，记录 (law_name_norm, article_label) -> chunk_id 的映射。
  3) 再次遍历 queries 文件：
     - 对每条 query，根据 (标准化法律名, 条文编号) 查找对应的 chunk_id 集合，
       合并为一个去重后的列表，写回到 relevant_chunk_ids 中。
     - 为方便调试，将原始的条文编号列表保存到 original_relevant_articles 字段。

- 输出：
  - 默认 embedding-test/eval/queries_lawbench_3-2_with_chunk_ids.jsonl
  - 每行结构示例：
    {
      "id": "q_189",
      "query": "...",
      "source_name": "民法典",
      "relevant_chunk_ids": ["3-民法典/民法典.md#123", ...],
      "original_relevant_articles": ["第一千零四十一条"]
    }

用法（在项目根目录 e:\\cp 下）：

    python -m embedding-test.map_relevant_chunks ^
      --queries-file embedding-test/eval/queries_lawbench_3-2_matched.jsonl ^
      --output-file embedding-test/eval/queries_lawbench_3-2_with_chunk_ids.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Set, Tuple

from .config import PROJECT_ROOT, CHUNKS_PATH
from .filter_queries_by_law_book import (
    normalize_law_name,
    extract_law_name_from_file,
)


def load_article_targets(
    queries_file: Path,
) -> Dict[str, Set[str]]:
    """
    从查询文件中收集每个“标准化法律名”下需要映射的所有条文编号。

    返回：
        { law_name_norm: { "第五十六条", "第一百四十条", ... } }
    """
    targets: Dict[str, Set[str]] = defaultdict(set)

    with queries_file.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"⚠️ 第 {line_num} 行 JSON 解析错误，已跳过: {e}")
                continue

            raw_law_name = obj.get("source_name", "")
            if not isinstance(raw_law_name, str) or not raw_law_name.strip():
                continue

            law_name_norm = normalize_law_name(raw_law_name.strip())
            articles = obj.get("relevant_chunk_ids", [])
            if not isinstance(articles, list):
                continue

            for art in articles:
                if isinstance(art, str) and art.strip():
                    targets[law_name_norm].add(art.strip())

    return targets


def build_article_to_chunk_map(
    chunks_file: Path,
    law_book_root: Path,
    article_targets: Mapping[str, Set[str]],
) -> Dict[Tuple[str, str], Set[str]]:
    """
    扫描 chunks 文件，构建 (标准化法律名, 条文编号) -> {chunk_id, ...} 的映射。
    """
    mapping: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    with chunks_file.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"⚠️ chunks 第 {line_num} 行 JSON 解析错误，已跳过: {e}")
                continue

            chunk_id = obj.get("id")
            content = obj.get("content", "")
            metadata = obj.get("metadata", {})

            if not isinstance(chunk_id, str) or not isinstance(content, str):
                continue
            if not isinstance(metadata, dict):
                continue

            source_name_rel = metadata.get("source_name")
            if not isinstance(source_name_rel, str) or not source_name_rel.strip():
                continue

            # 根据 chunks 中保存的相对路径恢复出对应的 .md 文件路径
            md_path = law_book_root / source_name_rel
            law_name_norm = extract_law_name_from_file(md_path)

            if law_name_norm not in article_targets:
                continue

            # 仅对该法律下“需要用到的”条文编号做匹配，避免无谓搜索
            for article_label in article_targets[law_name_norm]:
                if article_label in content:
                    mapping[(law_name_norm, article_label)].add(chunk_id)

    return mapping


def iter_queries_with_resolved_chunks(
    queries_file: Path,
    article_to_chunk: Mapping[Tuple[str, str], Set[str]],
) -> Iterable[dict]:
    """
    迭代查询文件，将 relevant_chunk_ids 从“条文编号”替换为实际 chunk_id。

    - 保留一份 original_relevant_articles 记录原有条文编号列表。
    """
    missing_pairs: Dict[Tuple[str, str], int] = defaultdict(int)

    with queries_file.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"⚠️ 第 {line_num} 行 JSON 解析错误，已原样跳过: {e}")
                continue

            raw_law_name = obj.get("source_name", "")
            if not isinstance(raw_law_name, str) or not raw_law_name.strip():
                yield obj
                continue

            law_name_norm = normalize_law_name(raw_law_name.strip())
            articles = obj.get("relevant_chunk_ids", [])
            if not isinstance(articles, list) or not articles:
                # 没有标注条文时，保持原样
                yield obj
                continue

            resolved_ids: Set[str] = set()
            for art in articles:
                if not isinstance(art, str) or not art.strip():
                    continue
                key = (law_name_norm, art.strip())
                chunk_ids = article_to_chunk.get(key)
                if not chunk_ids:
                    missing_pairs[key] += 1
                    continue
                resolved_ids.update(chunk_ids)

            # 记录原始条文编号
            obj["original_relevant_articles"] = articles
            # 将 relevant_chunk_ids 替换为真正的 chunk_id 列表
            obj["relevant_chunk_ids"] = sorted(resolved_ids)

            yield obj

    if missing_pairs:
        print("\n⚠️ 以下 (法律, 条文编号) 未能在 chunks 中找到匹配的 chunk_id（出现次数）：")
        for (law, art), cnt in sorted(missing_pairs.items(), key=lambda x: (-x[1], x[0])):
            print(f"  - {law} / {art}: {cnt}")


def write_jsonl(records: Iterable[dict], output_path: Path) -> int:
    """
    将记录写入 JSONL 文件，返回写入条数。

    - 不输出 source_name、original_relevant_articles 字段
    """
    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        for obj in records:
            to_save = {
                k: v
                for k, v in obj.items()
                if k not in ("source_name", "original_relevant_articles")
            }
            f.write(json.dumps(to_save, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将 LawBench 查询中的条文编号映射为实际的 chunk_id"
    )
    parser.add_argument(
        "--queries-file",
        type=str,
        default=str(PROJECT_ROOT / "embedding-test" / "eval" / "queries_lawbench_3-2_matched.jsonl"),
        help="输入查询 JSONL 文件（默认 embedding-test/eval/queries_lawbench_3-2_matched.jsonl）",
    )
    parser.add_argument(
        "--chunks-file",
        type=str,
        default=str(CHUNKS_PATH),
        help="chunks JSONL 文件路径（默认使用 config.CHUNKS_PATH）",
    )
    parser.add_argument(
        "--law-book-dir",
        type=str,
        default=str(PROJECT_ROOT / "Law-Book-lawbench"),
        help="Law-Book-lawbench 根目录（用于还原 chunks 中的 source_name）",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=str(PROJECT_ROOT / "embedding-test" / "eval" / "queries_lawbench_3-2_with_chunk_ids.jsonl"),
        help="输出 JSONL 文件路径",
    )

    args = parser.parse_args()

    queries_file = Path(args.queries_file).resolve()
    chunks_file = Path(args.chunks_file).resolve()
    law_book_root = Path(args.law_book_dir).resolve()
    output_file = Path(args.output_file).resolve()

    print("=" * 80)
    print("LawBench relevant_chunk_ids 解析脚本")
    print("=" * 80)
    print(f"查询文件: {queries_file}")
    print(f"chunks 文件: {chunks_file}")
    print(f"Law-Book-lawbench 根目录: {law_book_root}")
    print(f"输出文件: {output_file}")
    print("=" * 80)

    if not queries_file.exists():
        print(f"❌ 查询文件不存在: {queries_file}")
        return
    if not chunks_file.exists():
        print(f"❌ chunks 文件不存在: {chunks_file}")
        return
    if not law_book_root.exists():
        print(f"❌ Law-Book-lawbench 目录不存在: {law_book_root}")
        return

    print("\n📌 第一步：收集需要解析的 (法律, 条文编号)...")
    article_targets = load_article_targets(queries_file)
    print(f"✅ 共 {len(article_targets)} 个法律有条文标注")
    total_articles = sum(len(v) for v in article_targets.values())
    print(f"✅ 去重后的条文编号总数: {total_articles}")

    print("\n📌 第二步：扫描 chunks 文件，建立条文到 chunk_id 的映射...")
    article_to_chunk = build_article_to_chunk_map(
        chunks_file=chunks_file,
        law_book_root=law_book_root,
        article_targets=article_targets,
    )
    print(f"✅ 映射表中共有 {len(article_to_chunk)} 个 (法律, 条文编号) 键")

    print("\n📌 第三步：为每条查询写入解析后的 chunk_id ...")
    records = iter_queries_with_resolved_chunks(
        queries_file=queries_file,
        article_to_chunk=article_to_chunk,
    )
    count = write_jsonl(records, output_file)
    print(f"\n✅ 完成！共写出 {count} 条查询到 {output_file}")


if __name__ == "__main__":
    main()



