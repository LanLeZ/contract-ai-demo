# backend/app/services/kg_extractor.py

import json
import logging
from pathlib import Path
from textwrap import dedent
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models
from app.services.llm import QwenChatClient
from app.services.document_parser import DocumentParser

logger = logging.getLogger(__name__)


# 你已有的模板文件目录结构：
# - data/relations-templates/internship_new.json
# - data/relations-templates/lease.json
# - 也可以后续扩展 labor / sale 等
REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO_ROOT / "data" / "relations-templates"


# ========== 1) 合同分类（基于文件名） ==========

CONTRACT_CATEGORIES = ["internship", "lease", "labor", "sale", "other"]


def classify_contract_type_by_filename(client: QwenChatClient, filename: str) -> str:
    """
    让 LLM 根据文件名分类：internship / lease / labor / sale / other
    """
    system_prompt = (
        "你是一个合同文件分类助手，只根据“文件名”判断合同类别。\n"
        "可选类别：\n"
        "- internship：实习合同、实习协议、实习协议书等\n"
        "- lease：租赁合同、房屋租赁、租房协议等\n"
        "- labor：劳动合同、劳动聘用、劳动聘用协议等\n"
        "- sale：买卖合同、购销合同、采购合同、销售合同等\n"
        "- other：其他无法归类或不确定\n\n"
        "请严格只输出一个单词：internship / lease / labor / sale / other，不要输出其它内容。"
    )
    user_prompt = f"文件名：{filename}\n请给出该合同的类别（只输出一个单词）。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    raw = client.chat(messages, temperature=0.0).strip().lower()

    for cat in CONTRACT_CATEGORIES:
        if cat in raw:
            return cat
    # 兜底
    return "other"


def get_template_path_for_type(contract_type: str) -> Optional[Path]:
    """
    根据合同类别选择模板文件路径。
    目前模板示例：
      - internship -> internship.json
      - lease      -> lease.json
    其他类别暂无模板时返回 None。
    """
    mapping: Dict[str, str] = {
        "internship": "internship.json",
        "lease": "lease.json",
        # "labor": "labor.json",  # 未来可以扩展
        # "sale": "sale.json",
    }
    filename = mapping.get(contract_type)
    if not filename:
        return None
    path = TEMPLATE_DIR / filename
    return path if path.is_file() else None

