#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 LawBench 3-2.json 转换为 queries.jsonl 格式

处理规则：
1. 阿拉伯数字转换为汉字数字（如 149 -> 一百四十九条）
2. 处理"中的"之后提取法律名称（如"民法商法中的证券法" -> "证券法"）
3. 提取法条信息并标准化为"第xx条"格式
"""
import json
import re
from pathlib import Path

def number_to_chinese(num: int) -> str:
    """
    将阿拉伯数字转换为汉字数字
    支持范围：0-9999
    例如：149 -> 一百四十九, 102 -> 一百零二, 198 -> 一百九十八
    """
    if num == 0:
        return "零"
    
    # 数字映射
    digits = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    units = ['', '十', '百', '千']
    
    if num < 10:
        return digits[num]
    elif num < 20:
        if num == 10:
            return "十"
        return "十" + digits[num % 10]
    elif num < 100:
        tens = num // 10
        ones = num % 10
        if ones == 0:
            return digits[tens] + "十"
        return digits[tens] + "十" + digits[ones]
    elif num < 1000:
        hundreds = num // 100
        remainder = num % 100
        if remainder == 0:
            return digits[hundreds] + "百"
        elif remainder < 10:
            return digits[hundreds] + "百零" + digits[remainder]
        elif remainder < 20:
            if remainder == 10:
                return digits[hundreds] + "百一十"
            return digits[hundreds] + "百一十" + digits[remainder % 10]
        else:
            tens = remainder // 10
            ones = remainder % 10
            if ones == 0:
                return digits[hundreds] + "百" + digits[tens] + "十"
            return digits[hundreds] + "百" + digits[tens] + "十" + digits[ones]
    else:  # 1000-9999
        thousands = num // 1000
        remainder = num % 1000
        if remainder == 0:
            return digits[thousands] + "千"
        elif remainder < 10:
            return digits[thousands] + "千零" + digits[remainder]
        elif remainder < 100:
            tens = remainder // 10
            ones = remainder % 10
            if ones == 0:
                return digits[thousands] + "千零" + digits[tens] + "十"
            return digits[thousands] + "千零" + digits[tens] + "十" + digits[ones]
        else:
            hundreds = remainder // 100
            remainder2 = remainder % 100
            if remainder2 == 0:
                return digits[thousands] + "千" + digits[hundreds] + "百"
            elif remainder2 < 10:
                return digits[thousands] + "千" + digits[hundreds] + "百零" + digits[remainder2]
            elif remainder2 < 20:
                if remainder2 == 10:
                    return digits[thousands] + "千" + digits[hundreds] + "百一十"
                return digits[thousands] + "千" + digits[hundreds] + "百一十" + digits[remainder2 % 10]
            else:
                tens = remainder2 // 10
                ones = remainder2 % 10
                if ones == 0:
                    return digits[thousands] + "千" + digits[hundreds] + "百" + digits[tens] + "十"
                return digits[thousands] + "千" + digits[hundreds] + "百" + digits[tens] + "十" + digits[ones]

def extract_law_name(text: str) -> str:
    """
    从文本中提取法律名称，处理"中的"之后的情况
    例如：
    - "民法商法中的证券法" -> "证券法"
    - "民法商法类中的个人独资企业法" -> "个人独资企业法"
    - "公司法" -> "公司法"
    - "外商投资法的" -> "外商投资法"
    """
    # 去掉书名号
    text = re.sub(r'[《》]', '', text)
    
    # 去掉末尾的"的"、"类"等后缀
    text = re.sub(r'[的类]+$', '', text)
    
    # 查找"中的"之后的内容（包括"类中的"）
    match = re.search(r'(?:类)?中的([^的第条]+?法)', text)
    if match:
        law_name = match.group(1).strip()
        # 去掉可能的"的"、"类"等后缀
        law_name = re.sub(r'[的类]+$', '', law_name)
        return law_name
    
    # 如果没有"中的"，尝试直接提取法律名称（以"法"结尾）
    # 优先匹配最后一个"法"字
    match = re.search(r'([^第条]+?法)', text)
    if match:
        law_name = match.group(1).strip()
        # 去掉可能的"类"、"的"等后缀
        law_name = re.sub(r'[的类]+$', '', law_name)
        return law_name
    
    return text.strip()

def extract_law_info(answer: str) -> tuple[str, list[str]]:
    """
    从 answer 中提取法条信息
    
    规则：
    1. 提取"根据"之后、"条"之前包括"条"的内容
    2. "第"前的内容去掉书名号，处理"中的"之后提取法律名称，记为 source_name
    3. "第xx条"记为 relevant_chunk_ids（数组），如果是阿拉伯数字则转换为汉字
    
    返回: (source_name, relevant_chunk_ids)
    """
    # 查找"根据"之后的内容，匹配到第一个"条"字
    match = re.search(r'根据(.+?条)', answer)
    if not match:
        return "", []
    
    law_text = match.group(1)  # "根据"之后、"条"之前包括"条"的内容
    
    # 去掉可能的"的"、"规定"等后缀（在"条"之后）
    law_text = re.sub(r'条[的规定]*$', '条', law_text)
    
    # 查找"第"字的位置
    di_index = law_text.find('第')
    
    if di_index == -1:
        # 没有"第"字，尝试匹配"第xx条"的模式（如"第七十条"）
        pattern = r'([^第条]+?)([零一二三四五六七八九十百千万]+条)'
        match2 = re.search(pattern, law_text)
        if match2:
            source_name = extract_law_name(match2.group(1))
            article = match2.group(2)
            # 标准化为"第xx条"格式
            article_normalized = f"第{article}" if not article.startswith('第') else article
            return source_name, [article_normalized]
        else:
            # 无法解析，返回空
            return "", []
    
    # 有"第"字的情况
    source_name_text = law_text[:di_index].strip()
    # 去掉末尾的"的"、"法"等可能的后缀（但保留"法"字）
    source_name_text = re.sub(r'的+$', '', source_name_text)
    source_name = extract_law_name(source_name_text)
    
    # 提取"第xx条"（可能包含阿拉伯数字或汉字数字）
    # 先尝试匹配阿拉伯数字的情况：第149条、第102条、第32条等
    arabic_match = re.search(r'第(\d+)条', law_text[di_index:])
    if arabic_match:
        arabic_num = int(arabic_match.group(1))
        chinese_num = number_to_chinese(arabic_num)
        article = f"第{chinese_num}条"
        return source_name, [article]
    
    # 匹配汉字数字的情况：第一百四十二条、第七十条等
    chinese_match = re.search(r'第[零一二三四五六七八九十百千万]+条', law_text[di_index:])
    if chinese_match:
        article = chinese_match.group(0)
        return source_name, [article]
    
    return source_name, []

def convert_lawbench_to_queries(lawbench_file: Path, output_file: Path):
    """
    将 LawBench JSON 文件转换为 queries.jsonl 格式
    """
    # 读取 LawBench 数据
    with open(lawbench_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    queries = []
    
    for idx, item in enumerate(data, start=1):
        # 1. 生成 id: "q_001", "q_002" 等
        query_id = f"q_{idx:03d}"
        
        # 2. 处理 question: 去掉"场景:"前缀
        question = item.get('question', '')
        if question.startswith('场景:'):
            query_text = question[3:].strip()  # 去掉"场景:"（3个字符）
        else:
            query_text = question.strip()
        
        # 3. 处理 answer: 提取法条信息
        answer = item.get('answer', '')
        source_name, relevant_chunk_ids = extract_law_info(answer)
        
        # 构建查询对象
        query = {
            "id": query_id,
            "query": query_text,
            "relevant_chunk_ids": relevant_chunk_ids,
            "source_name": source_name
        }
        
        # 可选：添加 source_name 用于调试（如果需要）
        # query["source_name"] = source_name
        
        queries.append(query)
        
        # 打印一些信息用于调试
        if idx <= 10:
            print(f"\n示例 {idx}:")
            print(f"  原始 question: {question[:60]}...")
            print(f"  转换后 query: {query_text[:60]}...")
            print(f"  原始 answer: {answer[:100]}...")
            print(f"  提取的 source_name: {source_name}")
            print(f"  提取的 relevant_chunk_ids: {relevant_chunk_ids}")
    
    # 保存为 JSONL 格式
    with open(output_file, 'w', encoding='utf-8') as f:
        for query in queries:
            f.write(json.dumps(query, ensure_ascii=False) + '\n')
    
    print(f"\n转换完成！")
    print(f"共处理 {len(queries)} 条查询")
    print(f"输出文件: {output_file}")
    
    # 统计信息
    empty_chunks = sum(1 for q in queries if not q['relevant_chunk_ids'])
    print(f"未提取到法条信息的查询数: {empty_chunks}")
    
    # 统计提取到的法律名称
    source_names = {}
    for q in queries:
        if q['relevant_chunk_ids']:
            # 从 answer 中提取 source_name 用于统计
            answer = data[queries.index(q)].get('answer', '')
            _, _ = extract_law_info(answer)
            # 这里可以添加统计逻辑

if __name__ == '__main__':
    # 设置路径
    lawbench_file = Path(__file__).parent.parent / "LawBench-main" / "data" / "one_shot" / "3-2.json"
    output_file = Path(__file__).parent / "eval" / "queries_lawbench_3-2.jsonl"
    
    # 确保输出目录存在
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"读取 LawBench 文件: {lawbench_file}")
    print(f"输出文件: {output_file}")
    
    convert_lawbench_to_queries(lawbench_file, output_file)
    
    print("\n下一步：使用 update_queries_chunk_ids.py 将法条编号转换为 chunk_id")

