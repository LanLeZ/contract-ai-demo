import re
import json
from typing import List, Dict, Any, Optional


"""
合同条款切分与分层测试脚本

用法示例（在项目根目录或 problem_test 目录下）：

  python -m splitter_test.contract_splitter_test                      # 使用内置示例合同
  python -m splitter_test.contract_splitter_test path/to/contract.txt # 指定合同文本文件

运行后：
- 在终端打印分层后的条款结构（缩进显示）
- 在当前目录写出 JSON 结果：contract_split_result.json
"""


ARTICLE_LEVEL1_PATTERNS = [
    r"^第[一二三四五六七八九十百千万〇零两]+条",  # 第一条、第二条
    r"^\d+[\.\、、)]",  # 1. 1、 1)
    r"^[一二三四五六七八九十]+、",  # 一、 二、
]

ARTICLE_LEVEL2_PATTERNS = [
    r"^[（(]\d+[)）]",  # （1） (1)
    r"^[（(][一二三四五六七八九十]+[)）]",  # （一）
    r"^\d+[)）]",  # 1)
    r"^\d+\.\d+",  # 5.1  10.2 等
]

ARTICLE_LEVEL3_PATTERNS = [
    r"^[①②③④⑤⑥⑦⑧⑨]",
    r"^[a-zA-Z][\.\、、)]",
    r"^\d+\.\d+\.\d+",  # 1.2.3 这类三级编号
]


def _match_any(patterns: List[str], line: str) -> Optional[str]:
    for p in patterns:
        m = re.match(p, line)
        if m:
            return m.group(0)
    return None


def parse_clauses(full_text: str) -> List[Dict[str, Any]]:
    """
    将合同全文切分为分层条款结构：
    - level 1: 顶层条款（第一条 / 1. / 一、 等）
    - level 2: 子条款（（1）/ (1) / 1) / （一） /1.1 等）
    - level 3: 三级条款（① / a. 等）
    """
    # 保留空行信息以利于阅读，但可选择忽略完全空白行
    lines = [ln.rstrip() for ln in full_text.splitlines()]

    articles: List[Dict[str, Any]] = []
    current_art: Optional[Dict[str, Any]] = None
    current_sub: Optional[Dict[str, Any]] = None
    current_subsub: Optional[Dict[str, Any]] = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            # 空行：如果已经在某个条款里，就当作内容的一部分
            target = current_subsub or current_sub or current_art
            if target is not None:
                target["content"] = (target.get("content", "") + "\n").rstrip("\n")
            continue

        # 1. 顶层条款
        num1 = _match_any(ARTICLE_LEVEL1_PATTERNS, line)
        if num1:
            current_sub = None
            current_subsub = None
            current_art = {
                "level": 1,
                "number": num1,
                "title": line[len(num1) :].strip(),
                "content": "",
                "subclauses": [],
            }
            articles.append(current_art)
            continue

        # 2. 二级条款（必须在某个顶层条款下）
        if current_art:
            num2 = _match_any(ARTICLE_LEVEL2_PATTERNS, line)
            if num2:
                current_subsub = None
                current_sub = {
                    "level": 2,
                    "number": num2,
                    "content": line[len(num2) :].strip(),
                    "subclauses": [],
                }
                current_art["subclauses"].append(current_sub)
                continue

            # 3. 三级条款（在二级条款下）
            num3 = _match_any(ARTICLE_LEVEL3_PATTERNS, line)
            if num3 and current_sub:
                current_subsub = {
                    "level": 3,
                    "number": num3,
                    "content": line[len(num3) :].strip(),
                }
                current_sub["subclauses"].append(current_subsub)
                continue

            # 4. 普通内容行：拼接到最近层级
            target = current_subsub or current_sub or current_art
            if target is not None:
                if target.get("content"):
                    target["content"] += "\n" + raw_line
                else:
                    target["content"] = raw_line
            continue

        # 如果还没有任何顶层条款，就把内容视作前言，挂在一个 level=0 的虚拟条款上
        if not articles:
            current_art = {
                "level": 0,
                "number": "",
                "title": "前言",
                "content": raw_line,
                "subclauses": [],
            }
            articles.append(current_art)
        else:
            # 已有“前言”或之前的内容，继续追加
            current_art = articles[-1]
            if current_art.get("content"):
                current_art["content"] += "\n" + raw_line
            else:
                current_art["content"] = raw_line

    return articles


