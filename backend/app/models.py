# backend/app/models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
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