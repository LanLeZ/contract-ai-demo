"""
合同文本切分器（扁平条款策略，对齐 problem_test/splitter_test/contract_splitter_test.py）
专门处理合同文档：仅按「条款编号」扁平化切分，一条款=一个逻辑单元
"""
from typing import List, Dict, Optional
import re
from app.services.base_splitter import BaseTextSplitter


# 与 problem_test/splitter_test/contract_splitter_test.py 对齐的条款编号模式
CLAUSE_MARK_PATTERNS = [
    r"^第[一二三四五六七八九十百千万〇零两]+条",       # 第一条、第二条
    r"^[一二三四五六七八九十]+、",                    # 一、 二、
    r"^[（(]\d+[)）]",                               # （1） (1)
    r"^[（(][一二三四五六七八九十]+[)）]",            # （一）
    r"^\d+([.,，]\d+)*[、.)]?",                       # 1. / 1.1 / 4,2 / 5.1.3 等
    r"^[①②③④⑤⑥⑦⑧⑨]",
    r"^[a-zA-Z][\.\)、)]",
]


class ContractTextSplitter(BaseTextSplitter):
    """
    合同文本切分器（扁平条款版）
    - 仅按合同条款编号进行「扁平化」切分，一条款（可跨多行）≈ 一个逻辑单元
    - 不再使用旧的按边界/递归字符切分逻辑
    """

    def __init__(self, chunk_size: int = 200, chunk_overlap: int = 60, min_chunk_size: int = 50):
        """
        初始化合同切分器
        Args:
            chunk_size: 保留参数以兼容旧接口，目前不用于内部二次切分
            chunk_overlap: 保留占位
            min_chunk_size: 最小chunk大小，小于此值的chunk会被过滤
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    # ======================
    #   条款扁平化相关工具（与测试脚本对齐）
    # ======================

    @staticmethod
    def _is_page_separator(line: str) -> bool:
        """识别 OCR 合同中形如 '--- Page 1 ---' 的分页标记"""
        return bool(re.match(r"^\s*---\s*Page\s+\d+\s*---\s*$", line))

    def _match_clause_marker(self, line: str) -> Optional[str]:
        """
        匹配一行开头的「条款编号/章节编号」
        逻辑与 problem_test/splitter_test/contract_splitter_test.py 中 _match_marker 保持一致：
        - 不做额外启发式，只要命中 CLAUSE_MARK_PATTERNS 即认为是条款编号
        """
        s = line.strip()
        if not s:
            return None

        for p in CLAUSE_MARK_PATTERNS:
            m = re.match(p, s)
            if m:
                return m.group(0)
        return None

    def _split_clauses_flat(self, full_text: str) -> List[Dict]:
        """
        扁平条款切分：与 problem_test/splitter_test/contract_splitter_test.py 中
        的 split_clauses_flat 对齐。
        - 不做分层，只按编号切出「一条一条的条款」
        - 每条款允许跨多行（后续行没有编号时视为上一条的续行）
        - 返回列表元素结构：{"clause_index", "marker", "text"}
        """
        if not full_text or not full_text.strip():
            return []

        lines = [ln.rstrip() for ln in full_text.splitlines()]

        clauses: List[Dict] = []
        current: Optional[Dict] = None
        idx = 0

        for raw_line in lines:
            line = raw_line.strip()

            # 空行：如果已经在某条款中，就当作内容里的换行
            if not line:
                if current is not None and current.get("text"):
                    current["text"] += "\n"
                continue

            # 跳过分页分隔符
            if self._is_page_separator(raw_line):
                continue

            marker = self._match_clause_marker(line)
            if marker:
                # 遇到新的条款开头，先把上一条收尾
                if current is not None:
                    clauses.append(current)

                idx += 1
                current = {
                    "clause_index": idx,
                    "marker": marker,
                    "text": line[len(marker):].strip(),
                }
            else:
                # 续行：拼到当前条款
                if current is not None:
                    if current.get("text"):
                        current["text"] += "\n" + raw_line
                    else:
                        current["text"] = raw_line
                else:
                    # 文本开头就没有编号的，按“前言”单独记一条
                    # 这里为这类「无显式条款编号」的内容生成一个伪 marker，
                    # 方便后续按 clause_marker 对齐、对比（例如 a1, a2, ...）。
                    idx += 1
                    pseudo_marker = f"a{idx}"
                    current = {
                        "clause_index": idx,
                        "marker": pseudo_marker,
                        "text": raw_line,
                    }

        if current is not None:
            clauses.append(current)

        return clauses

    # ======================
    #   对外主接口
    # ======================

    def split_with_metadata(
        self,
        text: str,
        source_name: str,
        **extra_metadata,
    ) -> List[Dict]:
        """
        切分文本并添加元数据（仅采用扁平条款策略）
        - 完全不使用旧的按边界/递归字符切分逻辑
        - 每条款 = 一个 chunk
        """
        if not text or not text.strip():
            return []

        result: List[Dict] = []

        # 直接使用扁平条款切分
        flat_clauses = self._split_clauses_flat(text)

        for clause in flat_clauses:
            clause_text = (clause.get("text") or "").strip()
            if not clause_text:
                continue
            if len(clause_text) < self.min_chunk_size:
                continue
            if not self._is_valid_content(clause_text):
                continue

            metadata = {
                "source_name": source_name,
                "source_type": "contract",
                "chunk_index": len(result),
                "clause_marker": clause.get("marker"),
                **extra_metadata,
            }

            result.append(
                {
                    "content": clause_text,
                    "metadata": metadata,
                }
            )

        return result


