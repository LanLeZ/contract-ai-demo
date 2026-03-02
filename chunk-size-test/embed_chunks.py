"""
为不同配置的chunks进行向量化
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np

from .config import PROJECT_ROOT, DATA_DIR, EMBEDDING_DIR, TEST_CONFIGS


def add_backend_to_path():
    backend_path = PROJECT_ROOT / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


def embed_chunks_for_config(chunk_size: int, overlap: int):
    """为指定配置的chunks进行向量化"""
    add_backend_to_path()
    from app.services.embedding import DashScopeEmbedder
    
    chunks_file = DATA_DIR / f"chunks_{chunk_size}_{overlap}.jsonl"
    if not chunks_file.exists():
        print(f"❌ Chunks文件不存在: {chunks_file}")
        return
    
    # 加载chunks
    contents = []
    metadatas = []
    ids = []
    
    print(f"📥 加载chunks: {chunks_file}")
    with chunks_file.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            contents.append(obj["content"])
            metadatas.append(obj["metadata"])
            ids.append(obj["id"])
    
    print(f"   共 {len(contents)} 个chunks")
    
    # 向量化
    embedder = DashScopeEmbedder()
    print(f"🚀 开始向量化（模型: {embedder.model}）...")
    embeddings = embedder.embed_documents(contents)
    
    # 保存
    output_file = EMBEDDING_DIR / f"chunks_{chunk_size}_{overlap}.npz"
    np.savez_compressed(
        output_file,
        embeddings=np.array(embeddings, dtype="float32"),
        ids=np.array(ids, dtype="object"),
        metadatas=np.array(metadatas, dtype="object"),
        model_name=embedder.model,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    
    print(f"✅ 向量化完成，保存到: {output_file}")
    print(f"   向量维度: {len(embeddings[0]) if embeddings else 0}")


def main():
    parser = argparse.ArgumentParser(description="为不同配置的chunks进行向量化")
    parser.add_argument(
        "--config",
        type=str,
        help="配置名称，如 '500_50'，不指定则处理所有配置"
    )
    args = parser.parse_args()
    
    if args.config:
        try:
            chunk_size, overlap = map(int, args.config.split("_"))
            embed_chunks_for_config(chunk_size, overlap)
        except ValueError:
            print(f"❌ 配置格式错误，应为 'chunk_size_overlap'，如 '500_50'")
    else:
        print("=" * 60)
        print("为所有配置进行向量化")
        print("=" * 60)
        for config in TEST_CONFIGS:
            embed_chunks_for_config(
                chunk_size=config["chunk_size"],
                overlap=config["overlap"]
            )
            print()


if __name__ == "__main__":
    main()
