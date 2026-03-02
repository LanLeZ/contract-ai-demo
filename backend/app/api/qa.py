import logging
from typing import List, Dict, Any

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
vector_store = VectorStore()
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

    # 2. 确定检索范围：优先使用前端传入的 scope_hint，否则调用 LLM 分类
    scope: str
    if body.scope_hint in ("contract_only", "contract_and_law"):
        scope = body.scope_hint
    else:
        try:
            scope = qwen_client.classify_scope(question)
        except Exception as e:
            logger.warning("classify_scope 失败，回退为 contract_only: %s", e)
            scope = "contract_only"

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

    # 3.2 如有需要，再检索法律条文
    if scope == "contract_and_law":
        try:
            legal_results = vector_store.search(
                query=question,
                top_k=5,
                filter_metadata={
                    "user_id": current_user.id,
                    "source_type": "legal",
                },
            )
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

    # 5. 构造 RAG Prompt 调用 LLM
    system_prompt = (
        "你是一名精通中国合同与民商事法律的智能助手。\n"
        "你必须严格基于“检索到的合同条款片段”和“检索到的法律条文片段”来回答问题，"
        "优先引用这些片段中的关键信息进行分析与说明。\n"
        "如果上下文中没有足够信息支撑某个结论，请明确说明“上下文未提供相关条款/法条，因此只能给出一般性提示”，"
        "不要编造具体的条款号、法条内容或当事人名称。\n"
        "在回答中请尽量使用通俗易懂的中文，并在需要时给出实际操作建议（例如是否需要补充条款、修改条款或咨询律师）。"
    )

    user_prompt = (
        f"这是用户上传的一份合同：\n"
        f"- 文件名：{contract.filename}\n"
        f"- 问题检索范围：{scope}\n\n"
        f"以下是根据用户问题检索到的相关上下文（可能包括合同条款和法律条文）：\n\n"
        f"{context_text}\n\n"
        f"请你结合上述上下文，回答用户的问题：\n"
        f"{question}\n\n"
        "请注意：\n"
        "1. 优先引用给定片段中的信息进行分析，可以在表述中用“根据检索到的第[编号]条片段”来提示依据来源；\n"
        "2. 如果某个关键信息在上下文中找不到，请明确说明缺失，不要自行编造；\n"
        "3. 最后请用一两句话做“综合风险总结”和“建议下一步怎么做”。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        answer = qwen_client.chat(messages)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"智能问答服务调用失败: {str(e)}",
        )

    # 在后端日志中打印当前问题和回答简要信息，便于联调观察
    logger.info(
        "[Contract QA] contract_id=%s, user_id=%s, scope=%s, Q=%r, A(前80字符)=%r",
        contract_id,
        current_user.id,
        scope,
        question,
        (answer or "")[:80],
    )

    # 6. 记录一条对话历史（简单版：每一问一答一条记录）
    conversation = models.Conversation(
        user_id=current_user.id,
        contract_id=contract.id,
        question=question,
        answer=answer,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    # 7. 返回响应（包含引用与实际检索范围）
    return schemas.QAResponse(
        answer=answer,
        citations=citations,
        session_id=body.session_id,
        scope=scope,
    )


