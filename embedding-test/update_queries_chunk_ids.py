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

def build_chunk_index_to_article_mapping(chunks_path: Path) -> dict[str, str]:
    """建立从 chunk_index 到条款编号的映射（用于处理 民法典.md#214 格式）"""
    mapping = {}
    
    with open(chunks_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                chunk = json.loads(line.strip())
                chunk_id = chunk['id']
                if '#' not in chunk_id:
                    continue
                chunk_index = chunk_id.split('#')[1]
                content = chunk['content']
                
                # 提取第一个条款编号作为该 chunk 的代表
                articles = re.findall(r'第[零一二三四五六七八九十百千万]+条', content)
                if articles:
                    # 使用第一个条款编号
                    mapping[chunk_index] = articles[0]
            except Exception as e:
                print(f"处理chunk时出错: {e}")
                continue
    
    return mapping

def convert_to_chunk_id(item: str, article_to_chunk: dict[str, str], index_to_article: dict[str, str]) -> str:
    """将条款编号或 民法典.md#214 格式转换为 chunk_id"""
    # 如果已经是条款编号格式（第XXX条），直接查找映射
    if re.match(r'第[零一二三四五六七八九十百千万]+条', item):
        chunk_id = article_to_chunk.get(item)
        if chunk_id:
            return chunk_id
        else:
            print(f"警告: 未找到条款 '{item}' 对应的chunk")
            return item
    
    # 如果是 民法典.md#214 格式，先转换为条款编号，再转换为 chunk_id
    if item.startswith('民法典.md#'):
        chunk_index = item.split('#')[1]
        article = index_to_article.get(chunk_index)
        if article:
            chunk_id = article_to_chunk.get(article)
            if chunk_id:
                return chunk_id
            else:
                print(f"警告: 未找到条款 '{article}' (来自 {item}) 对应的chunk")
                return item
        else:
            print(f"警告: 未找到 chunk_index {chunk_index} 对应的条款编号")
            return item
    
    # 其他格式，保留原值
    return item

def update_queries_file(queries_path: Path, article_to_chunk: dict[str, str], index_to_article: dict[str, str]):
    """更新queries.jsonl文件，将条款编号替换为chunk id"""
    updated_queries = []
    not_found_items = set()
    
    with open(queries_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                query = json.loads(line.strip())
                original_chunk_ids = query['relevant_chunk_ids']
                new_chunk_ids = []
                
                for item in original_chunk_ids:
                    new_id = convert_to_chunk_id(item, article_to_chunk, index_to_article)
                    if new_id == item and item not in article_to_chunk and not item.startswith('民法典.md#'):
                        not_found_items.add(item)
                    new_chunk_ids.append(new_id)
                
                query['relevant_chunk_ids'] = new_chunk_ids
                updated_queries.append(query)
            except Exception as e:
                print(f"处理query时出错: {e}")
                continue
    
    # 写回文件
    with open(queries_path, 'w', encoding='utf-8') as f:
        for query in updated_queries:
            f.write(json.dumps(query, ensure_ascii=False) + '\n')
    
    print(f"\n更新完成！")
    print(f"共处理 {len(updated_queries)} 条查询")
    if not_found_items:
        print(f"未找到的条款编号: {sorted(not_found_items)}")

if __name__ == '__main__':
    project_root = Path(__file__).parent
    chunks_path = project_root / "data" / "civil_code_chunks.jsonl"
    queries_path = project_root / "eval" / "queries.jsonl"
    
    print("正在建立条款编号到chunk id的映射...")
    article_to_chunk = build_article_to_chunk_id_mapping(chunks_path)
    print(f"建立了 {len(article_to_chunk)} 个条款的映射关系")
    
    print("\n正在建立 chunk_index 到条款编号的映射...")
    index_to_article = build_chunk_index_to_article_mapping(chunks_path)
    print(f"建立了 {len(index_to_article)} 个 chunk_index 的映射关系")
    
    print("\n正在更新queries.jsonl文件...")
    update_queries_file(queries_path, article_to_chunk, index_to_article)
    print("完成！")
