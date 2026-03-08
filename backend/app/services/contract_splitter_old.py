"""
合同文本切分器（旧版策略备份）
原始实现：基于合同边界 + 递归字符切分，chunk_size 更小以提高检索细粒度
"""
from typing import List, Dict
import re
from app.services.base_splitter import BaseTextSplitter

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None
    print("警告: langchain未安装，请运行: pip install langchain langchain-community")


class ContractTextSplitter(BaseTextSplitter):
    """合同文本切分器（旧版）"""
    
    def __init__(self, chunk_size: int = 200, chunk_overlap: int = 60, min_chunk_size: int = 50):
        """
        初始化合同切分器
        Args:
            chunk_size: 每个文本块的最大字符数（合同使用更小的chunk_size）
            chunk_overlap: 文本块之间的重叠字符数
            min_chunk_size: 最小chunk大小，小于此值的chunk会被过滤
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        if RecursiveCharacterTextSplitter is None:
            raise ImportError("langchain未安装，请运行: pip install langchain langchain-community")
        
        # 合同专用的递归切分器（识别数字边界词，使用更小的chunk_size以提高检索细粒度）
        # chunk_size=200, chunk_overlap=60 适合1500字左右的合同（约6-8个chunk）
        self.contract_recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n第",      # "第X条"、"第X章"等
                "\n第",        # 行内"第X条"
                "\n\n（",      # "（一）"、"（1）"等
                "\n（",        # 行内编号
                "。",          # 句号
                "；",          # 分号
                "\n\n",        # 双换行
                "\n",          # 单换行
                "，",          # 逗号
            ]
        )
    
    def split_by_contract_boundary(self, text: str) -> List[str]:
        """
        按合同边界词切分文本（针对合同类型）
        识别多种数字边界词：阿拉伯数字、汉字数字（非大写）、条款标记等
        Args:
            text: 要切分的文本
        Returns:
            文本块列表
        """
        if not text.strip():
            return []
        
        # 合同使用更小的chunk_size（200）
        max_chunk_size = self.chunk_size
        
        # 如果文本本身不超过chunk_size，直接返回
        if len(text) <= max_chunk_size:
            return [text]
        
        # 扩展的边界匹配模式（按优先级排序）
        # 1. 阿拉伯数字："第1条"、"第2条"、"第10条"等
        # 2. 汉字数字（非大写）："第一条"、"第二条"、"第十条"等
        # 3. 编号格式："1."、"2."、"（1）"、"（2）"、"（一）"、"（二）"等
        # 4. 章节："第一章"、"第二章"、"第一项"等
        
        boundary_patterns = [
            r'(\n+第\d+条)',                    # "第1条"、"第2条"（阿拉伯数字）
            r'(\n+第[一二三四五六七八九十百千万零]+条)',  # "第一条"、"第二条"、"第一百零一条"（汉字数字）
            r'(\n+第\d+章)',                    # "第1章"、"第2章"
            r'(\n+第[一二三四五六七八九十百千万零]+章)',  # "第一章"、"第二章"、"第一百零一章"
            r'(\n+第\d+项)',                    # "第1项"、"第2项"
            r'(\n+第[一二三四五六七八九十百千万零]+项)',  # "第一项"、"第二项"、"第一百零一项"
            r'(\n+\d+[\.、])',                  # "1."、"2、"等（行首数字编号）
            r'(\n+[一二三四五六七八九十零]+[\.、])',    # "一、"、"二、"等（行首汉字编号）
            r'(\n+（\d+）)',                    # "（1）"、"（2）"等
            r'(\n+（[一二三四五六七八九十零]+）)',      # "（一）"、"（二）"等
        ]
        
        # 合并所有模式
        combined_pattern = '|'.join(boundary_patterns)
        
        # 分割文本，保留分隔符
        parts = re.split(combined_pattern, text)
        
        # 如果没有找到边界，使用合同专用递归切分器
        if len(parts) == 1:
            return self.contract_recursive_splitter.split_text(text)
        
        # 合并分隔符和内容，构建块
        chunks = []
        current_chunk = ""
        
        for i, part in enumerate(parts):
            # 跳过 None 值（re.split 使用捕获组时可能返回 None）
            if part is None or not isinstance(part, str):
                continue
            
            # 检查是否是边界标记
            # 使用完整的模式匹配（包含开头和结尾锚点）来确保准确识别边界标记
            is_boundary = any(re.match(pattern + '$', part) for pattern in boundary_patterns)
            
            if is_boundary:
                # 这是一个边界标记
                if current_chunk and len(current_chunk.strip()) > 0:
                    # 如果当前块加上这个边界标记不超过限制，合并
                    if len(current_chunk + part) <= max_chunk_size:
                        current_chunk += part
                    else:
                        # 当前块已满，保存它
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = part
                else:
                    current_chunk = part
            else:
                # 这是内容部分
                if current_chunk:
                    # 尝试添加内容
                    if len(current_chunk + part) <= max_chunk_size:
                        current_chunk += part
                    else:
                        # 当前块已满
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        # 如果新内容本身也超长，需要进一步切分
                        if len(part) > max_chunk_size:
                            sub_chunks = self.contract_recursive_splitter.split_text(part)
                            chunks.extend([chunk.strip() for chunk in sub_chunks if chunk.strip()])
                        else:
                            current_chunk = part
                else:
                    current_chunk = part
            
            # 如果当前块超长，需要进一步切分
            if len(current_chunk) > max_chunk_size:
                if current_chunk.strip():
                    sub_chunks = self.contract_recursive_splitter.split_text(current_chunk)
                    chunks.extend([chunk.strip() for chunk in sub_chunks if chunk.strip()])
                current_chunk = ""
        
        # 处理最后一个块
        if current_chunk.strip():
            if len(current_chunk) > max_chunk_size:
                sub_chunks = self.contract_recursive_splitter.split_text(current_chunk)
                chunks.extend([chunk.strip() for chunk in sub_chunks if chunk.strip()])
            else:
                chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if chunk]  # 过滤空块
    
    def split_with_metadata(
        self, 
        text: str, 
        source_name: str, 
        **extra_metadata
    ) -> List[Dict]:
        """
        切分文本并添加元数据
        Args:
            text: 要切分的文本
            source_name: 来源文件名
            **extra_metadata: 额外的元数据字段
        Returns:
            [{"content": "...", "metadata": {...}}, ...]
        """
        if not text.strip():
            return []
        
        # 检查是否包含条款/章节标记
        has_boundary = re.search(
            r'第\d+条|第[一二三四五六七八九十百千万零]+条|'
            r'第\d+章|第[一二三四五六七八九十百千万零]+章|'
            r'第\d+项|第[一二三四五六七八九十百千万零]+项|'
            r'\n\d+[\.、]|\n[一二三四五六七八九十零]+[\.、]|'
            r'\n（\d+）|\n（[一二三四五六七八九十零]+）',
            text
        )
        
        if has_boundary:
            # 如果包含条款/章节标记，使用边界切分
            chunks = self.split_by_contract_boundary(text)
        else:
            # 否则使用合同专用递归切分器
            chunks = self.contract_recursive_splitter.split_text(text)
        
        result = []
        for idx, chunk in enumerate(chunks):
            if len(chunk) >= self.min_chunk_size:  # 过滤过小的chunk
                result.append({
                    "content": chunk,
                    "metadata": {
                        "source_name": source_name,
                        "source_type": "contract",
                        "chunk_index": idx,
                        **extra_metadata
                    }
                })
        return result
    
    def split_long_chunks(
        self, 
        chunks: List[Dict], 
        max_chunk_size: int = None
    ) -> List[Dict]:
        """
        如果文本块过长，进一步切分
        对于合同，优先在合同边界处切分
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
            content = chunk['content']
            if len(content) <= max_chunk_size:
                # 检查内容是否有效
                if self._is_valid_content(content) and len(content) >= self.min_chunk_size:
                    result.append(chunk)
            else:
                # 进一步切分
                # 对于合同，优先使用合同边界切分
                has_boundary = re.search(
                    r'第\d+条|第[一二三四五六七八九十百千万零]+条|'
                    r'第\d+章|第[一二三四五六七八九十百千万零]+章|'
                    r'第\d+项|第[一二三四五六七八九十百千万零]+项|'
                    r'\n\d+[\.、]|\n[一二三四五六七八九十零]+[\.、]|'
                    r'\n（\d+）|\n（[一二三四五六七八九十零]+）',
                    content
                )
                if has_boundary:
                    sub_chunks = self.split_by_contract_boundary(content)
                else:
                    sub_chunks = self.contract_recursive_splitter.split_text(content)
                
                for idx, sub_chunk in enumerate(sub_chunks):
                    cleaned_chunk = sub_chunk.strip()
                    # 过滤掉无效内容
                    if cleaned_chunk and self._is_valid_content(cleaned_chunk) and len(cleaned_chunk) >= self.min_chunk_size:
                        new_chunk = {
                            "content": cleaned_chunk,
                            "metadata": chunk['metadata'].copy()
                        }
                        new_chunk['metadata']['sub_chunk_index'] = idx
                        result.append(new_chunk)
        
        return result










