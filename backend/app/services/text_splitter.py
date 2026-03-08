"""
文本切分工具（兼容层）
保持向后兼容，内部委托给专门的切分器
"""
from typing import List, Dict
from app.services.legal_splitter import LegalTextSplitter
from app.services.contract_splitter import ContractTextSplitter


class LawTextSplitter:
    """
    文本切分器（兼容层）
    根据 source_type 自动选择对应的切分器
    保持向后兼容，现有代码无需修改
    """
    
    def __init__(self, chunk_size: int = 200, chunk_overlap: int = 60):
        """
        初始化文本切分器
        注意：chunk_size 参数仅用于法律条文，合同使用固定值 200
        Args:
            chunk_size: 每个文本块的最大字符数（用于法律条文）
            chunk_overlap: 文本块之间的重叠字符数（用于法律条文）
        """
        # 法律条文切分器（使用传入的参数，默认 200 / 60）
        self.legal_splitter = LegalTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=1
        )
        
        # 合同切分器（使用固定参数）
        self.contract_splitter = ContractTextSplitter(
            chunk_size=200,
            chunk_overlap=60,
            min_chunk_size=1
        )
        
        # 保持向后兼容：保存原始参数
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_with_metadata(
        self, 
        text: str, 
        source_name: str, 
        source_type: str = "legal",
        **extra_metadata
    ) -> List[Dict]:
        """
        切分文本并添加元数据（兼容方法）
        根据 source_type 自动选择对应的切分器
        Args:
            text: 要切分的文本
            source_name: 来源文件名
            source_type: 来源类型（"legal"法律条文或"contract"合同）
            **extra_metadata: 额外的元数据字段
        Returns:
            [{"content": "...", "metadata": {...}}, ...]
        """
        if source_type == "contract":
            return self.contract_splitter.split_with_metadata(
                text=text,
                source_name=source_name,
                **extra_metadata
            )
        else:
            return self.legal_splitter.split_with_metadata(
                text=text,
                source_name=source_name,
                **extra_metadata
            )
    
    # 保留其他方法以保持兼容性（委托给对应的切分器）
    def split_markdown(self, text: str) -> List[Dict]:
        """
        切分Markdown格式的法律条文
        Args:
            text: Markdown格式的文本
        Returns:
            [{"content": "...", "metadata": {...}}, ...]
        """
        return self.legal_splitter.split_markdown(text)
    
    def split_text(self, text: str) -> List[str]:
        """
        普通文本切分
        Args:
            text: 普通文本
        Returns:
            文本块列表
        """
        chunks = self.legal_splitter.split_text(text)
        # 提取 content 字段以保持向后兼容（返回 List[str]）
        return [chunk['content'] for chunk in chunks]
    
    def split_by_article_boundary(self, text: str) -> List[str]:
        """
        按条款边界切分（法律条文）
        Args:
            text: 要切分的文本
        Returns:
            文本块列表
        """
        return self.legal_splitter.split_by_article_boundary(text)
    
    def split_by_contract_boundary(self, text: str) -> List[str]:
        """
        按合同边界切分
        Args:
            text: 要切分的文本
        Returns:
            文本块列表
        """
        return self.contract_splitter.split_by_contract_boundary(text)
    
    def split_long_chunks(
        self, 
        chunks: List[Dict], 
        max_chunk_size: int = None,
        source_type: str = "legal"
    ) -> List[Dict]:
        """
        如果文本块过长，进一步切分
        Args:
            chunks: 已切分的文本块列表
            max_chunk_size: 最大块大小（默认使用self.chunk_size）
            source_type: 来源类型，用于决定切分策略
        Returns:
            重新切分后的文本块列表
        """
        if source_type == "contract":
            if max_chunk_size is None:
                max_chunk_size = 200
            return self.contract_splitter.split_long_chunks(chunks, max_chunk_size)
        else:
            if max_chunk_size is None:
                max_chunk_size = self.chunk_size
            return self.legal_splitter.split_long_chunks(chunks, max_chunk_size)
    
    def _is_valid_content(self, content: str) -> bool:
        """
        检查内容是否有效（委托给基类方法）
        Args:
            content: 要检查的内容
        Returns:
            如果内容有效返回True，否则返回False
        """
        return self.legal_splitter._is_valid_content(content)
