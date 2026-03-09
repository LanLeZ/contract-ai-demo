"""
快速测试脚本 - 使用你提供的测试文本
用法: python tests/quick_test.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

def quick_test_with_text(text: str, source_name: str = "test.md"):
    """
    使用提供的文本进行快速测试
    Args:
        text: 测试文本内容
        source_name: 来源文件名
    """
    print("\n" + "="*60)
    print("快速测试 - 使用自定义文本")
    print("="*60)
    
    try:
        from app.services.text_splitter import LawTextSplitter
        from app.services.vector_store import VectorStore
        
        # 1. 文本切分
        print("\n步骤1: 文本切分...")
        splitter = LawTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_with_metadata(text, source_name, "legal")
        print(f"   ✅ 切分完成，生成 {len(chunks)} 个文本块")
        
        # 显示前3个块
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"\n   块 {i}:")
            print(f"     长度: {len(chunk['content'])} 字符")
            print(f"     内容: {chunk['content'][:100]}...")
            print(f"     元数据: {chunk['metadata']}")
        
        # 2. 添加到向量库
        print("\n步骤2: 添加到向量库...")
        vs = VectorStore(persist_directory="./chroma_db_test")
        
        # 清空旧数据（如果存在）
        try:
            vs.delete_collection()
            vs = VectorStore(persist_directory="./chroma_db_test")
        except:
            pass
        
        count = vs.add_documents(chunks, batch_size=10)
        print(f"   ✅ 成功添加 {count} 个文档")
        print(f"   向量库总文档数: {vs.get_collection_count()}")
        
        # 3. 测试搜索
        print("\n步骤3: 测试搜索功能...")
        test_queries = [
            "法律条文",
            "合同规定",
            "权利义务"
        ]
        
        for query in test_queries:
            results = vs.search(query, top_k=2)
            print(f"\n   查询: '{query}'")
            print(f"   找到 {len(results)} 个结果:")
            for i, r in enumerate(results, 1):
                print(f"     {i}. 相似度: {r['score']:.4f}")
                print(f"        内容: {r['content'][:80]}...")
        
        print("\n✅ 快速测试完成！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 检查API Key
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "your-dashscope-api-key-here":
        print("⚠️  请先在.env文件中设置DASHSCOPE_API_KEY")
        sys.exit(1)
    
    # 示例文本（你可以替换为你的测试文本）
    sample_text = """
# 劳动合同法

## 第一章 总则

第一条 为了完善劳动合同制度，明确劳动合同双方当事人的权利和义务，保护劳动者的合法权益，构建和发展和谐稳定的劳动关系，制定本法。

第二条 中华人民共和国境内的企业、个体经济组织、民办非企业单位等组织（以下称用人单位）与劳动者建立劳动关系，订立、履行、变更、解除或者终止劳动合同，适用本法。

## 第二章 劳动合同的订立

第三条 订立劳动合同，应当遵循合法、公平、平等自愿、协商一致、诚实信用的原则。

第四条 用人单位应当依法建立和完善劳动规章制度，保障劳动者享有劳动权利、履行劳动义务。

第五条 县级以上人民政府劳动行政部门会同工会和企业方面代表，建立健全协调劳动关系三方机制，共同研究解决有关劳动关系的重大问题。
"""
    
    print("="*60)
    print("快速测试脚本")
    print("="*60)
    print("\n使用示例文本进行测试...")
    print("(你可以修改此脚本，替换sample_text变量为你的测试文本)")
    
    quick_test_with_text(sample_text.strip(), "劳动合同法.md")
































