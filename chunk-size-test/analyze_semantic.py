"""
分析不同配置的语义完整性
"""
import json
import sys
import re
from pathlib import Path
from collections import Counter

from .config import PROJECT_ROOT, DATA_DIR, RESULTS_DIR, TEST_CONFIGS

# 中文句子结束符
SENTENCE_ENDINGS = ['。', '！', '？', '；', '\n\n']
# 条款模式
ARTICLE_PATTERN = re.compile(r'^第[一二三四五六七八九十百千万\d]+条')


def add_backend_to_path():
    backend_path = PROJECT_ROOT / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


def analyze_semantic_integrity(chunk_size: int, overlap: int):
    """分析语义完整性"""
    chunks_file = DATA_DIR / f"chunks_{chunk_size}_{overlap}.jsonl"
    if not chunks_file.exists():
        print(f"❌ Chunks文件不存在: {chunks_file}")
        return None
    
    # 加载chunks
    chunks = []
    with chunks_file.open("r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line.strip()))
    
    # 统计
    chunk_sizes = [len(chunk["content"]) for chunk in chunks]
    avg_size = sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0
    min_size = min(chunk_sizes) if chunk_sizes else 0
    max_size = max(chunk_sizes) if chunk_sizes else 0
    
    # 检查句子边界
    sentence_breaks = 0
    article_breaks = 0
    
    for chunk in chunks:
        content = chunk["content"]
        if not content:
            continue
        
        # 检查是否在句子中间结束
        if content[-1] not in SENTENCE_ENDINGS and content[-1] != '\n':
            sentence_breaks += 1
        
        # 检查是否在条款中间开始（简化检查）
        # 如果chunk不是以"第X条"开头，且内容中包含"第X条"，可能是在条款中间
        if not ARTICLE_PATTERN.match(content.strip()):
            # 检查内容中是否有条款标记
            if ARTICLE_PATTERN.search(content):
                # 进一步检查：如果第一个条款不在开头，可能是在条款中间开始
                first_match = ARTICLE_PATTERN.search(content)
                if first_match and first_match.start() > 0:
                    article_breaks += 1
    
    total_chunks = len(chunks)
    sentence_integrity = (total_chunks - sentence_breaks) / total_chunks if total_chunks > 0 else 0
    
    # 大小分布统计
    size_distribution = {
        "0-300": sum(1 for s in chunk_sizes if s < 300),
        "300-500": sum(1 for s in chunk_sizes if 300 <= s < 500),
        "500-800": sum(1 for s in chunk_sizes if 500 <= s < 800),
        "800-1000": sum(1 for s in chunk_sizes if 800 <= s < 1000),
        "1000-1200": sum(1 for s in chunk_sizes if 1000 <= s < 1200),
        "1200+": sum(1 for s in chunk_sizes if s >= 1200),
    }
    
    result = {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "total_chunks": total_chunks,
        "avg_chunk_size": round(avg_size, 2),
        "min_chunk_size": min_size,
        "max_chunk_size": max_size,
        "sentence_breaks": sentence_breaks,
        "sentence_integrity": round(sentence_integrity, 4),
        "article_breaks": article_breaks,
        "chunk_size_distribution": size_distribution,
    }
    
    # 保存结果
    output_file = RESULTS_DIR / f"semantic_{chunk_size}_{overlap}.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 分析完成: {output_file}")
    return result


def main():
    print("=" * 60)
    print("分析语义完整性")
    print("=" * 60)
    
    all_results = []
    for config in TEST_CONFIGS:
        result = analyze_semantic_integrity(
            chunk_size=config["chunk_size"],
            overlap=config["overlap"]
        )
        if result:
            all_results.append(result)
        print()
    
    # 打印对比
    if all_results:
        print("\n" + "=" * 80)
        print("语义完整性对比")
        print("=" * 80)
        print(f"{'配置':<15} {'平均大小':<12} {'句子完整性':<12} {'句子截断':<12} {'条款截断':<12}")
        print("-" * 80)
        for result in all_results:
            config_name = f"{result['chunk_size']}_{result['overlap']}"
            print(f"{config_name:<15} {result['avg_chunk_size']:<12.1f} "
                  f"{result['sentence_integrity']:<12.2%} {result['sentence_breaks']:<12} "
                  f"{result['article_breaks']:<12}")


if __name__ == "__main__":
    main()



















