#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

def build_article_to_chunk_id_mapping(chunks_path: Path) -> dict[str, str]:
    """建立从条款编号到 chunk id 的映射"""
    mapping = {}
    
    with open(chunks_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                chunk = json.loads(line.strip())
                chunk_id = chunk['id']
                content = chunk['content']
                
                # 在content中查找所有条款编号（格式：第XXX条）
                # 注意：要包含"零"字，因为有很多条款如"第一百零一条"、"第一千零三十四条"等
                articles = re.findall(r'第[零一二三四五六七八九十百千万]+条', content)
                for article in articles:
                    # 如果这个条款编号还没映射，或者当前chunk更早（id更小），则更新
                    if article not in mapping:
                        mapping[article] = chunk_id
            except Exception as e:
                print(f"处理chunk时出错: {e}")
                continue
    
    return mapping

def update_terms_file(terms_path: Path, mapping: dict[str, str]):
    """更新terms.jsonl文件，将条款编号替换为chunk id"""
    updated_terms = []
    not_found_articles = set()
    
    with open(terms_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                term = json.loads(line.strip())
                original_articles = term['relevant_chunk_ids']
                new_chunk_ids = []
                
                for article in original_articles:
                    if article in mapping:
                        new_chunk_ids.append(mapping[article])
                    else:
                        print(f"警告: 未找到条款 '{article}' 对应的chunk")
                        not_found_articles.add(article)
                        # 如果找不到，保留原值
                        new_chunk_ids.append(article)
                
                term['relevant_chunk_ids'] = new_chunk_ids
                updated_terms.append(term)
            except Exception as e:
                print(f"处理term时出错: {e}")
                continue
    
    # 写回文件
    with open(terms_path, 'w', encoding='utf-8') as f:
        for term in updated_terms:
            f.write(json.dumps(term, ensure_ascii=False) + '\n')
    
    print(f"\n更新完成！")
    print(f"共处理 {len(updated_terms)} 条术语")
    if not_found_articles:
        print(f"未找到的条款编号: {sorted(not_found_articles)}")

if __name__ == '__main__':
    project_root = Path(__file__).parent
    chunks_path = project_root / "data" / "civil_code_chunks.jsonl"
    terms_path = project_root / "eval" / "terms.jsonl"
    
    print("正在建立条款编号到chunk id的映射...")
    mapping = build_article_to_chunk_id_mapping(chunks_path)
    print(f"建立了 {len(mapping)} 个条款的映射关系")
    
    print("\n正在更新terms.jsonl文件...")
    update_terms_file(terms_path, mapping)
    print("完成！")
