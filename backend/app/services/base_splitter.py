"""
文本切分器基类
提供共享的工具方法
"""
from typing import List, Dict
import string


class BaseTextSplitter:
    """文本切分器基类，提供共享的工具方法"""
    
    @staticmethod
    def _is_valid_content(content: str) -> bool:
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

