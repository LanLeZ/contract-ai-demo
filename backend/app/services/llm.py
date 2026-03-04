import json
import logging
import os
from typing import List, Literal, Tuple

from dotenv import load_dotenv

try:
    from dashscope import Generation
    import dashscope
except ImportError:
    Generation = None
    dashscope = None


logger = logging.getLogger(__name__)

# 加载环境变量（使用默认 .env 位置，保持与项目其他模块一致）
load_dotenv()

ScopeType = Literal["contract_only", "contract_and_law"]


class QwenChatClient:
    """通义千问对话客户端封装"""

    def __init__(self, model: str = "qwen-plus") -> None:
        if Generation is None:
            raise ImportError("dashscope 未安装，请先运行: pip install dashscope")

        self.model = model
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("未找到 DASHSCOPE_API_KEY，请在 .env 中配置")

        # 与 test_llm.py 保持一致：直接设置全局 dashscope.api_key
        if dashscope is not None:
            dashscope.api_key = api_key

    def chat(self, messages: List[dict], temperature: float = 0.3) -> str:
        """
        调用通义千问进行对话

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
        """
        resp = Generation.call(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )

        if resp.status_code != 200:
            logger.error("Qwen chat error: %s", resp.message)
            raise RuntimeError(f"Qwen chat 调用失败: {resp.message}")

        # DashScope Generation.call qwen-plus 当前返回 output["text"]
        return resp.output.get("text", "").strip()

    def analyze_scope_and_laws(self, question: str) -> Tuple[ScopeType, List[str]]:
        """
        一次性完成：检索范围分类 + 可能相关法律文件名抽取（贴近 Law-Book 的文件名风格）
        laws 输出示例：["民法典", "兵役法", "电子签名法"]
        """
        
        system_prompt = (
            "你是合同问答场景下的“检索意图分析助手”。\n"
            "任务：根据用户问题，判断是否需要检索通用法律条文，并（如需要）识别其直接提到或明显隐含需要适用的可能相关的法律名称。\n\n"
            "请严格输出 JSON（不要输出除 JSON 以外的任何文字）：\n"
            "{\n"
            "  \"scope\": \"contract_only\" | \"contract_and_law\",\n"
            "  \"laws\": [\"民法典\", \"兵役法（2021-08-20）\", \"电子签名法（2019-04-23）\"]\n"
            "}\n\n"
            "规则：\n"
            "- scope 只能二选一。\n"
            "- laws 里的每一项必须是“Law-Book 文件名风格”的简称：\n"
            "  - 不要加《》\n"
            "  - 不要带“中华人民共和国/中国”等前缀\n"
            "  - 不要带路径、不带扩展名 .md\n"
            "  - 日期（如（2021-08-20））可写可不写；不确定就不要编造日期\n"
            "- 若 scope=contract_only，则 laws 必须为空数组 []。\n"
            "- 若无法确定具体法律，但判断需要法律检索：scope=contract_and_law 且 laws=[]。\n"
        )
        user_prompt = f"用户问题：{question}"

        raw = self.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        ).strip()

        scope: ScopeType = "contract_only"
        laws: List[str] = []

        try:
            data = json.loads(raw)
            scope_raw = str(data.get("scope", "")).strip()
            if scope_raw in ("contract_only", "contract_and_law"):
                scope = scope_raw  # type: ignore[assignment]

            items = data.get("laws") or []
            if isinstance(items, list):
                laws = [str(x).strip() for x in items if str(x).strip()]
        except Exception:
            # 解析失败：直接退化为仅合同范围
            scope = "contract_only"
            return scope, []

        # 兜底清洗（防止模型偶尔输出《》/全称/扩展名）
        cleaned: List[str] = []
        for name in laws:
            x = name
            x = x.replace("《", "").replace("》", "")
            x = x.replace("中华人民共和国", "").replace("中国", "")
            x = x.replace(".md", "").replace(".markdown", "")
            x = x.strip()
            if x:
                cleaned.append(x)

        if scope == "contract_only":
            cleaned = []

        return scope, cleaned

    def answer_question_with_rag(
        self,
        question: str,
        contract_filename: str,
        scope: ScopeType,
        context_text: str,
        temperature: float = 0.3,
    ) -> str:
        """
        基于 RAG 上下文回答合同相关问题

        Args:
            question: 用户问题
            contract_filename: 合同文件名
            scope: 检索范围（contract_only 或 contract_and_law）
            context_text: 检索到的上下文（合同片段+法律条文）
            temperature: LLM 温度参数，默认 0.3

        Returns:
            LLM 生成的回答文本
        """
        system_prompt = (
            "你是一名精通中国合同与民商事法律的智能助手。\n"
            '你必须严格基于\"检索到的合同条款片段\"和\"检索到的法律条文片段\"来回答问题，'
            "优先引用这些片段中的关键信息进行分析与说明。\n"
            "如果上下文中没有足够信息支撑某个结论，请明确说明\"上下文未提供相关条款/法条，因此只能给出一般性提示\"，"
            "不要编造具体的条款号、法条内容或当事人名称。\n"
            "在回答中请尽量使用通俗易懂的中文，并在需要时给出实际操作建议（例如是否需要补充条款、修改条款或咨询律师）。"
        )

        user_prompt = (
            f"这是用户上传的一份合同：\n"
            f"- 文件名：{contract_filename}\n"
            f"- 问题检索范围：{scope}\n\n"
            f"以下是根据用户问题检索到的相关上下文（可能包括合同条款和法律条文）：\n\n"
            f"{context_text}\n\n"
            f"请你结合上述上下文，回答用户的问题：\n"
            f"{question}\n\n"
            "请注意：\n"
            '1. 优先引用给定片段中的信息进行分析，可以在表述中用\"根据检索到的第[编号]条片段\"来提示依据来源；\n'
            "2. 如果某个关键信息在上下文中找不到，请明确说明缺失，不要自行编造；\n"
            '3. 最后请用一两句话做\"综合风险总结\"和\"建议下一步怎么做\"。'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return self.chat(messages, temperature=temperature)


