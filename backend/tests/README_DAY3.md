# 第3天测试方案文档

## 测试环境准备

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `env.example` 为 `.env` 并配置：

```bash
# 必须配置
DASHSCOPE_API_KEY=your-dashscope-api-key-here
```

**获取API Key步骤：**
1. 访问 https://dashscope.console.aliyun.com/
2. 注册/登录阿里云账号
3. 创建API Key
4. 将API Key填入 `.env` 文件

### 3. 准备测试文本（可选）

如果需要测试自定义文本，可以准备以下格式的文件：

**Markdown格式** (`test_law.md`):
```markdown
# 第一章 总则

第一条 法律条文内容...

第二条 法律条文内容...

## 第二章 分则

第三条 法律条文内容...
```

**普通文本格式** (`test_plain.txt`):
```
第一段内容...

第二段内容...
```

## 测试方法

### 方法1: 运行自动化测试脚本（推荐）

```bash
cd backend
python tests/test_day3.py
```

测试脚本会自动执行以下测试：
1. ✅ Embedding服务测试
2. ✅ 文本切分工具测试
3. ✅ 向量库初始化测试
4. ✅ 集成测试（完整流程）

### 方法2: 手动测试各个模块

#### 测试1: Embedding服务

```bash
cd backend
python -c "
from app.services.embedding import DashScopeEmbedder
embedder = DashScopeEmbedder()
result = embedder.embed_query('测试文本')
print(f'向量维度: {len(result)}')
print(f'前5个值: {result[:5]}')
"
```

**预期输出：**
```
向量维度: 1024
前5个值: [0.123, -0.456, 0.789, ...]
```

#### 测试2: 文本切分工具

```bash
python -c "
from app.services.text_splitter import LawTextSplitter
splitter = LawTextSplitter()
text = '''
# 第一章 总则
第一条 为了规范...
第二条 适用范围...
'''
chunks = splitter.split_with_metadata(text, 'test_law.md', 'legal')
print(f'切分块数: {len(chunks)}')
for i, chunk in enumerate(chunks[:2]):
    print(f'块{i+1}: {chunk[\"content\"][:50]}...')
"
```

**预期输出：**
```
切分块数: 2
块1: # 第一章 总则
第一条 为了规范...
块2: 第二条 适用范围...
```

#### 测试3: 向量库初始化

```bash
python -c "
from app.services.vector_store import VectorStore
vs = VectorStore()
print(f'向量库已初始化，当前文档数: {vs.get_collection_count()}')
"
```

**预期输出：**
```
向量库已初始化，当前文档数: 0
```

#### 测试4: 完整流程测试

```bash
python -c "
from app.services.text_splitter import LawTextSplitter
from app.services.vector_store import VectorStore

# 准备测试文本
text = '''
# 劳动合同法
第一条 为了完善劳动合同制度...
第二条 中华人民共和国境内的企业...
'''

# 切分
splitter = LawTextSplitter()
chunks = splitter.split_with_metadata(text, '劳动合同法.md', 'legal')

# 添加到向量库
vs = VectorStore(persist_directory='./chroma_db_test')
count = vs.add_documents(chunks)
print(f'成功添加 {count} 个文档')

# 搜索
results = vs.search('劳动合同', top_k=2)
print(f'搜索到 {len(results)} 个结果')
for r in results:
    print(f'相似度: {r[\"score\"]:.2f}, 内容: {r[\"content\"][:50]}...')
"
```

## 测试检查清单

第3天结束时，确保以下功能正常：

- [ ] ✅ `embedding.py` 能成功调用通义千问API（向量维度1024）
- [ ] ✅ `text_splitter.py` 能正确切分Markdown和普通文本
- [ ] ✅ `vector_store.py` 能初始化Chroma并持久化存储
- [ ] ✅ 文本切分后能正确添加元数据
- [ ] ✅ 向量库能存储和检索文档
- [ ] ✅ 相似度搜索返回正确的结果和分数
- [ ] ✅ 元数据过滤功能正常工作

## 常见问题

### Q1: `dashscope` 模块未找到
**解决：** `pip install dashscope`

### Q2: `langchain` 模块未找到
**解决：** `pip install langchain langchain-community`

### Q3: `chromadb` 模块未找到
**解决：** `pip install chromadb`

### Q4: API Key错误
**解决：** 检查 `.env` 文件中的 `DASHSCOPE_API_KEY` 是否正确设置

### Q5: 向量维度不是1024
**解决：** 确认使用的是 `text-embedding-v3` 模型（默认）

### Q6: Chroma数据库文件位置
**解决：** 默认存储在 `./chroma_db` 目录，可以通过 `persist_directory` 参数修改

## 下一步（第4天）

完成第3天测试后，第4天将实现：
1. 文档解析模块（PDF/DOCX/Markdown）
2. 批量导入脚本
3. 向量搜索API接口
4. 前端集成


