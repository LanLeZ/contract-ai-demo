import os
import sys
import json

# law_splitter_test.py
#
# 使用 backend.app.services.legal_splitter.LegalTextSplitter
# 对 Law-Book/1-宪法/宪法.md 进行切分，并将结果保存为 JSON 文件

# 把项目根目录 E:\cp 和 backend 目录加到 sys.path
# 当前文件在 E:\cp\problem_test\legal_splitter\ 下，所以需要往上三级
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
for p in (BASE_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.services.legal_splitter import LegalTextSplitter


def load_markdown_text(path: str) -> str:
    """读取 Markdown 文件为字符串"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    # 1) 读取宪法 Markdown 文件
    law_path = os.path.join(BASE_DIR, "Law-Book", "1-宪法", "宪法.md")
    if not os.path.exists(law_path):
        raise FileNotFoundError(f"找不到宪法文件: {law_path}")

    text = load_markdown_text(law_path)

    # 2) 初始化新版法律切分器
    splitter = LegalTextSplitter(
        chunk_size=200,      # 与后端默认配置保持一致
        chunk_overlap=60,
        min_chunk_size=50,
    )

    # 3) 调用主接口进行切分（带上你线上一致的元数据字段）
    chunks = splitter.split_with_metadata(
        text=text,
        source_name="宪法.md",
        user_id=0,
        contract_id=None,
    )

    # 4) 将结果保存为 JSON 文件，方便比对和查看
    output_path = os.path.join(
        BASE_DIR,
        "problem_test",
        "legal_splitter",
        "law_split_constitution1.json",
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"总共切出 {len(chunks)} 个 chunk")
    print(f"已将结果写入: {output_path}")


if __name__ == "__main__":
    main()

