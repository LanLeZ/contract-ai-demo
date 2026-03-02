import logging
import os
from typing import List, Literal

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

    def classify_scope(self, question: str) -> ScopeType:
        """
        根据问题内容判断检索范围：
        - contract_only: 仅依赖合同文本
        - contract_and_law: 需要结合通用法律条文
        """
        system_prompt = (
            "你是一个分类助手，只根据问题内容判断是否需要查询法律条文。"
            "仅回答这两个字符串之一：contract_only 或 contract_and_law。"
        )
        user_prompt = (
            "用户问题如下：\n"
            f"{question}\n\n"
            "如果只需要根据具体合同内容判断，回答：contract_only；\n"
            "如果需要结合通用法律条文判断，回答：contract_and_law。\n"
            "不要输出任何其他文字。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = self.chat(messages, temperature=0.0).strip()
        if "contract_and_law" in raw:
            return "contract_and_law"
        return "contract_only"


