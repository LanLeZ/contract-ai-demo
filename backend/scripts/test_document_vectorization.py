"""
综合测试脚本：验证文档解析向量化和 Law-Book 导入
用法: 
    python scripts/test_document_vectorization.py
    python scripts/test_document_vectorization.py --contract-id 19
    python scripts/test_document_vectorization.py --source-name "internship1.docx"
    python scripts/test_document_vectorization.py --test-law-book
"""
import sys
import io
import argparse
from pathlib import Path
from collections import Counter, defaultdict

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.vector_store import VectorStore


def test_document_by_contract_id(vector_store: VectorStore, contract_id: int):
    """
    测试指定合同ID的文档是否成功向量化
    """
    print("=" * 80)
    print(f"🔍 测试合同 ID: {contract_id}")
    print("=" * 80)
    
    try:
        # 获取所有文档
        all_data = vector_store.collection.get(include=['metadatas', 'documents'])
        
        # 过滤出指定合同ID的文档
        contract_chunks = []
        for i, metadata in enumerate(all_data['metadatas']):
            if metadata.get('contract_id') == contract_id:
                contract_chunks.append({
                    'id': all_data['ids'][i],
                    'metadata': metadata,
                    'content': all_data['documents'][i] if all_data.get('documents') else ''
                })
        
        if not contract_chunks:
            print(f"\n❌ 未找到合同 ID {contract_id} 的向量化文档")
            print("   可能的原因：")
            print("   1. 合同还未上传或向量化")
            print("   2. 合同ID不正确")
            print("   3. 向量化过程中出现错误")
            return False
        
        print(f"\n✅ 找到 {len(contract_chunks)} 个文档块")
        print(f"   来源文件: {contract_chunks[0]['metadata'].get('source_name', 'unknown')}")
        print(f"   用户ID: {contract_chunks[0]['metadata'].get('user_id', 'unknown')}")
        
        # 显示统计信息
        print("\n📊 文档块统计:")
        chunk_sizes = [len(chunk['content']) for chunk in contract_chunks]
        print(f"   总块数: {len(contract_chunks)}")
        print(f"   平均大小: {sum(chunk_sizes) / len(chunk_sizes):.1f} 字符")
        print(f"   最小大小: {min(chunk_sizes)} 字符")
        print(f"   最大大小: {max(chunk_sizes)} 字符")
        
        # 显示前3个文档块示例
        print("\n📝 文档块示例（前3个）:")
        for i, chunk in enumerate(contract_chunks[:3], 1):
            print(f"\n   块 {i}:")
            content_preview = chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content']
            print(f"   内容: {content_preview}")
            print(f"   索引: {chunk['metadata'].get('chunk_index', 'unknown')}")
        
        # 测试检索功能
        print("\n🧪 测试检索功能:")
        test_queries = [
            "实习薪资",
            "实习时间",
            "保密要求"
        ]
        
        for query in test_queries:
            results = vector_store.search(
                query=query,
                top_k=3,
                filter_metadata={"contract_id": contract_id}
            )
            print(f"\n   查询: '{query}'")
            if results:
                print(f"   ✅ 找到 {len(results)} 个相关结果")
                print(f"   最高相似度: {results[0]['score']:.4f}")
                print(f"\n   📋 检索结果详情:")
                for i, result in enumerate(results, 1):
                    print(f"\n      结果 {i}:")
                    print(f"        相似度: {result['score']:.4f}")
                    print(f"        块索引: {result['metadata'].get('chunk_index', 'unknown')}")
                    # 显示内容预览（前200字符）
                    content = result.get('content', '')
                    if content:
                        content_preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"        内容预览: {content_preview}")
                    else:
                        print(f"        内容预览: (无内容)")
            else:
                print(f"   ⚠️  未找到相关结果")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_document_by_source_name(vector_store: VectorStore, source_name: str):
    """
    测试指定文件名的文档是否成功向量化
    """
    print("=" * 80)
    print(f"🔍 测试文件: {source_name}")
    print("=" * 80)
    
    try:
        # 获取所有文档
        all_data = vector_store.collection.get(include=['metadatas', 'documents'])
        
        # 过滤出指定文件名的文档
        file_chunks = []
        for i, metadata in enumerate(all_data['metadatas']):
            if metadata.get('source_name') == source_name:
                file_chunks.append({
                    'id': all_data['ids'][i],
                    'metadata': metadata,
                    'content': all_data['documents'][i] if all_data.get('documents') else ''
                })
        
        if not file_chunks:
            print(f"\n❌ 未找到文件 '{source_name}' 的向量化文档")
            print("\n💡 提示: 尝试搜索相似的文件名...")
            
            # 尝试模糊匹配
            similar_files = []
            for i, metadata in enumerate(all_data['metadatas']):
                sn = metadata.get('source_name', '')
                if source_name.lower() in sn.lower() or sn.lower() in source_name.lower():
                    similar_files.append(sn)
            
            if similar_files:
                print(f"   找到相似的文件名:")
                for f in set(similar_files)[:5]:
                    print(f"     - {f}")
            
            return False
        
        print(f"\n✅ 找到 {len(file_chunks)} 个文档块")
        print(f"   来源类型: {file_chunks[0]['metadata'].get('source_type', 'unknown')}")
        print(f"   用户ID: {file_chunks[0]['metadata'].get('user_id', 'unknown')}")
        print(f"   合同ID: {file_chunks[0]['metadata'].get('contract_id', 'unknown')}")
        
        # 显示统计信息
        print("\n📊 文档块统计:")
        chunk_sizes = [len(chunk['content']) for chunk in file_chunks]
        print(f"   总块数: {len(file_chunks)}")
        print(f"   平均大小: {sum(chunk_sizes) / len(chunk_sizes):.1f} 字符")
        
        # 显示前3个文档块示例
        print("\n📝 文档块示例（前3个）:")
        for i, chunk in enumerate(file_chunks[:3], 1):
            print(f"\n   块 {i}:")
            content_preview = chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content']
            print(f"   内容: {content_preview}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_law_book_import(vector_store: VectorStore):
    """
    测试 Law-Book 是否成功导入
    """
    print("=" * 80)
    print("📚 测试 Law-Book 导入")
    print("=" * 80)
    
    try:
        # 获取所有文档
        all_data = vector_store.collection.get(include=['metadatas', 'documents'])
        
        # 过滤出法律条文
        legal_chunks = []
        for i, metadata in enumerate(all_data['metadatas']):
            if metadata.get('source_type') == 'legal':
                legal_chunks.append({
                    'id': all_data['ids'][i],
                    'metadata': metadata,
                    'content': all_data['documents'][i] if all_data.get('documents') else ''
                })
        
        if not legal_chunks:
            print("\n❌ 未找到法律条文（source_type='legal'）")
            print("\n💡 提示: 如果还没有导入 Law-Book，可以运行:")
            print("   python scripts/batch_import.py --dir ../Law-Book --source-type legal")
            return False
        
        print(f"\n✅ 找到 {len(legal_chunks)} 个法律条文文档块")
        
        # 统计文件数量
        source_names = Counter([chunk['metadata'].get('source_name', 'unknown') for chunk in legal_chunks])
        print(f"\n📁 法律文件统计:")
        print(f"   唯一文件数: {len(source_names)}")
        print(f"   总文档块数: {len(legal_chunks)}")
        
        # 显示文件列表（Top 20）
        print("\n📋 法律文件列表（Top 20）:")
        for i, (source_name, count) in enumerate(source_names.most_common(20), 1):
            print(f"   {i:2d}. {source_name:60s}: {count:6d} 个")
        
        if len(source_names) > 20:
            print(f"   ... 还有 {len(source_names) - 20} 个文件未显示")
        
        # 测试检索功能
        print("\n🧪 测试法律条文检索功能:")
        test_queries = [
            "劳动合同",
            "违约责任",
            "合同解除",
            "违约金",
            "合同效力"
        ]
        
        for query in test_queries:
            results = vector_store.search(
                query=query,
                top_k=3,
                filter_metadata={"source_type": "legal"}
            )
            print(f"\n   查询: '{query}'")
            if results:
                print(f"   ✅ 找到 {len(results)} 个相关结果")
                print(f"   最高相似度: {results[0]['score']:.4f}")
                print(f"\n   📋 检索结果详情:")
                for i, result in enumerate(results, 1):
                    print(f"\n      结果 {i}:")
                    print(f"        相似度: {result['score']:.4f}")
                    print(f"        来源: {result['metadata'].get('source_name', 'unknown')}")
                    print(f"        块索引: {result['metadata'].get('chunk_index', 'unknown')}")
                    # 显示内容预览（前200字符）
                    content = result.get('content', '')
                    if content:
                        content_preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"        内容预览: {content_preview}")
                    else:
                        print(f"        内容预览: (无内容)")
            else:
                print(f"   ⚠️  未找到相关结果")
        
        print("\n" + "=" * 80)
        print("✅ Law-Book 导入测试完成")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_all_contracts(vector_store: VectorStore):
    """
    测试所有用户上传的合同
    """
    print("=" * 80)
    print("📄 测试所有用户上传的合同")
    print("=" * 80)
    
    try:
        # 获取所有文档
        all_data = vector_store.collection.get(include=['metadatas', 'documents'])
        
        # 过滤出合同文档
        contract_chunks = []
        for i, metadata in enumerate(all_data['metadatas']):
            if metadata.get('source_type') == 'contract':
                contract_chunks.append({
                    'id': all_data['ids'][i],
                    'metadata': metadata,
                    'content': all_data['documents'][i] if all_data.get('documents') else ''
                })
        
        if not contract_chunks:
            print("\n⚠️  未找到用户上传的合同文档")
            return
        
        print(f"\n✅ 找到 {len(contract_chunks)} 个合同文档块")
        
        # 按合同ID分组
        contracts = defaultdict(lambda: {'chunks': [], 'source_name': None, 'user_id': None})
        for chunk in contract_chunks:
            contract_id = chunk['metadata'].get('contract_id', 'unknown')
            contracts[contract_id]['chunks'].append(chunk)
            if contracts[contract_id]['source_name'] is None:
                contracts[contract_id]['source_name'] = chunk['metadata'].get('source_name', 'unknown')
                contracts[contract_id]['user_id'] = chunk['metadata'].get('user_id', 'unknown')
        
        print(f"\n📊 合同统计:")
        print(f"   唯一合同数: {len(contracts)}")
        print(f"   总文档块数: {len(contract_chunks)}")
        
        # 显示合同列表
        print("\n📋 合同列表:")
        for i, (contract_id, info) in enumerate(sorted(contracts.items(), key=lambda x: len(x[1]['chunks']), reverse=True), 1):
            print(f"\n   合同 {i}:")
            print(f"     合同ID: {contract_id}")
            print(f"     文件名: {info['source_name']}")
            print(f"     用户ID: {info['user_id']}")
            print(f"     文档块数: {len(info['chunks'])}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="测试文档解析向量化和 Law-Book 导入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试所有内容
  python scripts/test_document_vectorization.py
  
  # 测试指定合同ID
  python scripts/test_document_vectorization.py --contract-id 1
  
  # 测试指定文件名
  python scripts/test_document_vectorization.py --source-name "internship1.docx"
  
  # 只测试 Law-Book 导入
  python scripts/test_document_vectorization.py --test-law-book
  
  # 测试所有用户上传的合同
  python scripts/test_document_vectorization.py --test-contracts
        """
    )
    
    parser.add_argument(
        "--contract-id",
        type=int,
        help="测试指定合同ID的文档"
    )
    
    parser.add_argument(
        "--source-name",
        type=str,
        help="测试指定文件名的文档"
    )
    
    parser.add_argument(
        "--test-law-book",
        action="store_true",
        help="测试 Law-Book 导入"
    )
    
    parser.add_argument(
        "--test-contracts",
        action="store_true",
        help="测试所有用户上传的合同"
    )
    
    args = parser.parse_args()
    
    # 初始化向量库
    vector_store = VectorStore()
    
    # 获取基本信息
    info = vector_store.get_collection_info()
    print("=" * 80)
    print("🔍 向量库测试工具")
    print("=" * 80)
    print(f"\n向量库信息:")
    print(f"  集合名称: {info['name']}")
    print(f"  总文档数: {info['count']}")
    
    if info['count'] == 0:
        print("\n⚠️  警告: 向量库为空，还没有导入任何文档")
        return
    
    # 根据参数执行不同的测试
    if args.contract_id:
        test_document_by_contract_id(vector_store, args.contract_id)
    elif args.source_name:
        test_document_by_source_name(vector_store, args.source_name)
    elif args.test_law_book:
        test_law_book_import(vector_store)
    elif args.test_contracts:
        test_all_contracts(vector_store)
    else:
        # 默认：执行所有测试
        print("\n" + "=" * 80)
        print("执行综合测试")
        print("=" * 80)
        
        # 1. 测试 Law-Book
        print("\n")
        test_law_book_import(vector_store)
        
        # 2. 测试所有合同
        print("\n")
        test_all_contracts(vector_store)
        
        print("\n" + "=" * 80)
        print("✅ 所有测试完成")
        print("=" * 80)


if __name__ == "__main__":
    main()

