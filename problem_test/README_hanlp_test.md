# HanLP 长难句复杂度测试（problem_test）

本目录新增了两条可直接跑的测试链路：

- **链路 A（本地合同文本 / 已切分 chunks）**：`hanlp_dep_complexity_test.py`
- **链路 B（向量库 Chroma 中抽样片段）**：`hanlp_from_chroma_sample.py`

两条链路都会输出 `jsonl`（一行一个句子分析结果），并在终端打印 Top 10 复杂句，方便你快速人工校准阈值/权重。

## 0. 安装依赖

进入你的后端 venv 后安装：

```bash
pip install hanlp
```

> 首次运行会自动下载模型，时间取决于网络。

## 1. 链路 A：从本地 docx / chunks.json 跑 HanLP

### A1) 直接读 docx（默认 internship1.docx）

```bash
python problem_test/hanlp_dep_complexity_test.py
```

你也可以指定 docx：

```bash
python problem_test/hanlp_dep_complexity_test.py --docx E:\cp\data\contract\internship\internship1.docx
```

### A2) 直接读已切分的 chunks.json

例如你已有 `problem_test/split_results/internship1_chunks.json`：

```bash
python problem_test/hanlp_dep_complexity_test.py --chunks-json E:\cp\problem_test\split_results\internship1_chunks.json
```

常用参数：

- `--max-chunks`：最多处理多少个 chunk（默认 30）
- `--max-sents`：最多处理多少个句子（默认 200）
- `--threshold`：复杂度阈值（默认 60.0，越小越“严格”）

## 2. 链路 B：从 Chroma 向量库抽样片段跑 HanLP（不需要 embedding）

```bash
python problem_test/hanlp_from_chroma_sample.py
```

常用参数：

- `--persist-dir`：Chroma 持久化目录（默认读 `CHROMA_PERSIST_DIR`，否则 `./chroma_db`）
- `--collection`：collection 名称（默认 `legal_contracts_v2`）
- `--source-type`：过滤 `source_type`（默认 `contract`）
- `--contract-id`：过滤指定合同（>=0 生效）
- `--limit`：从库里取多少条 document（默认 50）
- `--max-sents`：最多处理多少个句子（默认 200）

示例：只分析 contract_id=123 的片段：

```bash
python problem_test/hanlp_from_chroma_sample.py --contract-id 123
```

## 3. 输出结果说明（jsonl）

输出目录：`problem_test/hanlp_results/`

每行是一个 JSON，对应一个句子，包含：

- `sentence`: 原句
- `tokens/heads/deprels`: HanLP 依存句法基础结果
- `features`: 特征（句长、树深、从句数、并列数、依存跨度等）
- `score`: 复杂度分数
- `is_complex`: 是否判为长难句
- `reasons`: 可解释原因列表（用于 UI 展示或调参）
- `metadata`: 如果来源是 chunk/向量库，会附带原有元数据（如 contract_id、chunk_index、section_title 等）

## 4. 下一步建议（你跑完这一版以后）

- 抽 Top 50 `score` 最高的句子人工判断“是否真的难”
- 调整 `hanlp_complexity_utils.py` 里的权重和 `threshold`
- 如需更贴近合同条款表达，可以增强 `split_sentences()`（例如对“若/除非/否则/在…情况下”拆子句）


