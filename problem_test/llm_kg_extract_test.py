import argparse
import json
import os
import sys
from pathlib import Path
from textwrap import dedent

# 让本脚本在任意工作目录下运行时，都能稳定导入 backend/app 下的包：
# repo 结构是 backend/app/...（backend 不是 Python 包），因此要把 backend 目录加到 sys.path。
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

# 加载项目 .env（避免“明明写了 .env 但 os.getenv 读不到”的误判）
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:
    # dotenv 不是强依赖；如果环境变量已在系统里配置，也能继续跑
    pass

from app.services.llm import QwenChatClient  # pyright: ignore[reportMissingImports]
from app.services.document_parser import DocumentParser  # pyright: ignore[reportMissingImports]


def load_contract_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_template(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_template_description(template: dict) -> str:
    """
    把 internship_new.json 这种模板转换成可读描述，放到 prompt 里喂给 LLM。
    """
    entities = template.get("entities", [])
    relations = template.get("relations", [])

    parts: list[str] = []

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


def build_user_prompt(contract_text: str, template_desc: str) -> str:
    """
    构造给 LLM 的 user prompt，要求返回 JSON 三元组。
    """
    prompt = dedent(
        f"""
        你是一个合同信息抽取助手。现在给你一份中文实习合同的全文内容，以及一个“关系模板”说明。
        请你根据模板中定义的实体类型和关系类型，从合同中抽取所有符合模板的三元组（头实体-关系-尾实体）。

        要求：
        1. 只抽取模板中定义的实体类型和关系类型，其他一律忽略。
        2. 关系的方向必须严格按照模板中给出的 head_entity_type 和 tail_entity_type。
        3. 不要幻想或编造合同中没有出现的信息。
        4. 如果某个关系在合同中没有出现，就不要输出该关系的三元组。
        5. 输出为一个 JSON 数组，每个元素是一个对象，字段如下：
           - "head": 头实体在文本中的具体值（例如“张三”、“甲方”、“测试实习生”、“2024年08月12日至2024年09月11日”等）
           - "head_type": 头实体的类型（必须是模板中的某个实体类型字符串，例如“实习生”、“用人单位”等）
           - "relation": 关系名（必须是模板中定义的关系名，例如“实习单位”、“获得报酬”等）
           - "tail": 尾实体在文本中的具体值
           - "tail_type": 尾实体的类型（必须是模板中的某个实体类型字符串）
           - "evidence": 支撑这个三元组的原文句子（或者几个紧挨着的短句）

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
    使用项目里的 QwenChatClient 调用通义千问。
    要求只返回 JSON 字符串（模型可能仍会犯错，后面再尝试解析）。
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
    # 低温度，尽量减少胡思乱想
    return client.chat(messages, temperature=0.1).strip()


def main():
    """
    使用固定的测试文件：
    - 合同：data/contract/internship/internship1.docx
    - 模板：data/relations-templates/internship_new.json
    """

    contract_path = str(REPO_ROOT / "data" / "contract" / "internship" / "internship2.docx")
    template_path = str(REPO_ROOT / "data" / "relations-templates" / "internship_new.json")

    if not os.path.isfile(contract_path):
        raise FileNotFoundError(f"合同文件不存在: {contract_path}")
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("ERROR: 未检测到环境变量 DASHSCOPE_API_KEY，请在当前终端或 .env 中配置。")
        return

    # 初始化通义千问客户端
    client = QwenChatClient()
    doc_parser = DocumentParser()

    # 加载合同和模板
    # internship1 是 DOCX，因此使用 DocumentParser 解析成纯文本
    contract_text = doc_parser.parse(contract_path, file_type="docx")
    template = load_template(template_path)
    template_desc = build_template_description(template)
    user_prompt = build_user_prompt(contract_text, template_desc)

    print(">>> 已读取合同与模板，开始调用通义千问抽取三元组...\n")

    llm_output = call_llm_for_triples(client, user_prompt)

    print(">>> 通义千问原始输出（模型应只输出 JSON 数组）：")
    print(llm_output)

    # 可选：尝试解析 JSON，并以更易读的形式简单打印
    try:
        triples = json.loads(llm_output)
        print("\n>>> 解析后的三元组列表（简要展示）：")
        for i, t in enumerate(triples, start=1):
            print(f"\n#{i}")
            print(f"  head      : {t.get('head')} ({t.get('head_type')})")
            print(f"  relation  : {t.get('relation')}")
            print(f"  tail      : {t.get('tail')} ({t.get('tail_type')})")
            print(f"  evidence  : {t.get('evidence')}")
    except Exception as e:
        print("\n!!! 解析 JSON 失败，原始内容见上方。错误信息：", repr(e))


if __name__ == "__main__":
    main()


