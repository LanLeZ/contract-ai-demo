from dashscope import Generation
import dashscope

# 这里还是写你的真实 key，只是演示的时候注意别传出去
dashscope.api_key = "sk-05e1dee2d2e34bbdb3ebe4733698402b"

# 打印一下 SDK 里实际用的配置（不是环境变量）
print("dashscope.__version__ =", getattr(dashscope, "__version__", "unknown"))
print("dashscope.api_key      =", dashscope.api_key[:10] + "..." if dashscope.api_key else None)
print("dashscope.base_url     =", getattr(dashscope, "base_url", None))
print("dashscope.base_http_api_url =", getattr(dashscope, "base_http_api_url", None))

try:
    resp = Generation.call(
        model="qwen-plus",
        messages=[{"role": "user", "content": "你好"}],
    )
    print("resp =", resp)
except Exception as e:
    import traceback
    print("Exception type:", type(e))
    print("Exception str :", str(e))
    traceback.print_exc()