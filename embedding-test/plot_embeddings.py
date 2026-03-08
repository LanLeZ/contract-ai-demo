"""
语义分布可视化脚本

将指定模型的 Law-Book 向量降维到 2D 并绘制散点图：
- 不同法律门类（根据 source_name 的顶级目录）使用不同颜色
- 支持对多个模型生成对子图，方便横向对比

用法示例：
    python -m embedding-test.plot_embeddings \\
        --models embedding-test/embeddings/law_book_text-embedding-v3.npz \\
                 embedding-test/embeddings/law_book_text-embedding-v2.npz \\
        --max-points 3000 \\
        --output embedding-test/plots/law_book_tsne.png
"""

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from sklearn.manifold import TSNE

from .config import PLOTS_DIR
from .eval_utils import load_embeddings


def infer_category(source_name: str) -> str:
    """
    根据 source_name 推断法律门类：
    - 例如 "1-宪法/宪法.md" -> "1-宪法"
    - 例如 "4-行政法/行政处罚法.md" -> "4-行政法"
    """
    if not source_name:
        return "unknown"
    return source_name.split("/", 1)[0]


def prepare_points_for_model(
    npz_path: Path,
    max_points: int,
) -> Tuple[np.ndarray, List[str], str]:
    """
    从 .npz 文件中抽取最多 max_points 个样本，并返回：
        - 2D/高维向量（后续再做降维）
        - 对应的类别标签列表（法律门类）
        - 模型名称
    """
    embeddings, meta_arr, model_name = load_embeddings(npz_path)
    n = embeddings.shape[0]

    if n <= max_points:
        indices = np.arange(n)
    else:
        rng = np.random.default_rng(seed=42)
        indices = rng.choice(n, size=max_points, replace=False)

    emb_subset = embeddings[indices]
    labels: List[str] = []
    for idx in indices:
        meta = meta_arr[idx]
        md = meta["metadata"]
        source_name = md.get("source_name", "unknown")
        labels.append(infer_category(source_name))

    return emb_subset, labels, model_name


def plot_models(
    model_files: List[Path],
    max_points: int,
    output: Path,
) -> None:
    # 为每个模型准备高维点和标签
    model_data: List[Tuple[np.ndarray, List[str], str]] = []
    for npz_path in model_files:
        print(f"📥 加载模型向量: {npz_path}")
        emb_subset, labels, model_name = prepare_points_for_model(npz_path, max_points)
        print(f"   抽样点数: {emb_subset.shape[0]}, 向量维度: {emb_subset.shape[1]}")
        model_data.append((emb_subset, labels, model_name))

    # 对每个模型分别做 t-SNE（简单直接，避免不同模型空间混淆）
    n_models = len(model_data)
    fig, axes = plt.subplots(1, n_models, figsize=(6 * n_models, 5), squeeze=False)

    for col, (emb_subset, labels, model_name) in enumerate(model_data):
        ax = axes[0, col]

        print(f"🚀 t-SNE 降维中: {model_name}")
        tsne = TSNE(
            n_components=2,
            random_state=42,
            init="random",
            learning_rate="auto",
        )
        points_2d = tsne.fit_transform(emb_subset)

        # 统计类别 -> 点索引
        cat_to_indices: Dict[str, List[int]] = defaultdict(list)
        for i, cat in enumerate(labels):
            cat_to_indices[cat].append(i)

        # 为每个类别分配颜色
        categories = sorted(cat_to_indices.keys())
        cmap = plt.get_cmap("tab20")

        for i, cat in enumerate(categories):
            idxs = np.array(cat_to_indices[cat])
            color = cmap(i % 20)
            ax.scatter(
                points_2d[idxs, 0],
                points_2d[idxs, 1],
                s=5,
                alpha=0.7,
                label=cat,
                color=color,
            )

        ax.set_title(f"{model_name} ({points_2d.shape[0]} points)")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.legend(markerscale=3, fontsize=8, loc="best")

    plt.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output, dpi=200)
    print(f"✅ 已保存可视化图像: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="语义分布可视化（t-SNE）")
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        required=True,
        help="一个或多个 .npz 向量文件路径（来自 embedding-test/embed_model.py）",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=3000,
        help="每个模型最多采样多少个点做可视化（默认 3000）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PLOTS_DIR / "law_book_tsne.png"),
        help="输出图像路径（默认 embedding-test/plots/law_book_tsne.png）",
    )

    args = parser.parse_args()
    model_files = [Path(p).resolve() for p in args.models]
    output = Path(args.output).resolve()

    for p in model_files:
        if not p.exists():
            print(f"❌ 模型向量文件不存在: {p}")
            return

    plot_models(
        model_files=model_files,
        max_points=args.max_points,
        output=output,
    )


if __name__ == "__main__":
    main()































