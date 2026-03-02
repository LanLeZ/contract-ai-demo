"""
详细查看向量库中的所有内容，并测试检索功能
用法: python scripts/inspect_vector_store.py
"""
import sys
import io
from pathlib import Path
from collections import Counter, defaultdict

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.vector_store import VectorStore


def inspect_vector_store():
    """
    业务含义：
        - 对当前向量库做一次“体检”，帮助判断底层语料是否完整、结构是否符合预期；
        - 区分法律条文 (source_type='legal') 与用户上传合同 (source_type='contract')，
          方便评估批量导入和线上业务使用情况。

    技术实现：
        - 通过 app.services.vector_store.VectorStore 封装访问 ChromaDB 默认集合；
        - 调用 get_collection_info() 获取集合级统计信息（名称、总文档数等）；
        - 使用 collection.get(include=['metadatas', 'documents']) 直接从 ChromaDB 拉取所有文档，
          在当前数据规模下于内存中完成各维度聚合统计；
        - 使用 Counter / defaultdict 在 Python 侧对 source_type / source_name / user_id / contract_id
          做统计和 Top N 排序，并打印示例 metadata 与内容预览。
    """
    print("=" * 80)
    print("🔍 向量库详细内容检查")
    print("=" * 80)
    
    vector_store = VectorStore()
    
    # 获取集合信息
    info = vector_store.get_collection_info()
    print(f"\n📊 向量库基本信息:")
    print(f"  集合名称: {info['name']}")
    print(f"  总文档数: {info['count']}")
    
    if info['count'] == 0:
        print("\n⚠️  警告: 向量库为空，还没有导入任何文档")
        return
    
    # 获取所有文档（使用 ChromaDB 的 get 方法）
    print("\n" + "=" * 80)
    print("📥 正在获取所有文档...")
    print("=" * 80)
    
    try:
        # 获取所有文档的 metadata 和 ids
        all_data = vector_store.collection.get(include=['metadatas', 'documents'])
        
        total_count = len(all_data['ids'])
        print(f"\n✅ 成功获取 {total_count} 个文档")
        
        # 统计信息
        print("\n" + "-" * 80)
        print("📈 按 source_type 统计:")
        print("-" * 80)
        
        source_type_counter = Counter()
        source_name_counter = Counter()
        user_id_counter = Counter()
        contract_id_counter = Counter()
        
        # 按 source_name 分组统计（用于查看有哪些文件）
        source_name_details = defaultdict(lambda: {'count': 0, 'source_type': None, 'user_id': None})
        
        for i, metadata in enumerate(all_data['metadatas']):
            source_type = metadata.get('source_type', 'unknown')
            source_name = metadata.get('source_name', 'unknown')
            user_id = metadata.get('user_id', 'unknown')
            contract_id = metadata.get('contract_id', 'unknown')
            
            source_type_counter[source_type] += 1
            source_name_counter[source_name] += 1
            user_id_counter[user_id] += 1
            contract_id_counter[contract_id] += 1
            
            # 记录每个 source_name 的详细信息
            if source_name_details[source_name]['count'] == 0:
                source_name_details[source_name]['source_type'] = source_type
                source_name_details[source_name]['user_id'] = user_id
            source_name_details[source_name]['count'] += 1
        
        # 打印统计结果
        print("\n按类型 (source_type) 统计:")
        for stype, count in source_type_counter.most_common():
            percentage = (count / total_count) * 100
            print(f"  {stype:20s}: {count:6d} 个 ({percentage:5.2f}%)")
        
        print("\n" + "-" * 80)
        print("📁 按文件 (source_name) 统计 (Top 20):")
        print("-" * 80)
        
        # 按 source_type 分组显示
        legal_files = []
        contract_files = []
        
        for source_name, details in sorted(source_name_details.items(), key=lambda x: x[1]['count'], reverse=True):
            if details['source_type'] == 'legal':
                legal_files.append((source_name, details['count']))
            elif details['source_type'] == 'contract':
                contract_files.append((source_name, details['count']))
        
        if legal_files:
            print("\n📚 法律条文文件 (source_type='legal'):")
            for source_name, count in legal_files[:20]:  # 只显示前20个
                print(f"  {source_name:60s}: {count:6d} 个")
            if len(legal_files) > 20:
                print(f"  ... 还有 {len(legal_files) - 20} 个文件未显示")
        
        if contract_files:
            print("\n📄 用户上传的合同文件 (source_type='contract'):")
            for source_name, count in contract_files[:20]:  # 只显示前20个
                print(f"  {source_name:60s}: {count:6d} 个")
            if len(contract_files) > 20:
                print(f"  ... 还有 {len(contract_files) - 20} 个文件未显示")
        
        print("\n" + "-" * 80)
        print("👤 按用户 (user_id) 统计:")
        print("-" * 80)
        
        for user_id, count in user_id_counter.most_common():
            if user_id == 'unknown':
                print(f"  未知用户 (批量导入): {count:6d} 个")
            else:
                print(f"  用户 ID {user_id:10s}: {count:6d} 个")
        
        print("\n" + "-" * 80)
        print("📋 按合同 (contract_id) 统计 (Top 10):")
        print("-" * 80)
        
        for contract_id, count in contract_id_counter.most_common(10):
            if contract_id == 'unknown':
                print(f"  未知合同 (批量导入): {count:6d} 个")
            else:
                print(f"  合同 ID {contract_id:10s}: {count:6d} 个")
        
        # 显示一些示例文档的 metadata
        print("\n" + "=" * 80)
        print("📝 示例文档 metadata (前5个):")
        print("=" * 80)
        
        for i in range(min(5, len(all_data['metadatas']))):
            print(f"\n文档 {i+1}:")
            print(f"  ID: {all_data['ids'][i]}")
            print(f"  Metadata: {all_data['metadatas'][i]}")
            if all_data.get('documents'):
                doc_preview = all_data['documents'][i][:100] + "..." if len(all_data['documents'][i]) > 100 else all_data['documents'][i]
                print(f"  内容预览: {doc_preview}")
        
        print("\n" + "=" * 80)
        print("✅ 检查完成")
        print("=" * 80)
        
        # 总结
        print("\n📌 总结:")
        print(f"  - 向量库中共有 {total_count} 个文档块")
        print(f"  - 法律条文 (legal): {source_type_counter.get('legal', 0)} 个")
        print(f"  - 用户合同 (contract): {source_type_counter.get('contract', 0)} 个")
        print(f"  - 唯一文件数: {len(source_name_counter)} 个")
        print(f"  - 唯一用户数: {len([uid for uid in user_id_counter.keys() if uid != 'unknown'])} 个")
        
        return vector_store
        
    except Exception as e:
        print(f"\n❌ 获取文档时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_retrieval(vector_store: VectorStore):
    """
    业务含义：
        - 使用一组“租房合同”场景下的典型问题，对向量检索能力做端到端验证；
        - 帮助业务/产品快速判断：当前向量库 + 检索策略，能否命中正确的合同条款或法律条文。

    技术实现：
        - 依赖 VectorStore.search(query, top_k=3) 完成语义检索；
        - 由底层 embedding 模型与向量相似度度量提供 score / distance；
        - 通过 metadata 中的 source_name / source_type / user_id / contract_id
          恢复命中的具体来源，并打印片段内容做人工抽检。
    """
    print("\n" + "=" * 80)
    print("🧪 测试检索功能 - 验证向量化是否有效")
    print("=" * 80)
    
    # 测试问题列表
    test_questions = [
        "违约金",        # 看能不能找到违约相关条款
        "房租多少钱",    # 看能不能找到租金条款  
        "租期多久",      # 看能不能找到租期
        "押金",          # 看能不能找到押金条款
        "提前退租"       # 看能不能找到违约责任
    ]
    
    print("\n💡 提示: 每个问题会检索最相关的3个文档片段")
    print("   相似度分数越高（接近1.0），说明匹配度越好\n")
    
    for idx, question in enumerate(test_questions, 1):
        print(f"\n{'=' * 80}")
        print(f"🔍 问题 {idx}/{len(test_questions)}：{question}")
        print("-" * 80)
        
        try:
            # 使用 VectorStore 的 search 方法检索最相关的3个段落
            results = vector_store.search(question, top_k=3)
            
            if not results:
                print("⚠️  未找到相关文档")
            else:
                for i, result in enumerate(results, 1):
                    print(f"\n📄 匹配 {i} (相似度: {result['score']:.4f}, 距离: {result['distance']:.4f}):")
                    print(f"   来源: {result['metadata'].get('source_name', 'unknown')}")
                    print(f"   类型: {result['metadata'].get('source_type', 'unknown')}")
                    if result['metadata'].get('user_id') != 'unknown':
                        print(f"   用户ID: {result['metadata'].get('user_id')}")
                    
                    # 显示文档内容（限制长度）
                    content = result['content']
                    if len(content) > 300:
                        print(f"   内容: {content[:300]}...")
                    else:
                        print(f"   内容: {content}")
            
        except Exception as e:
            print(f"❌ 检索失败: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # 等待用户确认继续（除了最后一个问题）
        if idx < len(test_questions):
            try:
                input("\n按回车继续下一个问题...")
            except KeyboardInterrupt:
                print("\n\n⚠️  用户中断测试")
                return
    
    print("\n" + "=" * 80)
    print("✅ 检索测试完成")
    print("=" * 80)
    print("\n💡 评估建议:")
    print("  - 如果相似度分数 > 0.7，说明向量化效果较好")
    print("  - 如果检索到的内容与问题相关，说明向量化有效")
    print("  - 如果检索结果不相关，可能需要:")
    print("    1. 检查文档切分是否合理")
    print("    2. 检查 embedding 模型是否正常工作")
    print("    3. 检查向量库中是否有相关文档")


if __name__ == "__main__":
    # 1. 先检查向量库内容
    vector_store = inspect_vector_store()
    
    # 2. 如果向量库不为空，进行检索测试
    if vector_store and vector_store.get_collection_count() > 0:
        print("\n" + "=" * 80)
        response = input("\n是否进行检索测试？(y/n，默认y): ").strip().lower()
        if response != 'n':
            test_retrieval(vector_store)
        else:
            print("跳过检索测试")
    else:
        print("\n⚠️  向量库为空，无法进行检索测试")

