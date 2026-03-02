#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 queries_lawbench_3-2_matched.jsonl 文件中的 original_source_name 字段
"""

import json
from pathlib import Path

def clean_file(input_file: Path, output_file: Path):
    """清理文件中的 original_source_name 字段"""
    cleaned_count = 0
    total_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_file, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                total_count += 1
                
                # 移除 original_source_name 字段
                if 'original_source_name' in data:
                    del data['original_source_name']
                    cleaned_count += 1
                
                # 写入清理后的数据
                f_out.write(json.dumps(data, ensure_ascii=False) + '\n')
                
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 解析错误: {e}")
                continue
    
    print(f"✅ 处理完成！")
    print(f"   总记录数: {total_count}")
    print(f"   清理的记录数: {cleaned_count}")

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    input_file = project_root / "eval" / "queries_lawbench_3-2_matched.jsonl"
    output_file = input_file  # 覆盖原文件
    
    clean_file(input_file, output_file)

