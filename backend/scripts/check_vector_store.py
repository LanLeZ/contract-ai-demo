"""
检查向量库中的内容
用法: python scripts/check_vector_store.py
"""
import sys
import io
from pathlib import Path

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.vector_store import VectorStore


def check_vector_store():
    """
    业务含义：
        - 作为日常开发/运维使用的“快速健康检查脚本”，用于确认向量库是否已正确初始化并有数据；
        - 快速判断当前问答或检索异常，是因为没有导入法律条文 / 用户合同，还是出在上层业务逻辑。

    技术实现：
        - 通过 VectorStore.get_collection_info() 获取集合名称和总文档数，判断集合是否存在且非空；
        - 分别以 filter_metadata={"source_type": "legal"} 和 {"source_type": "contract"} 执行示例检索，
          验证不同来源类型的数据是否存在且可被检索到；
        - 再执行一次不带 filter 的全局搜索，粗略统计不同 source_type 的分布情况，
          用于判断导入是否覆盖了预期的数据类型。
    """
    print("=" * 60)
    print("检查向量库内容")
    print("=" * 60)
    
    vector_store = VectorStore()
    
    # 获取集合信息
    info = vector_store.get_collection_info()
    print(f"\n向量库信息:")
    print(f"  集合名称: {info['name']}")
    print(f"  总文档数: {info['count']}")
    
    if info['count'] == 0:
        print("\n警告: 向量库为空，还没有导入任何文档")
        return
    
    # 尝试搜索不同类型的文档
    print("\n" + "-" * 60)
    print("检查法律条文 (source_type='legal'):")
    print("-" * 60)
    
    try:
        legal_results = vector_store.search(
            query="劳动合同",
            top_k=5,
            filter_metadata={"source_type": "legal"}
        )
        print(f"  找到 {len(legal_results)} 个法律条文相关结果")
        if legal_results:
            print(f"  示例来源: {legal_results[0]['metadata'].get('source_name', 'unknown')}")
    except Exception as e:
        print(f"  警告: 搜索法律条文时出错: {str(e)}")
    
    print("\n" + "-" * 60)
    print("检查合同文档 (source_type='contract'):")
    print("-" * 60)
    
    try:
        contract_results = vector_store.search(
            query="合同",
            top_k=5,
            filter_metadata={"source_type": "contract"}
        )
        print(f"  找到 {len(contract_results)} 个合同相关结果")
        if contract_results:
            print(f"  示例来源: {contract_results[0]['metadata'].get('source_name', 'unknown')}")
    except Exception as e:
        print(f"  警告: 搜索合同时出错: {str(e)}")
    
    # 尝试不指定 source_type 的搜索
    print("\n" + "-" * 60)
    print("全局搜索（不指定类型）:")
    print("-" * 60)
    
    try:
        all_results = vector_store.search(
            query="法律",
            top_k=10
        )
        print(f"  找到 {len(all_results)} 个结果")
        
        # 统计不同 source_type 的数量
        source_type_count = {}
        for result in all_results:
            source_type = result['metadata'].get('source_type', 'unknown')
            source_type_count[source_type] = source_type_count.get(source_type, 0) + 1
        
        print(f"\n  按类型统计:")
        for stype, count in source_type_count.items():
            print(f"    {stype}: {count} 个")
            
    except Exception as e:
        print(f"  ⚠️  全局搜索时出错: {str(e)}")
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)
    
    # 给出建议
    if info['count'] > 0:
        legal_count = source_type_count.get('legal', 0) if 'source_type_count' in locals() else 0
        if legal_count == 0:
            print("\n提示: 向量库中没有找到法律条文 (source_type='legal')")
            print("   如果还没有导入 Law-Book，可以运行:")
            print("   python scripts/batch_import.py --dir ../Law-Book --source-type legal")
        else:
            print(f"\n向量库中已有 {legal_count} 个法律条文相关文档")


if __name__ == "__main__":
    check_vector_store()

