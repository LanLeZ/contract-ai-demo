"""
合同文本切分器（扁平条款策略，对齐 problem_test/splitter_test/contract_splitter_test.py）
专门处理合同文档：仅按「条款编号」扁平化切分，一条款=一个逻辑单元
"""
from typing import List, Dict, Optional
import re
from app.services.base_splitter import BaseTextSplitter


# 合同条款/编号识别与层级判定
#
# 你的方案（level 数字越小级别越高）：
# 第1级：一、二、（章节）
# 第2级：第一条 第二条（条款）
# 第3级：1. 2. / （一）（二）/ 1、2、（第一层子编号）
# 第4级：1.1 2.1（第二层子编号）
# 第5级：（1）（2）/ ①②（细项，最小）
#
# 注意：规则必须“按优先级有序”，否则像 `1.1` 会被 `^\d+\.` 抢先命中而误判层级。

# 用于“抽取 marker”的模式（顺序很重要：更具体的放前面）
CLAUSE_MARK_PATTERNS: List[str] = [
    r"^第[一二三四五六七八九十百千万〇零两]+条",        # 第2级：第一条
    r"^[一二三四五六七八九十]+、",                     # 第1级：一、
    r"^\d+\.\d+",                                     # 第4级：1.1
    r"^\d+\.",                                        # 第3级：1.
    r"^[（(][一二三四五六七八九十]+[)）]",             # 第3级：（一）
    r"^\d+、",                                        # 第3级：1、
    r"^[（(]\d+[)）]",                                # 第5级：（1）
    r"^[①②③④⑤⑥⑦⑧⑨]",                               # 第5级：①
    r"^[a-zA-Z][\.\)、)]",                            # 其他：英文编号 A.
]

# 用于“marker -> level”的判定规则（同样按优先级有序）
MARKER_LEVEL_RULES: List[tuple[int, str]] = [
    (2, r"^第[一二三四五六七八九十百千万〇零两]+条"),      # 第2级：第一条
    (1, r"^[一二三四五六七八九十]+、"),                   # 第1级：一、
    (4, r"^\d+\.\d+"),                                   # 第4级：1.1（必须在 1. 前）
    (3, r"^\d+\."),                                      # 第3级：1.
    (3, r"^[（(][一二三四五六七八九十]+[)）]"),           # 第3级：（一）
    (3, r"^\d+、"),                                      # 第3级：1、
    (5, r"^[（(]\d+[)）]"),                              # 第5级：（1）
    (5, r"^[①②③④⑤⑥⑦⑧⑨]"),                              # 第5级：①
]


class ContractTextSplitter(BaseTextSplitter):
    """
    合同文本切分器（扁平条款版）
    - 仅按合同条款编号进行「扁平化」切分，一条款（可跨多行）≈ 一个逻辑单元
    - 不再使用旧的按边界/递归字符切分逻辑
    - 支持层级追踪：章节 -> 条款 -> 子条款 -> 细项
    """

    def __init__(self, chunk_size: int = 200, chunk_overlap: int = 60, min_chunk_size: int = 1):
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
    #   层级判断工具
    # ======================

    def _get_marker_level(self, marker: str) -> int:
        """
        根据 marker 判断所属层级
        返回 1-5，数字越小级别越高
        """
        if not marker:
            return 99
        for level, pattern in MARKER_LEVEL_RULES:
            if re.match(pattern, marker):
                return level
        return 99  # 无法识别

    @staticmethod
    def _extract_number_from_marker(marker: str) -> str:
        """
        从 marker 中提取数字部分
        例如：第一条 -> 1，一、 -> 1，3.1 -> 3.1
        """
        # 中文数字映射
        cn_to_num = {
            '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
            '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
            '百': '100', '千': '1000', '万': '10000',
        }

        result = marker
        for cn, num in cn_to_num.items():
            result = result.replace(cn, num)

        # 清理格式，保留数字和小数点
        cleaned = re.sub(r'[^\d.]', '', result)
        return cleaned if cleaned else '0'

    def _generate_normalized_marker(
        self,
        marker_stack: List[str]
    ) -> str:
        """
        利用 marker_stack 直接生成统一的 clause_marker

        注意：调用此函数时，marker_stack 已经包含了当前 marker（刚被 append）

        例如：
        - 栈是 ["第一条"] → 返回 "1"
        - 栈是 ["第一条", "1、"] → 返回 "1.1"
        - 栈是 ["第一条", "1、", "（1）"] → 返回 "1.1.1"
        """
        if not marker_stack:
            return "0"

        # 从栈底到栈顶，收集所有数字
        numbers = []
        for m in marker_stack:
            # 跳过伪 marker（如 a1, a2）
            if m.startswith('a') and m[1:].isdigit():
                continue
            num = self._extract_number_from_marker(m)
            if num and num != '0':
                numbers.append(num)

        return ".".join(numbers) if numbers else marker_stack[-1]

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
        - 使用栈追踪层级信息
        - 每条款允许跨多行（后续行没有编号时视为上一条的续行）
        - 返回列表元素结构：
          {"clause_index", "marker", "parent_marker", "marker_level", "hierarchy_depth", "text"}
        """
        if not full_text or not full_text.strip():
            return []

        lines = [ln.rstrip() for ln in full_text.splitlines()]

        clauses: List[Dict] = []
        current: Optional[Dict] = None
        marker_stack: List[str] = []  # 层级栈（存 marker）
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

                # 计算当前 marker 的层级
                current_level = self._get_marker_level(marker)

                # 出栈：弹出所有级别 >= 当前级别的元素
                while marker_stack and self._get_marker_level(marker_stack[-1]) >= current_level:
                    marker_stack.pop()

                # 入栈
                marker_stack.append(marker)

                # 父级 marker（栈中倒数第二个）
                parent_marker = marker_stack[-2] if len(marker_stack) >= 2 else None

                idx += 1
                current = {
                    "clause_index": idx,
                    "marker": marker,
                    "parent_marker": parent_marker,
                    # marker_level：严格按你的 1-5 方案的“层级编号”
                    "marker_level": current_level,
                    # hierarchy_depth：当前 marker 在栈中的深度（用于展示缩进/父子关系）
                    "hierarchy_depth": len(marker_stack),
                    "text": line[len(marker):].strip(),
                    # 新增：统一格式的 clause_marker（如 1.1, 3.2.1）
                    "normalized_marker": self._generate_normalized_marker(marker_stack),
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
                    marker_stack.append(pseudo_marker)
                    current = {
                        "clause_index": idx,
                        "marker": pseudo_marker,
                        "parent_marker": None,
                        "marker_level": 99,
                        "hierarchy_depth": 0,
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
                "clause_marker": clause.get("normalized_marker", clause.get("marker")) or "",
                "parent_marker": clause.get("parent_marker"),
                # 兼容旧字段：hierarchy_level 过去被当作“深度”使用（test_hierarchy_split.py 会拿它做缩进）
                "hierarchy_level": clause.get("hierarchy_depth") or 0,
                # 新增更明确的字段，便于前端/对比服务精确展示
                "marker_level": clause.get("marker_level") or 0,
                "hierarchy_depth": clause.get("hierarchy_depth") or 0,
                **extra_metadata,
            }

            # 过滤 None 值（parent_marker 除外），确保 ChromaDB 兼容
            metadata = {k: v if v is not None else "" for k, v in metadata.items()}

            result.append(
                {
                    "content": clause_text,
                    "metadata": metadata,
                }
            )

        return result

