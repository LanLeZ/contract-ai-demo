"""
HanLP 依存句法 + 合同长难句复杂度打分（测试工具）

设计目标：
- 只依赖 HanLP 输出的 tokens/heads/deprels（可选 pos）
- 输出可解释的复杂度 score + reasons，方便你调阈值/权重
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Tuple


_SENT_SPLIT_RE = re.compile(r"(?<=[。！？；;])\s*")


def split_sentences(text: str) -> List[str]:
    """
    粗切句：优先用强断句标点。
    说明：合同里经常一条很长，强断句不足；但先用这个跑通测试，再按需要增强。
    """
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENT_SPLIT_RE.split(text) if p and p.strip()]
    return parts


def _dep_tree_depth(heads_1based: List[int]) -> int:
    """
    heads: 1-based，0 表示 ROOT
    """
    n = len(heads_1based)
    if n == 0:
        return 0

    # 计算每个 token 到 root 的路径长度，取最大值
    max_depth = 0
    for i in range(n):
        depth = 0
        j = i
        seen = set()
        while True:
            if j in seen:
                # 防御：避免环导致死循环
                break
            seen.add(j)
            h = heads_1based[j]
            if h == 0:
                break
            j = h - 1
            depth += 1
            if depth > n:  # 再次防御
                break
        if depth > max_depth:
            max_depth = depth
    return max_depth


def _dep_dist_stats(heads_1based: List[int]) -> Tuple[float, int]:
    """
    依存跨度：|i - head(i)|（以 1-based 位置计算更直观）
    """
    dists: List[int] = []
    for i0, h in enumerate(heads_1based):
        if h == 0:
            continue
        i = i0 + 1
        dists.append(abs(i - h))
    if not dists:
        return 0.0, 0
    return sum(dists) / len(dists), max(dists)


@dataclass
class ComplexityConfig:
    # 权重（建议你后续调参）
    w_len_chars: float = 0.25
    w_len_tokens: float = 0.8
    w_tree_depth: float = 3.5
    w_num_clauses: float = 5.0
    w_num_conj: float = 2.0
    w_avg_dep_dist: float = 1.0
    w_max_dep_dist: float = 0.5
    w_contract_markers: float = 1.5

    # 阈值：先给个默认，跑一轮后再根据 top-N 人工校准
    threshold: float = 60.0


def score_sentence_complexity(
    raw_sentence: str,
    tokens: List[str],
    heads: List[int],
    deprels: List[str],
    *,
    cfg: ComplexityConfig | None = None,
) -> Dict[str, Any]:
    """
    输入：HanLP 依存句法的基础输出（tokens/heads/deprels）
    输出：可解释的 score / is_complex / reasons / features
    """
    cfg = cfg or ComplexityConfig()

    s = (raw_sentence or "").strip()
    len_chars = len(s)
    len_tokens = len(tokens or [])

    tree_depth = _dep_tree_depth(heads or [])
    avg_dep_dist, max_dep_dist = _dep_dist_stats(heads or [])

    # 从句数量：依存标签集可能因模型不同略有差异，这里先用通用标签名做近似
    clause_labels = {"ccomp", "advcl", "acl", "csubj", "xcomp"}
    num_clauses = sum(1 for r in (deprels or []) if r in clause_labels)

    # 并列结构
    num_conj = sum(1 for r in (deprels or []) if r == "conj")

    # 合同“复杂表达”触发词（不依赖句法）
    markers = [
        "除非",
        "否则",
        "如若",
        "若",
        "如果",
        "在.*?情况下",
        "包括但不限于",
        "应当",
        "有权",
        "不得",
        "违约金",
        "承担",
        "责任",
        "赔偿",
    ]
    marker_hits = 0
    for m in markers:
        if m.startswith("在") and "情况下" in m:
            if re.search(m, s):
                marker_hits += 1
        else:
            marker_hits += s.count(m)

    score = (
        cfg.w_len_chars * len_chars
        + cfg.w_len_tokens * len_tokens
        + cfg.w_tree_depth * tree_depth
        + cfg.w_num_clauses * num_clauses
        + cfg.w_num_conj * num_conj
        + cfg.w_avg_dep_dist * avg_dep_dist
        + cfg.w_max_dep_dist * max_dep_dist
        + cfg.w_contract_markers * marker_hits
    )

    reasons: List[str] = []
    if len_chars >= 80:
        reasons.append("句子较长")
    if tree_depth >= 6:
        reasons.append("依存结构嵌套较深")
    if num_clauses >= 2:
        reasons.append("从句/从属结构较多")
    if num_conj >= 2:
        reasons.append("并列结构较多")
    if max_dep_dist >= 10:
        reasons.append("长距离依存较多")
    if marker_hits >= 2:
        reasons.append("权利义务/例外条款触发词较多")

    return {
        "score": float(score),
        "is_complex": bool(score >= cfg.threshold),
        "reasons": reasons,
        "features": {
            "len_chars": len_chars,
            "len_tokens": len_tokens,
            "tree_depth": tree_depth,
            "num_clauses": num_clauses,
            "num_conj": num_conj,
            "avg_dep_dist": float(avg_dep_dist),
            "max_dep_dist": int(max_dep_dist),
            "marker_hits": int(marker_hits),
        },
    }


