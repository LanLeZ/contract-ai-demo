-- 为contracts表添加新字段
-- 执行时间：2024年
-- 说明：添加file_size、file_content、chunk_count字段以支持文件内容预览功能

-- 添加文件大小字段（字节）
ALTER TABLE contracts ADD COLUMN file_size INTEGER;

-- 添加文件内容字段（解析后的文本内容）
ALTER TABLE contracts ADD COLUMN file_content TEXT;

-- 添加分块数量字段
ALTER TABLE contracts ADD COLUMN chunk_count INTEGER;

-- 为已存在的记录设置默认值（可选）
-- UPDATE contracts SET file_size = 0 WHERE file_size IS NULL;
-- UPDATE contracts SET chunk_count = 0 WHERE chunk_count IS NULL;