def load_template(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_template_description(template: dict) -> str:
    """
    把 relations-templates 下的 JSON 模板转换成人类可读描述，放入 prompt。
    """
    entities = template.get("entities", [])
    relations = template.get("relations", [])

    parts: List[str] = []
    parts.append("实体类型列表：")
    for e in entities:
        parts.append(f"- {e}")

    parts.append("\n关系类型列表（带定义、头尾实体类型、触发词、示例）：")
    for r in relations:
        parts.append(
            f"\n关系名：{r.get('relation')}\n"
            f"定义：{r.get('definition')}\n"
            f"头实体类型：{r.get('head_entity_type')}\n"
            f"尾实体类型：{r.get('tail_entity_type')}\n"
            f"触发词：{', '.join(r.get('triggers', []))}\n"
            f"示例：{'; '.join(r.get('examples', []))}"
        )

    return "\n".join(parts)


def build_user_prompt(contract_text: str, template_desc: str, contract_type: str) -> str:
    """
    构造给 LLM 的 user prompt，要求返回 JSON 三元组。
    """
    type_label_map = {
        "internship": "实习合同",
        "lease": "租赁合同",
        "labor": "劳动合同",
        "sale": "买卖合同",
        "other": "其他类型合同",
    }
    pretty_type = type_label_map.get(contract_type, "合同")

    prompt = dedent(
        f"""
        你是一个合同信息抽取助手。现在给你一份中文{pretty_type}的全文内容，以及一个“关系模板”说明。
        请你根据模板中定义的实体类型和关系类型，从合同中抽取所有符合模板的三元组（头实体-关系-尾实体）。

        要求：
        1. 只抽取模板中定义的实体类型和关系类型，其他一律忽略。
        2. 关系的方向必须严格按照模板中给出的 head_entity_type 和 tail_entity_type。
        3. 不要幻想或编造合同中没有出现的信息。
        4. 如果某个关系在合同中没有出现，就不要输出该关系的三元组。

        重要提醒（必须严格遵守）：
        - 你必须根据每种关系的"触发词"来判断该关系是否在合同中出现！
        - 如果合同原文中完全没有出现某个关系对应的触发词（如"购买保险"关系的触发词是"意外伤害保险"、"办理保险"、"购买保险"等），即使模板中定义了这种关系，也绝对不要抽取！
        - 宁可少抽，也不要抽错！不要因为"模板里有这个关系"就自行推断或编造三元组！

        5. 输出为一个 JSON 数组，每个元素是一个对象，字段如下：
           - "head": 头实体在文本中的具体值
           - "head_type": 头实体的类型（必须是模板中的某个实体类型字符串）
           - "relation": 关系名（必须是模板中定义的关系名）
           - "tail": 尾实体在文本中的具体值
           - "tail_type": 尾实体的类型（必须是模板中的某个实体类型字符串）
           - "evidence": 支撑这个三元组的原文句子（必须包含对应关系的触发词）

        6. 输出必须是合法的 JSON，不要包含多余的解释性文字，只输出 JSON。

        下面是关系模板说明：
        ---
        {template_desc}
        ---
        下面是合同全文：
        ---
        {contract_text}
        ---

        请开始抽取，并按照要求输出 JSON 数组。
        """
    ).strip()
    return prompt


def call_llm_for_triples(client: QwenChatClient, prompt: str) -> str:
    """
    调用通义千问，要求只返回 JSON 字符串。
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个严谨的合同信息抽取助手。"
                "你只输出用户要求格式的 JSON，不输出其他任何文字。"
            ),
        },
        {"role": "user", "content": prompt},
    ]
    return client.chat(messages, temperature=0.1).strip()


def parse_llm_triples(raw: str) -> List[dict]:
    """
    尝试把 LLM 输出的 JSON 解析为三元组列表。
    若解析失败，返回空列表。
    """
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error("解析三元组 JSON 失败: %r", e)
        return []


def build_relation_triggers_map(template: dict) -> Dict[str, List[str]]:
    """
    从模板中构建关系名到触发词列表的映射。
    """
    triggers_map: Dict[str, List[str]] = {}
    for r in template.get("relations", []):
        relation_name = r.get("relation", "")
        triggers = r.get("triggers", [])
        if relation_name and triggers:
            triggers_map[relation_name] = triggers
    return triggers_map


def filter_valid_triples(
    triples: List[dict],
    relation_triggers_map: Optional[Dict[str, List[str]]] = None,
) -> List[dict]:
    """
    过滤掉不合法的三元组：
    1. 若 head 或 tail 为 None / 空字符串 / 只包含空白，则丢弃该条。
    2. 若提供了 relation_triggers_map，则检查 evidence 中是否包含对应关系的触发词。
       如果不包含，则认为是 LLM 幻觉，丢弃该条。
    """
    result: List[dict] = []
    for t in triples:
        head = str(t.get("head", "") or "").strip()
        tail = str(t.get("tail", "") or "").strip()
        if not head or not tail:
            continue

        relation = str(t.get("relation", "") or "").strip()
        evidence = str(t.get("evidence") or "").strip()

        # 方案2：检查 evidence 是否包含对应关系的触发词
        if relation_triggers_map and relation in relation_triggers_map:
            triggers = relation_triggers_map[relation]
            # 检查 evidence 中是否包含至少一个触发词（忽略大小写）
            evidence_lower = evidence.lower()
            has_trigger = any(
                trigger.lower() in evidence_lower for trigger in triggers
            )
            if not has_trigger:
                logger.warning(
                    "过滤掉疑似幻觉三元组: relation=%s, evidence='%s'...', "
                    "未找到触发词 %s",
                    relation,
                    evidence[:50] if evidence else "",
                    triggers,
                )
                continue

        result.append(
            {
                "head": head,
                "head_type": (t.get("head_type") or "") or None,
                "relation": relation,
                "tail": tail,
                "tail_type": (t.get("tail_type") or "") or None,
                "evidence": evidence or None,
            }
        )
    return result


def extract_kg_for_contract(
    db: Session,
    contract: models.Contract,
    client: Optional[QwenChatClient] = None,
    parser: Optional[DocumentParser] = None,
) -> Tuple[str, List[models.KnowledgeTriple]]:
    """
    对单份合同执行：
    1. 根据 filename 分类合同类别
    2. 根据类别选择模板（若无模板则直接返回空结果）
    3. 调用 LLM 抽取三元组
    4. 过滤掉 head/tail 为空的三元组
    5. 写入数据库 knowledge_triples 表（先清空旧的，再插入新的）

    返回：(合同类别, 三元组 ORM 对象列表)
    """
    if client is None:
        client = QwenChatClient()
    if parser is None:
        parser = DocumentParser()

    # 1) 分类（只看文件名）
    contract_type = classify_contract_type_by_filename(client, contract.filename)

    # 更新合同表中的 contract_type
    contract.contract_type = contract_type
    db.add(contract)
    db.flush()  # 先不提交，整体最后 commit

    # 2) 选择模板
    template_path = get_template_path_for_type(contract_type)
    if not template_path:
        logger.info("合同类型 %s 暂无模板，跳过抽取", contract_type)
        # 清空旧的 KG 结果
        db.query(models.KnowledgeTriple).filter(
            models.KnowledgeTriple.contract_id == contract.id
        ).delete(synchronize_session=False)
        db.commit()
        return contract_type, []

    template = load_template(template_path)
    template_desc = build_template_description(template)

    # 3) 获取合同全文文本（优先用 file_content，没有就从文件解析）
    if contract.file_content and contract.file_content.strip():
        contract_text = contract.file_content
    else:
        contract_text = parser.parse(contract.file_path, file_type=None)

    # 4) 构造 Prompt 并调用 LLM
    user_prompt = build_user_prompt(contract_text, template_desc, contract_type)
    raw_output = call_llm_for_triples(client, user_prompt)
    triples_raw = parse_llm_triples(raw_output)

    # 构建关系触发词映射，用于后处理过滤幻觉
    relation_triggers_map = build_relation_triggers_map(template)
    triples_clean = filter_valid_triples(triples_raw, relation_triggers_map)

    # 5) 清空旧的，再写入新的
    db.query(models.KnowledgeTriple).filter(
        models.KnowledgeTriple.contract_id == contract.id
    ).delete(synchronize_session=False)

    orm_triples: List[models.KnowledgeTriple] = []
    for t in triples_clean:
        if not t["relation"]:
            # 没有关系名也跳过
            continue
        orm_triple = models.KnowledgeTriple(
            contract_id=contract.id,
            head=t["head"],
            head_type=t["head_type"],
            relation=t["relation"],
            tail=t["tail"],
            tail_type=t["tail_type"],
            evidence=t["evidence"],
            template_name=template_path.name,
        )
        db.add(orm_triple)
        orm_triples.append(orm_triple)

    db.commit()
    # 重新加载，确保带上 created_at 等
    for t in orm_triples:
        db.refresh(t)

    return contract_type, orm_triples