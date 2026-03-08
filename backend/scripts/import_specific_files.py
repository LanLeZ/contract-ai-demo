"""
补充导入失败的法律文件到向量库
用法: python scripts/import_specific_files.py
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.document_parser import DocumentParser
from app.services.text_splitter import LawTextSplitter
from app.services.vector_store import VectorStore


def import_specific_file(file_path: str, source_type: str = "legal"):
    """
    导入指定的法律文件到向量库
    
    Args:
        file_path: 文件路径（相对于项目根目录）
        source_type: 来源类型（默认 "legal"）
    """
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"\n📄 处理文件: {file_path_obj.name}")
    print(f"   路径: {file_path}")
    
    try:
        # 初始化服务
        parser = DocumentParser()
        splitter = LawTextSplitter(chunk_size=500, chunk_overlap=50)
        vector_store = VectorStore()
        
        # 1. 解析文件
        text_content = parser.parse(str(file_path_obj), file_type='md')
        
        if not text_content.strip():
            print(f"  ⚠️  文件内容为空，跳过")
            return False
        
        # 2. 切分文本
        # 使用相对于 Law-Book 目录的路径作为 source_name
        if 'Law-Book' in str(file_path_obj):
            # 找到 Law-Book 目录的位置
            parts = file_path_obj.parts
            law_book_idx = None
            for i, part in enumerate(parts):
                if part == 'Law-Book':
                    law_book_idx = i
                    break
            
            if law_book_idx is not None:
                relative_parts = parts[law_book_idx + 1:]
                source_name = '/'.join(relative_parts)
            else:
                source_name = file_path_obj.name
        else:
            source_name = file_path_obj.name
        
        print(f"   source_name: {source_name}")
        
        chunks = splitter.split_with_metadata(
            text=text_content,
            source_name=source_name,
            source_type=source_type
        )
        
        if not chunks:
            print(f"  ⚠️  文本切分失败，跳过")
            return False
        
        print(f"   ✅ 切分为 {len(chunks)} 个文本块")
        
        # 3. 向量化并存储
        chunk_count = vector_store.add_documents(chunks, batch_size=50)
        
        print(f"  ✅ 成功导入 {chunk_count} 个文本块到向量库")
        return True
        
    except Exception as e:
        print(f"  ❌ 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数：导入两个失败的法律文件"""
    
    # 项目根目录
    project_root = Path(__file__).parent.parent.parent
    
    # 要导入的文件列表
    files_to_import = [
        "Law-Book/3-民法商法/著作权法（2020-11-11）.md",
        "Law-Book/4-行政法/境外非政府组织境内活动管理法（2017-11-04）.md"
    ]
    
    print("=" * 60)
    print("🚀 开始补充导入失败的法律文件")
    print("=" * 60)
    
    success_count = 0
    failed_count = 0
    
    for file_path in files_to_import:
        full_path = project_root / file_path
        if import_specific_file(str(full_path)):
            success_count += 1
        else:
            failed_count += 1
    
    # 打印统计信息
    print("\n" + "=" * 60)
    print("📊 导入统计:")
    print(f"  成功: {success_count}")
    print(f"  失败: {failed_count}")
    
    # 显示向量库总文档数
    try:
        vector_store = VectorStore()
        total_count = vector_store.get_collection_count()
        print(f"  向量库总文档数: {total_count}")
    except Exception as e:
        print(f"  ⚠️  无法获取向量库统计: {str(e)}")
    
    print("=" * 60)
    
    if success_count == len(files_to_import):
        print("\n✅ 所有文件导入成功！")
    else:
        print(f"\n⚠️  有 {failed_count} 个文件导入失败")


if __name__ == "__main__":
    main()






























