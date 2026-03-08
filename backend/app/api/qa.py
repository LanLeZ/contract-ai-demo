import logging
from typing import List, Dict, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user
from app.services.vector_store import VectorStore
from app.services.llm import QwenChatClient

logger = logging.getLogger(__name__)

router = APIRouter()

# 初始化服务（与 documents.py 中保持一致的风格）
# 使用新的 collection 存放基于最新切分逻辑的向量数据
vector_store = VectorStore(collection_name="legal_contracts_v2")
qwen_client = QwenChatClient()


def _build_citation_from_result(result: Dict[str, Any]) -> schemas.QACitation:
    """
    将向量检索结果转换为前端可用的引用结构
    """
    metadata = result.get("metadata") or {}
    content = result.get("content") or ""
    source_type = metadata.get("source_type", "contract")

    # 基于元数据推断一个尽量可读的标题
    title_parts: List[str] = []
    if source_type == "contract":
        # 合同片段：尝试使用条款编号或文件名 + 分块索引
        section = metadata.get("section_title") or metadata.get("header_2")
        if section:
            title_parts.append(str(section))
        else:
            source_name = metadata.get("source_name") or "合同片段"
            chunk_index = metadata.get("chunk_index")
            if chunk_index is not None:
                title_parts.append(f"{source_name} - 片段#{chunk_index}")
            else:
                title_parts.append(str(source_name))
    else:
        # 法律条文：尝试使用法条标题 / 章节标题
        law_name = metadata.get("law_name") or metadata.get("header_1")
        article = metadata.get("article_no") or metadata.get("header_2")
        if law_name:
            title_parts.append(str(law_name))
        if article:
            title_parts.append(str(article))

    title = " / ".join([p for p in title_parts if p])

    # 构造一个稳定的 source_id，方便后续如果需要做去重 / 追踪
    source_id_parts: List[str] = []
    if source_type == "contract":
        if metadata.get("contract_id") is not None:
            source_id_parts.append(f"contract-{metadata.get('contract_id')}")
        if metadata.get("chunk_index") is not None:
            source_id_parts.append(f"chunk-{metadata.get('chunk_index')}")
    else:
        # 法律条文
        if metadata.get("law_id") is not None:
            source_id_parts.append(f"law-{metadata.get('law_id')}")
        if metadata.get("article_no"):
            source_id_parts.append(f"article-{metadata.get('article_no')}")

    if not source_id_parts and metadata.get("source_name"):
        source_id_parts.append(str(metadata.get("source_name")))

    source_id = "|".join(source_id_parts) if source_id_parts else "unknown"

    return schemas.QACitation(
        source_type=source_type,
        source_id=source_id,
        title=title or None,
        snippet=content.strip(),
    )


