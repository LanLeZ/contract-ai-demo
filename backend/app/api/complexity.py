from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user
from app.services.complexity_analyzer import analyze_contract_complexity_and_store


router = APIRouter()


@router.post(
    "/contracts/{contract_id}/complexity/analyze",
    response_model=schemas.ContractComplexityResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_contract_complexity(
    contract_id: int,
    threshold: float = 100.0,
    with_llm_explain: bool = True,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    触发对指定合同的条款复杂度分析。
    - 调用 HanLP sentence_analyze 服务获取条款复杂度
    - 可选：对复杂条款调用 LLM 生成解释与简化版本
    - 结果写入 clause_complexities 表并返回
    """
    contract = (
        db.query(models.Contract)
        .filter(
            models.Contract.id == contract_id,
            models.Contract.user_id == current_user.id,
        )
        .first()
    )
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )

    items = await analyze_contract_complexity_and_store(
        db,
        contract,
        threshold=threshold,
        with_llm_explain=with_llm_explain,
    )

    clauses: List[schemas.ClauseComplexityItem] = []
    for it in sorted(items, key=lambda x: (x.clause_index, x.id)):
        clauses.append(
            schemas.ClauseComplexityItem(
                clause_index=it.clause_index,
                clause_marker=it.clause_marker,
                clause_text=it.clause_text,
                complexity_score=it.complexity_score,
                is_complex=it.is_complex,
                llm_plain_explanation=it.llm_plain_explanation,
                llm_simplified_clause=it.llm_simplified_clause,
            )
        )

    return schemas.ContractComplexityResponse(
        contract_id=contract.id,
        threshold=threshold,
        clauses=clauses,
    )


@router.get(
    "/contracts/{contract_id}/complexity",
    response_model=schemas.ContractComplexityResponse,
    status_code=status.HTTP_200_OK,
)
async def get_contract_complexity(
    contract_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取指定合同已保存的条款复杂度结果。
    若尚未分析，则返回 404。
    """
    contract = (
        db.query(models.Contract)
        .filter(
            models.Contract.id == contract_id,
            models.Contract.user_id == current_user.id,
        )
        .first()
    )
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在",
        )

    rows = (
        db.query(models.ClauseComplexity)
        .filter(models.ClauseComplexity.contract_id == contract.id)
        .order_by(models.ClauseComplexity.clause_index.asc(), models.ClauseComplexity.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该合同尚未进行复杂度分析",
        )

    # 由于 threshold 信息目前只保存在 HanLP 调用时的参数中，这里无法精确还原。
    # 为保持响应字段完整，使用一个占位值 -1.0，前端可忽略或自定义展示。
    threshold = -1.0

    clauses: List[schemas.ClauseComplexityItem] = []
    for it in rows:
        clauses.append(
            schemas.ClauseComplexityItem(
                clause_index=it.clause_index,
                clause_marker=it.clause_marker,
                clause_text=it.clause_text,
                complexity_score=it.complexity_score,
                is_complex=it.is_complex,
                llm_plain_explanation=it.llm_plain_explanation,
                llm_simplified_clause=it.llm_simplified_clause,
            )
        )

    return schemas.ContractComplexityResponse(
        contract_id=contract.id,
        threshold=threshold,
        clauses=clauses,
    )


