"""
向量检索服务模块
"""
from app.services.embedding import DashScopeEmbedder
from app.services.text_splitter import LawTextSplitter
from app.services.legal_splitter import LegalTextSplitter
from app.services.contract_splitter import ContractTextSplitter
from app.services.llm import QwenChatClient
from app.services.vector_store import VectorStore  # VectorStore延迟导入chromadb，不会在模块级别触发导入

__all__ = [
    "DashScopeEmbedder",
    "LawTextSplitter",
    "LegalTextSplitter",
    "ContractTextSplitter",
    "VectorStore",
    "QwenChatClient",
]

# *** End of File
"""
向量检索服务模块
"""
from app.services.embedding import DashScopeEmbedder
from app.services.text_splitter import LawTextSplitter
from app.services.legal_splitter import LegalTextSplitter
from app.services.contract_splitter import ContractTextSplitter
# VectorStore延迟导入chromadb，不会在模块级别触发导入
from app.services.vector_store import VectorStore

__all__ = [
    "DashScopeEmbedder", 
    "LawTextSplitter", 
    "LegalTextSplitter", 
    "ContractTextSplitter",
    "VectorStore"
]

