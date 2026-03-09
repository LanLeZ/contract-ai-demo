"""
后端条款复杂度分析功能测试脚本。

用法示例（在项目根目录 e:/cp 下，确保 backend & sentence_analyze 服务都已启动）：

    python -m problem_test.backend_complexity_test --contract-id 1 --output problem_test/results/complexity_contract1.json

脚本会：
1. 使用已有的用户 token 调用后端 /api/complexity/contracts/{id}/complexity/analyze 接口；
2. 再调用 GET /api/complexity/contracts/{id}/complexity 获取结果；
3. 将结果 JSON 写入指定输出文件。

注意：
- 需要先在 .env 中配置 TEST_USERNAME / TEST_PASSWORD 以便自动登录获取 token，
  或者手动在 --token 参数中提供一个有效的 Bearer Token。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    load_dotenv(dotenv_path=REPO_ROOT / ".env")


def get_base_url() -> str:
    """
    读取 BACKEND_BASE_URL 环境变量，默认为 http://127.0.0.1:8000
    """
    return os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def login_and_get_token() -> str:
    """
    使用 .env 中的 TEST_USERNAME / TEST_PASSWORD 登录获取 Bearer Token。
    """
    username = os.getenv("TEST_USERNAME", "")
    password = os.getenv("TEST_PASSWORD", "")
    if not username or not password:
        raise RuntimeError(
            "请在 .env 中配置 TEST_USERNAME / TEST_PASSWORD，"
            "或在命令行参数中通过 --token 提供现成的访问令牌。"
        )

    base = get_base_url()
    url = f"{base}/api/auth/login"
    data = {
        "username": username,
        "password": password,
    }
    # FastAPI OAuth2PasswordRequestForm 期望 application/x-www-form-urlencoded
    resp = requests.post(
        url,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"登录失败：HTTP {resp.status_code} {resp.text}")
    js = resp.json()
    token = js.get("access_token")
    if not token:
        raise RuntimeError("登录响应中没有 access_token 字段")
    return token


def call_analyze_complexity(
    contract_id: int,
    token: str,
    threshold: float = 100.0,
    with_llm_explain: bool = True,
) -> Dict[str, Any]:
    base = get_base_url()
    url = f"{base}/api/complexity/contracts/{contract_id}/complexity/analyze"
    params = {
        "threshold": threshold,
        "with_llm_explain": "true" if with_llm_explain else "false",
    }
    headers = {
        "Authorization": f"Bearer {token}",
    }
    resp = requests.post(url, params=params, headers=headers, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(
            f"调用 analyze 接口失败：HTTP {resp.status_code} {resp.text}"
        )
    return resp.json()


def fetch_complexity_result(contract_id: int, token: str) -> Dict[str, Any]:
    base = get_base_url()
    url = f"{base}/api/complexity/contracts/{contract_id}/complexity"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(
            f"获取复杂度结果失败：HTTP {resp.status_code} {resp.text}"
        )
    return resp.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--contract-id",
        type=int,
        required=True,
        help="要测试的合同 ID（必须已存在于 backend 数据库中）",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=100.0,
        help="复杂度阈值（传给 HanLP 服务的 complexity_threshold）",
    )
    ap.add_argument(
        "--no-llm",
        action="store_true",
        help="不调用 LLM 生成条款解释（只做 HanLP 复杂度分析）",
    )
    ap.add_argument(
        "--token",
        type=str,
        default="",
        help="可选：直接提供 Bearer Token，若不提供则用 TEST_USERNAME/TEST_PASSWORD 登录获取",
    )
    ap.add_argument(
        "--output",
        type=str,
        default="",
        help="输出结果文件路径（JSON）。默认写入 problem_test/results/contract_complexity_<id>.json",
    )
    args = ap.parse_args()

    _load_env()

    token = args.token.strip()
    if not token:
        token = login_and_get_token()

    print(f"使用合同 ID={args.contract_id}，threshold={args.threshold}，with_llm_explain={not args.no_llm}")

    # 1) 触发分析
    analyze_result = call_analyze_complexity(
        contract_id=args.contract_id,
        token=token,
        threshold=float(args.threshold),
        with_llm_explain=not args.no_llm,
    )
    print(f"分析接口返回条款数：{len(analyze_result.get('clauses') or [])}")

    # 2) 再拉取一次结果，验证持久化是否成功
    fetched = fetch_complexity_result(contract_id=args.contract_id, token=token)
    clauses = fetched.get("clauses") or []
    print(f"GET 接口返回条款数：{len(clauses)}")

    # 3) 写入输出文件
    out_path: Optional[Path]
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = (REPO_ROOT / args.output).resolve()
    else:
        out_dir = REPO_ROOT / "problem_test" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"contract_complexity_{args.contract_id}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(fetched, f, ensure_ascii=False, indent=2)

    print(f"结果已写入：{out_path}")


if __name__ == "__main__":
    main()


