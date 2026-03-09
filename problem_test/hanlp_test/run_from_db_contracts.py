"""
HanLP 依存句法 + 长难句复杂度测试（从数据库 contracts 表读取 file_content）

前置条件：
- 本地可连接 MySQL（配置来自项目根目录 .env 的 MYSQL_*）
- 已安装 pymysql（后端通常已装）

输出：
- problem_test/hanlp_test/results/hanlp_dep_complexity_db_contracts_*.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

from complexity_utils import split_sentences, score_sentence_complexity, ComplexityConfig
from hanlp_dep import lazy_load_hanlp_dep, parse_dep


def _fetch_contracts(
    *,
    contract_id: Optional[int],
    user_id: Optional[int],
    limit: int,
) -> List[Dict[str, Any]]:
    """
    直接用 PyMySQL 读 contracts 表，避免引入后端依赖（FastAPI/Pydantic/SQLAlchemy）。
    MySQL 配置来自项目根目录 .env：MYSQL_USER / MYSQL_PASSWORD / MYSQL_HOST / MYSQL_PORT / MYSQL_DATABASE
    """
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError as e:
        raise ImportError("缺少依赖 python-dotenv，请先 pip install python-dotenv") from e

    load_dotenv(dotenv_path=REPO_ROOT / ".env")

    import os

    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "password")
    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_database = os.getenv("MYSQL_DATABASE", "contract_ai")

    try:
        import pymysql  # type: ignore
    except ImportError as e:
        raise ImportError("缺少依赖 pymysql，请先 pip install pymysql") from e

    conn = pymysql.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database,
        port=mysql_port,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        where = []
        params: List[Any] = []
        if contract_id is not None:
            where.append("id=%s")
            params.append(int(contract_id))
        if user_id is not None:
            where.append("user_id=%s")
            params.append(int(user_id))
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        sql = (
            "SELECT id, user_id, filename, contract_type, file_content, upload_time "
            "FROM contracts"
            f"{where_sql} "
            "ORDER BY upload_time DESC "
            "LIMIT %s"
        )
        params.append(int(limit))

        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
        return rows
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract-id", type=int, default=-1, help="只分析某一份合同（>=0 生效）")
    ap.add_argument("--user-id", type=int, default=-1, help="只拉某个用户的合同（>=0 生效）")
    ap.add_argument("--limit", type=int, default=10, help="最多拉多少份合同（默认 10）")
    ap.add_argument(
        "--max-sents-per-contract",
        type=int,
        default=200,
        help="每份合同最多处理多少句（避免太慢）",
    )
    ap.add_argument("--threshold", type=float, default=60.0, help="复杂度阈值")
    ap.add_argument(
        "--hanlp-dep-model",
        type=str,
        default="",
        help="可选：指定 HanLP dep 模型名（留空用默认 CTB7）",
    )
    args = ap.parse_args()

    contract_id = args.contract_id if args.contract_id >= 0 else None
    user_id = args.user_id if args.user_id >= 0 else None

    try:
        contracts = _fetch_contracts(contract_id=contract_id, user_id=user_id, limit=args.limit)
    except Exception as e:
        print("从数据库读取 contracts 失败。请检查：MySQL 是否可连、.env 的 MYSQL_* 配置、pymysql 是否安装。")
        print(f"错误：{e!r}")
        return

    if not contracts:
        print("没有查询到任何合同记录。请检查：过滤条件或数据库里是否有数据。")
        return

    dep = lazy_load_hanlp_dep(args.hanlp_dep_model or None)
    cfg = ComplexityConfig(threshold=float(args.threshold))

    results: List[Dict[str, Any]] = []
    for c in contracts:
        text = (c.get("file_content") or "").strip()
        if not text:
            continue

        sents = split_sentences(text)
        sents = sents[: max(int(args.max_sents_per_contract), 1)]

        for sent_idx, sent in enumerate(sents):
            parsed = parse_dep(dep, sent)
            scored = score_sentence_complexity(
                sent, parsed["tokens"], parsed["heads"], parsed["deprels"], cfg=cfg
            )
            results.append(
                {
                    "source": "db_contracts",
                    "contract_id": int(c.get("id")),
                    "user_id": int(c.get("user_id")),
                    "filename": c.get("filename"),
                    "contract_type": c.get("contract_type"),
                    "sentence_index": sent_idx,
                    "sentence": sent,
                    "tokens": parsed["tokens"],
                    "heads": parsed["heads"],
                    "deprels": parsed["deprels"],
                    **scored,
                }
            )

    out_dir = REPO_ROOT / "problem_test" / "hanlp_test" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "all"
    if user_id is not None:
        tag = f"user{user_id}"
    if contract_id is not None:
        tag = f"contract{contract_id}"
    out_path = out_dir / f"hanlp_dep_complexity_db_contracts_{tag}.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    top = sorted(results, key=lambda x: float(x.get("score", 0.0)), reverse=True)[:10]
    print(f"输出：{out_path}")
    print(f"总句子数：{len(results)}  阈值：{cfg.threshold}")
    print("\n===== Top 10 (score desc) =====")
    for i, r in enumerate(top, start=1):
        print("-" * 80)
        print(f"#{i} score={r['score']:.2f} is_complex={r['is_complex']} reasons={r.get('reasons')}")
        print(r["sentence"])


if __name__ == "__main__":
    main()


