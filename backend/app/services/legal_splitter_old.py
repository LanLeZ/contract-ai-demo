"""
法律条文文本切分器（旧版本）
保留作为备份，新的切分逻辑请参考 legal_splitter.LegalTextSplitter
"""
from typing import List, Dict
import re
import logging
from app.services.base_splitter import BaseTextSplitter

try:
    from langchain.text_splitter import (
        MarkdownHeaderTextSplitter,
        RecursiveCharacterTextSplitter
    )
except ImportError:
    MarkdownHeaderTextSplitter = None
    RecursiveCharacterTextSplitter = None
    print("警告: langchain未安装，请运行: pip install langchain langchain-community")

# 配置日志
logger = logging.getLogger(__name__)


class LegalTextSplitter(BaseTextSplitter):
    """法律条文文本切分器（旧实现）"""
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100, min_chunk_size: int = 50):
        """
        初始化法律条文切分器
        Args:
            chunk_size: 每个文本块的最大字符数（建议800-1200）
            chunk_overlap: 文本块之间的重叠字符数（建议100-150）
            min_chunk_size: 最小chunk大小，小于此值的chunk会尝试合并，无法合并则保留并标记
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        if MarkdownHeaderTextSplitter is None:
            raise ImportError("langchain未安装，请运行: pip install langchain langchain-community")
        
        # Markdown切分器（按标题层级）
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "header_1"),
                ("##", "header_2"),
                ("###", "header_3"),
            ]
        )
        
        # 普通文本递归切分器（用于非Markdown格式）
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "，", " ", ""]
        )
        
        # 法律条文专用的递归切分器（优先在条款边界和句号处切分）
        # 注意：separators 中已经包含了 "\n\n第" 和 "\n第"，会自动在条款边界处切分
        # 移除了 "，" 和 " "，避免过度切分（法律条文的空格用于分隔编号和内容，不应切分）
        # 移除了 ""，避免按字符切分（过于细粒度）
        self.legal_recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n第", "\n第", "。", "；", "\n\n", "\n"]
        )
    
    def _normalize_chunk(self, content: str, metadata: Dict = None) -> Dict:
        """
        规范化chunk格式
        Args:
            content: chunk内容
            metadata: 元数据字典
        Returns:
            规范化后的chunk字典
        """
        if metadata is None:
            metadata = {}
        return {
            "content": content.strip(),
            "metadata": metadata.copy()
        }
    
    def _filter_and_merge_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        统一过滤和合并策略
        1. 过滤无效内容
        2. 对于过小的chunk，优先合并到相邻chunk
        3. 无法合并的小chunk保留但标记为小chunk
        
        Args:
            chunks: 原始chunk列表
        Returns:
            处理后的chunk列表
        """
        if not chunks:
            return []
        
        # 第一步：过滤无效内容
        valid_chunks = []
        for chunk in chunks:
            content = chunk.get('content', '').strip()
            if content and self._is_valid_content(content):
                valid_chunks.append(chunk)
            else:
                logger.debug(f"过滤无效内容: {content[:50]}...")
        
        if not valid_chunks:
            return []
        
        # 第二步：处理过小的chunk（优先合并，无法合并则保留）
        result = []
        i = 0
        while i < len(valid_chunks):
            current_chunk = valid_chunks[i]
            content = current_chunk.get('content', '').strip()
            content_len = len(content)
            
            # 如果chunk太小，尝试合并
            if content_len < self.min_chunk_size:
                # 尝试合并到下一个chunk
                if i + 1 < len(valid_chunks):
                    next_chunk = valid_chunks[i + 1]
                    next_content = next_chunk.get('content', '').strip()
                    merged_content = content + "\n\n" + next_content
                    
                    # 如果合并后不超过chunk_size，则合并
                    if len(merged_content) <= self.chunk_size:
                        merged_chunk = {
                            "content": merged_content,
                            "metadata": current_chunk['metadata'].copy()
                        }
                        # 合并元数据（优先使用当前chunk的元数据）
                        merged_chunk['metadata'].update(next_chunk['metadata'])
                        merged_chunk['metadata']['merged'] = True
                        merged_chunk['metadata']['original_chunk_count'] = 2
                        result.append(merged_chunk)
                        i += 2  # 跳过下一个chunk
                        logger.debug(f"合并小chunk: {content_len} + {len(next_content)} = {len(merged_content)}")
                        continue
                
                # 无法合并，保留但标记为小chunk
                current_chunk['metadata']['is_small_chunk'] = True
                current_chunk['metadata']['chunk_size'] = content_len
                logger.warning(f"保留小chunk（无法合并）: {content_len} 字符，内容: {content[:50]}...")
                result.append(current_chunk)
            else:
                # chunk大小正常，直接添加
                result.append(current_chunk)
            
            i += 1
        
        return result
    
    def split_markdown(self, text: str) -> List[Dict]:
        """
        切分Markdown格式的法律条文
        Args:
            text: Markdown格式的文本
        Returns:
            [{"content": "...", "metadata": {"header_1": "...", "header_2": "..."}}, ...]
        """
        if not text.strip():
            return []
        
        try:
            chunks = self.markdown_splitter.split_text(text)
            result = []
            for chunk in chunks:
                content = chunk.page_content.strip()
                if content:  # 只检查非空，有效性检查在统一过滤中处理
                    result.append(self._normalize_chunk(
                        content=content,
                        metadata=chunk.metadata.copy()
                    ))
            return result
        except Exception as e:
            # 如果Markdown切分失败，降级为普通文本切分
            logger.warning(f"Markdown切分失败，降级为普通文本切分: {str(e)}")
            return self.split_text(text)
    
    def split_text(self, text: str) -> List[Dict]:
        """
        普通文本切分（用于非Markdown格式）
        Args:
            text: 普通文本
        Returns:
            [{"content": "...", "metadata": {}}, ...]
        """
        if not text.strip():
            return []
        
        chunks = self.recursive_splitter.split_text(text)
        result = []
        for idx, chunk in enumerate(chunks):
            if chunk.strip():  # 只检查非空，有效性检查在统一过滤中处理
                result.append(self._normalize_chunk(
                    content=chunk,
                    metadata={"chunk_index": idx}
                ))
        return result
    
    def split_by_legal_recursive(self, text: str) -> List[Dict]:
        """
        使用法律条文专用的递归切分器切分
        该方法充分利用了 legal_recursive_splitter 的配置，会自动在条款边界处切分
        
        Args:
            text: 要切分的文本
        Returns:
            [{"content": "...", "metadata": {}}, ...]
        """
        if not text.strip():
            return []
        
        # 如果文本本身不超过chunk_size，直接返回
        if len(text) <= self.chunk_size:
            return [self._normalize_chunk(text, {})]
        
        # 使用法律条文递归切分器（已配置条款边界分隔符）
        chunks = self.legal_recursive_splitter.split_text(text)
        result = []
        for idx, chunk in enumerate(chunks):
            if chunk.strip():  # 只检查非空，有效性检查在统一过滤中处理
                result.append(self._normalize_chunk(
                    content=chunk,
                    metadata={"chunk_index": idx, "split_method": "legal_recursive"}
                ))
        return result
    
    def split_by_article_boundary(self, text: str) -> List[str]:
        """
        按条款边界切分文本（向后兼容方法）
        注意：此方法返回 List[str]，内部使用 split_by_legal_recursive 实现
        
        Args:
            text: 要切分的文本
        Returns:
            文本块列表（字符串列表）
        """
        chunks = self.split_by_legal_recursive(text)
        # 提取 content 字段以保持向后兼容
        return [chunk['content'] for chunk in chunks]
    
    def split_long_chunks(
        self, 
        chunks: List[Dict], 
        max_chunk_size: int = None
    ) -> List[Dict]:
        """
        如果文本块过长，进一步切分
        对于法律条文，优先在条款边界（"第X条"）处切分
        
        Args:
            chunks: 已切分的文本块列表
            max_chunk_size: 最大块大小（默认使用self.chunk_size）
        Returns:
            重新切分后的文本块列表
        """
        if max_chunk_size is None:
            max_chunk_size = self.chunk_size
        
        result = []
        for chunk in chunks:
            content = chunk.get('content', '').strip()
            if not content:
                continue
            
            if len(content) <= max_chunk_size:
                # chunk大小正常，直接添加（后续统一过滤）
                result.append(chunk)
            else:
                # 进一步切分：直接使用 legal_recursive_splitter
                # 因为它已经配置了条款边界分隔符，会自动在合适的地方切分
                sub_chunks = self.split_by_legal_recursive(content)
                
                # 保留原始元数据
                for sub_chunk in sub_chunks:
                    merged_metadata = chunk['metadata'].copy()
                    merged_metadata.update(sub_chunk['metadata'])
                    merged_metadata['is_sub_chunk'] = True
                    result.append({
                        "content": sub_chunk['content'],
                        "metadata": merged_metadata
                    })
        
        return result
    
    def split_with_metadata(
        self, 
        text: str, 
        source_name: str, 
        **extra_metadata
    ) -> List[Dict]:
        """
        切分文本并添加元数据（主入口方法，旧实现）
        
        Args:
            text: 要切分的文本
            source_name: 来源文件名
            **extra_metadata: 额外的元数据字段
        Returns:
            [{"content": "...", "metadata": {...}}, ...]
        """
        if not text.strip():
            return []
        
        # 判断是否为Markdown格式
        is_markdown = text.strip().startswith("#") or re.search(r'^#{1,3}\s+', text, re.MULTILINE)
        
        if is_markdown:
            # Markdown格式：先使用Markdown切分器
            chunks = self.split_markdown(text)
            
            # 对超长块进一步切分
            chunks = self.split_long_chunks(chunks, max_chunk_size=self.chunk_size)
        else:
            # 普通文本：使用法律条文递归切分器（已配置条款边界分隔符）
            chunks = self.split_by_legal_recursive(text)
        
        # 统一过滤和合并策略
        chunks = self._filter_and_merge_chunks(chunks)
        
        # 添加统一的元数据
        for chunk in chunks:
            chunk['metadata'].update({
                "source_name": source_name,
                "source_type": "legal",
                **extra_metadata
            })
        
        return chunks









