#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 LawBench queries_lawbench_3-2_matched.jsonl 中的条款编号（如“第一百四十条”）
转换为统一 chunks 语料中的实际 chunk_id。

设计目标（针对本次 LawBench 评测）：
- LawBench 查询文件中：
    - source_name: 法律名称（可能带有“中华人民共和国”等前缀）
    - relevant_chunk_ids: 条款编号列表（如 ["第一百四十条"]）
- 统一 chunks 语料（lawbench_laws_chunks.jsonl）中：
    - id: 形如 "<相对路径>.md#<chunk_index>"
    - metadata.source_name: 相对路径（如 "3-民法商法/公司法（2018-10-26）.md"）
    - content: 文本内容，包含若干 “第XX条”

核心逻辑：
1. 扫描 chunks 文件：
   - 依据 metadata.source_name 推导出法律文件名，并使用 normalize_law_name 归一化
   - 在 content 中用正则提取所有 “第[零一二三四五六七八九十百千万]+条”
   - 为每个 (归一化法律名, 条款编号) 建立映射 -> chunk_id
2. 扫描 LawBench 查询文件：
   - 对每条查询，根据 source_name 归一化出法律名
   - 将其中每个条款编号映射为对应的 chunk_id
   - 输出新的 JSONL 文件，relevant_chunk_ids 将变为真正的 chunk_id 列表

注意：
- 为避免覆盖原始标注文件，默认输出为 queries_lawbench_3-2_chunk_ids.jsonl
- 如果某些 (法律, 条款) 在 chunks 中找不到对应的 chunk，会打印警告，并保留原始条款编号
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Tuple

from .config import CHUNKS_PATH, BASE_DIR
from .filter_queries_by_law_book import normalize_law_name


LawArticleKey = Tuple[str, str]


def build_law_article_to_chunk_id_mapping(chunks_path: Path) -> Dict[LawArticleKey, str]:
    """
    建立从 (归一化法律名, 条款编号) 到 chunk_id 的映射。

    条款编号格式示例：
        - "第一百四十条"
        - "第七十条"
    """
    mapping: Dict[LawArticleKey, str] = {}

    with chunks_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"⚠️  解析 chunks 第 {line_num} 行失败: {e}")
                continue

            chunk_id = obj.get("id")
            content: str = obj.get("content", "")
            metadata = obj.get("metadata", {}) or {}

            if not isinstance(chunk_id, str):
                continue

            # 推导法律文件名：优先使用 metadata.source_name，其次从 chunk_id 前缀推导
            source_name = metadata.get("source_name") or chunk_id.split("#", 1)[0]
            # source_name 一般为类似 "3-民法商法/公司法（2018-10-26）.md"
            law_file_stem = Path(source_name).stem
            law_normalized = normalize_law_name(law_file_stem)
            if not law_normalized:
                continue

            # 在 content 中查找所有条款编号（格式：第XXX条）
            # 注意：要包含"零"字，因为有很多条款如"第一百零一条"、"第一千零三十四条"等
            articles = re.findall(r"第[零一二三四五六七八九十百千万]+条", content)
            if not articles:
                continue

            for article in articles:
                key: LawArticleKey = (law_normalized, article)
                # 如果已经存在映射且 chunk_id 不同，打印一次警告，但保留第一个映射
                if key in mapping and mapping[key] != chunk_id:
                    print(
                        f"⚠️  条款重复映射: 法律={law_normalized}, 条款={article}, "
                        f"已有={mapping[key]}, 新={chunk_id}"
                    )
                    continue
                mapping[key] = chunk_id

    print(f"\n✅ 已建立 (法律, 条款) -> chunk_id 映射，共 {len(mapping)} 条")
    return mapping


def update_lawbench_queries_file(
    queries_path: Path,
    output_path: Path,
    mapping: Dict[LawArticleKey, str],
) -> None:
    """
    读取 LawBench 匹配后的查询文件，将其中的条款编号转换为具体 chunk_id。

    输入文件示例（queries_lawbench_3-2_matched.jsonl）：
        {
            "id": "q_010",
            "query": "...",
            "relevant_chunk_ids": ["第一百四十条"],
            "source_name": "公司法"
        }

    输出文件中 relevant_chunk_ids 将变为真实 chunk_id：
        {
            "id": "q_010",
            "query": "...",
            "relevant_chunk_ids": ["3-民法商法/公司法（2018-10-26）.md#140"],
            "source_name": "公司法"
        }
    """
    updated_queries = []
    not_found_keys: Dict[LawArticleKey, int] = {}

    with queries_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                query = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"⚠️  解析 queries 第 {line_num} 行失败: {e}")
                continue

            source_name_raw = query.get("source_name", "")
            law_normalized = normalize_law_name(str(source_name_raw))
            original_ids = query.get("relevant_chunk_ids", []) or []

            if not law_normalized or not original_ids:
                # 没有法律名或没有条款编号的记录，直接原样保留
                updated_queries.append(query)
                continue

            new_chunk_ids = []
            for article in original_ids:
                key: LawArticleKey = (law_normalized, str(article))
                chunk_id = mapping.get(key)
                if chunk_id:
                    new_chunk_ids.append(chunk_id)
                else:
                    # 找不到映射时，保留原值并记录统计
                    new_chunk_ids.append(article)
                    not_found_keys[key] = not_found_keys.get(key, 0) + 1

            query["relevant_chunk_ids"] = new_chunk_ids
            updated_queries.append(query)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for query in updated_queries:
            f.write(json.dumps(query, ensure_ascii=False) + "\n")

    print(f"\n✅ 更新完成！共处理 {len(updated_queries)} 条 LawBench 查询")
    if not_found_keys:
        print(f"⚠️  有 {len(not_found_keys)} 个 (法律, 条款) 未找到对应 chunk，示例：")
        for (law, article), cnt in list(not_found_keys.items())[:20]:
            print(f"   - 法律={law}, 条款={article} （共 {cnt} 次）")
    else:
        print("✅ 所有 (法律, 条款) 均找到对应 chunk_id")


def main() -> None:
    # 默认使用 config.CHUNKS_PATH（当前指向 lawbench_laws_chunks.jsonl）
    chunks_path = Path(CHUNKS_PATH).resolve()
    # LawBench 匹配后的原始 queries 文件
    queries_path = BASE_DIR / "eval" / "queries_lawbench_3-2_matched.jsonl"
    # 输出：带真实 chunk_id 的 LawBench queries
    output_path = BASE_DIR / "eval" / "queries_lawbench_3-2_chunk_ids.jsonl"

    print("LawBench 查询条款编号 -> chunk_id 映射脚本")
    print("=" * 80)
    print(f"chunks 文件: {chunks_path}")
    print(f"输入 queries: {queries_path}")
    print(f"输出文件: {output_path}")
    print("=" * 80)

    if not chunks_path.exists():
        print(f"❌ chunks 文件不存在: {chunks_path}")
        return
    if not queries_path.exists():
        print(f"❌ LawBench 查询文件不存在: {queries_path}")
        return

    print("\n📚 正在建立 (法律, 条款) -> chunk_id 映射 ...")
    mapping = build_law_article_to_chunk_id_mapping(chunks_path)

    print("\n📝 正在转换 LawBench 查询中的条款编号为 chunk_id ...")
    update_lawbench_queries_file(queries_path, output_path, mapping)

    print("\n🎉 完成！可以使用新的 queries_lawbench_3-2_chunk_ids.jsonl 进行检索评测。")


if __name__ == "__main__":
    main()


