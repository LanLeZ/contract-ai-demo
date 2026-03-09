from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services.kg_extractor import extract_kg_for_contract

router = APIRouter()


@router.post(
    "/contracts/{contract_id}/kg-extract",
    response_model=schemas.KGExtractResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_contract_kg(
    contract_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    对指定合同执行：分类 + 根据模板抽取知识图谱三元组。
    - 过滤掉 head 或 tail 为空的三元组，不入库
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

    contract_type, triples = extract_kg_for_contract(db, contract)

    return schemas.KGExtractResponse(
        contract_id=contract.id,
        contract_type=contract_type,
        triples=triples,
    )


@router.get(
    "/contracts/{contract_id}/kg",
    response_model=List[schemas.KGTriple],
)
async def get_contract_kg(
    contract_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取指定合同已经抽取并入库的所有三元组。
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

    triples = (
        db.query(models.KnowledgeTriple)
        .filter(models.KnowledgeTriple.contract_id == contract.id)
        .order_by(models.KnowledgeTriple.id.asc())
        .all()
    )
    return triples














