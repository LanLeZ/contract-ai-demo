# 向量库存储说明

## 📍 向量库存储位置

向量库默认存储在：**`E:/cp/backend/chroma_db/`**

目录结构：
```
chroma_db/
├── chroma.sqlite3          # ChromaDB的元数据数据库
└── {collection-uuid}/      # 每个集合的向量数据目录
    ├── data_level0.bin
    ├── header.bin
    ├── length.bin
    └── link_lists.bin
```

## 🔄 重新向量化是否需要删除旧数据？

### 情况1：批量导入法律条文（batch_import.py）

**建议：删除旧数据后再重新导入**

原因：
- 批量导入时，文档ID基于 `source_name + chunk_index` 生成
- 如果重新运行相同的导入命令，会生成相同的ID
- ChromaDB遇到相同ID时，**会更新现有文档**（不是添加新文档）
- 但如果之前导入失败或部分成功，可能会有重复或数据不一致

**如何删除：**
```bash
# 方法1：删除整个向量库目录（会删除所有数据，包括用户上传的合同）
# 谨慎使用！
rm -rf backend/chroma_db

# 方法2：使用Python脚本删除特定集合（推荐）
python -c "from app.services.vector_store import VectorStore; vs = VectorStore(); vs.delete_collection(); print('已删除集合')"
```

### 情况2：用户上传合同（通过API）

**不需要删除**

原因：
- 用户上传的合同ID包含 `user_id + contract_id`，每次上传都是唯一的
- 即使重新上传同名文件，也会生成新的ID（因为contract_id不同）
- 旧数据会保留在向量库中，但可以通过metadata过滤查询

## 📝 文档ID生成规则

文档ID格式：`user_{user_id}_contract_{contract_id}_{source_type}_{source_name}_{chunk_index}_{idx}`

- **批量导入法律条文**：`user_unknown_contract_unknown_legal_{source_name}_{chunk_index}_{idx}`
- **用户上传合同**：`user_{user_id}_contract_{contract_id}_contract_{filename}_{chunk_index}_{idx}`

## 🛠️ 清理向量库的方法

### 方法1：删除整个向量库（删除所有数据）
```bash
# Windows PowerShell
Remove-Item -Recurse -Force backend\chroma_db

# Linux/Mac
rm -rf backend/chroma_db
```

### 方法2：只删除特定集合（推荐）
```python
from app.services.vector_store import VectorStore

# 删除默认集合 "legal_contracts"
vs = VectorStore()
vs.delete_collection()
print("✅ 已删除集合")
```

### 方法3：在批量导入脚本中添加清理选项
```bash
# 使用 --clear 参数先清理再导入
python scripts/batch_import.py --dir Law-Book --source-type legal --clear
```

## ⚠️ 注意事项

1. **删除向量库会丢失所有数据**，包括：
   - 批量导入的法律条文
   - 用户上传的合同向量数据

2. **删除后需要重新向量化**，这会：
   - 重新调用通义千问API（会产生费用）
   - 需要重新等待向量化完成

3. **建议在重新导入前备份**：
   ```bash
   # 备份向量库
   cp -r backend/chroma_db backend/chroma_db_backup
   ```

## 🔍 查看向量库信息

```python
from app.services.vector_store import VectorStore

vs = VectorStore()
info = vs.get_collection_info()
print(f"集合名称: {info['name']}")
print(f"文档总数: {info['count']}")
print(f"元数据: {info['metadata']}")
```

