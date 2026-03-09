"""
HanLP 依存句法：模型加载 + 输出归一化

说明：
- 从 problem_test/hanlp_test/hanlp_dep.py 拷贝而来
- 作为独立的 HanLP 句法分析服务的内部模块使用
"""

from __future__ import annotations

from typing import Any, Dict, List


def lazy_load_hanlp_dep(model_name: str | None = None):
    """
    延迟加载 HanLP 模型，避免 import 即下载。
    """
    import hanlp  # type: ignore

    dep = hanlp.load(model_name) if model_name else None

    if dep is None:
        # 默认：CTB7 中文依存句法（不同 HanLP 版本名字可能不同）
        try:
            model = hanlp.pretrained.dep.CTB7_BIAFFINE_DEP_ZH  # type: ignore[attr-defined]
        except Exception:
            model = "CTB7_BIAFFINE_DEP_ZH"
        dep = hanlp.load(model)

    # 说明：CTB7_BIAFFINE_DEP_ZH（TF biaffine parser）通常不能直接吃 raw string。
    # 它依赖 (token, POS) 特征，因此这里自动补齐 tok + pos。
    try:
        from hanlp.components.parsers.biaffine_parser_tf import (  # type: ignore
            BiaffineDependencyParserTF,
        )
    except Exception:
        BiaffineDependencyParserTF = ()  # type: ignore

    if isinstance(dep, BiaffineDependencyParserTF):
        try:
            tok_model = hanlp.pretrained.tok.COARSE_ELECTRA_SMALL_ZH  # type: ignore[attr-defined]
        except Exception:
            tok_model = "COARSE_ELECTRA_SMALL_ZH"
        # POS：优先使用不依赖 HuggingFace 的老模型，避免在受限网络环境下超时。
        # 说明：tagset 可能与 CTB7 训练集不完全一致，但可保证链路可跑通；不在 vocab 的 tag 会被映射为 UNK。
        try:
            pos_model = hanlp.pretrained.pos.CTB5_POS_RNN  # type: ignore[attr-defined]
        except Exception:
            pos_model = "CTB5_POS_RNN"

        tok = hanlp.load(tok_model)
        try:
            pos = hanlp.load(pos_model)
        except Exception:
            # 兜底：如果上面 model_name 常量不存在或加载失败，再尝试另一个 CTB5 RNN 模型
            try:
                pos = hanlp.load(hanlp.pretrained.pos.CTB5_POS_RNN_FASTTEXT_ZH)  # type: ignore[attr-defined]
            except Exception:
                pos = hanlp.load("CTB5_POS_RNN_FASTTEXT_ZH")
        return {"tok": tok, "pos": pos, "dep": dep}

    return dep


def parse_dep(dep_model, sentence: str) -> Dict[str, Any]:
    """
    统一成：tokens/heads/deprels 三件套
    """

    def _unwrap_singleton(x: Any) -> Any:
        return x[0] if isinstance(x, list) and len(x) == 1 else x

    # A) TF biaffine dep bundle: sentence -> tok -> pos -> dep
    if isinstance(dep_model, dict) and "dep" in dep_model and "tok" in dep_model and "pos" in dep_model:
        tok_out = dep_model["tok"]([sentence])
        tokens = _unwrap_singleton(tok_out)

        pos_out = dep_model["pos"]([tokens])
        pos_tags = _unwrap_singleton(pos_out)

        dep_out = dep_model["dep"]([list(zip(tokens, pos_tags))])
        out = _unwrap_singleton(dep_out)
    else:
        out = dep_model(sentence)

    # B) 输出已经是 dict（常见于 MTL）
    if isinstance(out, dict):
        tokens = out.get("tok") or out.get("tok/fine") or out.get("tok/coarse") or out.get("token") or []
        dep = out.get("dep") or {}
        heads = dep.get("head") or out.get("dep/head") or []
        deprels = dep.get("rel") or out.get("dep/rel") or []
        return {"tokens": list(tokens), "heads": list(heads), "deprels": list(deprels)}

    # C) 输出是 CoNLLSentence（或 list[CoNLLSentence]）
    try:
        from hanlp_common.conll import CoNLLSentence  # type: ignore
    except Exception:
        CoNLLSentence = ()  # type: ignore

    if isinstance(out, CoNLLSentence):
        return {
            "tokens": [w.form for w in out],
            "heads": [int(w.head) for w in out],
            "deprels": [w.deprel for w in out],
        }
    if isinstance(out, list) and out and isinstance(out[0], CoNLLSentence):
        s = out[0]
        return {
            "tokens": [w.form for w in s],
            "heads": [int(w.head) for w in s],
            "deprels": [w.deprel for w in s],
        }

    # D) 输出是 list-of-dicts（CTB7 biaffine dep 常见形态：[[{form, head, deprel, ...}, ...]]）
    out2 = _unwrap_singleton(out)
    if isinstance(out2, list):
        out3 = _unwrap_singleton(out2)
        if isinstance(out3, list) and out3 and isinstance(out3[0], dict):
            tokens2: List[str] = []
            heads2: List[int] = []
            deprels2: List[str] = []
            for w in out3:
                tokens2.append(str(w.get("form") or ""))
                try:
                    heads2.append(int(w.get("head") or 0))
                except Exception:
                    heads2.append(0)
                deprels2.append(str(w.get("deprel") or ""))
            return {"tokens": tokens2, "heads": heads2, "deprels": deprels2}

    raise TypeError(f"无法识别 HanLP dep 输出类型：{type(out)!r}")


