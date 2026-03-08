import os
import sys
import json
import difflib
from typing import Dict, List

# 把项目根目录 E:\cp 和 backend 目录加到 sys.path（和 demo_split_contract.py 保持一致）
# 当前文件在 problem_test/compare_test/ 下面，所以需要向上三级到项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
for p in (BASE_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.services.contract_splitter import ContractTextSplitter


def build_marker_map(chunks: List[Dict]) -> Dict[str, str]:
    """
    根据 split_with_metadata 的结果，构建:
        clause_marker -> 合并后的内容文本
    简单策略：如果同一个 marker 对应多个 chunk，就按换行拼接。
    """
    marker_map: Dict[str, List[str]] = {}

    for c in chunks:
        content = (c.get("content") or "").strip()
        meta = c.get("metadata") or {}
        marker = meta.get("clause_marker") or ""

        # 如果没有条款编号，可以选择跳过或单独处理，这里先跳过
        if not marker:
            continue

        marker_map.setdefault(marker, []).append(content)

    # 合并为单个字符串
    merged: Dict[str, str] = {
        m: "\n".join(parts) for m, parts in marker_map.items()
    }
    return merged


def diff_clause_text(old_text: str, new_text: str) -> List[str]:
    """
    对两段条款文本做 diff，返回逐行 diff 结果（列表形式，方便保存 JSON）
    你也可以换成 ndiff / HtmlDiff 等其它形式。
    """
    old_lines = old_text.splitlines(keepends=False)
    new_lines = new_text.splitlines(keepends=False)

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            lineterm="",
        )
    )
    return diff_lines


def compare_two_texts(text_a: str, text_b: str, output_path: str) -> None:
    """
    核心函数：
    1. 用 ContractTextSplitter 切分 text_a / text_b
    2. 用 clause_marker 对齐
    3. 找出缺失/新增/内容不同的条款
    4. 把结果保存到 JSON 文件，并在终端打印概要
    """
    splitter = ContractTextSplitter(
        chunk_size=200,
        chunk_overlap=60,
        min_chunk_size=1, 
    )

    # 1) 切分
    chunks_a = splitter.split_with_metadata(
        text=text_a,
        source_name="text_a",
        side="A",
    )
    chunks_b = splitter.split_with_metadata(
        text=text_b,
        source_name="text_b",
        side="B",
    )

    print(f"[INFO] text_a 切出 {len(chunks_a)} 个 chunk")
    print(f"[INFO] text_b 切出 {len(chunks_b)} 个 chunk")

    # 2) 构建 marker -> text 映射
    markers_a = build_marker_map(chunks_a)
    markers_b = build_marker_map(chunks_b)

    set_a = set(markers_a.keys())
    set_b = set(markers_b.keys())

    only_in_a = sorted(list(set_a - set_b))
    only_in_b = sorted(list(set_b - set_a))
    in_both = sorted(list(set_a & set_b))

    print(f"[INFO] 只在 A 中存在的条款数: {len(only_in_a)}")
    print(f"[INFO] 只在 B 中存在的条款数: {len(only_in_b)}")
    print(f"[INFO] 双方共有的条款数: {len(in_both)}")

    # 3) 对共有条款，比较内容并做 diff
    changed_clauses = []
    for marker in in_both:
        a_text = markers_a.get(marker, "")
        b_text = markers_b.get(marker, "")

        if a_text == b_text:
            continue  # 内容完全一致，跳过

        diff_lines = diff_clause_text(a_text, b_text)
        changed_clauses.append(
            {
                "clause_marker": marker,
                "text_a": a_text,
                "text_b": b_text,
                "diff": diff_lines,
            }
        )

    print(f"[INFO] 内容有差异的共有条款数: {len(changed_clauses)}")

    # 4) 组织结果并写入文件
    result = {
        "summary": {
            "only_in_a_count": len(only_in_a),
            "only_in_b_count": len(only_in_b),
            "in_both_count": len(in_both),
            "changed_in_both_count": len(changed_clauses),
        },
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
        "changed_clauses": changed_clauses,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[INFO] 对比结果已写入: {output_path}")


def main():
    """
    从 compare_test 目录下的 testa.txt / textb.txt 读取两个合同文本进行对比。
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path_a = os.path.join(base_dir, "testa.txt")
    path_b = os.path.join(base_dir, "textb.txt")

    with open(path_a, "r", encoding="utf-8") as fa:
        text_a = fa.read()
    with open(path_b, "r", encoding="utf-8") as fb:
        text_b = fb.read()

    # 结果文件放在 problem_test 目录下
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "contract_compare_by_clause_marker_result.json",
    )

    compare_two_texts(text_a, text_b, output_path)


if __name__ == "__main__":
    main()