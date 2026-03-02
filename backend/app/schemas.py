from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any


# 用户相关Schema
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72, description="密码长度必须在6-72字符之间")
    
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
    
    class Config:
        from_attributes = True


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
