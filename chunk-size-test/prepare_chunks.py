"""
为不同chunk配置准备测试数据
"""
import json
import sys
from pathlib import Path
from typing import Iterable

from .config import (
    PROJECT_ROOT, DATA_DIR, LAW_BOOK_DIR, TEST_FILES, TEST_CONFIGS
)


def add_backend_to_path():
    """将 backend 目录添加到 sys.path"""
    backend_path = PROJECT_ROOT / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


def prepare_chunks_for_config(chunk_size: int, overlap: int) -> int:
    """
    为指定配置准备chunks
    
    Args:
        chunk_size: chunk大小
        overlap: chunk重叠大小
    
    Returns:
        生成的chunk数量
    """
    add_backend_to_path()
    from app.services.document_parser import DocumentParser
    from app.services.text_splitter import LawTextSplitter
    
    parser = DocumentParser()
    splitter = LawTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    
    output_file = DATA_DIR / f"chunks_{chunk_size}_{overlap}.jsonl"
    count = 0
    
    with output_file.open("w", encoding="utf-8") as f:
        for file_rel_path in TEST_FILES:
            file_path = LAW_BOOK_DIR / file_rel_path
            if not file_path.exists():
                print(f"⚠️  文件不存在: {file_path}")
                continue
            
            print(f"处理: {file_rel_path}")
            text = parser.parse(str(file_path), file_type="md")
            if not text.strip():
                print(f"  ⚠️  文件内容为空，跳过")
                continue
            
            source_name = file_rel_path.replace("\\", "/")
            chunks = splitter.split_with_metadata(
                text=text,
                source_name=source_name,
                source_type="legal",
            )
            
            if not chunks:
                print(f"  ⚠️  切分结果为空，跳过")
                continue
            
            for local_idx, chunk in enumerate(chunks):
                metadata = dict(chunk.get("metadata", {}))
                metadata.setdefault("source_name", source_name)
                metadata.setdefault("source_type", "legal")
                metadata["chunk_index"] = local_idx
                
                chunk_id = f"{source_name}#{local_idx}"
                
                record = {
                    "id": chunk_id,
                    "content": chunk["content"],
                    "metadata": metadata,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
    
    print(f"✅ 配置 chunk_size={chunk_size}, overlap={overlap}: 共生成 {count} 个chunks")
    return count


def main():
    """为所有配置准备chunks"""
    print("=" * 60)
    print("准备不同配置的chunks")
    print("=" * 60)
    
    for config in TEST_CONFIGS:
        prepare_chunks_for_config(
            chunk_size=config["chunk_size"],
            overlap=config["overlap"]
        )
        print()


if __name__ == "__main__":
    main()
