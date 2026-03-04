#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试转换函数的功能
"""
import sys
from pathlib import Path

# 导入转换函数
sys.path.insert(0, str(Path(__file__).parent))
from convert_lawbench_to_queries import number_to_chinese, extract_law_name, extract_law_info

def test_number_to_chinese():
    """测试阿拉伯数字转汉字"""
    test_cases = [
        (149, "一百四十九"),
        (102, "一百零二"),
        (198, "一百九十八"),
        (32, "三十二"),
        (110, "一百一十"),
        (100, "一百"),
        (1000, "一千"),
        (1024, "一千零二十四"),
    ]
    
    print("测试 number_to_chinese 函数:")
    for num, expected in test_cases:
        result = number_to_chinese(num)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {num} -> {result} (期望: {expected})")
        if result != expected:
            print(f"    错误！")

def test_extract_law_name():
    """测试法律名称提取"""
    test_cases = [
        ("民法商法中的证券法", "证券法"),
        ("民法商法类中的个人独资企业法", "个人独资企业法"),
        ("公司法", "公司法"),
        ("外商投资法的", "外商投资法"),
        ("《公司法》", "公司法"),
        ("证券法", "证券法"),
    ]
    
    print("\n测试 extract_law_name 函数:")
    for text, expected in test_cases:
        result = extract_law_name(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' -> '{result}' (期望: '{expected}')")
        if result != expected:
            print(f"    错误！")

def test_extract_law_info():
    """测试法条信息提取"""
    test_cases = [
        ("根据公司法第149条规定，董事、监事、高级管理人员执行公司职务时违反法律、行政法规或者公司章程的规定，给公司造成损失的，应当承担赔偿责任。", ("公司法", ["第一百四十九条"])),
        ("根据民法商法中的证券法的第一百四十二条，若证券公司的董事、监事、高级管理人员未能勤勉尽责，致使证券公司存在重大违法违规行为或者重大风险的，国务院证券监督管理机构可以责令证券公司予以更换。", ("证券法", ["第一百四十二条"])),
        ("根据外商投资法的第32条规定，外商投资企业开展生产经营活动，应当遵守法律、行政法规有关劳动保护的规定。", ("外商投资法", ["第三十二条"])),
        ("根据证券法第198条规定，证券公司违反本法第88条的规定未履行或者未按照规定履行投资者适当性管理义务的，要责令改正，并处以10万元以上1百万元以下的罚款。", ("证券法", ["第一百九十八条"])),
        ("根据《公司法》第102条的规定，无记名股票持有人出席股东大会会议的，应当于会议召开五日前至股东大会闭会时将股票交存于公司。", ("公司法", ["第一百零二条"])),
        ("根据证券法的第四十二条规定，证券服务机构和人员在证券承销期内和期满后六个月内不得买卖该证券。", ("证券法", ["第四十二条"])),
    ]
    
    print("\n测试 extract_law_info 函数:")
    for answer, (expected_name, expected_articles) in test_cases:
        name, articles = extract_law_info(answer)
        name_ok = name == expected_name
        articles_ok = articles == expected_articles
        status = "✓" if (name_ok and articles_ok) else "✗"
        print(f"  {status} 法律名称: '{name}' (期望: '{expected_name}')")
        print(f"     法条: {articles} (期望: {expected_articles})")
        if not (name_ok and articles_ok):
            print(f"    错误！")
        print()

if __name__ == '__main__':
    test_number_to_chinese()
    test_extract_law_name()
    test_extract_law_info()
    print("\n测试完成！")



















