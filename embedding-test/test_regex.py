#!/usr/bin/env python3
import re

text = "第七百零三条 租赁合同是出租人将租赁物交付承租人使用、收益，承租人支付租金的合同。"
pattern = r'第[一二三四五六七八九十百千万]+条'
matches = re.findall(pattern, text)
print('匹配结果:', matches)
print('是否包含"第七百零三条":', '第七百零三条' in matches)































