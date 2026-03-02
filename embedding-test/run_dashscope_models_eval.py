#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量运行三个通义千问模型的评测脚本

运行三个 DashScope 模型：
- text-embedding-v3
- text-embedding-v4
- qwen3-embedding-8b

对以下数据集进行评测：
- queries.jsonl (50条检索样本)
- terms.jsonl (50条术语样本)

结果文件会自动包含样本量标注（_n50）
"""

import subprocess
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
EMBEDDINGS_DIR = PROJECT_ROOT / "embeddings"
EVAL_DIR = PROJECT_ROOT / "eval"

# 三个通义千问模型
DASHSCOPE_MODELS = [
    "text-embedding-v3",
    "text-embedding-v4",
    "qwen3-embedding-8b",
]

# 评测数据集
DATASETS = [
    ("queries.jsonl", "eval_retrieval"),
    ("terms.jsonl", "eval_terms"),
]


def find_model_file(model_name: str) -> Path | None:
    """查找模型文件，支持 civil_code_ 和 law_book_ 前缀"""
    # 优先查找 civil_code_ 前缀的文件
    civil_code_file = EMBEDDINGS_DIR / f"civil_code_{model_name}.npz"
    if civil_code_file.exists():
        return civil_code_file
    
    # 如果没有，查找 law_book_ 前缀的文件
    law_book_file = EMBEDDINGS_DIR / f"law_book_{model_name}.npz"
    if law_book_file.exists():
        return law_book_file
    
    return None


def run_eval(model_name: str, dataset_file: str, eval_type: str):
    """运行单个模型的评测"""
    model_npz = find_model_file(model_name)
    dataset_path = EVAL_DIR / dataset_file
    
    if not model_npz:
        print(f"⚠️  跳过 {model_name}：向量文件不存在（已查找 civil_code_{model_name}.npz 和 law_book_{model_name}.npz）")
        return False
    
    if not dataset_path.exists():
        print(f"⚠️  跳过 {dataset_file}：数据集文件不存在 {dataset_path}")
        return False
    
    print(f"\n{'='*80}")
    print(f"🚀 开始评测: {model_name} - {dataset_file}")
    print(f"{'='*80}")
    
    # 构建命令
    if eval_type == "eval_retrieval":
        cmd = [
            sys.executable,
            "-m", "embedding-test.eval_retrieval",
            "--model-npz", str(model_npz),
            "--dataset", str(dataset_path),
            "--top-k", "5",
        ]
    else:  # eval_terms
        cmd = [
            sys.executable,
            "-m", "embedding-test.eval_terms",
            "--model-npz", str(model_npz),
            "--dataset", str(dataset_path),
            "--top-k", "5",
        ]
    
    try:
        result = subprocess.run(cmd, check=True, cwd=PROJECT_ROOT.parent)
        print(f"✅ {model_name} - {dataset_file} 评测完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {model_name} - {dataset_file} 评测失败: {e}")
        return False


def main():
    """主函数：批量运行所有模型的评测"""
    print("="*80)
    print("📊 批量运行通义千问模型评测")
    print("="*80)
    print(f"模型列表: {', '.join(DASHSCOPE_MODELS)}")
    print(f"数据集: {', '.join([d[0] for d in DATASETS])}")
    print("="*80)
    
    success_count = 0
    total_count = len(DASHSCOPE_MODELS) * len(DATASETS)
    
    for model_name in DASHSCOPE_MODELS:
        for dataset_file, eval_type in DATASETS:
            if run_eval(model_name, dataset_file, eval_type):
                success_count += 1
    
    print("\n" + "="*80)
    print("📈 评测汇总")
    print("="*80)
    print(f"成功: {success_count}/{total_count}")
    print(f"失败: {total_count - success_count}/{total_count}")
    print("="*80)
    
    if success_count == total_count:
        print("\n🎉 所有评测任务完成！")
        return 0
    else:
        print(f"\n⚠️  有 {total_count - success_count} 个任务失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

