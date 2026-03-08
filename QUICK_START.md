# 快速测试指南

## 前置准备

### 1. 安装OCR依赖（PNG文件支持）

**方式1：使用PaddleOCR（推荐）**
```bash
pip install paddleocr
```

**方式2：使用pytesseract（备选）**
```bash
# 安装Python包
pip install pytesseract pillow

# Windows系统还需要安装Tesseract OCR引擎
# 下载地址：https://github.com/UB-Mannheim/tesseract/wiki
# 安装后需要配置环境变量或指定路径
```

### 2. 执行数据库迁移

```bash
# 方式1：使用MySQL客户端
mysql -u root -p contract_ai < backend/migrations/add_contract_fields.sql

# 方式2：在MySQL客户端中执行
mysql -u root -p
use contract_ai;
source backend/migrations/add_contract_fields.sql;
```

### 3. 重启后端服务

```bash
cd backend
# 如果使用uvicorn
uvicorn app.main:app --reload

# 如果使用其他方式，按原方式重启
```

---

## 快速测试步骤

### 测试1：合同列表展示修改

1. **启动前端和后端服务**
2. **登录系统**
3. **查看合同列表**
   - 检查"上传时间"列是否只显示日期（不显示时间）
   - 检查分页控件是否只显示页码，无"每页条数"选择器和总数

**预期结果：**
- ✅ 上传时间格式：2024/1/15（只有日期）
- ✅ 分页：固定10条/页，无选择器和总数

---

### 测试2：TXT文件上传

1. **准备测试文件**
   - 创建一个 `test.txt` 文件，内容包含中文和英文
   - 确保文件小于50MB

2. **上传文件**
   - 在合同列表页面，点击上传区域
   - 选择 `test.txt` 文件
   - 等待上传完成

3. **验证结果**
   - ✅ 上传成功提示
   - ✅ 合同列表中出现该文件，类型标签为"TXT"（橙色）
   - ✅ 点击文件，查看详情页面
   - ✅ 详情页面TAB1显示文件内容

**测试不同编码：**
- UTF-8编码的TXT文件
- GBK编码的TXT文件

---

### 测试3：PNG文件上传（需要OCR库）

1. **准备测试文件**
   - 创建一个包含文字的PNG图片（可以用截图工具）
   - 确保文件小于50MB

2. **上传文件**
   - 在合同列表页面，拖拽或选择PNG文件
   - 等待上传和OCR处理完成

3. **验证结果**
   - ✅ 上传成功提示
   - ✅ 合同列表中出现该文件，类型标签为"PNG"（紫色）
   - ✅ 点击文件，查看详情页面
   - ✅ 详情页面TAB1显示OCR识别出的文字内容

**注意事项：**
- 如果未安装OCR库，上传会失败并提示安装
- OCR处理可能需要几秒到几十秒，取决于图片大小

---

### 测试4：合同详情页面（TAB1）

1. **上传任意支持的文件**（PDF/DOCX/MD/TXT/PNG）

2. **点击合同列表中的文件**

3. **验证详情页面**
   - ✅ 标题显示文件名
   - ✅ 有"返回"按钮
   - ✅ 显示"合同详情"标签页（TAB1）
   - ✅ TAB1包含：
     - 文件ID（代码格式）
     - 文件类型（带颜色标签）
     - 文件大小（MB格式，如果有）
     - 分块数量（如果有）
     - 上传时间（完整日期时间）
     - 文件内容预览区域（显示解析后的文本）

4. **验证文件内容预览**
   - ✅ 文本内容正确显示
   - ✅ 长文本可以滚动查看
   - ✅ 文本格式保持（换行、空格等）

---

## 常见问题排查

### 问题1：PNG文件上传失败，提示需要安装OCR库

**解决方案：**
```bash
# 安装PaddleOCR（推荐）
pip install paddleocr

# 或安装pytesseract
pip install pytesseract pillow
```

### 问题2：数据库迁移失败

**检查：**
- 确认数据库连接正常
- 确认contracts表存在
- 检查是否已经执行过迁移（字段已存在）

**手动执行：**
```sql
-- 检查字段是否已存在
DESCRIBE contracts;

-- 如果字段不存在，手动执行
ALTER TABLE contracts ADD COLUMN file_size INTEGER;
ALTER TABLE contracts ADD COLUMN file_content TEXT;
ALTER TABLE contracts ADD COLUMN chunk_count INTEGER;
```

### 问题3：TXT文件内容显示乱码

**原因：** 文件编码不是UTF-8或GBK

**解决方案：**
- 将文件转换为UTF-8编码
- 或使用支持的文件编码（UTF-8、GBK）

### 问题4：PNG OCR识别不准确

**原因：** OCR识别准确度受图片质量影响

**解决方案：**
- 使用清晰的图片（分辨率足够）
- 确保文字清晰可读
- 尝试使用PaddleOCR（中文识别效果更好）

### 问题5：合同详情页面不显示文件内容

**检查：**
- 确认文件上传成功
- 检查数据库 `file_content` 字段是否有值
- 查看后端日志是否有错误

---

## 验证清单

完成快速测试后，确认以下项目：

- [ ] 合同列表上传时间只显示日期
- [ ] 合同列表分页配置正确（固定10条，无选择器和总数）
- [ ] TXT文件可以上传和解析
- [ ] PNG文件可以上传和OCR识别（如果安装了OCR库）
- [ ] 合同详情页面TAB1显示完整信息
- [ ] 文件内容预览区域正确显示文本
- [ ] 数据库新字段正确保存

---

## 下一步

完成快速测试后，可以：
1. 查看完整测试方案：`TEST_PLAN.md`
2. 查看修改总结：`MODIFICATION_SUMMARY.md`
3. 进行更详细的测试






























