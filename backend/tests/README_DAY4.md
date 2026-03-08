# 第四天功能测试文档

## 📋 测试概述

本文档描述第四天开发功能的测试方案，包括文档解析、文件上传、向量搜索等功能的测试。

---

## 🧪 测试环境准备

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

### 2. 配置环境变量

确保 `.env` 文件中配置了：
- `DASHSCOPE_API_KEY`: 阿里云DashScope API密钥
- `DATABASE_URL`: 数据库连接字符串

### 3. 启动测试数据库

确保数据库服务正在运行。

---

## 📝 测试模块说明

### 1. TestDocumentParser - 文档解析器测试

测试文档解析器的核心功能：

- ✅ `test_parse_markdown`: 测试Markdown文件解析
- ✅ `test_detect_file_type`: 测试文件类型自动检测
- ✅ `test_parse_unsupported_type`: 测试不支持的文件类型处理

**测试文件**: `test_day4.py::TestDocumentParser`

### 2. TestFileUpload - 文件上传API测试

测试文件上传和管理功能：

- ✅ `test_upload_without_auth`: 测试未认证上传（应返回401）
- ✅ `test_upload_markdown`: 测试上传Markdown文件
- ✅ `test_upload_invalid_type`: 测试上传不支持的文件类型
- ✅ `test_get_documents_list`: 测试获取文档列表
- ✅ `test_get_document_detail`: 测试获取文档详情
- ✅ `test_delete_document`: 测试删除文档

**测试文件**: `test_day4.py::TestFileUpload`

### 3. TestVectorSearch - 向量搜索API测试

测试向量搜索功能：

- ✅ `test_search_without_auth`: 测试未认证搜索（应返回401）
- ✅ `test_search_documents`: 测试向量搜索
- ✅ `test_search_by_contract`: 测试按合同搜索
- ✅ `test_search_empty_query`: 测试空查询处理

**测试文件**: `test_day4.py::TestVectorSearch`

### 4. TestIntegration - 集成测试

测试完整的工作流程：

- ✅ `test_full_workflow`: 测试完整流程（上传 -> 搜索 -> 删除）

**测试文件**: `test_day4.py::TestIntegration`

---

## 🚀 运行测试

### 运行所有测试

```bash
cd backend
pytest tests/test_day4.py -v
```

### 运行特定测试类

```bash
# 测试文档解析器
pytest tests/test_day4.py::TestDocumentParser -v

# 测试文件上传
pytest tests/test_day4.py::TestFileUpload -v

# 测试向量搜索
pytest tests/test_day4.py::TestVectorSearch -v

# 测试集成流程
pytest tests/test_day4.py::TestIntegration -v
```

### 运行特定测试方法

```bash
pytest tests/test_day4.py::TestFileUpload::test_upload_markdown -v
```

### 生成测试报告

```bash
pytest tests/test_day4.py -v --html=report.html --self-contained-html
```

---

## 📊 测试用例详细说明

### 1. 文档解析测试

#### test_parse_markdown
- **目的**: 验证Markdown文件能正确解析
- **步骤**:
  1. 创建临时Markdown文件
  2. 使用DocumentParser解析
  3. 验证解析结果包含预期内容
- **预期结果**: 解析成功，内容正确

#### test_detect_file_type
- **目的**: 验证文件类型自动检测功能
- **步骤**: 测试不同扩展名的文件类型检测
- **预期结果**: 正确识别pdf/docx/md文件类型

---

### 2. 文件上传测试

#### test_upload_markdown
- **目的**: 验证Markdown文件上传功能
- **步骤**:
  1. 准备测试文件内容
  2. 调用上传API
  3. 验证返回的合同信息
- **预期结果**: 
  - 状态码201
  - 返回合同ID、文件名等信息
  - 文件已保存到uploads目录
  - 文件已向量化并存储到Chroma

#### test_get_documents_list
- **目的**: 验证获取文档列表功能
- **步骤**:
  1. 上传几个测试文件
  2. 调用获取列表API
  3. 验证返回的列表
- **预期结果**: 返回当前用户的所有合同列表

#### test_delete_document
- **目的**: 验证删除文档功能
- **步骤**:
  1. 上传一个文件
  2. 调用删除API
  3. 验证文件已删除
- **预期结果**: 
  - 状态码204
  - 文件已从磁盘删除
  - 数据库记录已删除

---

### 3. 向量搜索测试

