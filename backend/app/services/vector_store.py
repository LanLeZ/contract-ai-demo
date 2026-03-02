"""
Chroma向量库管理
"""
import os
import logging
import re
import hashlib
import string
from typing import List, Dict, Optional, TYPE_CHECKING
from pathlib import Path

# 延迟导入chromadb，避免在模块级别触发DefaultEmbeddingFunction的初始化
if TYPE_CHECKING:
    import chromadb
    from chromadb.config import Settings
    from chromadb.api.types import Documents, Embeddings

from app.services.embedding import DashScopeEmbedder

# 配置日志
logger = logging.getLogger(__name__)


def _lazy_import_chromadb():
    """延迟导入chromadb，只在真正需要时才导入"""
    import sys
    import types
    
    # 在导入chromadb之前，先mock掉onnxruntime，避免ChromaDB在类定义时触发onnxruntime导入失败
    # ChromaDB的Collection类在类定义时会执行ef.DefaultEmbeddingFunction()，
    # 这会尝试导入onnxruntime，如果onnxruntime有问题（如DLL加载失败），会导致导入失败
    if 'onnxruntime' not in sys.modules:
        # 创建一个假的onnxruntime模块，避免ChromaDB导入时失败
        fake_onnxruntime = types.ModuleType('onnxruntime')
        # 添加一个假的类，模拟ONNXMiniLM_L6_V2
        class FakeONNXEmbedding:
            def __init__(self, *args, **kwargs):
                pass
        fake_onnxruntime.ONNXMiniLM_L6_V2 = FakeONNXEmbedding
        sys.modules['onnxruntime'] = fake_onnxruntime
    
    try:
        import chromadb
        from chromadb.config import Settings
        from chromadb.api.types import Documents, Embeddings
        return chromadb, Settings, Documents, Embeddings
    except ImportError:
        raise ImportError("chromadb未安装，请运行: pip install chromadb")


class DashScopeEmbeddingFunction:
    """自定义Embedding函数，包装DashScopeEmbedder，避免ChromaDB使用默认的onnxruntime依赖"""
    
    def __init__(self):
        self.embedder = DashScopeEmbedder()
    
    def __call__(self, input) -> List[List[float]]:
        """
        ChromaDB的EmbeddingFunction接口
        Args:
            input: 文档列表（字符串列表）
        Returns:
            向量列表（二维列表）
        """
        if isinstance(input, str):
            input = [input]
        return self.embedder.embed_documents(input)