def _print_clauses_human_readable(articles: List[Dict[str, Any]]) -> None:
    """在终端以缩进方式打印分层条款，便于肉眼检查规则是否合适。"""

    def print_article(a: Dict[str, Any], indent: int = 0) -> None:
        prefix = " " * indent
        header = f"{a.get('number', '')} {a.get('title', '')}".strip()
        if header:
            print(f"{prefix}{header}")
        content = a.get("content", "")
        if content:
            for ln in content.splitlines():
                print(f"{prefix}  {ln}")
        for sub in a.get("subclauses", []) or []:
            print_article(sub, indent=indent + 2)

    for art in articles:
        print_article(art, indent=0)
        print("-" * 60)


def _example_text() -> str:
    """内置一个简单示例合同文本，便于直接运行观察切分效果。"""
    return """合同示例标题
甲方（出卖人）：XXXX公司
乙方（买受人）：YYYY公司

第一条 合同标的
（1）甲方同意向乙方出售如下产品：A产品、B产品等，具体数量与规格以附件清单为准。
（2）乙方同意按照本合同约定的条件向甲方购买上述产品。

第二条 价款及支付方式
1、合同总价款为人民币壹佰万元整（¥1,000,000.00），具体组成以附件为准。
2、乙方应在本合同签署之日起五个工作日内支付合同总价款的30%作为预付款，剩余价款在产品验收合格后五个工作日内一次性付清。

第三条 违约责任
一、任何一方违反本合同约定，均应承担违约责任。
二、如乙方逾期付款，每逾期一日，应按逾期金额的万分之五向甲方支付违约金。
"""

CLAUSE_MARK_PATTERNS = [
    r"^第[一二三四五六七八九十百千万〇零两]+条",       # 第一条、第二条
    r"^[一二三四五六七八九十]+、",                    # 一、 二、
    r"^[（(]\d+[)）]",                               # （1） (1)
    r"^[（(][一二三四五六七八九十]+[)）]",            # （一）
    r"^\d+([.,，]\d+)*[、.)]?",                       # 1. / 1.1 / 4,2 / 5.1.3 等
    r"^[①②③④⑤⑥⑦⑧⑨]",
    r"^[a-zA-Z][\.\)、)]",
]


def _match_marker(line: str) -> Optional[str]:
    for p in CLAUSE_MARK_PATTERNS:
        m = re.match(p, line)
        if m:
            return m.group(0)
    return None


def split_clauses_flat(full_text: str) -> List[Dict[str, Any]]:
    """
    扁平条款切分：不做分层，只按编号切出「一条一条的条款」。
    每个条款允许跨多行（后续行没有编号时视为上一条的续行）。
    """
    lines = [ln.rstrip() for ln in full_text.splitlines()]

    clauses: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    idx = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            # 空行：如果已经在某条款中，就当作内容里的换行
            if current is not None and current.get("text"):
                current["text"] += "\n"
            continue

        marker = _match_marker(line)
        if marker:
            # 遇到新的条款开头，先把上一条收尾
            if current is not None:
                clauses.append(current)

            idx += 1
            current = {
                "idx": idx,
                "marker": marker,
                "text": line[len(marker):].strip(),
            }
        else:
            # 续行：拼到当前条款
            if current is not None:
                if current.get("text"):
                    current["text"] += "\n" + raw_line
                else:
                    current["text"] = raw_line
            else:
                # 文本开头就没有编号的，按“前言”单独记一条
                idx += 1
                current = {
                    "idx": idx,
                    "marker": "",
                    "text": raw_line,
                }

    if current is not None:
        clauses.append(current)

    return clauses


def main():
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        print(f"从文件加载合同文本: {path}")
    else:
        text = _example_text()
        print("未指定文件路径，使用内置示例合同文本进行切分测试。\n")

    articles = parse_clauses(text)

    print("\n===== 分层条款结构（人类可读） =====\n")
    _print_clauses_human_readable(articles)

    # 写出 JSON 文件，方便你用编辑器查看
    out_path = "contract_split_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 结果已写入: {out_path}")


if __name__ == "__main__":
    main()


