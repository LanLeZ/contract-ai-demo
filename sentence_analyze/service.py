from __future__ import annotations

"""
FastAPI 服务：HanLP 依存句法 + 合同句子复杂度分析

说明：
- 运行在单独的虚拟环境（如 venv_hanlp_test）中
- 对外只暴露 HTTP 接口，供 backend 项目通过 HTTP 调用
"""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from hanlp_dep import lazy_load_hanlp_dep, parse_dep
from complexity_utils import split_sentences, score_sentence_complexity, ComplexityConfig


app = FastAPI(title="HanLP Sentence Analyze Service")


# ---------- Pydantic 模型 ----------


class ClauseIn(BaseModel):
    clause_index: int
    clause_marker: Optional[str] = None
    text: str


class AnalyzeRequest(BaseModel):
    doc_id: Optional[str] = None
    complexity_threshold: Optional[float] = None
    clauses: List[ClauseIn]


class SentenceDepOut(BaseModel):
    tokens: List[str]
    heads: List[int]
    deprels: List[str]


class SentenceComplexityOut(BaseModel):
    score: float
    is_complex: bool
    reasons: List[str]
    features: Dict[str, Any]


class SentenceResultOut(BaseModel):
    sentence_index: int
    sentence_text: str
    dep: SentenceDepOut
    complexity: SentenceComplexityOut


class ClauseResultOut(BaseModel):
    clause_index: int
    clause_marker: Optional[str] = None
    text: str
    clause_complexity_score: float
    is_complex: bool
    sentence_results: List[SentenceResultOut]


class HighClauseOut(BaseModel):
    clause_index: int
    clause_marker: Optional[str] = None
    clause_complexity_score: float


class AnalyzeResponse(BaseModel):
    doc_id: Optional[str] = None
    config: Dict[str, Any]
    clauses: List[ClauseResultOut]
    high_complexity_clauses: List[HighClauseOut]


# ---------- 模型懒加载（进程级缓存） ----------

_dep_model = None


def get_dep_model():
    global _dep_model
    if _dep_model is None:
        _dep_model = lazy_load_hanlp_dep()
    return _dep_model


# ---------- 健康检查 ----------


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ---------- 主接口 ----------


@app.post("/analyze_clauses", response_model=AnalyzeResponse)
def analyze_clauses(payload: AnalyzeRequest) -> AnalyzeResponse:
    """
    输入：一份合同（或任意文档）的条款列表
    输出：每条条款的句子级句法 + 复杂度结果，以及整体高复杂条款列表
    """
    dep_model = get_dep_model()

    base_cfg = ComplexityConfig()
    if payload.complexity_threshold is not None:
        cfg = ComplexityConfig(**{**base_cfg.__dict__, "threshold": payload.complexity_threshold})
    else:
        cfg = base_cfg

    clause_results: List[ClauseResultOut] = []
    high_clauses: List[HighClauseOut] = []

    for clause in payload.clauses:
        # 1) 粗分句
        sents = split_sentences(clause.text)
        sent_results: List[SentenceResultOut] = []

        for si, sent in enumerate(sents):
            if not sent.strip():
                continue

            # 2) HanLP 依存分析
            dep_out = parse_dep(dep_model, sent)
            tokens = dep_out["tokens"]
            heads = dep_out["heads"]
            deprels = dep_out["deprels"]

            # 3) 复杂度评分
            comp = score_sentence_complexity(
                raw_sentence=sent,
                tokens=tokens,
                heads=heads,
                deprels=deprels,
                cfg=cfg,
            )

            sent_results.append(
                SentenceResultOut(
                    sentence_index=si,
                    sentence_text=sent,
                    dep=SentenceDepOut(tokens=tokens, heads=heads, deprels=deprels),
                    complexity=SentenceComplexityOut(
                        score=comp["score"],
                        is_complex=comp["is_complex"],
                        reasons=list(comp["reasons"]),
                        features=dict(comp["features"]),
                    ),
                )
            )

        if sent_results:
            max_score = max(sr.complexity.score for sr in sent_results)
        else:
            max_score = 0.0

        clause_is_complex = bool(max_score >= cfg.threshold)

        clause_result = ClauseResultOut(
            clause_index=clause.clause_index,
            clause_marker=clause.clause_marker,
            text=clause.text,
            clause_complexity_score=max_score,
            is_complex=clause_is_complex,
            sentence_results=sent_results,
        )

        # 只有超过阈值的复杂条款才返回给主系统
        if clause_is_complex:
            clause_results.append(clause_result)
            high_clauses.append(
                HighClauseOut(
                    clause_index=clause.clause_index,
                    clause_marker=clause.clause_marker,
                    clause_complexity_score=max_score,
                )
            )

    return AnalyzeResponse(
        doc_id=payload.doc_id,
        config={"threshold": cfg.threshold},
        clauses=clause_results,
        high_complexity_clauses=high_clauses,
    )


if __name__ == "__main__":
    # 方便直接 python service.py 启动
    import uvicorn

    uvicorn.run("service:app", host="0.0.0.0", port=8001, reload=False)


