# HanLP 句法分析 + 长难句复杂度打分（problem_test/hanlp_test）

本目录提供**可直接运行**的 HanLP 依存句法分析 + 合同句子复杂度打分流程，支持 3 种数据源：

- **本地合同文件**：读取 `docx` 并按现有切分逻辑切 chunk（复用后端 `DocumentParser` / `ContractTextSplitter`）
- **已切分 chunk 文件**：读取 `chunks.json`（例如 `problem_test/split_results/*_chunks.json`）
- **向量库 Chroma**：直接 `collection.get()` 抽样 documents（不需要 embedding）
- **数据库 contracts 表**：直接读取 `contracts.file_content`（需要本地能连接 MySQL）

输出为 `jsonl`（一行一个句子结果），位置：`problem_test/hanlp_test/results/`。

## 0) 安装依赖（强烈建议单独环境）

HanLP 的依存句法模型通常需要额外运行时（如 TensorFlow），并且**会与后端依赖（FastAPI/Pydantic2 等）产生版本冲突**（典型冲突是 TensorFlow 限制 `typing-extensions<4.6`，而 Pydantic2 需要更新版本）。

建议为本目录单独建一个 venv（示例 Windows）：

```bash
python -m venv .venv_hanlp_test
.\.venv_hanlp_test\Scripts\python -m pip install -U pip
.\.venv_hanlp_test\Scripts\pip install -r problem_test/hanlp_test/requirements_hanlp_env.txt
```

> 首次运行 HanLP 会自动下载模型，时间取决于网络。

## 重要说明：为什么你会遇到 `'<bos>'` / int 转换报错？

本目录默认使用 `CTB7_BIAFFINE_DEP_ZH`（biaffine + TensorFlow）依存句法模型。**这个模型通常不能直接接收原始字符串**，它需要带词性特征的输入（形如 `[(token, POS), ...]`）。

为避免你手动做 tok/pos，本目录的 `hanlp_dep.py` 已做了兼容：
- 若检测到加载的是 TF biaffine dep（如 CTB7），会自动 `tok → pos → dep` 再归一化输出；
- 若你改用 MTL 模型（例如同时输出 tok/pos/dep 的 joint 模型），则会直接使用其 dict 输出。

## 1) 链路 A：本地 docx / chunks.json

### A1) 直接读 docx（默认 internship1.docx）

```bash
python problem_test/hanlp_test/run_from_docx_or_chunks.py
```

指定 docx：

```bash
python problem_test/hanlp_test/run_from_docx_or_chunks.py --docx E:\cp\data\contract\internship\internship1.docx
```

### A2) 直接读已切分的 chunks.json

```bash
python problem_test/hanlp_test/run_from_docx_or_chunks.py --chunks-json E:\cp\problem_test\split_results\internship1_chunks.json
```

常用参数：
- `--max-chunks`：最多处理多少个 chunk（默认 30）
- `--max-sents`：最多处理多少个句子（默认 200）
- `--threshold`：复杂度阈值（默认 100.0）
- `--skip-clause-marker-regex`：跳过匹配该正则的 `metadata.clause_marker`（默认跳过 `a1` / `a1a2` 这类结构标记；置空则不跳过）

## 2) 链路 B：从 Chroma 向量库抽样片段（不需要 embedding）

**推荐做法（避免环境冲突）**：先在你的后端环境里导出一份 `chunks.json`，再用 HanLP 环境分析它。

1) 在后端环境（已装 chromadb）导出：

```bash
python problem_test/hanlp_test/export_chroma_docs.py --limit 50
```

2) 在 HanLP 环境里跑分析（把导出的文件当作 chunks.json 输入）：

```bash
python problem_test/hanlp_test/run_from_docx_or_chunks.py --chunks-json E:\cp\problem_test\hanlp_test\results\chroma_export_chunks.json
```

如果你确认当前环境能同时满足 HanLP 与 chromadb 依赖，也可以直接跑：

```bash
python problem_test/hanlp_test/run_from_chroma.py
```

常用参数：
- `--persist-dir`：Chroma persist dir（默认读 `CHROMA_PERSIST_DIR`，否则 `./chroma_db`）
- `--collection`：collection 名称（默认 `legal_contracts_v2`）
- `--source-type`：过滤 `source_type`（默认 `contract`）
- `--contract-id`：过滤指定合同（>=0 生效）
- `--limit`：从库里取多少条 document（默认 50）
- `--max-sents`：最多处理多少个句子（默认 200）

示例：只分析 contract_id=123 的片段：

```bash
python problem_test/hanlp_test/run_from_chroma.py --contract-id 123
```

## 3) 链路 C：从数据库 contracts 表取 file_content

```bash
python problem_test/hanlp_test/run_from_db_contracts.py --limit 10
```

常用参数：
- `--contract-id`：只分析某一份合同
- `--user-id`：只拉某个用户的合同
- `--limit`：拉多少份合同（默认 10）
- `--max-sents-per-contract`：每份合同最多处理多少句（默认 200）

> DB 连接使用后端 `backend/app/database.py` 里读取的 `.env`（`MYSQL_*`）配置。

## 4) 输出结果说明（jsonl）

每行是一个 JSON，对应一个句子，包含：
- `sentence`: 原句
- `tokens/heads/deprels`: HanLP 依存句法基础结果
- `features`: 特征（句长、树深、从句数、并列数、依存跨度、触发词命中等）
- `score`: 复杂度分数
- `is_complex`: 是否判为长难句
- `reasons`: 可解释原因列表（用于 UI 展示或调参）
- `metadata`: 来源元数据（如 contract_id / filename / chunk_index 等）

## 5) 调参建议

- 先抽 Top 50 `score` 最高的句子人工判断“是否真的难”
- 调整 `complexity_utils.py` 中的权重和 `threshold`
- 如果希望更贴近合同条款表达，可增强 `split_sentences()`（例如对“若/除非/否则/在…情况下”拆子句）


