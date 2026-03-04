#排查分类模型无法调用LLM的问题
import socket
print(socket.getaddrinfo("dashscope.aliyuncs.com", 443))

import requests
print(requests.get("https://dashscope.aliyuncs.com/actuator/health", timeout=5))