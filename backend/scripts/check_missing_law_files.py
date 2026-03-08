"""
检查向量库中缺失的法律条文文件，并可选择只对缺失文件重新导入

用法示例：
1) 只检查哪些文件缺失：
   python scripts/check_missing_law_files.py --dir E:\cp\Law-Book

2) 检查并仅对缺失文件重新导入向量库：
   python scripts/check_missing_law_files.py --dir E:\cp\Law-Book --reimport
"""

import argparse
import os
from pathlib import Path
from typing import Set, List

import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.document_parser import DocumentParser
from app.services.text_splitter import LawTextSplitter
from app.services.vector_store import VectorStore, _lazy_import_chromadb


def scan_markdown_files(directory: Path) -> List[Path]:
    """扫描目录下的所有 Markdown 文件"""
    markdown_files: List[Path] = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith((".md", ".markdown")):
                markdown_files.append(Path(root) / file)
    return sorted(markdown_files)


def collect_source_names_from_fs(root_dir: Path) -> Set[str]:
    """
    从 Law-Book 目录收集所有相对路径形式的 source_name
    例如：'1-宪法/宪法.md'
    """
    result: Set[str] = set()
    for path in scan_markdown_files(root_dir):
        rel = path.relative_to(root_dir).as_posix()
        result.add(rel)
    return result


def collect_source_names_from_chroma(
    collection_name: str = "legal_contracts_v2",
) -> Set[str]:
    """
    从 Chroma 向量库中，收集所有 metadata.source_name（仅 source_type=legal）
    """
    chromadb, Settings, Documents, Embeddings = _lazy_import_chromadb()

    # 与 VectorStore 一致的持久化目录逻辑
    persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    client = chromadb.PersistentClient(
        path=persist_directory, settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=collection_name)

    seen: Set[str] = set()

    # 通过分页方式遍历所有 metadatas
    limit = 1000
    offset = 0

    while True:
        res = collection.get(
            where={"source_type": "legal"},
            include=["metadatas"],
            limit=limit,
            offset=offset,
        )

        ids = res.get("ids") or []
        metadatas = res.get("metadatas") or []

        if not ids:
            break

        for md in metadatas:
            if not md:
                continue
            src = md.get("source_name")
            if src:
                seen.add(src)

        offset += len(ids)

        # 安全保护：如果每次都拿不到新条目，避免死循环
        if len(ids) < limit:
            break

    return seen


def reimport_missing_files(
    root_dir: Path,
    missing_files: List[str],
    collection_name: str = "legal_contracts_v2",
):
    """
    仅对缺失的 Markdown 文件重新导入向量库
    """
    if not missing_files:
        print("✅ 没有缺失文件，无需重新导入。")
        return

    print(f"\n🚀 开始重新导入缺失文件，共 {len(missing_files)} 个")

    parser = DocumentParser()
    splitter = LawTextSplitter(chunk_size=200, chunk_overlap=60)
    vector_store = VectorStore(collection_name=collection_name)

    total_chunks = 0
    success_files = 0
    failed_files = 0

    for idx, rel_path in enumerate(sorted(missing_files), 1):
        file_path = root_dir / rel_path
        print(f"\n[{idx}/{len(missing_files)}] 处理缺失文件: {rel_path}")

        if not file_path.exists():
            print(f"  ⚠️ 文件不存在，跳过: {file_path}")
            failed_files += 1
            continue

        try:
            # 1. 解析
            text_content = parser.parse(str(file_path), file_type="md")
            if not text_content.strip():
                print("  ⚠️ 文件内容为空，跳过")
                failed_files += 1
                continue

            # 2. 切分（保持与 batch_import.py 中一致的 source_name 规则）
            source_name = rel_path.replace("\\", "/")
            chunks = splitter.split_with_metadata(
                text=text_content,
                source_name=source_name,
                source_type="legal",
            )

            if not chunks:
                print("  ⚠️ 文本切分失败，跳过")
                failed_files += 1
                continue

            # 3. 写入向量库
            chunk_count = vector_store.add_documents(chunks, batch_size=50)
            total_chunks += chunk_count
            success_files += 1
            print(f"  ✅ 成功导入 {chunk_count} 个文本块")

        except Exception as e:
            print(f"  ❌ 导入失败: {e}")
            failed_files += 1
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print("📊 缺失文件重新导入统计：")
    print(f"  成功文件数: {success_files}")
    print(f"  失败文件数: {failed_files}")
    print(f"  新增文本块数: {total_chunks}")
    print(f"  当前向量库总文档数: {vector_store.get_collection_count()}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="检查向量库中缺失的法律条文文件，并可选择只对缺失文件重新导入"
    )
    parser.add_argument(
        "--dir",
        type=str,
        required=True,
        help="Law-Book 根目录路径（例如 E:\\cp\\Law-Book）",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="legal_contracts_v2",
        help="要检查的集合名称（默认 legal_contracts_v2）",
    )
    parser.add_argument(
        "--reimport",
        action="store_true",
        help="对检测到的缺失文件执行重新导入",
    )

    args = parser.parse_args()

    root_dir = Path(args.dir)
    if not root_dir.exists():
        print(f"❌ 目录不存在: {root_dir}")
        return

    print("=" * 60)
    print(f"📂 Law-Book 目录: {root_dir}")
    print(f"📦 检查集合: {args.collection}")
    print("=" * 60)

    fs_sources = collect_source_names_from_fs(root_dir)
    print(f"📁 文件系统中 Markdown 文件数: {len(fs_sources)}")

    chroma_sources = collect_source_names_from_chroma(args.collection)
    print(f"🧠 向量库中已存在的 source_name 数: {len(chroma_sources)}")

    missing = sorted(fs_sources - chroma_sources)
    extra = sorted(chroma_sources - fs_sources)

    print("\n--- 结果对比 ---")
    print(f"❌ 向量库中缺失的文件数: {len(missing)}")
    if missing:
        for m in missing:
            print(f"   - {m}")

    print(f"\n⚠️ 向量库中存在但文件系统中不存在的 source_name 数: {len(extra)}")
    if extra:
        for e in extra:
            print(f"   - {e}")

    if args.reimport and missing:
        reimport_missing_files(root_dir, missing, args.collection)
    elif args.reimport and not missing:
        print("\n✅ 没有缺失文件，无需重新导入。")


if __name__ == "__main__":
    main()