class VectorStore:
    """Chroma向量库封装"""
    
    def __init__(self, persist_directory: str = None, collection_name: str = "legal_contracts"):
        """
        初始化向量库
        Args:
            persist_directory: 持久化目录路径（如果为None，从环境变量CHROMA_PERSIST_DIR读取，默认./chroma_db）
            collection_name: 集合名称
        """
        # 延迟导入chromadb，避免在模块级别触发DefaultEmbeddingFunction的初始化
        chromadb, Settings, Documents, Embeddings = _lazy_import_chromadb()
        
        # 从环境变量读取持久化目录，如果没有则使用默认值
        if persist_directory is None:
            persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedder = DashScopeEmbedder()
        
        # 确保目录存在
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"初始化向量库: 持久化目录={persist_directory}, 集合名称={collection_name}")
        
        # 初始化Chroma客户端（持久化）
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 获取或创建集合 - 使用自定义embedding函数，避免ChromaDB使用默认的onnxruntime依赖
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=DashScopeEmbeddingFunction(),
            metadata={"description": "法律条文和合同向量库"}
        )
        logger.info(f"向量库集合已就绪，当前文档数: {self.collection.count()}")
    
    def _sanitize_id(self, doc_id: str) -> str:
        """
        清理文档ID，移除或替换ChromaDB不支持的字符
        ChromaDB ID要求：不能包含特殊字符，建议使用字母、数字、下划线、连字符
        
        Args:
            doc_id: 原始ID
        Returns:
            清理后的ID
        """
        # 替换路径分隔符和特殊字符
        sanitized = doc_id.replace('\\', '_').replace('/', '_')
        sanitized = sanitized.replace(' ', '_').replace(':', '_')
        sanitized = sanitized.replace('(', '_').replace(')', '_')
        sanitized = sanitized.replace('[', '_').replace(']', '_')
        sanitized = sanitized.replace('{', '_').replace('}', '_')
        sanitized = re.sub(r'[^\w\-_]', '_', sanitized)
        
        # 如果ID太长，使用哈希缩短（ChromaDB对ID长度有限制）
        MAX_ID_LENGTH = 200
        if len(sanitized) > MAX_ID_LENGTH:
            # 保留前缀，后缀用哈希替代
            prefix = sanitized[:MAX_ID_LENGTH - 33]  # 保留空间给哈希（32字符）+ 分隔符（1字符）
            hash_suffix = hashlib.md5(sanitized.encode()).hexdigest()
            sanitized = f"{prefix}_{hash_suffix}"
        
        return sanitized
    
    def _is_valid_content(self, content: str) -> bool:
        """
        检查内容是否有效（不是只有标点符号或空格）
        Args:
            content: 要检查的内容
        Returns:
            如果内容有效返回True，否则返回False
        """
        if not content or not content.strip():
            return False
        
        # 移除所有标点符号和空格，检查是否还有实际内容
        # 中英文标点符号
        punctuation = string.punctuation + "。，、；：？！""''（）【】《》〈〉「」『』〔〕…—～·"
        cleaned = content.strip()
        for char in punctuation:
            cleaned = cleaned.replace(char, "")
        cleaned = cleaned.replace(" ", "").replace("\n", "").replace("\t", "")
        
        # 如果清理后还有内容，说明是有效的
        return len(cleaned) > 0
    
    def _generate_doc_id(self, metadata: Dict, idx: int, existing_ids: set) -> str:
        """
        生成唯一的文档ID
        
        Args:
            metadata: 文档元数据
            idx: 文档索引
            existing_ids: 已存在的ID集合（用于去重）
        Returns:
            唯一的文档ID
        """
        source_name = metadata.get('source_name', 'unknown')
        source_type = metadata.get('source_type', 'unknown')
        chunk_index = metadata.get('chunk_index', idx)
        user_id = metadata.get('user_id', 'unknown')
        contract_id = metadata.get('contract_id', 'unknown')
        
        # 使用 user_id + contract_id + source_type + source_name + chunk_index 组合生成更稳定且全局唯一的ID，
        # 避免同一用户多次上传同名文件时发生ID冲突，导致Chroma忽略后续插入的数据。
        doc_id = f"user_{user_id}_contract_{contract_id}_{source_type}_{source_name}_{chunk_index}_{idx}"
        
        # 清理ID中的特殊字符
        doc_id = self._sanitize_id(doc_id)
        
        # 确保在本批次中ID唯一（极端情况下如果重复，追加哈希后缀）
        if doc_id in existing_ids:
            import time
            hash_suffix = hashlib.md5(f"{doc_id}_{time.time()}".encode()).hexdigest()[:8]
            doc_id = f"{doc_id}_{hash_suffix}"
        
        return doc_id
    
    def add_documents(self, documents: List[Dict], batch_size: int = 100) -> int:
        """
        批量添加文档到向量库
        Args:
            documents: [{"content": "...", "metadata": {...}}, ...]
            batch_size: 批处理大小（避免API限流）
        Returns:
            成功添加的文档数量
        """
        if not documents:
            logger.warning("文档列表为空，跳过添加")
            return 0
        
        all_ids = []
        all_contents = []
        all_metadatas = []
        existing_ids = set()
        
        # 准备数据
        for idx, doc in enumerate(documents):
            # 验证文档格式
            if 'content' not in doc or 'metadata' not in doc:
                logger.warning(f"文档 {idx} 格式不正确，跳过")
                continue
            
            # 验证内容不为空且有效
            content = doc['content']
            if not content or not content.strip():
                logger.warning(f"文档 {idx} 内容为空，跳过")
                continue
            
            # 检查内容是否只包含标点符号
            if not self._is_valid_content(content):
                logger.warning(f"文档 {idx} 内容只包含标点符号，跳过")
                continue
            
            # 生成唯一ID
            doc_id = self._generate_doc_id(doc['metadata'], idx, existing_ids)
            existing_ids.add(doc_id)
            
            all_ids.append(doc_id)
            all_contents.append(doc['content'])
            all_metadatas.append(doc['metadata'])
        
        if not all_ids:
            logger.warning("没有有效的文档可添加")
            return 0
        
        # 批量embedding
        embeddings = []
        total_batches = (len(all_contents) + batch_size - 1) // batch_size
        
        logger.info(f"开始向量化 {len(all_contents)} 个文档，分 {total_batches} 批处理...")
        
        for i in range(0, len(all_contents), batch_size):
            batch = all_contents[i:i+batch_size]
            batch_num = i // batch_size + 1
            logger.debug(f"处理第 {batch_num}/{total_batches} 批 ({len(batch)} 个文档)...")
            
            try:
                batch_embeddings = self.embedder.embed_documents(batch)
                if len(batch_embeddings) != len(batch):
                    logger.warning(f"第 {batch_num} 批返回的向量数量({len(batch_embeddings)})与输入数量({len(batch)})不匹配")
                embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"第 {batch_num} 批embedding失败: {str(e)}")
                raise
        
        # 验证向量数量匹配
        if len(embeddings) != len(all_ids):
            error_msg = f"向量数量({len(embeddings)})与文档数量({len(all_ids)})不匹配"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 添加到Chroma
        try:
            self.collection.add(
                ids=all_ids,
                embeddings=embeddings,
                documents=all_contents,
                metadatas=all_metadatas
            )
            logger.info(f"✅ 成功添加 {len(all_ids)} 个文档到向量库")
            return len(all_ids)
        except Exception as e:
            logger.error(f"❌ 添加到向量库失败: {str(e)}")
            raise
    
    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        相似度搜索
        Args:
            query: 查询文本
            top_k: 返回top K个结果
            filter_metadata: 过滤条件，如 {"source_type": "legal", "user_id": 1}
        Returns:
            [{"content": "...", "metadata": {...}, "score": 0.95}, ...]
        """
        if not query:
            return []
        
        # 获取查询向量
        query_embedding = self.embedder.embed_query(query)
        
        # 构建where条件（Chroma的过滤语法）
        # ChromaDB要求：多个条件必须使用 $and 操作符
        where = None
        if filter_metadata:
            if len(filter_metadata) == 1:
                # 单个条件，直接使用
                where = filter_metadata
            else:
                # 多个条件，使用 $and 操作符
                where = {
                    "$and": [
                        {key: value} for key, value in filter_metadata.items()
                    ]
                }
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where
            )
            
            # 格式化结果
            formatted_results = []
            if results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    # Chroma返回的是距离（distance），转换为相似度分数（score）
                    # 距离越小，相似度越高
                    distance = results['distances'][0][i]
                    score = 1 - distance  # 简单的转换，也可以使用其他公式
                    
                    formatted_results.append({
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "score": score,
                        "distance": distance
                    })
            
            logger.debug(f"搜索完成，返回 {len(formatted_results)} 个结果")
            return formatted_results
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            raise
    
    def get_collection_count(self) -> int:
        """
        获取向量库中的文档数量
        Returns:
            文档总数
        """
        return self.collection.count()
    
    def delete_collection(self):
        """删除整个集合（谨慎使用）"""
        count = self.collection.count()
        self.client.delete_collection(name=self.collection_name)
        logger.warning(f"已删除集合: {self.collection_name}（包含 {count} 个文档）")
    
    def get_collection_info(self) -> Dict:
        """
        获取集合信息
        Returns:
            集合信息字典
        """
        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "metadata": self.collection.metadata
        }