@router.post("/documents/{contract_id}/qa", response_model=schemas.QAResponse)
async def contract_qa(
    contract_id: int,
    body: schemas.QARequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    合同智能问答（LLM + 合同向量检索 + 法条检索）

    流程：
    1. 校验合同归属
    2. 判断问题范围（仅合同 / 合同+法律），可由前端提示或由 LLM 分类
    3. 针对当前合同做向量检索，获取 TopK 合同片段
    4. 如需要，检索法律条文向量库，获取 TopK 法条片段
    5. 将检索到的片段整理为上下文，构造 RAG Prompt 调用 LLM
    6. 记录对话历史，并返回回答 + 引用列表
    """
    # 1. 校验合同是否存在且属于当前用户
    contract = db.query(models.Contract).filter(
        models.Contract.id == contract_id,
        models.Contract.user_id == current_user.id,
    ).first()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="合同不存在或无权限访问",
        )

    if not body.question or not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="问题不能为空",
        )

    question = body.question.strip()

    # 2.1 处理会话 ID：如果前端未传入，则视为开启新会话
    if body.session_id:
        session_id = body.session_id
    else:
        # 使用 UUID 生成一个新的会话 ID
        session_id = uuid.uuid4().hex

    # 2. 确定检索范围：一次性分析 scope + law_names
    law_names: List[str] = []
    try:
        scope, law_names = qwen_client.analyze_scope_and_laws(question)
        logger.info("scope=%s, law_names=%s", scope, law_names)
    except Exception as e:
        logger.exception("analyze_scope_and_laws 失败，回退为 contract_only")
        scope = "contract_only"
        law_names = []

    # 3. 执行向量检索
    contract_results: List[Dict[str, Any]] = []
    legal_results: List[Dict[str, Any]] = []

    # 3.1 针对当前合同的检索
    try:
        contract_results = vector_store.search(
            query=question,
            top_k=5,
            filter_metadata={
                "user_id": current_user.id,
                "contract_id": contract_id,
                "source_type": "contract",
            },
        )
    except Exception as e:
        logger.error("合同向量检索失败，将在无合同上下文的情况下回答: %s", e)
        contract_results = []

    # 3.2 如有需要，再检索法律条文（利用 law_names 做更精确匹配）
    if scope == "contract_and_law":
        # 使用 analyze_scope_and_laws 返回的法律名称；如果没有，就在法律库中不加限定检索
        if law_names:
            logger.info("[Legal Retrieval] 从 analyze_scope_and_laws 抽取到法律名称: %s", law_names)
        else:
            logger.info(
                "[Legal Retrieval] analyze_scope_and_laws 未抽取到法律名称，将在法律库中不加限定检索"
            )

        # 组装基础 filter_metadata
        # 注意：法律条文是“公共语料”，导入时通常不会写入 user_id；
        # 若在这里附加 user_id 会导致 where 过滤后 0 命中，看起来像“没有检索到”。
        legal_filter = {"source_type": "legal"}

        try:
            # 先进行全法律库检索（如果抽取到法律名称，增加 top_k 以获取更多候选）
            search_top_k = 10 if law_names else 5
            logger.info(
                "[Legal Retrieval] query top_k=%s filter=%s", search_top_k, legal_filter
            )
            all_legal_results = vector_store.search(
                query=question,
                top_k=search_top_k,
                filter_metadata=legal_filter,
            )
            logger.info(
                "[Legal Retrieval] raw results count=%d", len(all_legal_results)
            )
            if all_legal_results:
                top1_meta = all_legal_results[0].get("metadata") or {}
                logger.info(
                    "[Legal Retrieval] top1 score=%.4f source_name=%s",
                    float(all_legal_results[0].get("score", -1.0)),
                    top1_meta.get("source_name"),
                )

            # 如果抽取到了法律名称，在结果中按“Law-Book 文件名风格”进行归一化匹配
            if law_names and all_legal_results:
                import os
                import re

                def _normalize_law_key(s: str) -> str:
                    x = (s or "").strip().lower()
                    x = x.replace("《", "").replace("》", "")
                    x = x.replace("中华人民共和国", "").replace("中国", "")
                    # 去掉路径前缀，例如 3-民法商法/电子签名法（2019-04-23）.md
                    x = os.path.basename(x)
                    # 去扩展名
                    x = re.sub(r"\.(md|markdown)$", "", x, flags=re.IGNORECASE)
                    # 去掉尾部日期括号（全角/半角）
                    x = re.sub(r"（\d{4}-\d{2}-\d{2}）$", "", x)
                    x = re.sub(r"\(\d{4}-\d{2}-\d{2}\)$", "", x)
                    # 去掉空白
                    x = re.sub(r"\s+", "", x)
                    return x

                targets = {_normalize_law_key(n) for n in law_names if _normalize_law_key(n)}

                filtered_results = []
                for result in all_legal_results:
                    metadata = result.get("metadata") or {}
                    # 只使用 source_name 做匹配：这是 Law-Book 导入时稳定存在的字段
                    source_name_norm = _normalize_law_key(str(metadata.get("source_name", "")))
                    if not source_name_norm:
                        continue

                    # 只要任一目标在 source_name 中出现（或相互包含），即认为匹配
                    matched = any(t and (t in source_name_norm or source_name_norm in t) for t in targets)
                    if matched:
                        filtered_results.append(result)

                if filtered_results:
                    legal_results = filtered_results[:5]
                    logger.info(
                        "[Legal Retrieval] 使用法律简称归一化匹配，从 %d 个结果中筛选出 %d 个",
                        len(all_legal_results),
                        len(legal_results),
                    )
                else:
                    legal_results = all_legal_results[:5]
                    logger.info(
                        "[Legal Retrieval] 法律简称归一化匹配后无命中，使用全部检索结果"
                    )
            else:
                legal_results = all_legal_results[:5]
        except Exception as e:
            logger.error("法律条文向量检索失败，退化为仅基于合同片段回答: %s", e)
            legal_results = []

    # 4. 组装引用信息，构造 RAG 上下文
    citations: List[schemas.QACitation] = []
    for r in contract_results:
        try:
            citations.append(_build_citation_from_result(r))
        except Exception as e:
            logger.warning("构造合同引用信息失败，已跳过某条结果: %s", e)

    for r in legal_results:
        try:
            citations.append(_build_citation_from_result(r))
        except Exception as e:
            logger.warning("构造法律引用信息失败，已跳过某条结果: %s", e)

    # 构造给 LLM 的上下文文本（适度截断，避免 prompt 过长）
    def _format_results_block(
        label: str, results: List[Dict[str, Any]], source_type: str
    ) -> str:
        if not results:
            return ""

        lines: List[str] = [label]
        for idx, r in enumerate(results, start=1):
            meta = r.get("metadata") or {}
            content = (r.get("content") or "").strip()
            # 适当截断单条内容
            max_len = 400
            if len(content) > max_len:
                content = content[:max_len] + "……"

            title = ""
            if source_type == "contract":
                title = (
                    meta.get("section_title")
                    or meta.get("header_2")
                    or meta.get("source_name")
                    or f"合同片段 {idx}"
                )
            else:
                title = (
                    meta.get("law_name")
                    or meta.get("header_1")
                    or meta.get("source_name")
                    or f"法律条文片段 {idx}"
                )

            lines.append(f"[{idx}] 标题：{title}")
            lines.append(f"内容片段：{content}")
            lines.append("")  # 空行分隔

        return "\n".join(lines).strip()

    contract_block = _format_results_block(
        "【与本合同最相关的条款片段】", contract_results, "contract"
    )
    legal_block = _format_results_block(
        "【可能相关的法律条文片段】", legal_results, "legal"
    )

    context_sections: List[str] = []
    if contract_block:
        context_sections.append(contract_block)
    if legal_block and scope == "contract_and_law":
        context_sections.append(legal_block)

    if context_sections:
        context_text = "\n\n".join(context_sections)
    else:
        context_text = (
            "（未能从合同向量库或法律向量库中检索到明显相关的片段，"
            "请你仅基于一般的合同与法律常识，给出风险提示和建议。）"
        )

    # 5. 调用 LLM 基于 RAG 上下文回答问题
    try:
        answer = qwen_client.answer_question_with_rag(
            question=question,
            contract_filename=contract.filename,
            scope=scope,
            context_text=context_text,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"智能问答服务调用失败: {str(e)}",
        )

    # 在后端日志中打印当前问题和回答简要信息，便于联调观察
    logger.info(
        "[Contract QA] contract_id=%s, user_id=%s, scope=%s, session_id=%s, Q=%r, A(前80字符)=%r",
        contract_id,
        current_user.id,
        scope,
        session_id,
        question,
        (answer or "")[:80],
    )

    # 6. 记录一条对话历史（每一问一答一条记录，带上会话 ID）
    conversation = models.Conversation(
        user_id=current_user.id,
        contract_id=contract.id,
        question=question,
        answer=answer,
        session_id=session_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    # 7. 返回响应（包含引用、实际检索范围和当前会话 ID）
    return schemas.QAResponse(
        answer=answer,
        citations=citations,
        session_id=session_id,
        scope=scope,
    )


@router.get(
    "/documents/{contract_id}/sessions",
    response_model=schemas.ConversationSessionListResponse,
)
def list_conversation_sessions(
    contract_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    列出当前用户在某份合同下的历史会话（按 session_id 聚合）。

    默认按最近对话时间倒序排列。
    """
    # 校验合同归属
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
            detail="合同不存在或无权限访问",
        )

    # 按 session_id 聚合最近一条记录和计数
    from sqlalchemy import func as sa_func

    subq = (
        db.query(
            models.Conversation.session_id.label("session_id"),
            sa_func.max(models.Conversation.id).label("max_id"),
            sa_func.count(models.Conversation.id).label("cnt"),
        )
        .filter(
            models.Conversation.user_id == current_user.id,
            models.Conversation.contract_id == contract_id,
        )
        .group_by(models.Conversation.session_id)
        .subquery()
    )

    rows = (
        db.query(models.Conversation, subq.c.cnt)
        .join(
            subq,
            (models.Conversation.id == subq.c.max_id)
            & (models.Conversation.session_id == subq.c.session_id),
        )
        .order_by(models.Conversation.created_at.desc())
        .all()
    )

    sessions: List[schemas.ConversationSession] = []
    for conv, cnt in rows:
        sessions.append(
            schemas.ConversationSession(
                session_id=conv.session_id,
                contract_id=conv.contract_id,
                last_question=conv.question,
                last_answer=conv.answer,
                last_time=conv.created_at,
                message_count=cnt,
            )
        )

    return schemas.ConversationSessionListResponse(sessions=sessions)


@router.get(
    "/documents/{contract_id}/sessions/{session_id}",
    response_model=schemas.ConversationHistoryResponse,
)
def get_conversation_history(
    contract_id: int,
    session_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取某个会话（按 session_id）的完整问答历史。
    """
    # 校验合同归属
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
            detail="合同不存在或无权限访问",
        )

    conversations = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.user_id == current_user.id,
            models.Conversation.contract_id == contract_id,
            models.Conversation.session_id == session_id,
        )
        .order_by(models.Conversation.created_at.asc())
        .all()
    )

    if not conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该会话历史",
        )

    messages: List[schemas.ConversationMessage] = []
    for conv in conversations:
        # 一问一答两条消息
        messages.append(
            schemas.ConversationMessage(
                role="user",
                content=conv.question,
                created_at=conv.created_at,
            )
        )
        messages.append(
            schemas.ConversationMessage(
                role="assistant",
                content=conv.answer,
                created_at=conv.created_at,
            )
        )

    return schemas.ConversationHistoryResponse(
        session_id=session_id,
        contract_id=contract_id,
        messages=messages,
    )
