"""
批量导入法律条文到向量库
用法: python scripts/batch_import.py --dir Law-Book --source-type legal
"""
import argparse
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.document_parser import DocumentParser
from app.services.text_splitter import LawTextSplitter
from app.services.vector_store import VectorStore


def scan_markdown_files(directory: Path) -> list[Path]:
    """扫描目录下的所有Markdown文件"""
    markdown_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.md', '.markdown')):
                markdown_files.append(Path(root) / file)
    return sorted(markdown_files)

def import_law_files(directory: str, source_type: str = "legal", clear_existing: bool = False):
    """
    业务含义：
        - 批量将法律条文（或其他 Markdown 形式的法规文档）导入到底层向量库；
        - 这些数据作为“公共法律语料”，为所有用户的问答和合同分析提供基础知识，
          通过 metadata 中的 source_type="legal" 与用户上传合同数据进行区分。

    技术实现：
        - 递归扫描指定目录下的 `.md` / `.markdown` 文件，每个文件视为一份“原始文档”；
        - 使用 DocumentParser 统一解析文档内容（屏蔽具体文件格式差异）；
        - 使用 LawTextSplitter 依据 chunk_size / chunk_overlap 将长文本切分为适合向量检索的片段；
        - 调用 VectorStore.add_documents() 将片段批量写入 ChromaDB，附带 source_type / source_name 等 metadata；
        - 当 clear_existing=True 时，先删除原有集合并重建，避免历史导入残留导致统计混乱（用户上传的合同集合不受影响）。

    Args:
        directory: 法律条文目录路径
        source_type: 来源类型（默认 "legal"，也可用于导入模拟合同等数据）
        clear_existing: 是否在导入前清理现有集合（会删除当前集合内所有法律条文数据）
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"❌ 目录不存在: {directory}")
        return
    
    print(f"📂 扫描目录: {directory}")
    markdown_files = scan_markdown_files(dir_path)
    
    if not markdown_files:
        print(f"❌ 未找到Markdown文件")
        return
    
    print(f"✅ 找到 {len(markdown_files)} 个Markdown文件")
    print("-" * 60)
    
    # 初始化服务
    parser = DocumentParser()
    splitter = LawTextSplitter()
    vector_store = VectorStore()
    
    # 如果指定清理，先删除现有集合
    if clear_existing:
        print("\n🗑️  清理现有向量库集合...")
        try:
            old_count = vector_store.get_collection_count()
            vector_store.delete_collection()
            print(f"   ✅ 已删除旧集合（包含 {old_count} 个文档）")
            # 重新初始化向量库（创建新集合）
            vector_store = VectorStore()
        except Exception as e:
            print(f"   ⚠️  清理失败（可能集合不存在）: {str(e)}")
            vector_store = VectorStore()
    
    # 统计信息
    total_files = len(markdown_files)
    success_files = 0
    failed_files = 0
    total_chunks = 0
    
    # 处理每个文件
    for idx, file_path in enumerate(markdown_files, 1):
        print(f"\n[{idx}/{total_files}] 处理文件: {file_path.name}")
        
        try:
            # 1. 解析文件
            text_content = parser.parse(str(file_path), file_type='md')
            
            if not text_content.strip():
                print(f"  ⚠️  文件内容为空，跳过")
                failed_files += 1
                continue
            
            # 2. 切分文本
            # 使用相对路径作为source_name
            relative_path = file_path.relative_to(dir_path)
            source_name = str(relative_path).replace('\\', '/')
            
            chunks = splitter.split_with_metadata(
                text=text_content,
                source_name=source_name,
                source_type=source_type
            )
            
            if not chunks:
                print(f"  ⚠️  文本切分失败，跳过")
                failed_files += 1
                continue
            
            # 3. 向量化并存储
            chunk_count = vector_store.add_documents(chunks, batch_size=50)
            total_chunks += chunk_count
            
            print(f"  ✅ 成功导入 {chunk_count} 个文本块")
            success_files += 1
            
        except Exception as e:
            print(f"  ❌ 导入失败: {str(e)}")
            failed_files += 1
            import traceback
            traceback.print_exc()
    
    # 打印统计信息
    print("\n" + "=" * 60)
    print("📊 导入统计:")
    print(f"  总文件数: {total_files}")
    print(f"  成功: {success_files}")
    print(f"  失败: {failed_files}")
    print(f"  总文本块数: {total_chunks}")
    print(f"  向量库总文档数: {vector_store.get_collection_count()}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="批量导入法律条文到向量库")
    parser.add_argument(
        "--dir",
        type=str,
        required=True,
        help="法律条文目录路径"
    )
    parser.add_argument(
        "--source-type",
        type=str,
        default="legal",
        choices=["legal", "contract"],
        help="来源类型（legal/contract）"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前清理现有向量库集合（删除所有法律条文数据，用户上传的合同数据不受影响）"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 开始批量导入法律条文")
    if args.clear:
        print("⚠️  警告：将清理现有向量库集合")
    print("=" * 60)
    
    import_law_files(args.dir, args.source_type, clear_existing=args.clear)
    
    print("\n✅ 批量导入完成！")


if __name__ == "__main__":
    main()

