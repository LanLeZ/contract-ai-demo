import json
import logging
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from app import models
from app.services.contract_splitter import ContractTextSplitter
from app.services.llm import attach_contract_compare_llm_analysis

logger = logging.getLogger(__name__)


def _build_marker_map(chunks: List[Dict]) -> Dict[str, str]:
    """
    根据 ContractTextSplitter.split_with_metadata 的结果，构建:
        clause_marker -> 合并后的内容文本
    简单策略：如果同一个 marker 对应多个 chunk，就按换行拼接。
    """
    marker_map: Dict[str, List[str]] = {}

    for c in chunks:
        content = (c.get("content") or "").strip()
        meta = c.get("metadata") or {}
        marker = meta.get("clause_marker") or ""

        # 如果没有条款编号，可以选择跳过或单独处理，这里先跳过
        if not marker:
            continue

        marker_map.setdefault(marker, []).append(content)

    # 合并为单个字符串
    merged: Dict[str, str] = {m: "\n".join(parts) for m, parts in marker_map.items()}
    return merged


def _diff_clause_text(old_text: str, new_text: str) -> List[str]:
    """
    对两段条款文本做 diff，返回逐行 diff 结果（列表形式，方便保存 JSON）
    """
    import difflib

    old_lines = old_text.splitlines(keepends=False)
    new_lines = new_text.splitlines(keepends=False)

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="left",
            tofile="right",
            lineterm="",
        )
    )
    return diff_lines


def _build_clause_marker_diff(
    left_contract: models.Contract,
    right_contract: models.Contract,
) -> Dict[str, Any]:
    """
    使用 ContractTextSplitter 的条款扁平切分结果，按 clause_marker 对齐做差异对比。

    返回结构参考 problem_test/compare_test/contract_compare_by_clause_marker_result.json：
    {
      "summary": {...},
      "only_in_left": [...],
      "only_in_right": [...],
      "changed_clauses": [...],
    }
    """
    splitter = ContractTextSplitter(
        chunk_size=200,
        chunk_overlap=60,
        # 对比场景下尽量不要因为 min_chunk_size 过滤掉小条款，对齐 demo 脚本设为 1
        min_chunk_size=1,
    )

    left_text = (left_contract.file_content or "").strip()
    right_text = (right_contract.file_content or "").strip()

    left_chunks = splitter.split_with_metadata(
        text=left_text,
        source_name=left_contract.filename or f"contract_{left_contract.id}_left",
        side="left",
        contract_id=left_contract.id,
        contract_type=left_contract.contract_type,
    )
    right_chunks = splitter.split_with_metadata(
        text=right_text,
        source_name=right_contract.filename or f"contract_{right_contract.id}_right",
        side="right",
        contract_id=right_contract.id,
        contract_type=right_contract.contract_type,
    )

    markers_left = _build_marker_map(left_chunks)
    markers_right = _build_marker_map(right_chunks)

    set_left = set(markers_left.keys())
    set_right = set(markers_right.keys())

    only_in_left_markers = sorted(list(set_left - set_right))
    only_in_right_markers = sorted(list(set_right - set_left))
    in_both = sorted(list(set_left & set_right))

    # 构建 delete 类型的差异（只在左侧存在）
    only_in_left: List[Dict[str, Any]] = []
    for marker in only_in_left_markers:
        left_text = markers_left.get(marker, "")
        only_in_left.append(
            {
                "clause_marker": marker,
                "left_text": left_text,
                "right_text": "",
                "change_type": "delete",
            }
        )

    # 构建 add 类型的差异（只在右侧存在）
    only_in_right: List[Dict[str, Any]] = []
    for marker in only_in_right_markers:
        right_text = markers_right.get(marker, "")
        only_in_right.append(
            {
                "clause_marker": marker,
                "left_text": "",
                "right_text": right_text,
                "change_type": "add",
            }
        )

    # 构建 alter 类型的差异（两侧都存在但内容不同）
    changed_clauses: List[Dict[str, Any]] = []
    for marker in in_both:
        left_clause = markers_left.get(marker, "")
        right_clause = markers_right.get(marker, "")

        if left_clause == right_clause:
            continue

        diff_lines = _diff_clause_text(left_clause, right_clause)
        changed_clauses.append(
            {
                "clause_marker": marker,
                "left_text": left_clause,
                "right_text": right_clause,
                "diff": diff_lines,
                "change_type": "alter",
            }
        )

    # 构建统一的 all_differences 列表，包含所有差异
    all_differences: List[Dict[str, Any]] = []
    all_differences.extend(only_in_left)
    all_differences.extend(only_in_right)
    all_differences.extend(changed_clauses)

    result: Dict[str, Any] = {
        "summary": {
            "only_in_left_count": len(only_in_left),
            "only_in_right_count": len(only_in_right),
            "in_both_count": len(in_both),
            "changed_in_both_count": len(changed_clauses),
        },
        "only_in_left": only_in_left,
        "only_in_right": only_in_right,
        "changed_clauses": changed_clauses,
        "all_differences": all_differences,  # 新增：统一的差异列表
    }

    return result


def run_contract_compare(
    db: Session,
    user: models.User,
    left_contract: models.Contract,
    right_contract: models.Contract,
) -> models.ContractCompare:
    """
    运行一次合同对比：
    - 新建一条 ContractCompare 记录
    - 执行条款级对比 + 可选 LLM 风险分析

    目前实现为同步执行，后续如有需要可以改成异步任务队列。
    """
    compare = models.ContractCompare(
        user_id=user.id,
        left_contract_id=left_contract.id,
        right_contract_id=right_contract.id,
        status="running",
    )
    db.add(compare)
    db.commit()
    db.refresh(compare)

    try:
        logger.info(
            "开始执行合同对比 compare_id=%s left=%s right=%s",
            compare.id,
            left_contract.id,
            right_contract.id,
        )

        # 1) 先按条款编号进行结构化对比
        result_obj = _build_clause_marker_diff(
            left_contract=left_contract,
            right_contract=right_contract,
        )

        # 2) 调用 LLM 对差异做综合分析与风险提示（非强制，失败则降级）
        attach_contract_compare_llm_analysis(
            base_result=result_obj,
            left_contract=left_contract,
            right_contract=right_contract,
        )

        compare.result_json = json.dumps(result_obj, ensure_ascii=False)
        compare.status = "success"
        compare.finished_at = datetime.utcnow()

        db.add(compare)
        db.commit()
        db.refresh(compare)
    except Exception as e:  # noqa: BLE001
        logger.exception("合同对比执行失败 compare_id=%s: %s", compare.id, e)
        compare.status = "failed"
        compare.error_message = str(e)
        compare.finished_at = datetime.utcnow()
        db.add(compare)
        db.commit()
        db.refresh(compare)

    return compare
