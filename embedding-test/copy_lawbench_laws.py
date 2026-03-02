#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 LawBench 查询文件中出现的法律名称，从 Law-Book 目录中筛选出对应的法律 .md 文件，
并将它们拷贝到一个单独目录（默认：Law-Book-lawbench），用于后续统一切分和评测。

默认行为：
- 查询来源：embedding-test/eval/queries_lawbench_3-2_matched.jsonl
- 源目录：Law-Book
- 目标目录：Law-Book-lawbench
- 目录结构：保留在 Law-Book 下的相对路径，例如：
    Law-Book/3-民法商法/公司法（2018-10-26）.md
  会被复制为：
    Law-Book-lawbench/3-民法商法/公司法（2018-10-26）.md

匹配逻辑：
- 复用 filter_queries_by_law_book.normalize_law_name 和 match_law_name：
  - 去掉“中华人民共和国”“中国”等前缀
  - 去掉文件名中的日期后缀（如“（2018-10-26）”）
  - 内置若干特殊映射（如“我国的消费者权益保护法” -> “消费者权益保护法”）

用法示例（在项目根目录 e:\\cp 下）：
    python -m embedding-test.copy_lawbench_laws

    # 如需自定义查询文件或输出目录：
    python -m embedding-test.copy_lawbench_laws \
        --queries-file embedding-test/eval/queries_lawbench_3-2_matched.jsonl \
        --output-dir Law-Book-lawbench
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

from .config import PROJECT_ROOT, LAW_BOOK_DIR
from .filter_queries_by_law_book import (
    build_law_book_index,
    match_law_name,
)


def load_unique_law_names(queries_file: Path) -> List[str]:
    """从 LawBench 查询文件中提取去重后的法律名称（source_name 字段）"""
    law_names: Set[str] = set()
    with queries_file.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"⚠️  第 {line_num} 行 JSON 解析错误，已跳过: {e}")
                continue
            source_name = obj.get("source_name")
            if isinstance(source_name, str) and source_name.strip():
                law_names.add(source_name.strip())
    return sorted(law_names)


def collect_law_files_for_queries(
    law_names: List[str],
    law_book_index: Dict[str, List[Path]],
) -> tuple[Dict[str, List[Path]], Dict[str, int]]:
    """
    为每个 source_name 找到对应的 Law-Book 文件列表。

    返回：
    - matched: {source_name: [Path, ...]}
    - unmatched_counts: {source_name: 出现次数}
    """
    matched: Dict[str, List[Path]] = {}
    unmatched_counts: Dict[str, int] = {}

    # 统计每个法律在 queries 中出现次数，仅用于报告
    law_stats = Counter(law_names)

    for law_name in law_names:
        # match_law_name 现在返回 (matched_files, mapped_name)
        matched_files, _mapped_name = match_law_name(law_name, law_book_index)
        if matched_files:
            # 这里只关心要拷贝哪些文件，键仍然使用原始 law_name 便于打印
            matched[law_name] = matched_files
        else:
            unmatched_counts[law_name] = law_stats[law_name]

    return matched, unmatched_counts


def copy_law_files(
    matched: Dict[str, List[Path]],
    output_root: Path,
    law_book_root: Path,
) -> int:
    """
    将匹配到的法律文件从 Law-Book 复制到目标目录。

    - 保留 Law-Book 下的相对路径结构
    - 已存在同名文件将被覆盖（视为刷新 LawBench 子集）
    """
    copied = 0
    for law_name, paths in matched.items():
        print(f"\n📄 法律: {law_name}")
        for src in paths:
            try:
                rel = src.relative_to(law_book_root)
            except ValueError:
                # 理论上不应发生，保险起见
                rel = src.name
            dst = output_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
            print(f"  ✅ {src}  ->  {dst}")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "根据 LawBench 查询文件中涉及的法律名称，从 Law-Book 中筛选并拷贝对应 .md 文件"
        )
    )
    parser.add_argument(
        "--queries-file",
        type=str,
        default=str(
            PROJECT_ROOT
            / "embedding-test"
            / "eval"
            / "queries_lawbench_3-2_matched.jsonl"
        ),
        help=(
            "LawBench 查询文件路径（默认 "
            "embedding-test/eval/queries_lawbench_3-2_matched.jsonl）"
        ),
    )
    parser.add_argument(
        "--law-book-dir",
        type=str,
        default=str(LAW_BOOK_DIR),
        help="Law-Book 根目录（默认使用 config.LAW_BOOK_DIR）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "Law-Book-lawbench"),
        help="拷贝后的目标目录（默认 Law-Book-lawbench）",
    )

    args = parser.parse_args()

    queries_file = Path(args.queries_file).resolve()
    law_book_dir = Path(args.law_book_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    print("=" * 80)
    print("LawBench 涉及法律拷贝脚本")
    print("=" * 80)
    print(f"查询文件: {queries_file}")
    print(f"Law-Book 源目录: {law_book_dir}")
    print(f"输出目录: {output_dir}")
    print("=" * 80)

    if not queries_file.exists():
        print(f"❌ 查询文件不存在: {queries_file}")
        return
    if not law_book_dir.exists():
        print(f"❌ Law-Book 目录不存在: {law_book_dir}")
        return

    # 1. 加载查询中的法律名称
    print("\n📖 正在扫描查询文件中的法律名称 ...")
    law_names = load_unique_law_names(queries_file)
    print(f"✅ 共提取到 {len(law_names)} 个去重后的法律名称（source_name）")

    # 2. 构建 Law-Book 索引
    print("\n📚 正在扫描 Law-Book 目录以建立索引 ...")
    law_book_index = build_law_book_index(law_book_dir)
    print(f"✅ Law-Book 中共索引到 {len(law_book_index)} 个标准化法律名称")

    # 3. 为每个查询中的法律名称寻找对应文件
    print("\n🔍 正在为查询中的法律名称匹配 Law-Book 文件 ...")
    matched, unmatched = collect_law_files_for_queries(law_names, law_book_index)
    print(f"✅ 找到 {len(matched)} 个可匹配的法律，{len(unmatched)} 个未匹配到")

    if unmatched:
        print("\n⚠️  下列法律名称在 Law-Book 中未找到匹配文件（名称：出现次数）：")
        for name, cnt in unmatched.items():
            print(f"  - {name}: {cnt}")

    if not matched:
        print("\n❌ 未找到任何可匹配的法律文件，终止。")
        return

    # 4. 拷贝匹配到的 .md 文件
    print("\n📦 正在拷贝匹配到的法律文件到目标目录 ...")
    total_copied = copy_law_files(matched, output_dir, law_book_dir)

    print("\n" + "=" * 80)
    print("✅ 拷贝完成")
    print("=" * 80)
    print(f"匹配到的法律种类数: {len(matched)}")
    print(f"拷贝的 .md 文件总数: {total_copied}")
    print(f"目标目录: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()


