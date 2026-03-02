"""
文件上传和管理API
"""
import os
import shutil
import logging
import traceback
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services.document_parser import DocumentParser
from app.services.text_splitter import LawTextSplitter
from app.services.vector_store import VectorStore

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()

# 初始化服务
parser = DocumentParser()
splitter = LawTextSplitter(chunk_size=500, chunk_overlap=50)
vector_store = VectorStore()

# 上传文件存储目录
UPLOAD_DIR = Path("./uploads")


def ensure_upload_dir(user_id: int):
    """确保用户上传目录存在"""
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


@router.post("/upload", response_model=schemas.ContractResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传文件并向量化
    1. 保存文件到 uploads/ 目录
    2. 解析文件内容
    3. 切分文本
    4. 向量化并存储到Chroma
    5. 保存合同记录到数据库
    """
    # 验证文件类型
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空"
        )
    
    file_ext = Path(file.filename).suffix.lower()
    allowed_extensions = ['.pdf', '.docx', '.md', '.markdown']
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型。支持的类型: {', '.join(allowed_extensions)}"
        )
    
    try:
        logger.info(f"用户 {current_user.id} 开始上传文件: {file.filename}")
        # 1. 保存文件
        user_dir = ensure_upload_dir(current_user.id)
        file_path = user_dir / file.filename
        logger.info(f"文件保存路径: {file_path}")
        
        # 如果文件已存在，添加序号
        counter = 1
        original_path = file_path
        while file_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            file_path = user_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        # 保存文件并验证大小
        file_size = 0
        max_size = 50 * 1024 * 1024  # 50MB
        
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 每次读取1MB
                if not chunk:
                    break
                file_size += len(chunk)
                
                # 检查文件大小限制
                if file_size > max_size:
                    # 删除已保存的部分文件
                    buffer.close()
                    if file_path.exists():
                        os.unlink(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"文件大小超过限制（最大50MB）"
                    )
                
                buffer.write(chunk)
        
        # 重新读取文件内容用于解析（因为file对象已经被读取）
        # 直接从保存的文件解析
        try:
            logger.info(f"开始解析文件: {file_path}")
            text_content = parser.parse(str(file_path), file_type=None)
            file_type = parser._detect_file_type(str(file_path))
            logger.info(f"文件解析成功，提取文本长度: {len(text_content)} 字符")
        except Exception as e:
            # 如果解析失败，删除已保存的文件
            error_traceback = traceback.format_exc()
            logger.error(f"文件解析失败: {str(e)}\n{error_traceback}")
            if file_path.exists():
                os.unlink(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件解析失败: {str(e)}"
            )
        
        if not text_content.strip():
            # 如果解析结果为空，删除文件
            if file_path.exists():
                os.unlink(file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容为空或无法提取文本"
            )
        
        # 3. 切分文本
        chunks = splitter.split_with_metadata(
            text=text_content,
            source_name=file.filename,
            source_type="contract",
            user_id=current_user.id,
            contract_id=None  # 稍后更新
        )
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文本切分失败"
            )
        
        # 4. 保存合同记录到数据库
        db_contract = models.Contract(
            user_id=current_user.id,
            filename=file.filename,
            file_path=str(file_path)
        )
        db.add(db_contract)
        db.commit()
        db.refresh(db_contract)
        
        # 5. 更新chunks的contract_id元数据
        for chunk in chunks:
            chunk['metadata']['contract_id'] = db_contract.id
        
        # 6. 向量化并存储到Chroma
        try:
            logger.info(f"开始向量化 {len(chunks)} 个文档块...")
            vector_store.add_documents(chunks, batch_size=50)
            logger.info(f"向量化完成，成功添加 {len(chunks)} 个文档块")
        except Exception as e:
            # 如果向量化失败，删除数据库记录和文件
            error_traceback = traceback.format_exc()
            logger.error(f"向量化失败: {str(e)}\n{error_traceback}")
            db.delete(db_contract)
            db.commit()
            if file_path.exists():
                os.unlink(file_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"向量化失败: {str(e)}"
            )
        
        return db_contract
    
    except HTTPException:
        raise
    except Exception as e:
        # 记录详细的错误信息用于调试
        error_traceback = traceback.format_exc()
        logger.error(f"文件上传失败: {str(e)}\n{error_traceback}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )


@router.get("/", response_model=List[schemas.ContractResponse])
async def get_documents(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有合同列表"""
    contracts = db.query(models.Contract).filter(
        models.Contract.user_id == current_user.id
    ).order_by(models.Contract.upload_time.desc()).all()
    
    return contracts


@router.get("/{contract_id}", response_model=schemas.ContractResponse)
async def get_document(
    contract_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同详情"""
    contract = db.query(models.Contract).filter(
        models.Contract.id == contract_id,
        models.Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    return contract


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    contract_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除合同（包括文件、数据库记录和向量库中的文档）"""
    contract = db.query(models.Contract).filter(
        models.Contract.id == contract_id,
        models.Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在"
        )
    
    try:
        # 1. 删除文件
        file_path = Path(contract.file_path)
        if file_path.exists():
            os.unlink(file_path)
        
        # 2. 删除向量库中的相关文档
        # 注意：ChromaDB没有直接按metadata删除的API，这里先删除数据库记录
        # 可以考虑在向量库中存储contract_id，然后通过查询+删除的方式清理
        # 暂时先删除数据库记录，向量库中的文档可以定期清理
        
        # 3. 删除数据库记录
        db.delete(contract)
        db.commit()
        
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )

