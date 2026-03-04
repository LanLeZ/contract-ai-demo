# Chunk Size 测试方案

## 概述

本测试方案用于评估不同 `chunk_size` 和 `overlap` 配置对检索性能和语义完整性的影响。

## 测试文件

- 民法典.md（约4576行）
- 合伙企业法.md（约475行）
- 食品安全法.md（约895行）
- 宪法.md（约785行）

## 测试配置

- `chunk_size=500, overlap=50`
- `chunk_size=800, overlap=100`
- `chunk_size=1000, overlap=100`
- `chunk_size=1200, overlap=150`

## 使用步骤

### 1. 准备chunks

为所有配置生成chunks文件：

```bash
cd E:\cp
python -m chunk-size-test.prepare_chunks
```

输出文件保存在 `chunk-size-test/data/` 目录下，格式为 `chunks_{chunk_size}_{overlap}.jsonl`。

### 2. 向量化chunks

为所有配置的chunks进行向量化：

```bash
python -m chunk-size-test.embed_chunks
```

或者为单个配置向量化：

```bash
python -m chunk-size-test.embed_chunks --config 500_50
```

输出文件保存在 `chunk-size-test/embeddings/` 目录下，格式为 `chunks_{chunk_size}_{overlap}.npz`。

**注意**：向量化需要调用API，可能需要一些时间。确保已配置好 `.env` 文件中的 `EMBEDDING_API_KEY` 或 `DASHSCOPE_API_KEY`。

### 3. 评估检索性能

评估所有配置的检索性能：

```bash
python -m chunk-size-test.evaluate_configs
```

评估结果保存在 `chunk-size-test/results/` 目录下，格式为 `eval_{chunk_size}_{overlap}.json`。

评估指标：
- Recall@K (K=3, 5, 10)：前K个结果中命中相关文档的比例
- MRR@K：平均倒数排名

### 4. 分析语义完整性

分析所有配置的语义完整性：

```bash
python -m chunk-size-test.analyze_semantic
```

分析结果保存在 `chunk-size-test/results/` 目录下，格式为 `semantic_{chunk_size}_{overlap}.json`。

分析指标：
- 平均chunk大小
- 句子完整性：chunk在句子边界结束的比例
- 句子截断数：在句子中间截断的chunk数量
- 条款截断数：在条款中间截断的chunk数量
- Chunk大小分布

### 5. 生成对比报告

生成HTML格式的对比报告：

```bash
python -m chunk-size-test.compare_results
```

报告保存在 `chunk-size-test/results/comparison_report.html`，可以在浏览器中打开查看。

## 评估指标说明

### 检索性能指标

- **Recall@K**：在前K个检索结果中，至少包含一个相关文档的查询比例。值越高越好。
- **MRR@K**：平均倒数排名，衡量相关文档的平均排名。值越高越好。

### 语义完整性指标

- **句子完整性**：chunk在句子边界（。！？；）结束的比例。值越高越好。
- **句子截断**：在句子中间截断的chunk数量。值越低越好。
- **条款截断**：在条款（"第X条"）中间截断的chunk数量。值越低越好。

## 结果解读

1. **检索性能**：关注 Recall@5 和 MRR@5，这两个指标最能反映实际检索效果。
2. **语义完整性**：关注句子完整性，值应尽可能高（>90%）。
3. **综合评估**：需要平衡检索性能和语义完整性，选择综合评分最高的配置。

## 注意事项

1. 确保已安装所有依赖：
   ```bash
   pip install numpy dashscope
   ```

2. 确保 `.env` 文件配置正确，包含：
   - `EMBEDDING_API_KEY` 或 `DASHSCOPE_API_KEY`
   - `EMBEDDING_MODEL`（可选，默认使用 qwen3-embedding-8b）

3. 向量化过程可能需要较长时间，请耐心等待。

4. 如果某个配置的评估失败，检查：
   - chunks文件是否存在
   - 向量文件是否存在
   - 查询数据集是否存在

## 文件结构

```
chunk-size-test/
├── __init__.py
├── config.py                    # 配置和路径
├── prepare_chunks.py            # 准备不同配置的chunks
├── embed_chunks.py              # 向量化chunks
├── evaluate_configs.py         # 评估不同配置
├── analyze_semantic.py          # 语义完整性分析
├── compare_results.py           # 对比报告生成
├── README.md                    # 使用说明
├── data/                        # 测试数据
│   ├── chunks_500_50.jsonl
│   ├── chunks_800_100.jsonl
│   ├── chunks_1000_100.jsonl
│   └── chunks_1200_150.jsonl
├── embeddings/                  # 向量文件
│   ├── chunks_500_50.npz
│   ├── chunks_800_100.npz
│   ├── chunks_1000_100.npz
│   └── chunks_1200_150.npz
└── results/                     # 评估结果
    ├── eval_500_50.json
    ├── eval_800_100.json
    ├── eval_1000_100.json
    ├── eval_1200_150.json
    ├── semantic_500_50.json
    ├── semantic_800_100.json
    ├── semantic_1000_100.json
    ├── semantic_1200_150.json
    └── comparison_report.html
```



















