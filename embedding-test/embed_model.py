"""
对统一切分后的 chunks 进行向量化，并将结果保存为 .npz 文件（仅使用通义千问 DashScope 模型）。

用法示例（在项目根目录 e:\\cp 下）:
    # 使用通义千问 text-embedding-v3（推荐方式）
    python -m embedding-test.embed_model \\
        --model-type dashscope \\
        --model-name text-embedding-v3 \\
        --input embedding-test/data/lawbench_laws_chunks.jsonl \\
        --output embedding-test/new_embeddings/lawbench_laws_text-embedding-v3.npz

    # 向后兼容：使用 --model 参数（等价于 --model-type dashscope --model-name <model>）
    python -m embedding-test.embed_model \\
        --model text-embedding-v3 \\
        --input embedding-test/data/lawbench_laws_chunks.jsonl \\
        --output embedding-test/new_embeddings/lawbench_laws_text-embedding-v3.npz
"""

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import numpy as np

from .config import CHUNKS_PATH, EMBEDDING_DIR
from .embedders import create_embedder


def load_chunks(input_path: Path) -> Tuple[List[str], List[dict]]:
    """
    从 JSONL 中加载文本块内容及其元数据。

    返回:
        contents: List[str]      # 文本内容列表（用于向量化）
        metadatas: List[dict]    # 对应的元数据列表（与 contents 一一对应）
    """
    contents: List[str] = []
    metadatas: List[dict] = []

    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            contents.append(obj["content"])
            metadatas.append(
                {
                    "id": obj.get("id"),
                    "metadata": obj.get("metadata", {}),
                }
            )

    return contents, metadatas


def save_embeddings(
    embeddings: List[List[float]],
    metadatas: List[dict],
    output_path: Path,
    model_name: str,
) -> None:
    """
    将向量与对应元数据保存为 .npz 文件。

    说明：
        - embeddings: List[List[float]]  -> 存为 float32 的二维数组
        - metadatas: List[dict]          -> 存为 object 数组（Python dict），仅供 Python 评测脚本使用
    """
    arr = np.array(embeddings, dtype="float32")
    meta_arr = np.array(metadatas, dtype=object)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        output_path,
        embeddings=arr,
        metadatas=meta_arr,
        model=model_name,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="对统一切分后的 chunks 进行向量化，并保存为 .npz 文件"
    )
    parser.add_argument(
        "--model-type",
        type=str,
        default=None,
        choices=["dashscope"],
        help="模型类型（当前仅支持 dashscope，用于通义千问 embedding 模型）",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help=(
            "具体模型名称（可选，使用默认值 text-embedding-v3），例如：\n"
            "dashscope: text-embedding-v3, text-embedding-v2, text-embedding-v4, qwen3-embedding-8b"
        ),
    )
    # 向后兼容：保留 --model 参数
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="[已弃用，建议使用 --model-type 和 --model-name] DashScope embedding 模型名称，例如 text-embedding-v3",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(CHUNKS_PATH),
        help=(
            "输入 chunks JSONL 文件路径（默认使用 config.CHUNKS_PATH，"
            "当前指向 embedding-test/data/lawbench_laws_chunks.jsonl）"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "输出 .npz 文件路径（默认 embedding-test/embeddings/law_book_<model>.npz；"
            "LawBench 实验推荐显式指定到 embedding-test/new_embeddings/）"
        ),
    )

    args = parser.parse_args()

    # 处理向后兼容：如果只提供了 --model，则使用 dashscope 类型
    if args.model and not args.model_type:
        args.model_type = "dashscope"
        args.model_name = args.model
        print("⚠️  警告: --model 参数已弃用，建议使用 --model-type dashscope --model-name <model-name>")

    # 如果没有提供任何模型参数，报错
    if not args.model_type:
        parser.error("必须提供 --model-type 参数，或使用 --model 参数（向后兼容）")

    input_path = Path(args.input).resolve()
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        EMBEDDING_DIR.mkdir(parents=True, exist_ok=True)
        # 生成输出文件名
        model_display_name = args.model_name or args.model or args.model_type
        # 将模型名称中的特殊字符替换为下划线，避免文件名问题
        safe_name = model_display_name.replace("/", "_").replace(":", "_")
        output_path = EMBEDDING_DIR / f"law_book_{safe_name}.npz"

    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_path}")
        return

    print(f"📥 读取 chunks: {input_path}")
    contents, metadatas = load_chunks(input_path)
    if not contents:
        print("❌ 未在输入文件中找到任何文本块")
        return

    print(f"✅ 共加载 {len(contents)} 个文本块")

    # 使用工厂函数创建 embedder
    try:
        embedder = create_embedder(args.model_type, args.model_name)
    except Exception as e:
        print(f"❌ 创建 Embedder 失败: {str(e)}")
        return

    model_display_name = args.model_name or args.model or f"{args.model_type}-default"
    print(f"🚀 开始向量化，模型: {model_display_name}")
    
    try:
        embeddings = embedder.embed_documents(contents)
    except Exception as e:
        print(f"❌ 向量化失败: {str(e)}")
        return

    if not embeddings or len(embeddings) != len(contents):
        print("❌ 向量化结果数量与输入文本数量不一致")
        return

    print(f"✅ 向量化完成，向量维度: {embedder.get_embedding_dimension()}")
    print(f"💾 开始保存到: {output_path}")
    save_embeddings(embeddings, metadatas, output_path, model_name=model_display_name)
    print(f"🎉 已保存向量文件: {output_path}")


if __name__ == "__main__":
    main()


