from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any


# 用户相关Schema
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72, description="密码长度必须在8-72字符之间")
    
    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        # 检查 UTF-8 编码后的字节长度
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 72:
            raise ValueError('密码长度不能超过72字节（UTF-8编码）')
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=72,
        description="密码长度必须在6-72字符之间",
    )

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: Optional[str]) -> Optional[str]:
        # 允许不更新密码（None）
        if v is None:
            return v
        # 检查 UTF-8 编码后的字节长度
        password_bytes = v.encode("utf-8")
        if len(password_bytes) > 72:
            raise ValueError("密码长度不能超过72字节（UTF-8编码）")
        return v


class UserStats(BaseModel):
    contract_count: int = Field(default=0, description="已上传合同数")
    compare_count: int = Field(default=0, description="已对比合同数")
    conversation_count: int = Field(default=0, description="问答会话数")
    clause_complexity_count: int = Field(default=0, description="已解析长难句数")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# 合同相关Schema
class ContractResponse(BaseModel):
    id: int
    user_id: int
    filename: str
    file_path: str
    file_size: Optional[int] = None
    file_content: Optional[str] = None
    chunk_count: Optional[int] = None
    upload_time: datetime
    # 新增：合同类别
    contract_type: Optional[str] = Field(
        default=None,
        description="合同类别：internship / lease / labor / sale / other",
    )

    class Config:
        from_attributes = True


class ContractCompareRequest(BaseModel):
    """创建合同对比请求"""
    left_contract_id: int = Field(..., description="左侧合同 ID")
    right_contract_id: int = Field(..., description="右侧合同 ID")


class ContractCompareSummary(BaseModel):
    """合同对比概要信息（用于列表）"""
    id: int
    # 历史数据中可能存在部分字段为 NULL 的情况，这里统一放宽为可选，避免响应校验失败导致 422
    left_contract_id: int | None = None
    right_contract_id: int | None = None
    status: str | None = None
    # 允许历史数据中 created_at 为空
    created_at: datetime | None = None
    finished_at: datetime | None = None

    # 新增：左右合同的文件名（用于前端历史列表展示）
    left_contract_filename: Optional[str] = None
    right_contract_filename: Optional[str] = None

    class Config:
        from_attributes = True


class ContractCompareDetail(BaseModel):
    """单次合同对比详情"""
    id: int
    # 同样放宽这些字段为可选，以兼容历史脏数据
    left_contract_id: int | None = None
    right_contract_id: int | None = None
    status: str | None = None
    # 某些情况下（例如老数据或未刷新 server_default），created_at 可能为 None
    created_at: datetime | None = None
    finished_at: datetime | None = None
    result: Dict[str, Any] | None = Field(
        default=None,
        description="结构化对比结果（从数据库的 result_json 反序列化）",
    )


class ContractCompareListResponse(BaseModel):
    """合同对比历史列表响应"""
    items: List[ContractCompareSummary]



# 搜索相关Schema
class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询文本")
    top_k: Optional[int] = Field(5, ge=1, le=50, description="返回结果数量")
    source_type: Optional[str] = Field(None, description="来源类型过滤（legal/contract）")


class ContractSearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询文本")
    contract_id: int = Field(..., description="合同ID")
    top_k: Optional[int] = Field(5, ge=1, le=50, description="返回结果数量")


class SearchResult(BaseModel):
    content: str
    metadata: Dict[str, Any]
    score: float
    distance: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


# 智能问答相关Schema
class QACitation(BaseModel):
    source_type: str = Field(..., description="来源类型：contract / legal")
    source_id: str = Field(..., description="来源标识，如向量ID或法条号")
    title: Optional[str] = Field(None, description="引用标题，例如合同第几条、法条名称")
    snippet: str = Field(..., description="被引用的文本片段")


class QARequest(BaseModel):
    question: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(None, description="对话会话ID（可选）")
    scope_hint: Optional[str] = Field(
        None,
        description="检索范围提示：contract_only / contract_and_law，可为空表示交给后端判断"
    )


class QAResponse(BaseModel):
    answer: str = Field(..., description="LLM 给出的回答")
    citations: List[QACitation] = Field(default_factory=list, description="引用的证据列表")
    session_id: Optional[str] = Field(None, description="本轮会话ID，前端需保存")
    scope: Optional[str] = Field(None, description="实际检索范围：contract_only / contract_and_law")


# 会话历史相关 Schema
class ConversationMessage(BaseModel):
    role: str = Field(..., description="角色：user / assistant")
    content: str = Field(..., description="消息内容")
    created_at: datetime


class ConversationSession(BaseModel):
    session_id: str = Field(..., description="会话ID")
    contract_id: int = Field(..., description="合同ID")
    last_question: str = Field(..., description="最近一次提问")
    last_answer: str = Field(..., description="最近一次回答")
    last_time: datetime = Field(..., description="最近对话时间")
    message_count: int = Field(..., description="该会话问题条数（一问一答记一条）")


class ConversationSessionListResponse(BaseModel):
    sessions: List[ConversationSession]


class ConversationHistoryResponse(BaseModel):
    session_id: str
    contract_id: int
    messages: List[ConversationMessage]


# ====== 知识图谱相关 Schema ======

class KGTriple(BaseModel):
    id: int
    contract_id: int
    head: str
    head_type: Optional[str] = None
    relation: str
    tail: str
    tail_type: Optional[str] = None
    evidence: Optional[str] = None
    template_name: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
    
    
class KGExtractResponse(BaseModel):
    contract_id: int
    contract_type: Optional[str] = None
    triples: List[KGTriple]


# ====== 条款复杂度相关 Schema ======

class ClauseComplexityItem(BaseModel):
    clause_index: int
    clause_marker: Optional[str] = None
    clause_text: str
    complexity_score: float
    is_complex: bool
    llm_plain_explanation: Optional[str] = None
    llm_simplified_clause: Optional[str] = None


class ContractComplexityResponse(BaseModel):
    contract_id: int
    threshold: float
    clauses: List[ClauseComplexityItem]