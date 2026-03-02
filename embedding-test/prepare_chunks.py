"""
从 Law-Book 读取 Markdown 法律条文，统一使用 LawTextSplitter 切分并导出为 JSONL。

用法示例（在项目根目录 e:\\cp 下）:
    # 1) 统一为 LawBench 涉及的所有法律生成 chunks：
    #    （先在 Law-Book 中筛选出 LawBench 相关法律到某个目录，如 Law-Book-lawbench/）
    python -m embedding-test.prepare_chunks \\
        --law-book-dir Law-Book-lawbench \\
        --output embedding-test/data/lawbench_laws_chunks.jsonl \\
        --chunk-size 800 \\
        --chunk-overlap 100

    # 2) 仅针对民法典生成 chunks（向后兼容示例）：
    python -m embedding-test.prepare_chunks \\
        --law-book-dir Law-Book/3-民法典 \\
        --output embedding-test/data/civil_code_chunks.jsonl \\
        --chunk-size 800 \\
        --chunk-overlap 100
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

from .config import PROJECT_ROOT, LAW_BOOK_DIR, CHUNKS_PATH


def add_backend_to_path() -> None:
    """
    将 backend 目录添加到 sys.path，便于导入 app.services 下的工具类。
    不修改原有 backend 代码，仅作为本地实验脚本的依赖注入。
    """
    backend_path = PROJECT_ROOT / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


def scan_markdown_files(directory: Path) -> list[Path]:
    """递归扫描目录下的所有 Markdown 文件"""
    markdown_files: list[Path] = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith((".md", ".markdown")):
                markdown_files.append(Path(root) / file)
    return sorted(markdown_files)


def iter_chunks_from_files(
    markdown_files: Iterable[Path],
    chunk_size: int,
    chunk_overlap: int,
    base_dir: Path,
) -> Iterable[dict]:
    """
    对给定的 Markdown 文件列表进行解析与切分，产出统一格式的 chunk 记录。
    
    业务逻辑：
    - 使用 LawTextSplitter 进行文本切分，保持与线上服务一致的切分策略
    - 生成全局唯一的 chunk_id，格式为 source_name#chunk_index
    - 保留完整的 metadata 信息，包括 source_name、source_type、chunk_index 等
    - 确保每个 chunk 都能追溯到原始文件和位置
    
    技术实现：
    - 使用 DocumentParser 解析 Markdown 文件，提取纯文本内容
    - 使用 LawTextSplitter 进行智能切分，考虑法律条文的语义边界
      * 先按 Markdown 标题层级切分（保持章节结构）
      * 对超长块，优先在条款边界（"第X条"）处切分，保持条款语义完整性
      * 如果单个条款仍超长，再按句号、分号等标点切分
    - 通过相对路径计算 source_name，确保跨平台兼容性（使用 / 分隔符）
    - 使用生成器模式，避免一次性加载所有文件到内存
    
    返回元素格式：
        {
            "id": str,              # 全局唯一 id（基于相对路径 + chunk_index）
            "content": str,         # 文本内容
            "metadata": dict        # LawTextSplitter 生成的元数据 + chunk_index + source_path
        }
    
    Args:
        markdown_files: Markdown 文件路径列表
        chunk_size: 每个文本块的最大字符数
        chunk_overlap: 相邻文本块的重叠字符数
        base_dir: 基础目录，用于计算相对路径（source_name）
    
    Yields:
        dict: 包含 id、content、metadata 的 chunk 记录
    """
    # 延迟导入 backend 依赖
    add_backend_to_path()
    from app.services.document_parser import DocumentParser  # type: ignore
    from app.services.text_splitter import LawTextSplitter  # type: ignore

    parser = DocumentParser()
    # LawTextSplitter 内部会统一使用 chunk_size=800, chunk_overlap=100, min_chunk_size=50
    # 这里通过参数保持与线上配置一致（默认 800 / 100，min_chunk_size 固定为 50）
    splitter = LawTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    global_chunk_index = 0

    for file_path in markdown_files:
        print(f"处理文件: {file_path}")
        text = parser.parse(str(file_path), file_type="md")
        if not text.strip():
            print("  ⚠️ 文件内容为空，跳过")
            continue

        # 以 Law-Book 下的相对路径作为 source_name
        relative_path = file_path.relative_to(base_dir)
        source_name = str(relative_path).replace("\\", "/")

        chunks = splitter.split_with_metadata(
            text=text,
            source_name=source_name,
            source_type="legal",
        )

        if not chunks:
            print("  ⚠️ 切分结果为空，跳过")
            continue

        for local_idx, chunk in enumerate(chunks):
            # chunk 结构: {"content": str, "metadata": {...}}
            metadata = dict(chunk.get("metadata", {}))
            metadata.setdefault("source_name", source_name)
            metadata.setdefault("source_type", "legal")
            metadata["chunk_index"] = local_idx

            # 构造全局唯一 id：source_name#chunk_index
            chunk_id = f"{source_name}#{local_idx}"

            yield {
                "id": chunk_id,
                "content": chunk["content"],
                "metadata": metadata,
            }

            global_chunk_index += 1


def write_jsonl(records: Iterable[dict], output_path: Path) -> int:
    """
    将记录按行写入 JSONL 文件，返回写入条数。
    
    业务逻辑：
    - 使用 JSONL 格式（每行一个 JSON 对象），便于流式处理和增量加载
    - 确保 JSON 输出不转义中文字符（ensure_ascii=False），保持可读性
    
    技术实现：
    - 使用生成器模式，逐条写入，避免一次性加载所有记录到内存
    - 使用 UTF-8 编码，确保中文字符正确保存
    - 返回写入的记录数，便于统计和验证
    
    Args:
        records: 待写入的记录迭代器
        output_path: 输出文件路径
    
    Returns:
        int: 写入的记录条数
    """
    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    """
    主函数：从法律条文目录读取 Markdown 文件，切分后导出为 JSONL。

    业务逻辑：
    - 默认仍指向民法典目录（Law-Book/3-民法典/），以兼容早期仅民法典的实验
    - 实际 LawBench 评测时，推荐先将 LawBench 涉及的所有法律收集到单独目录（如 Law-Book-lawbench/），
      再通过 --law-book-dir 和 --output 指定，生成统一的 lawbench_laws_chunks.jsonl
    - 切分参数统一为：chunk_size=800, chunk_overlap=100, min_chunk_size=50，
      与线上服务的 LawTextSplitter 保持一致

    技术实现：
    - 使用 LawTextSplitter 进行文本切分，保持与线上服务一致的切分策略
      * 先按 Markdown 标题层级切分，再对超长块使用条款边界优先的递归切分
    - 生成全局唯一的 chunk_id，格式为 source_name#chunk_index
    - 保留完整的 metadata 信息，包括 source_name、source_type、chunk_index、sub_chunk_index 等
    """
    parser = argparse.ArgumentParser(
        description="从 Law-Book 读取并用 LawTextSplitter 切分后导出为 JSONL"
    )
    # 默认只读取民法典目录，聚焦民法典相关的向量化评测
    default_civil_code_dir = LAW_BOOK_DIR / "3-民法典"
    parser.add_argument(
        "--law-book-dir",
        type=str,
        default=str(default_civil_code_dir),
        help="法律条文 Markdown 根目录（默认使用 Law-Book/3-民法典/，仅处理民法典内容）",
    )
    # 输出文件名默认仍为 civil_code_chunks.jsonl（向后兼容），
    # LawBench 实验推荐显式指定为 lawbench_laws_chunks.jsonl
    default_output = PROJECT_ROOT / "embedding-test" / "data" / "civil_code_chunks.jsonl"
    parser.add_argument(
        "--output",
        type=str,
        default=str(default_output),
        help="输出 JSONL 文件路径（默认 embedding-test/data/civil_code_chunks.jsonl）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="每个文本块的最大字符数（默认 800，与线上配置保持一致）",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="相邻文本块的重叠字符数（默认 100，与线上配置保持一致）",
    )

    args = parser.parse_args()

    law_book_dir = Path(args.law_book_dir).resolve()
    output_path = Path(args.output).resolve()

    if not law_book_dir.exists():
        print(f"❌ Law-Book 目录不存在: {law_book_dir}")
        return

    print(f"📂 Law-Book 根目录: {law_book_dir}")
    print(f"📤 输出文件: {output_path}")
    print(f"   chunk_size={args.chunk_size}, chunk_overlap={args.chunk_overlap}")

    markdown_files = scan_markdown_files(law_book_dir)
    if not markdown_files:
        print("❌ 未找到任何 Markdown 文件")
        return

    print(f"✅ 共找到 {len(markdown_files)} 个 Markdown 文件，开始切分...")

    records = iter_chunks_from_files(
        markdown_files=markdown_files,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        base_dir=law_book_dir,
    )

    count = write_jsonl(records, output_path)
    print(f"✅ 完成！共导出 {count} 个文本块到 {output_path}")


if __name__ == "__main__":
    main()


