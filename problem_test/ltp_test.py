import torch
from ltp import LTP

# 1. 选择模型：建议从 small 开始
ltp = LTP(r"E:\cp\backend\small")  # 也可以换成 "LTP/base" / "LTP/base1" 等

# 2. 可选：放到 GPU
if torch.cuda.is_available():
    ltp.to("cuda")

# 3. 自定义一些合同里常见的词（可选）
# ltp.add_words(["甲方", "乙方", "本合同", "违约金"], freq=5)

# 4. 调用 pipeline，拿到依存、语义角色等结果
clause = "乙方承诺保守甲方的商业秘密，即：不得将因实习而知悉的公司商业秘密有意或由于疏使第三方知晓(第三方指除甲方之外的公司、个人等)。未经甲方部门经理同意，乙方不得将甲方的文件、资料等以任何方式带出公司，否则，将视为严重违反公司的规章制度。"

output = ltp.pipeline(
    [clause],
    tasks=["cws", "pos", "ner", "srl", "dep", "sdp", "sdpg"]  # 你可以只要["cws","pos","srl","dep"]
)

# 5. 结果访问
cws = output.cws[0]   # 分词
pos = output.pos[0]   # 词性
dep = output.dep[0]   # 依存句法
srl = output.srl[0]   # 语义角色

print("cws:", cws)
print("pos:", pos)
print("dep:", dep)
print("srl:", srl)