#### test_search_documents
- **目的**: 验证向量搜索功能
- **步骤**:
  1. 上传包含特定内容的文件
  2. 等待向量化完成（可能需要几秒）
  3. 执行搜索查询
  4. 验证搜索结果
- **预期结果**: 
  - 状态码200
  - 返回相关搜索结果
  - 结果包含内容、元数据、相似度分数

#### test_search_by_contract
- **目的**: 验证按合同搜索功能
- **步骤**:
  1. 上传一个文件
  2. 等待向量化完成
  3. 使用合同ID执行搜索
  4. 验证只返回该合同内的结果
- **预期结果**: 只返回指定合同内的搜索结果

---

### 4. 集成测试

#### test_full_workflow
- **目的**: 验证完整工作流程
- **步骤**:
  1. 上传文件
  2. 等待向量化
  3. 执行搜索
  4. 删除文件
- **预期结果**: 所有步骤都成功执行

---

## 🔍 手动测试指南

### 1. 使用Swagger UI测试

1. 启动后端服务：
```bash
cd backend
uvicorn app.main:app --reload
```

2. 访问 http://localhost:8000/docs

3. 测试流程：
   - 先调用 `/api/auth/login` 获取token
   - 在Swagger UI右上角点击"Authorize"，输入token
   - 测试 `/api/documents/upload` 上传文件
   - 测试 `/api/documents/` 获取列表
   - 测试 `/api/search/` 执行搜索

### 2. 使用curl测试

#### 登录获取token
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test_user&password=test_password"
```

#### 上传文件
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_contract.md"
```

#### 获取文档列表
```bash
curl -X GET "http://localhost:8000/api/documents/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 执行搜索
```bash
curl -X POST "http://localhost:8000/api/search/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "合同条款", "top_k": 5}'
```

---

## 🐛 常见问题

### 1. 向量化失败
- **原因**: DashScope API密钥未配置或无效
- **解决**: 检查 `.env` 文件中的 `DASHSCOPE_API_KEY`

### 2. 文件上传失败
- **原因**: 文件大小超过限制或文件格式不支持
- **解决**: 检查文件大小（最大50MB）和文件格式（pdf/docx/md）

### 3. 搜索无结果
- **原因**: 向量化尚未完成
- **解决**: 上传文件后等待几秒再搜索，或增加等待时间

### 4. 数据库连接失败
- **原因**: 数据库服务未启动或连接字符串错误
- **解决**: 检查数据库服务和 `.env` 中的 `DATABASE_URL`

---

## 📈 性能测试

### 测试文件大小限制
- 小文件（< 1MB）: 应快速处理
- 中等文件（1-10MB）: 应在合理时间内完成
- 大文件（10-50MB）: 可能需要较长时间，但应能完成

### 测试并发上传
```python
import asyncio
import aiohttp

async def upload_file(session, token, file_content):
    async with session.post(
        "http://localhost:8000/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": file_content}
    ) as response:
        return await response.json()

# 并发上传10个文件
async def test_concurrent_upload():
    token = "YOUR_TOKEN"
    async with aiohttp.ClientSession() as session:
        tasks = [upload_file(session, token, b"test content") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        print(results)
```

---

## ✅ 测试检查清单

- [ ] 文档解析器能正确解析PDF/DOCX/Markdown文件
- [ ] 文件上传API能接收文件并保存
- [ ] 上传的文件能自动解析、切分、向量化
- [ ] 向量搜索API能返回相关结果
- [ ] 按合同搜索功能正常
- [ ] 文档列表API能正确返回用户文档
- [ ] 文档删除功能正常（包括文件、数据库、向量库）
- [ ] 错误处理正确（未认证、文件类型错误、文件过大等）
- [ ] 批量导入脚本能导入法律条文
- [ ] 所有API都有Swagger文档

---

## 📝 测试报告模板

测试完成后，应生成测试报告，包括：

1. **测试环境信息**
   - Python版本
   - 依赖包版本
   - 数据库类型和版本

2. **测试结果统计**
   - 总测试数
   - 通过数
   - 失败数
   - 跳过数

3. **失败用例详情**
   - 失败的测试用例
   - 错误信息
   - 可能的原因

4. **性能指标**
   - 平均响应时间
   - 文件上传速度
   - 向量化速度
   - 搜索响应时间

---

## 🔗 相关文档

- [第三天测试文档](README_DAY3.md)
- [API文档](http://localhost:8000/docs)
- [项目README](../README.md)































