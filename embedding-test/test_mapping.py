#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from pathlib import Path

chunks_path = Path(__file__).parent / "data" / "civil_code_chunks.jsonl"
mapping = defaultdict(list)

with open(chunks_path, 'r', encoding='utf-8') as f:
    for line in f:
        chunk = json.loads(line.strip())
        chunk_id = chunk['id']
        content = chunk['content']
        articles = re.findall(r'第[一二三四五六七八九十百千万]+条', content)
        for article in articles:
            mapping[article].append(chunk_id)

print('第五百四十三条:', mapping.get('第五百四十三条'))
print('第七百零三条:', mapping.get('第七百零三条'))
print('第七百三十三条:', mapping.get('第七百三十三条'))

# 检查包含"七百零三"的所有条款
for k, v in mapping.items():
    if '七百零三' in k:
        print(f'找到包含"七百零三"的条款: {k} -> {v}')

print(f'总共 {len(mapping)} 个条款')

