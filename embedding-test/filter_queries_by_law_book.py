#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本功能：
1. 从 queries_lawbench_3-2.jsonl 中提取所有涉及的法律名称
2. 扫描 Law-Book 目录，建立法律名称到文件路径的映射
3. 智能匹配查询中的法律名称和 Law-Book 中的法律文件
4. 将能匹配上的查询条目保存到新的 jsonl 文件中
"""

import json
import re
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple, Optional


def normalize_law_name(name: str) -> str:
    """
    标准化法律名称，用于匹配
    
    处理：
    - 去除"中华人民共和国"前缀
    - 去除"中国"前缀
    - 去除日期后缀（如"（2018-10-26）"）
    - 去除空格和特殊字符
    """
    if not name:
        return ""
    
    # 去除常见前缀
    name = re.sub(r'^中华人民共和国', '', name)
    name = re.sub(r'^中国', '', name)
    
    # 去除日期后缀
    name = re.sub(r'（\d{4}-\d{1,2}-\d{1,2}）', '', name)
    name = re.sub(r'\(\d{4}-\d{1,2}-\d{1,2}\)', '', name)
    
    # 去除文件扩展名
    name = re.sub(r'\.md$', '', name)
    
    # 去除空格
    name = name.strip()
    
    return name


def extract_law_name_from_file(file_path: Path) -> str:
    """从文件路径中提取法律名称"""
    # 获取文件名（不含扩展名）
    name = file_path.stem
    return normalize_law_name(name)


def build_law_book_index(law_book_dir: Path) -> Dict[str, List[Path]]:
    """
    扫描 Law-Book 目录，建立法律名称到文件路径的映射
    
    返回: {标准化法律名称: [文件路径列表]}
    """
    index: Dict[str, List[Path]] = {}
    
    # 递归扫描所有 .md 文件
    for md_file in law_book_dir.rglob("*.md"):
        normalized_name = extract_law_name_from_file(md_file)
        if normalized_name:
            if normalized_name not in index:
                index[normalized_name] = []
            index[normalized_name].append(md_file)
    
    return index


def match_law_name(query_law_name: str, law_book_index: Dict[str, List[Path]]) -> Tuple[Optional[List[Path]], Optional[str]]:
    """
    匹配查询中的法律名称和 Law-Book 中的文件
    
    返回: (匹配的文件路径列表, 映射后的法律名称)
    如果找不到则返回 (None, None)
    如果使用了特殊映射，返回映射后的名称；否则返回 None（表示使用原始名称）
    """
    if not query_law_name:
        return None, None
    
    # 特殊映射规则（先检查特殊映射）
    special_mappings = {
        "我国的消费者权益保护法": "消费者权益保护法",
        "中华人民共和国外商投资法": "外商投资法",
        "中华人民共和国票据法": "票据法",
        "中华人民共和国合伙企业法": "合伙企业法",
        "中华人民共和国农村土地承包法": "农村土地承包法",
        "中华人民共和国残疾人保障法": "残疾人保障法",
        "中华人民共和国军人保险法": "军人保险法",
        "中华人民共和国慈善法": "慈善法",
        "中华人民共和国个人独资企业法": "个人独资企业法",
        "中华人民共和国公司法": "公司法",
        "中华人民共和国电子商务法": "电子商务法",
        "中华人民共和国行政诉讼法": "行政诉讼法",
        "中华人民共和国刑事诉讼法": "刑事诉讼法",
        "中华人民共和国民事诉讼法": "民事诉讼法",
        "中华人民共和国宪法": "宪法",
        "中华人民共和国引渡法": "引渡法",
        "中华人民共和国国际刑事司法": "国际刑事司法协助法",
        "中国引渡法": "引渡法",
    }
    
    # 先检查是否需要特殊映射
    mapped_name = None
    search_name = query_law_name
    if query_law_name in special_mappings:
        mapped_name = special_mappings[query_law_name]
        search_name = mapped_name
    
    normalized_query = normalize_law_name(search_name)
    
    # 精确匹配
    if normalized_query in law_book_index:
        return law_book_index[normalized_query], mapped_name
    
    # 模糊匹配：尝试部分匹配
    for law_name, file_paths in law_book_index.items():
        if normalized_query in law_name or law_name in normalized_query:
            return file_paths, mapped_name
    
    return None, None


def process_queries_file(queries_file: Path, law_book_index: Dict[str, List[Path]]) -> Tuple[List[dict], Dict[str, int]]:
    """
    处理查询文件，返回匹配的查询和统计信息
    
    返回: (匹配的查询列表, 统计信息字典)
    """
    matched_queries = []
    unmatched_queries = []
    law_stats = Counter()
    unmatched_laws = Counter()
    
    with open(queries_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                query_data = json.loads(line)
                source_name = query_data.get('source_name', '')
                
                if source_name:
                    law_stats[source_name] += 1
                    
                    # 尝试匹配
                    matched_files, mapped_name = match_law_name(source_name, law_book_index)
                    
                    if matched_files:
                        # 如果使用了特殊映射，更新 source_name
                        if mapped_name:
                            query_data['source_name'] = mapped_name
                        
                        # 添加匹配的文件路径信息
                        query_data['matched_law_files'] = [str(f) for f in matched_files]
                        matched_queries.append(query_data)
                    else:
                        unmatched_queries.append(query_data)
                        unmatched_laws[source_name] += 1
                else:
                    # source_name 为空的情况
                    unmatched_queries.append(query_data)
                    
            except json.JSONDecodeError as e:
                print(f"⚠️  第 {line_num} 行 JSON 解析错误: {e}")
                continue
    
    stats = {
        'total_queries': len(matched_queries) + len(unmatched_queries),
        'matched_queries': len(matched_queries),
        'unmatched_queries': len(unmatched_queries),
        'unique_laws_in_queries': len(law_stats),
        'unique_matched_laws': len(set(q.get('source_name') for q in matched_queries if q.get('source_name'))),
        'unique_unmatched_laws': len(unmatched_laws),
        'law_stats': dict(law_stats),
        'unmatched_laws': dict(unmatched_laws),
    }
    
    return matched_queries, stats


def main():
    """主函数"""
    # 路径配置
    project_root = Path(__file__).resolve().parent.parent
    queries_file = project_root / "embedding-test" / "eval" / "queries_lawbench_3-2.jsonl"
    law_book_dir = project_root / "Law-Book"
    output_file = project_root / "embedding-test" / "eval" / "queries_lawbench_3-2_matched.jsonl"
    
    print("=" * 80)
    print("法律查询过滤脚本")
    print("=" * 80)
    print(f"\n查询文件: {queries_file}")
    print(f"Law-Book 目录: {law_book_dir}")
    print(f"输出文件: {output_file}")
    print()
    
    # 检查文件是否存在
    if not queries_file.exists():
        print(f"❌ 查询文件不存在: {queries_file}")
        return
    
    if not law_book_dir.exists():
        print(f"❌ Law-Book 目录不存在: {law_book_dir}")
        return
    
    # 1. 建立 Law-Book 索引
    print("📚 正在扫描 Law-Book 目录...")
    law_book_index = build_law_book_index(law_book_dir)
    print(f"✅ 找到 {len(law_book_index)} 个法律文件")
    
    # 显示一些示例
    print("\n法律文件示例（前10个）:")
    for i, (law_name, file_paths) in enumerate(list(law_book_index.items())[:10]):
        print(f"  {i+1}. {law_name} -> {file_paths[0].name}")
    
    # 2. 处理查询文件
    print(f"\n📖 正在处理查询文件...")
    matched_queries, stats = process_queries_file(queries_file, law_book_index)
    
    # 3. 保存匹配的查询
    print(f"\n💾 正在保存匹配的查询到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        for query in matched_queries:
            # 移除临时添加的 matched_law_files 和 original_source_name 字段
            query_to_save = {k: v for k, v in query.items() if k not in ('matched_law_files', 'original_source_name')}
            f.write(json.dumps(query_to_save, ensure_ascii=False) + '\n')
    
    # 4. 打印统计信息
    print("\n" + "=" * 80)
    print("统计信息")
    print("=" * 80)
    print(f"总查询数: {stats['total_queries']}")
    print(f"匹配的查询数: {stats['matched_queries']}")
    print(f"未匹配的查询数: {stats['unmatched_queries']}")
    print(f"查询中涉及的法律种类数: {stats['unique_laws_in_queries']}")
    print(f"匹配上的法律种类数: {stats['unique_matched_laws']}")
    print(f"未匹配上的法律种类数: {stats['unique_unmatched_laws']}")
    
    # 显示未匹配的法律
    if stats['unmatched_laws']:
        print("\n⚠️  未匹配上的法律（前20个）:")
        for law_name, count in list(stats['unmatched_laws'].items())[:20]:
            print(f"  - {law_name}: {count} 条查询")
    
    # 显示匹配最多的法律
    print("\n✅ 匹配最多的法律（前20个）:")
    matched_law_counts = Counter()
    for query in matched_queries:
        source_name = query.get('source_name', '')
        if source_name:
            matched_law_counts[source_name] += 1
    
    for law_name, count in matched_law_counts.most_common(20):
        print(f"  - {law_name}: {count} 条查询")
    
    print("\n" + "=" * 80)
    print(f"✅ 完成！已保存 {len(matched_queries)} 条匹配的查询到: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()

