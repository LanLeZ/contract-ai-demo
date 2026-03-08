import os
import sys
import json

from docx import Document

# demo_split_contract.py

# 把项目根目录 E:\cp 和 backend 目录加到 sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
for p in (BASE_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.services.contract_splitter import ContractTextSplitter


def load_docx_text(path: str) -> str:
    """将 .docx 合同文件加载为纯文本"""
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def main():
    # 1) 读取一份真实合同文本（这里用你的 internship1.docx）
    contract_path = os.path.join(
        BASE_DIR, "data", "contract", "internship", "internship1.docx"
    )
    text = load_docx_text(contract_path)

    splitter = ContractTextSplitter(
        chunk_size=200,      # 可以先用默认
        chunk_overlap=60,
        min_chunk_size=1,
    )

    # 2) 调用新版主接口（注意带上你线上实际用的元数据字段）
    chunks = splitter.split_with_metadata(
        text=text,
        source_name="internship1.docx",
        user_id=1,
        contract_id=123,
        contract_type="internship",   # 可选
    )

    # 3) 打印观察切分结果 & metadata
    print(f"总共切出 {len(chunks)} 个 chunk")
    for i, c in enumerate(chunks):
        print("=" * 80)
        print(f"Chunk #{i}")
        print("Metadata:", c["metadata"])
        print("- 内容预览 -")
        print(c["content"])

    # 4) 将切分结果写入文件，方便线下审查
    output_dir = os.path.join(BASE_DIR, "problem_test", "split_results")
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(contract_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_chunks.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"\n切分结果已写入文件：{output_path}")


if __name__ == "__main__":
    main()