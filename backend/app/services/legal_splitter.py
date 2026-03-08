"""
法律条文文本切分器（新版本）
切分逻辑参考 problem_test/demo_split_law_constitution.py：
1) Markdown：先按标题切，再按“第X条”切成条文，对极长条文用递归规则细分
2) 普通文本：直接用法律递归规则
"""
from typing import List, Dict, Any
import re
import logging
from app.services.base_splitter import BaseTextSplitter

try:
    from langchain.text_splitter import (
        MarkdownHeaderTextSplitter,
        RecursiveCharacterTextSplitter,
    )
except ImportError:
    MarkdownHeaderTextSplitter = None
    RecursiveCharacterTextSplitter = None
    print("警告: langchain未安装，请运行: pip install langchain langchain-community")

# 配置日志
logger = logging.getLogger(__name__)


class LegalTextSplitter(BaseTextSplitter):
    """
    法律条文文本切分器（新实现）
    - Markdown：先按标题切，再按“第X条”切成条文，对极长条文用递归规则细分
    - 普通文本：直接用法律递归规则
    """

    def __init__(self, chunk_size: int = 200, chunk_overlap: int = 60, min_chunk_size: int = 50):
        """
        初始化法律条文切分器
        Args:
            chunk_size: 每个文本块的最大字符数（推荐 200）
            chunk_overlap: 文本块之间的重叠字符数（推荐 60）
            min_chunk_size: 保留参数以保持向后兼容，但不再使用（切分规则已明确，无需合并小块）
        """
        if MarkdownHeaderTextSplitter is None or RecursiveCharacterTextSplitter is None:
            raise ImportError("langchain未安装，请运行: pip install langchain langchain-community")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size  # 保留但不使用

        # Markdown 按标题切分（支持 1~4 级标题）
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "header_1"),
                ("##", "header_2"),
                ("###", "header_3"),
                ("####", "header_4"),
            ]
        )

        # 法律条文专用递归切分器：优先在条款边界和句号处切
        self.legal_recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n第",  # 空行后条款
                "\n第",   # 行首条款
                "。",     # 句号
                "；",     # 分号
                "\n\n",   # 双换行
                "\n",     # 单换行
            ],
        )

    def _normalize_chunk(self, content: str, metadata: Dict | None = None) -> Dict:
        """规范化 chunk 格式"""
        if metadata is None:
            metadata = {}
        return {
            "content": (content or "").strip(),
            "metadata": metadata.copy(),
        }

    def _is_valid_content(self, content: str) -> bool:
        """复用基类的有效性判断，过滤掉全标点/空白内容"""
        return super()._is_valid_content(content)

    def _filter_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        过滤无效内容
        不再合并过小块，因为切分规则已经明确：Markdown标题 → 条款 → 过长条款再细分
        短条款是正常的切分结果，无需强制合并
        """
        if not chunks:
            return []

        result: List[Dict] = []
        for ch in chunks:
            c = (ch.get("content") or "").strip()
            if c and self._is_valid_content(c):
                result.append(ch)
            else:
                logger.debug(f"过滤无效内容: {c[:50]}...")

        return result

    def _split_by_legal_recursive(self, text: str) -> List[Dict]:
        """使用法律递归切分器"""
        text = text or ""
        if not text.strip():
            return []

        if len(text) <= self.chunk_size:
            return [self._normalize_chunk(text, {"split_method": "legal_recursive"})]

        parts = self.legal_recursive_splitter.split_text(text)
        out: List[Dict] = []
        for idx, p in enumerate(parts):
            if p.strip():
                out.append(
                    self._normalize_chunk(
                        p,
                        {
                            "chunk_index": idx,
                            "split_method": "legal_recursive",
                        },
                    )
                )
        return out

    def _split_by_article(self, text: str, base_metadata: Dict) -> List[Dict]:
        """
        按“第X条”切分成一条一条
        语义参考 demo_split_law_constitution._split_by_article
        """
        # 兼容全角/半角空格
        pattern = re.compile(r"(第\S*条[ 　])")
        parts = pattern.split(text or "")

        chunks: List[Dict] = []

        # parts 结构: [前言, "第一条 ", 第一条内容, "第二条 ", 第二条内容, ...]
        prefix = parts[0].strip() if parts else ""
        if prefix:
            md = base_metadata.copy()
            md["split_method"] = "article_preface"
            chunks.append(self._normalize_chunk(prefix, md))

        for i in range(1, len(parts), 2):
            title = parts[i].strip()                  # 例如 "第一条"
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if not body:
                continue

            content = f"{title} {body}".strip()
            md = base_metadata.copy()
            md.update(
                {
                    "article_title": title,
                    "split_method": "article",
                }
            )
            chunks.append(self._normalize_chunk(content, md))

        return chunks

    def _split_markdown(self, text: str) -> List[Dict]:
        """
        Markdown：
        1) 先按标题（宪法名、章节名）切
        2) 每个章节内部再按“第X条”切成条文
        3) 对极长条文再用递归规则细分
        """
        if not (text or "").strip():
            return []

        # 1) Markdown 标题切分
        docs = self.markdown_splitter.split_text(text)
        article_level_chunks: List[Dict] = []

        for d in docs:
            c = (d.page_content or "").strip()
            if not c:
                continue

            base_md = d.metadata.copy()

            # 如果这一块里包含“第X条”，就按条文再拆
            if re.search(r"第\S*条", c):
                article_chunks = self._split_by_article(c, base_md)
                article_level_chunks.extend(article_chunks)
            else:
                # 否则保持整块
                article_level_chunks.append(self._normalize_chunk(c, base_md))

        # 2) 对过长的条文再用法律递归规则细分（一般用不到，但保底）
        refined: List[Dict] = []
        for ch in article_level_chunks:
            content = (ch.get("content") or "").strip()
            if len(content) <= self.chunk_size:
                refined.append(ch)
                continue

            subs = self._split_by_legal_recursive(content)
            for sub in subs:
                md = ch.get("metadata", {}).copy()
                md.update(sub.get("metadata", {}))
                md["is_sub_chunk"] = True
                refined.append(
                    {
                        "content": sub["content"],
                        "metadata": md,
                    }
                )

        return refined

    # ===== 对外兼容方法 =====

    def split_markdown(self, text: str) -> List[Dict]:
        """保持方法名兼容，直接复用新 Markdown 流程（不追加统一元数据）"""
        return self._split_markdown(text)

    def split_text(self, text: str) -> List[Dict]:
        """普通文本切分：使用法律递归规则"""
        return self._split_by_legal_recursive(text)

    def split_by_legal_recursive(self, text: str) -> List[Dict]:
        """向后兼容旧方法名"""
        return self._split_by_legal_recursive(text)

    def split_by_article_boundary(self, text: str) -> List[str]:
        """
        按条款边界切分文本（向后兼容方法）
        返回 List[str]
        """
        base_metadata: Dict[str, Any] = {}
        chunks = self._split_by_article(text, base_metadata)
        return [c["content"] for c in chunks]

    def split_long_chunks(
        self,
        chunks: List[Dict],
        max_chunk_size: int | None = None,
    ) -> List[Dict]:
        """
        如果已有的文本块过长，进一步切分
        对于法律条文，优先在条款边界（"第X条"）处切分
        """
        if max_chunk_size is None:
            max_chunk_size = self.chunk_size

        result: List[Dict] = []
        for chunk in chunks:
            content = (chunk.get("content") or "").strip()
            if not content:
                continue

            if len(content) <= max_chunk_size:
                result.append(chunk)
            else:
                # 直接按法律递归规则再切一遍
                sub_chunks = self._split_by_legal_recursive(content)
                for sub in sub_chunks:
                    merged_metadata = chunk.get("metadata", {}).copy()
                    merged_metadata.update(sub.get("metadata", {}))
                    merged_metadata["is_sub_chunk"] = True
                    result.append(
                        {
                            "content": sub["content"],
                            "metadata": merged_metadata,
                        }
                    )

        return result

    def split_with_metadata(
        self,
        text: str,
        source_name: str,
        **extra_metadata: Any,
    ) -> List[Dict]:
        """
        主入口：返回 [{"content": "...", "metadata": {...}}, ...]
        切分逻辑与 problem_test/demo_split_law_constitution.py 一致
        """
        if not (text or "").strip():
            return []

        # 判断是否为 Markdown（以 # 开头 或 存在多级标题）
        is_markdown = text.strip().startswith("#")
        if not is_markdown:
            if re.search(r"^#{1,4}\s+", text, re.MULTILINE):
                is_markdown = True

        if is_markdown:
            chunks = self._split_markdown(text)
        else:
            chunks = self._split_by_legal_recursive(text)

        # 统一过滤无效内容
        chunks = self._filter_chunks(chunks)

        # 统一追加元数据
        for ch in chunks:
            ch.setdefault("metadata", {})
            ch["metadata"].update(
                {
                    "source_name": source_name,
                    "source_type": "legal",
                    **extra_metadata,
                }
            )

        return chunks
