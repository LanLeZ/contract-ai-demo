"""
使用最新 ContractTextSplitter 规则切分 docx/txt，并把 chunks（含metadata）落盘。

用法：
  python problem_test/splitter_test/run_split_docx_new_logic.py problem_test/input_contracts/xxx.docx
  python problem_test/splitter_test/run_split_docx_new_logic.py problem_test/input_contracts/xxx.txt

输出：
  problem_test/splitter_test/split_results/new_logic_<文件名stem>_chunks.json
"""

import json
import os
import sys
from pathlib import Path


def _project_root() -> Path:
    # e:\cp\problem_test\splitter_test\run_split_docx_new_logic.py -> e:\cp
    return Path(__file__).resolve().parent.parent.parent


def _read_file_content(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8")
    if suffix == ".docx":
        try:
            from docx import Document  # type: ignore
        except ImportError as e:
            raise ImportError("缺少依赖：请先安装 python-docx（pip install python-docx）") from e
        doc = Document(str(file_path))
        return "\n".join([p.text for p in doc.paragraphs])
    raise ValueError(f"不支持的文件格式：{suffix}（仅支持 .txt/.docx）")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "请传入待切分文件路径，例如：\n"
            "  python problem_test/splitter_test/run_split_docx_new_logic.py problem_test/input_contracts/lease2.docx"
        )

    root = _project_root()
    target_path = (root / sys.argv[1]).resolve() if not Path(sys.argv[1]).is_absolute() else Path(sys.argv[1]).resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"找不到文件：{target_path}")

    # 让后端导入路径稳定（与 test_hierarchy_split.py 一致）
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "backend"))
    os.chdir(root / "backend")

    from app.services.contract_splitter import ContractTextSplitter  # noqa: E402

    text = _read_file_content(target_path)
    splitter = ContractTextSplitter(chunk_size=200, chunk_overlap=60, min_chunk_size=1)
    chunks = splitter.split_with_metadata(
        text=text,
        source_name=target_path.name,
        user_id=0,
        contract_id=0,
    )

    out_dir = root / "problem_test" / "splitter_test" / "split_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"new_logic_{target_path.stem}_chunks.json"
    out_path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"输入文件: {target_path}")
    print(f"输出文件: {out_path}")
    print(f"chunks 数量: {len(chunks)}")


if __name__ == "__main__":
    main()

