import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user
from app.services.contract_compare import run_contract_compare

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/documents/compare",
    response_model=schemas.ContractCompareDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_compare(
    body: schemas.ContractCompareRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    创建一次合同对比任务（当前实现为同步执行对比逻辑）。
    """
    if body.left_contract_id == body.right_contract_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能选择同一份合同进行对比",
        )

    # 校验两份合同均存在且属于当前用户
    contracts: List[models.Contract] = (
        db.query(models.Contract)
        .filter(
            models.Contract.user_id == current_user.id,
            models.Contract.id.in_(
                [body.left_contract_id, body.right_contract_id],
            ),
        )
        .all()
    )

    if len(contracts) != 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在或无权限访问",
        )

    left = next(c for c in contracts if c.id == body.left_contract_id)
    right = next(c for c in contracts if c.id == body.right_contract_id)

    if not left.file_content or not right.file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有合同缺少解析后的文本内容，无法进行对比",
        )

    compare = run_contract_compare(
        db=db,
        user=current_user,
        left_contract=left,
        right_contract=right,
    )

    result: dict | None = None
    if compare.result_json:
        try:
            result = json.loads(compare.result_json)
        except Exception:  # noqa: BLE001
            logger.exception("解析对比结果 JSON 失败 compare_id=%s", compare.id)

    return schemas.ContractCompareDetail(
        id=compare.id,
        left_contract_id=compare.left_contract_id,
        right_contract_id=compare.right_contract_id,
        status=compare.status,
        created_at=compare.created_at,
        finished_at=compare.finished_at,
        result=result,
    )

@router.get(
    "/documents/compare/history",
    response_model=schemas.ContractCompareListResponse,
)
def list_contract_compare_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取当前用户的合同对比历史列表（按创建时间倒序）。
    """
    rows: List[models.ContractCompare] = (
        db.query(models.ContractCompare)
        .filter(models.ContractCompare.user_id == current_user.id)
        .order_by(models.ContractCompare.created_at.desc())
        .all()
    )

    items: List[schemas.ContractCompareSummary] = []
    for row in rows:
        items.append(
            schemas.ContractCompareSummary(
                id=row.id,
                left_contract_id=row.left_contract_id,
                right_contract_id=row.right_contract_id,
                status=row.status,
                created_at=row.created_at,
                finished_at=row.finished_at,
            ),
        )

    return schemas.ContractCompareListResponse(items=items)

@router.get(
    "/documents/compare/{compare_id}",
    response_model=schemas.ContractCompareDetail,
)
def get_contract_compare_detail(
    compare_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取某次合同对比的详细结果。
    """
    compare = (
        db.query(models.ContractCompare)
        .filter(
            models.ContractCompare.id == compare_id,
            models.ContractCompare.user_id == current_user.id,
        )
        .first()
    )

    if not compare:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该合同对比记录",
        )

    result: dict | None = None
    if compare.result_json:
        try:
            result = json.loads(compare.result_json)
        except Exception:  # noqa: BLE001
            logger.exception("解析对比结果 JSON 失败 compare_id=%s", compare.id)

    return schemas.ContractCompareDetail(
        id=compare.id,
        left_contract_id=compare.left_contract_id,
        right_contract_id=compare.right_contract_id,
        status=compare.status,
        created_at=compare.created_at,
        finished_at=compare.finished_at,
        result=result,
    )








