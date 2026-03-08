"""
生成对比报告
"""
import json
from pathlib import Path
from typing import List, Dict

from .config import RESULTS_DIR, TEST_CONFIGS


def load_eval_result(chunk_size: int, overlap: int) -> Dict:
    """加载评估结果"""
    file_path = RESULTS_DIR / f"eval_{chunk_size}_{overlap}.json"
    if not file_path.exists():
        return None
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_semantic_result(chunk_size: int, overlap: int) -> Dict:
    """加载语义完整性结果"""
    file_path = RESULTS_DIR / f"semantic_{chunk_size}_{overlap}.json"
    if not file_path.exists():
        return None
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def generate_html_report(all_results: List[Dict]):
    """生成HTML对比报告"""
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chunk Size 测试对比报告</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        h2 {
            color: #555;
            margin-top: 30px;
            border-left: 4px solid #4CAF50;
            padding-left: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .best {
            background-color: #d4edda;
            font-weight: bold;
        }
        .metric {
            font-family: 'Courier New', monospace;
        }
        .summary {
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <h1>Chunk Size 测试对比报告</h1>
    
    <div class="summary">
        <h2>📊 检索性能对比</h2>
        <table>
            <thead>
                <tr>
                    <th>配置</th>
                    <th>Recall@3</th>
                    <th>Recall@5</th>
                    <th>Recall@10</th>
                    <th>MRR@5</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # 找出最佳值
    best_recall_3 = max(r["metrics"]["recall@3"] for r in all_results if r.get("metrics"))
    best_recall_5 = max(r["metrics"]["recall@5"] for r in all_results if r.get("metrics"))
    best_recall_10 = max(r["metrics"]["recall@10"] for r in all_results if r.get("metrics"))
    best_mrr = max(r["metrics"]["mrr@5"] for r in all_results if r.get("metrics"))
    
    for result in all_results:
        if not result.get("metrics"):
            continue
        config_name = f"{result['chunk_size']}_{result['overlap']}"
        metrics = result["metrics"]
        
        # 标记最佳值
        recall_3_class = "best" if metrics["recall@3"] == best_recall_3 else ""
        recall_5_class = "best" if metrics["recall@5"] == best_recall_5 else ""
        recall_10_class = "best" if metrics["recall@10"] == best_recall_10 else ""
        mrr_class = "best" if metrics["mrr@5"] == best_mrr else ""
        
        html_content += f"""
                <tr>
                    <td><strong>{config_name}</strong></td>
                    <td class="metric {recall_3_class}">{metrics['recall@3']:.4f}</td>
                    <td class="metric {recall_5_class}">{metrics['recall@5']:.4f}</td>
                    <td class="metric {recall_10_class}">{metrics['recall@10']:.4f}</td>
                    <td class="metric {mrr_class}">{metrics['mrr@5']:.4f}</td>
                </tr>
"""
    
    html_content += """
            </tbody>
        </table>
    </div>
    
    <div class="summary">
        <h2>📝 语义完整性对比</h2>
        <table>
            <thead>
                <tr>
                    <th>配置</th>
                    <th>平均大小</th>
                    <th>最小大小</th>
                    <th>最大大小</th>
                    <th>句子完整性</th>
                    <th>句子截断</th>
                    <th>条款截断</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # 找出最佳句子完整性
    best_integrity = max(r.get("sentence_integrity", 0) for r in all_results if r.get("sentence_integrity") is not None)
    
    for result in all_results:
        semantic = result.get("semantic")
        if not semantic:
            continue
        
        config_name = f"{result['chunk_size']}_{result['overlap']}"
        integrity_class = "best" if semantic.get("sentence_integrity", 0) == best_integrity else ""
        
        html_content += f"""
                <tr>
                    <td><strong>{config_name}</strong></td>
                    <td class="metric">{semantic['avg_chunk_size']:.1f}</td>
                    <td class="metric">{semantic['min_chunk_size']}</td>
                    <td class="metric">{semantic['max_chunk_size']}</td>
                    <td class="metric {integrity_class}">{semantic['sentence_integrity']:.2%}</td>
                    <td class="metric">{semantic['sentence_breaks']}</td>
                    <td class="metric">{semantic['article_breaks']}</td>
                </tr>
"""
    
    html_content += """
            </tbody>
        </table>
    </div>
    
    <div class="summary">
        <h2>📈 Chunk大小分布</h2>
        <table>
            <thead>
                <tr>
                    <th>配置</th>
                    <th>0-300</th>
                    <th>300-500</th>
                    <th>500-800</th>
                    <th>800-1000</th>
                    <th>1000-1200</th>
                    <th>1200+</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for result in all_results:
        semantic = result.get("semantic")
        if not semantic:
            continue
        
        config_name = f"{result['chunk_size']}_{result['overlap']}"
        dist = semantic.get("chunk_size_distribution", {})
        
        html_content += f"""
                <tr>
                    <td><strong>{config_name}</strong></td>
                    <td>{dist.get('0-300', 0)}</td>
                    <td>{dist.get('300-500', 0)}</td>
                    <td>{dist.get('500-800', 0)}</td>
                    <td>{dist.get('800-1000', 0)}</td>
                    <td>{dist.get('1000-1200', 0)}</td>
                    <td>{dist.get('1200+', 0)}</td>
                </tr>
"""
    
    html_content += """
            </tbody>
        </table>
    </div>
    
    <div class="summary">
        <h2>💡 推荐配置</h2>
        <p>根据检索性能和语义完整性的综合评估，推荐使用以下配置：</p>
        <ul>
"""
    
    # 找出综合最佳配置
    best_config = None
    best_score = 0
    
    for result in all_results:
        if not result.get("metrics") or not result.get("semantic"):
            continue
        
        # 综合评分：检索性能权重0.7，语义完整性权重0.3
        recall_score = result["metrics"]["recall@5"] * 0.7
        integrity_score = result["semantic"]["sentence_integrity"] * 0.3
        total_score = recall_score + integrity_score
        
        if total_score > best_score:
            best_score = total_score
            best_config = result
    
    if best_config:
        config_name = f"{best_config['chunk_size']}_{best_config['overlap']}"
        html_content += f"""
            <li><strong>{config_name}</strong> - 综合评分最高</li>
            <li>检索性能: Recall@5 = {best_config['metrics']['recall@5']:.4f}</li>
            <li>语义完整性: {best_config['semantic']['sentence_integrity']:.2%}</li>
"""
    
    html_content += """
        </ul>
    </div>
    
</body>
</html>
"""
    
    return html_content


def main():
    print("=" * 60)
    print("生成对比报告")
    print("=" * 60)
    
    all_results = []
    
    for config in TEST_CONFIGS:
        chunk_size = config["chunk_size"]
        overlap = config["overlap"]
        
        eval_result = load_eval_result(chunk_size, overlap)
        semantic_result = load_semantic_result(chunk_size, overlap)
        
        if eval_result or semantic_result:
            all_results.append({
                "chunk_size": chunk_size,
                "overlap": overlap,
                "metrics": eval_result.get("metrics") if eval_result else None,
                "semantic": semantic_result if semantic_result else None,
            })
    
    if not all_results:
        print("❌ 未找到任何评估结果，请先运行 evaluate_configs.py 和 analyze_semantic.py")
        return
    
    # 生成HTML报告
    html_content = generate_html_report(all_results)
    output_file = RESULTS_DIR / "comparison_report.html"
    with output_file.open("w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ 对比报告已生成: {output_file}")
    
    # 打印简要对比
    print("\n" + "=" * 80)
    print("检索性能对比")
    print("=" * 80)
    print(f"{'配置':<15} {'Recall@3':<12} {'Recall@5':<12} {'Recall@10':<12} {'MRR@5':<12}")
    print("-" * 80)
    for result in all_results:
        if not result.get("metrics"):
            continue
        config_name = f"{result['chunk_size']}_{result['overlap']}"
        metrics = result["metrics"]
        print(f"{config_name:<15} {metrics['recall@3']:<12.4f} {metrics['recall@5']:<12.4f} "
              f"{metrics['recall@10']:<12.4f} {metrics['mrr@5']:<12.4f}")
    
    print("\n" + "=" * 80)
    print("语义完整性对比")
    print("=" * 80)
    print(f"{'配置':<15} {'平均大小':<12} {'句子完整性':<12} {'句子截断':<12} {'条款截断':<12}")
    print("-" * 80)
    for result in all_results:
        semantic = result.get("semantic")
        if not semantic:
            continue
        config_name = f"{result['chunk_size']}_{result['overlap']}"
        print(f"{config_name:<15} {semantic['avg_chunk_size']:<12.1f} "
              f"{semantic['sentence_integrity']:<12.2%} {semantic['sentence_breaks']:<12} "
              f"{semantic['article_breaks']:<12}")


if __name__ == "__main__":
    main()






























