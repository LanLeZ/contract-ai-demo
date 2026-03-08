import json
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import sys


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

# 确保可以直接 import 同目录下的 contract_splitter_test
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from contract_splitter_test import split_clauses_flat  # type: ignore  # noqa: E402


def docx_to_text(docx_path: Path) -> str:
    """从 .docx 中抽取纯文本（简单版），按段落换行。"""
    with zipfile.ZipFile(docx_path) as z:
        xml_bytes = z.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs = []
    for p in root.findall(".//w:p", ns):
        texts = [t.text for t in p.findall(".//w:t", ns) if t.text]
        if texts:
            paragraphs.append("".join(texts))

    return "\n".join(paragraphs)


def run_for_docx(docx_rel_path: str, out_json_name: str) -> None:
    docx_path = PROJECT_ROOT / docx_rel_path
    if not docx_path.exists():
        print(f"[WARN] 文件不存在: {docx_path}")
        return

    print(f"\n===== 处理文档: {docx_path} =====")
    text = docx_to_text(docx_path)
    # articles = parse_clauses(text)
    clauses = split_clauses_flat(text)

    out_path = BASE_DIR / out_json_name
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(clauses, f, ensure_ascii=False, indent=2)
    print(f"分条结果已写入: {out_path}")

    # 简要打印顶层条款，方便肉眼看看水准
    print("\n--- 顶层条款预览 ---")
    for art in clauses:
        if art.get("level") == 1:
            num = (art.get("number") or "").strip()
            title = (art.get("title") or "").strip()
            header = f"{num} {title}".strip()
            print(f"- {header}")


def main() -> None:
    # 实习协议
    run_for_docx(
        r"data/contract/internship/internship1.docx",
        "internship1_split.json",
    )

    # 租赁合同
    run_for_docx(
        r"data/contract/lease/lease2.docx",
        "lease2_split.json",
    )


if __name__ == "__main__":
    main()









