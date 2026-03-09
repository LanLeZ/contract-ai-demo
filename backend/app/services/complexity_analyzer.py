"""
条款复杂度分析服务：
- 调用 sentence_analyze 子服务的 /analyze_clauses
- 复用 ContractTextSplitter 生成条款列表
- 可选地调用 LLM 为复杂条款生成解释与简化版本
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app import models
from app.services.contract_splitter import ContractTextSplitter
from app.services.llm import QwenChatClient, explain_clause_complexity_with_llm


logger = logging.getLogger(__name__)


HANLP_SERVICE_URL = os.getenv("HANLP_SERVICE_URL", "http://127.0.0.1:8001")


def _build_clauses_payload_from_text(
    full_text: str,
    source_name: str,
) -> List[Dict[str, Any]]:
    """
    使用 ContractTextSplitter 扁平切分合同，构造发送给 HanLP 服务的条款列表。
    """
    splitter = ContractTextSplitter()
    chunks = splitter.split_with_metadata(
        text=full_text,
        source_name=source_name,
    )

    clauses: List[Dict[str, Any]] = []
    for ch in chunks:
        meta = ch.get("metadata") or {}
        clauses.append(
            {
                "clause_index": int(meta.get("clause_index") or 0),
                "clause_marker": meta.get("clause_marker"),
                "text": ch.get("content") or "",
            }
        )
    # 过滤掉无效条款
    clauses = [
        c for c in clauses if c["clause_index"] is not None and str(c["text"]).strip()
    ]
    # 送去复杂度分析前，过滤掉“无编号条款”（包括签署区等，已在 splitter 中被赋予 a1/a2/...）
    # 约定：自动生成的匿名条款 marker 形如 a1/a2/...，这里统一剔除
    clauses = [
        c
        for c in clauses
        if c.get("clause_marker") and not str(c.get("clause_marker")).startswith("a")
    ]
    return clauses


async def call_hanlp_analyze_clauses(
    *,
    doc_id: str,
    full_text: str,
    source_name: str,
    complexity_threshold: float = 100.0,
) -> Dict[str, Any]:
    """
    调用 sentence_analyze 服务的 /analyze_clauses 接口。
    返回值为该服务的原始 JSON 响应。
    """
    clauses = _build_clauses_payload_from_text(full_text=full_text, source_name=source_name)
    if not clauses:
        return {
            "doc_id": doc_id,
            "config": {"threshold": complexity_threshold},
            "clauses": [],
            "high_complexity_clauses": [],
        }

    payload = {
        "doc_id": doc_id,
        "complexity_threshold": complexity_threshold,
        "clauses": clauses,
    }

    url = HANLP_SERVICE_URL.rstrip("/") + "/analyze_clauses"
    logger.info("Calling HanLP sentence_analyze service: %s", url)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def analyze_contract_complexity_and_store(
    db: Session,
    contract: models.Contract,
    *,
    threshold: float = 100.0,
    with_llm_explain: bool = True,
    qwen_client: Optional[QwenChatClient] = None,
) -> List[models.ClauseComplexity]:
    """
    对单份合同执行条款复杂度分析，并将结果写入数据库 clause_complexities 表。

    步骤：
    1. 准备合同全文（优先使用 file_content，兜底从文件路径解析）；
    2. 调用 HanLP /analyze_clauses 获取条款级复杂度结果；
    3. 清空该合同已有的 ClauseComplexity 记录；
    4. 对每条条款写入一条 ClauseComplexity 记录；
       - 若 with_llm_explain=True 且 is_complex=True，则调用 LLM 生成解释与简化版本。
    """
    # 1) 准备合同全文
    full_text = (contract.file_content or "").strip()
    if not full_text:
        # 为避免引入 DocumentParser 的重量级依赖，这里要求上传时已经填充 file_content
        # 若为空则直接返回空结果
        logger.warning(
            "Contract(id=%s) 没有 file_content，跳过复杂度分析", contract.id
        )
        # 清理旧记录
        db.query(models.ClauseComplexity).filter(
            models.ClauseComplexity.contract_id == contract.id
        ).delete(synchronize_session=False)
        db.commit()
        return []

    # 2) 调用 HanLP 服务
    hanlp_result = await call_hanlp_analyze_clauses(
        doc_id=str(contract.id),
        full_text=full_text,
        source_name=contract.filename,
        complexity_threshold=threshold,
    )

    clauses: List[Dict[str, Any]] = hanlp_result.get("clauses") or []

    # 3) 清空旧记录
    db.query(models.ClauseComplexity).filter(
        models.ClauseComplexity.contract_id == contract.id
    ).delete(synchronize_session=False)

    if not clauses:
        db.commit()
        return []

    if with_llm_explain and qwen_client is None:
        qwen_client = QwenChatClient()

    orm_items: List[models.ClauseComplexity] = []
    for clause in clauses:
        clause_index = int(clause.get("clause_index") or 0)
        clause_marker = clause.get("clause_marker")
        clause_text = clause.get("text") or ""
        score = float(clause.get("clause_complexity_score") or 0.0)
        is_complex = bool(clause.get("is_complex"))

        if not clause_text.strip():
            continue

        plain_exp: Optional[str] = None
        simplified: Optional[str] = None
        if with_llm_explain and is_complex and qwen_client is not None:
            plain_exp, simplified = explain_clause_complexity_with_llm(
                qwen_client, clause
            )

        item = models.ClauseComplexity(
            contract_id=contract.id,
            clause_index=clause_index,
            clause_marker=clause_marker,
            clause_text=clause_text,
            complexity_score=score,
            is_complex=is_complex,
            hanlp_raw_json=json.dumps(clause, ensure_ascii=False),
            llm_plain_explanation=plain_exp,
            llm_simplified_clause=simplified,
        )
        db.add(item)
        orm_items.append(item)

    db.commit()
    for it in orm_items:
        db.refresh(it)

    return orm_items


