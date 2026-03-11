# sentence_analyze：HanLP 句法分析独立服务

本目录是为 `backend` 提供依存句法 + 句子复杂度分析的**独立 FastAPI 服务**，运行在单独的虚拟环境中，避免与主后端依赖冲突。

## 1. 创建与激活虚拟环境（示例）

建议在项目根目录下使用你已经建立好的 `venv_hanlp_test`，或新建一个专用环境：

```bash
cd e:/cp

python -m venv venv_hanlp_test
.\venv_hanlp_test\Scripts\python -m pip install -U pip
.\venv_hanlp_test\Scripts\pip install -r sentence_analyze/requirements.txt
```

> 首次运行 HanLP 会自动下载依存句法模型，时间取决于网络。

## 2. 启动服务

在激活了 `venv_hanlp_test` 的终端中：

```bash
cd e:/cp/sentence_analyze

python -m uvicorn service:app --host 0.0.0.0 --port 8001
```

或直接：

```bash
python service.py
```

默认监听 `http://127.0.0.1:8001`。

健康检查：

```bash
GET http://127.0.0.1:8001/health
```

## 3. 接口说明：POST /analyze_clauses

- URL：`POST /analyze_clauses`
- 请求体示例：

```json
{
  "doc_id": "contract_123",
  "complexity_threshold": 100.0,
  "clauses": [
    {
      "clause_index": 1,
      "clause_marker": "第一条",
      "text": "甲方应当在签署本合同之日起五个工作日内向乙方支付全部费用。"
    },
    {
      "clause_index": 2,
      "clause_marker": "第二条",
      "text": "除非双方另有约定，否则任何一方不得擅自解除本合同。"
    }
  ]
}
```

- 响应体概览：
  - `doc_id`：原样回传
  - `config.threshold`：本次使用的复杂度阈值
  - `clauses[]`：每条条款的句子级句法与复杂度结果
    - `clause_index / clause_marker / text`
    - `clause_complexity_score`：该条款内所有句子复杂度得分的最大值
    - `is_complex`：是否判定为复杂条款
    - `sentence_results[]`：条款内每个句子的
      - `sentence_text`
      - `dep.tokens / dep.heads / dep.deprels`（HanLP 依存句法输出）
      - `complexity.score / is_complex / reasons / features`
  - `high_complexity_clauses[]`：只保留判定为复杂的条款（`clause_index / clause_marker / clause_complexity_score`）

## 4. 与 backend 的协作方式（建议）

1. 在 `backend` 中保持原有虚拟环境，不安装 `hanlp` / TensorFlow。
2. 在需要句法分析的地方，将已经拆好的条款列表（含 `clause_index / clause_marker / text`）通过 HTTP POST 调用本服务的 `/analyze_clauses`。
3. 使用 `high_complexity_clauses` 快速筛选出“疑似长难句条款”，再结合 LLM 或人工进行后续处理。

这样可以做到：

- HanLP 相关的重量级依赖、模型下载全部隔离在 `sentence_analyze` 服务中。
- 主后端只依赖标准 Web 协议（HTTP + JSON），易于维护和部署。







