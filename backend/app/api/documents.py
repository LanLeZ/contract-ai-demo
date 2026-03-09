"""
文件上传和管理API
"""
import os
import shutil
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import get_current_user
from app.services.document_parser import DocumentParser
from app.services.text_splitter import LawTextSplitter
from app.services.vector_store import VectorStore
from app.services.llm import QwenChatClient

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()

# 初始化服务
parser = DocumentParser()
# 使用测试验证的最佳参数：chunk_size=200, chunk_overlap=60
# 注意：LawTextSplitter 会根据 source_type 自动选择切分器
# - source_type="contract" 时使用 ContractTextSplitter（固定参数 200/60）
# - source_type="legal" 时使用 LegalTextSplitter（使用传入的参数）
splitter = LawTextSplitter(chunk_size=200, chunk_overlap=60)
# 使用新的 collection 存放基于最新切分逻辑的合同向量，保留旧的 collection 以便回滚/对比
vector_store = VectorStore(collection_name="legal_contracts_v2")
qwen_client = QwenChatClient()

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
    allowed_extensions = ['.pdf', '.docx', '.md', '.markdown', '.txt', '.png', '.jpg', '.jpeg']
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
            file_path=str(file_path),
            file_size=file_size,  # 添加文件大小
            file_content=text_content,  # 添加文件内容
            chunk_count=len(chunks)  # 添加分块数量
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


@router.post("/upload-images", response_model=schemas.ContractResponse, status_code=status.HTTP_201_CREATED)
async def upload_images_as_one_contract(
    files: List[UploadFile] = File(...),
    display_name: Optional[str] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    多张图片合并成一份合同并向量化
    - 前端可多次追加图片页，最终一次性上传
    - 后端逐张 OCR → 拼接 → 切分 → 向量化 → 保存一条合同记录
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少上传一张图片")

    allowed_image_ext = {".png", ".jpg", ".jpeg"}

    # 创建合同目录
    user_dir = ensure_upload_dir(current_user.id)
    safe_stem = Path(display_name or "图片合同").stem.strip() or "图片合同"
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    contract_dir = user_dir / f"{safe_stem}_{ts}"
    contract_dir.mkdir(parents=True, exist_ok=True)

    total_size = 0
    max_total_size = 50 * 1024 * 1024  # 50MB
    saved_paths: List[Path] = []

    try:
        # 1) 保存每一页图片
        for idx, f in enumerate(files, start=1):
            if not f.filename:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")

            ext = Path(f.filename).suffix.lower()
            if ext not in allowed_image_ext:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的图片类型: {ext}。支持: {', '.join(sorted(allowed_image_ext))}",
                )

            out_path = contract_dir / f"page_{idx:03d}{ext}"
            with open(out_path, "wb") as buffer:
                while True:
                    chunk = await f.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_total_size:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片总大小超过限制（最大50MB）")
                    buffer.write(chunk)

            saved_paths.append(out_path)

        if not saved_paths:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未保存任何图片")

        # 2) OCR + 拼接文本
        pages_text: List[str] = []
        for i, p in enumerate(saved_paths, start=1):
            page_text = parser.parse(str(p), file_type=None)
            page_text = (page_text or "").strip()
            if page_text:
                pages_text.append(f"\n\n--- Page {i} ---\n{page_text}\n")

        text_content = "".join(pages_text).strip()
        if not text_content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片内容为空或无法提取文本")

        # 3) 切分文本
        contract_filename = (display_name or f"{safe_stem}_pages{len(saved_paths)}.png").strip()
        chunks = splitter.split_with_metadata(
            text=text_content,
            source_name=contract_filename,
            source_type="contract",
            user_id=current_user.id,
            contract_id=None,
        )
        if not chunks:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文本切分失败")

        # 4) 保存合同记录
        db_contract = models.Contract(
            user_id=current_user.id,
            filename=contract_filename,
            file_path=str(contract_dir),  # 目录
            file_size=total_size,
            file_content=text_content,
            chunk_count=len(chunks),
        )
        db.add(db_contract)
        db.commit()
        db.refresh(db_contract)

        # 5) 更新 chunks 的 contract_id 元数据
        for chunk in chunks:
            chunk["metadata"]["contract_id"] = db_contract.id

        # 6) 向量化
        try:
            logger.info(f"开始向量化（图片合同）{len(chunks)} 个文档块...")
            vector_store.add_documents(chunks, batch_size=50)
            logger.info(f"向量化完成（图片合同），成功添加 {len(chunks)} 个文档块")
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"向量化失败（图片合同）: {str(e)}\n{error_traceback}")
            db.delete(db_contract)
            db.commit()
            if contract_dir.exists():
                shutil.rmtree(contract_dir, ignore_errors=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"向量化失败: {str(e)}")

        return db_contract

    except HTTPException:
        if contract_dir.exists():
            shutil.rmtree(contract_dir, ignore_errors=True)
        raise
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"图片合同上传失败: {str(e)}\n{error_traceback}")
        if contract_dir.exists():
            shutil.rmtree(contract_dir, ignore_errors=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"图片合同上传失败: {str(e)}")


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
    """删除合同（包括文件、数据库记录、会话记录、对比历史和向量库中的文档）"""
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
            if file_path.is_dir():
                shutil.rmtree(file_path, ignore_errors=True)
            else:
                os.unlink(file_path)

        # 2. 删除该合同下的所有会话记录，避免产生孤儿会话数据
        db.query(models.Conversation).filter(
            models.Conversation.user_id == current_user.id,
            models.Conversation.contract_id == contract.id,
        ).delete(synchronize_session=False)

        # 3. 删除与该合同相关的所有对比历史记录
        db.query(models.ContractCompare).filter(
            models.ContractCompare.user_id == current_user.id,
            or_(
                models.ContractCompare.left_contract_id == contract.id,
                models.ContractCompare.right_contract_id == contract.id,
            ),
        ).delete(synchronize_session=False)

        # 4. 删除向量库中的相关文档（按 metadata 过滤）
        try:
            vector_store.delete_documents(
                filter_metadata={
                    "user_id": current_user.id,
                    "contract_id": contract.id,
                    "source_type": "contract",
                },
                batch_size=500,
            )
        except Exception as e:
            # 向量库删除失败不影响主流程，只记录日志
            logger.error(
                "删除合同 %s 相关向量失败，将忽略向量库错误继续删除合同: %s",
                contract.id,
                e,
            )

        # 5. 删除数据库中的合同记录
        db.delete(contract)
        db.commit()

        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )

