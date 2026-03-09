# backend/app/models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    contracts = relationship("Contract", back_populates="owner")
    conversations = relationship("Conversation", back_populates="user")
    contract_compares = relationship(
        "ContractCompare",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Contract(Base):
    """合同模型"""
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # 文件大小（字节）
    file_content = Column(Text)  # 解析后的文本内容
    chunk_count = Column(Integer)  # 分块数量
    # 合同类别：internship / lease / labor / sale / other
    contract_type = Column(String(50), nullable=True, index=True)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    owner = relationship("User", back_populates="contracts")
    conversations = relationship("Conversation", back_populates="contract")
    kg_triples = relationship(
        "KnowledgeTriple",
        back_populates="contract",
        cascade="all, delete-orphan",
    )
    chunks = relationship(
        "ContractChunk",
        back_populates="contract",
        cascade="all, delete-orphan",
    )
    clause_complexities = relationship(
        "ClauseComplexity",
        back_populates="contract",
        cascade="all, delete-orphan",
    )


class ContractCompare(Base):
    """合同对比结果模型"""
    __tablename__ = "contract_compares"

    id = Column(Integer, primary_key=True, index=True)

    # 归属用户
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 被对比的两份合同
    left_contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    right_contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)

    # 对比状态：pending / running / success / failed
    status = Column(String(32), nullable=False, default="success")

    # 对比结果，使用 JSON 字符串存储结构化结果
    result_json = Column(Text, nullable=True)

    # 若失败，记录错误信息
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # 关系
    user = relationship("User", back_populates="contract_compares")
    left_contract = relationship(
        "Contract",
        foreign_keys=[left_contract_id],
    )
    right_contract = relationship(
        "Contract",
        foreign_keys=[right_contract_id],
    )


class Conversation(Base):
    """对话历史模型"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    # 会话 ID，用于将多轮问答绑定到同一对话
    session_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="conversations")
    contract = relationship("Contract", back_populates="conversations")


class KnowledgeTriple(Base):
    """基于合同抽取出的知识图谱三元组"""
    __tablename__ = "knowledge_triples"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False, index=True)

    head = Column(String(512), nullable=False)
    head_type = Column(String(128), nullable=True)
    relation = Column(String(256), nullable=False)
    tail = Column(String(512), nullable=False)
    tail_type = Column(String(128), nullable=True)

    # 支撑该三元组的原文句子
    evidence = Column(Text, nullable=True)

    # 使用的模板名称（例如 internship_new.json）
    template_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    contract = relationship("Contract", back_populates="kg_triples")


class ContractChunk(Base):
    """合同切分片段模型（条款级）"""
    __tablename__ = "contract_chunks"

    id = Column(Integer, primary_key=True, index=True)

    # 所属合同
    contract_id = Column(
        Integer,
        ForeignKey("contracts.id"),
        nullable=False,
        index=True,
    )

    # 在当前合同中的顺序索引（从 0 开始）
    chunk_index = Column(Integer, nullable=False)

    # 条款编号/标记，例如 "1.1"、"4.3"、"a1" 等
    clause_marker = Column(String(64), nullable=True, index=True)

    # 片段文本内容（一个条款或前言等逻辑单元）
    content = Column(Text, nullable=False)

    # 冗余信息，便于检索/调试
    source_name = Column(String(255), nullable=True)
    contract_type = Column(String(50), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    contract = relationship("Contract", back_populates="chunks")


class ClauseComplexity(Base):
    """条款复杂度分析结果"""
    __tablename__ = "clause_complexities"

    id = Column(Integer, primary_key=True, index=True)

    # 所属合同
    contract_id = Column(
        Integer,
        ForeignKey("contracts.id"),
        nullable=False,
        index=True,
    )

    # 条款在合同中的顺序索引
    clause_index = Column(Integer, nullable=False)

    # 条款编号/标记，例如 "1.1"、"第3条"
    clause_marker = Column(String(64), nullable=True, index=True)

    # 条款原文
    clause_text = Column(Text, nullable=False)

    # HanLP 计算出的条款复杂度得分（取条款内句子最大复杂度）
    complexity_score = Column(Float, nullable=False, default=0.0)

    # 是否为复杂条款（超过阈值）
    is_complex = Column(Boolean, nullable=False, default=False)

    # HanLP 返回的原始 JSON（方便排查）
    hanlp_raw_json = Column(Text, nullable=True)

    # LLM 生成的通俗解释
    llm_plain_explanation = Column(Text, nullable=True)

    # LLM 生成的简化重写条款
    llm_simplified_clause = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    contract = relationship("Contract", back_populates="clause_complexities")