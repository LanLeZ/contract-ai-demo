import os
import sys
import traceback
from pathlib import Path

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


def main():
    # 1) 检查环境变量（可选但强烈建议）
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("ERROR: 未检测到环境变量 DASHSCOPE_API_KEY（请在当前终端 setx 或在项目 .env 配置）")
        return

    client = QwenChatClient()

    # 2) monkey-patch：拦截并打印 LLM 原始输出
    _orig_chat = client.chat

    call_idx = 0

    def chat_with_debug(messages, temperature=0.0):
        nonlocal call_idx
        call_idx += 1
        raw = _orig_chat(messages, temperature=temperature)
        # 打印一点上下文，方便分辨同一问题下不同提示词/不同调用
        try:
            user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), {})
            user_content = str(user_msg.get("content", ""))
        except Exception:
            user_content = ""

        print(f"\n========== LLM RAW OUTPUT (call #{call_idx}) BEGIN ==========")
        if user_content:
            print("USER_PROMPT:", user_content)
        print(raw)
        print(f"=========== LLM RAW OUTPUT (call #{call_idx}) END ===========\n")
        return raw

    client.chat = chat_with_debug  # 用调试版替换

    # 3) 你可以改这里的 question 来测不同输入
    question = "这个合同条款是否有效？"
    print("QUESTION:", question)

    # 4) 调用分类 + 法律名抽取（看它到底吐了什么）
    try:
        scope, laws = client.analyze_scope_and_laws(question)
        print("PARSED scope:", scope)
        print("PARSED laws :", laws)
    except Exception as e:
        print("ERROR: analyze_scope_and_laws 抛异常：", repr(e))
        print(traceback.format_exc())


if __name__ == "__main__":
    main()