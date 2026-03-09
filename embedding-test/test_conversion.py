#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from collections import defaultdict

def extract_article_numbers(content: str) -> list[str]:
    """从内容中提取所有条款编号"""
    pattern = r'第[一二三四五六七八九十百千万]+条'
    articles = re.findall(pattern, content)
    return articles

def build_article_to_chunk_mapping(chunks_path: Path) -> dict[str, list[str]]:
    """建立从条款编号到 chunk id 列表的映射"""
    mapping = defaultdict(list)
    
    with open(chunks_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                chunk = json.loads(line.strip())
                chunk_id = chunk['id']
                content = chunk['content']
                
                # 提取该 chunk 中包含的所有条款编号
                articles = extract_article_numbers(content)
                for article in articles:
                    mapping[article].append(chunk_id)
            except Exception as e:
                print(f"处理行时出错: {e}")
                continue
    
    return dict(mapping)

# 测试
project_root = Path(__file__).parent
chunks_path = project_root / "data" / "civil_code_chunks.jsonl"

print("建立映射...")
mapping = build_article_to_chunk_mapping(chunks_path)
print(f"建立了 {len(mapping)} 个条款的映射关系")

# 测试几个条款
test_articles = ["第五百四十三条", "第七百零三条", "第七百三十三条"]
print("\n测试转换:")
for article in test_articles:
    chunk_ids = mapping.get(article, [])
    print(f"  {article}: {chunk_ids}")

# 读取 terms.jsonl 的第一条
terms_path = project_root / "eval" / "terms.jsonl"
with open(terms_path, 'r', encoding='utf-8') as f:
    first_line = f.readline().strip()
    term = json.loads(first_line)
    print(f"\n第一条术语: {term['id']}")
    print(f"  relevant_chunk_ids: {term['relevant_chunk_ids']}")
    
    # 转换
    new_chunk_ids = []
    for article in term['relevant_chunk_ids']:
        chunk_ids = mapping.get(article, [])
        if chunk_ids:
            new_chunk_ids.append(chunk_ids[0])
        else:
            print(f"  警告: 找不到 {article}")
            new_chunk_ids.append(article)
    print(f"  转换后: {new_chunk_ids}")































