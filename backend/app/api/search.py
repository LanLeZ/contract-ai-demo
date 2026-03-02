"""
向量搜索API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services.vector_store import VectorStore

router = APIRouter()

# 初始化向量库
vector_store = VectorStore()


@router.post("/", response_model=schemas.SearchResponse)
async def search_documents(
    query: schemas.SearchRequest,
    current_user: models.User = Depends(get_current_user)
):
    """
    向量搜索
    1. 对查询文本进行embedding
    2. 在Chroma中搜索相似文档
    3. 返回结果列表
    """
    if not query.query or not query.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="查询内容不能为空"
        )
    
    try:
        # 构建过滤条件
        filter_metadata = {}
        if query.source_type:
            filter_metadata['source_type'] = query.source_type
        
        # 只搜索当前用户的文档
        filter_metadata['user_id'] = current_user.id
        
        # 执行搜索
        results = vector_store.search(
            query=query.query,
            top_k=query.top_k or 5,
            filter_metadata=filter_metadata
        )
        
        return {
            "query": query.query,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


@router.post("/by-contract", response_model=schemas.SearchResponse)
async def search_by_contract(
    query: schemas.ContractSearchRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    按合同搜索
    只搜索指定合同内的内容
    """
    if not query.query or not query.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="查询内容不能为空"
        )
    
    # 验证合同是否存在且属于当前用户
    contract = db.query(models.Contract).filter(
        models.Contract.id == query.contract_id,
        models.Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    try:
        # 构建过滤条件：只搜索该合同的内容
        filter_metadata = {
            'user_id': current_user.id,
            'contract_id': query.contract_id,
            'source_type': 'contract'
        }
        
        # 执行搜索
        results = vector_store.search(
            query=query.query,
            top_k=query.top_k or 5,
            filter_metadata=filter_metadata
        )
        
        return {
            "query": query.query,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


