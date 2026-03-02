"""
第3天功能测试脚本
测试向量检索基础设施：Embedding服务、文本切分、向量库
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

def test_embedding_service():
    """测试1: 验证Embedding服务"""
    print("\n" + "="*60)
    print("测试1: 验证通义千问Embedding服务")
    print("="*60)
    
    try:
        from app.services.embedding import DashScopeEmbedder
        
        embedder = DashScopeEmbedder()
        print(f"✅ Embedding服务初始化成功")
        print(f"   模型: {embedder.model}")
        print(f"   向量维度: {embedder.get_embedding_dimension()}")
        
        # 测试单个文本embedding
        test_text = "这是一个测试文本"
        result = embedder.embed_query(test_text)
        
        print(f"✅ 查询文本embedding成功")
        print(f"   输入文本: {test_text}")
        print(f"   向量维度: {len(result)}")
        print(f"   前5个值: {result[:5]}")
        
        # 测试批量embedding - 使用有意义的法律文本
        test_texts = [
            "中华人民共和国是工人阶级领导的、以工农联盟为基础的人民民主专政的社会主义国家。",
            "中华人民共和国的一切权力属于人民。",
            "今天天气很好，适合出去散步。"
        ]
        batch_results = embedder.embed_documents(test_texts)
        
        print(f"✅ 批量embedding成功")
        print(f"   输入文本数: {len(test_texts)}")
        print(f"   输出向量数: {len(batch_results)}")
        print(f"   每个向量维度: {len(batch_results[0]) if batch_results else 0}")
        
        # 验证语义相似度
        if len(batch_results) >= 3:
            import numpy as np
            vec1 = np.array(batch_results[0])  # 宪法条文1
            vec2 = np.array(batch_results[1])  # 宪法条文2
            vec3 = np.array(batch_results[2])  # 日常文本
            
            # 计算余弦相似度
            similarity_12 = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            similarity_13 = np.dot(vec1, vec3) / (np.linalg.norm(vec1) * np.linalg.norm(vec3))
            
            print(f"\n📊 语义相似度验证:")
            print(f"   文本1: {test_texts[0][:30]}...")
            print(f"   文本2: {test_texts[1][:30]}...")
            print(f"   文本3: {test_texts[2]}")
            print(f"\n   相似度对比:")
            print(f"   宪法条文1 vs 宪法条文2: {similarity_12:.4f}")
            print(f"   宪法条文1 vs 日常文本: {similarity_13:.4f}")
            
            if similarity_12 > similarity_13:
                print(f"   ✅ 验证通过: 相关文本相似度({similarity_12:.4f}) > 不相关文本相似度({similarity_13:.4f})")
            else:
                print(f"   ⚠️  注意: 相似度差异不明显，可能需要调整模型或文本")
        
        return True
    except Exception as e:
        print(f"❌ Embedding服务测试失败: {str(e)}")
        return False


def test_text_splitter():
    """测试2: 验证文本切分工具"""
    print("\n" + "="*60)
    print("测试2: 验证文本切分工具")
    print("="*60)
    
    try:
        from app.services.text_splitter import LawTextSplitter
        
        # 增大块大小以适应长文档
        splitter = LawTextSplitter(chunk_size=500, chunk_overlap=50)
        print(f"✅ 文本切分器初始化成功")
        print(f"   块大小: {splitter.chunk_size}")
        print(f"   重叠大小: {splitter.chunk_overlap}")
        
        # 读取宪法.md文件
        constitution_path = Path(__file__).parent.parent.parent / "Law-Book" / "1-宪法" / "宪法.md"
        
        if not constitution_path.exists():
            print(f"⚠️  文件不存在: {constitution_path}")
            print("   使用示例文本进行测试...")
            # 回退到原来的示例文本
            markdown_text = """
# 第一章 总则

第一条 为了规范合同行为，保护当事人的合法权益，维护社会经济秩序，促进社会主义现代化建设，制定本法。

第二条 本法所称合同是平等主体的自然人、法人、其他组织之间设立、变更、终止民事权利义务关系的协议。

## 第二章 合同的订立

第三条 合同当事人的法律地位平等，一方不得将自己的意志强加给另一方。
"""
        else:
            print(f"📖 读取文件: {constitution_path}")
            with open(constitution_path, "r", encoding="utf-8") as f:
                markdown_text = f.read()
            print(f"   文件大小: {len(markdown_text)} 字符")
        
        chunks = splitter.split_with_metadata(
            markdown_text.strip(),
            source_name="宪法.md",
            source_type="legal"
        )
        
        print(f"✅ Markdown文本切分成功")
        print(f"   输入文本长度: {len(markdown_text)} 字符")
        print(f"   切分块数: {len(chunks)}")
        
        # 显示前5个块（因为内容较长）
        for i, chunk in enumerate(chunks[:5], 1):
            print(f"\n   块 {i}:")
            print(f"     内容长度: {len(chunk['content'])} 字符")
            print(f"     内容预览: {chunk['content'][:100]}...")
            print(f"     元数据: {chunk['metadata']}")
        
        if len(chunks) > 5:
            print(f"\n   ... 还有 {len(chunks) - 5} 个块未显示")
        
        # 测试普通文本（保留原有测试）
        plain_text = """
        这是普通文本的第一段。包含一些法律条文的内容。
        
        这是第二段。继续描述相关的法律条款和规定。
        
        第三段内容。说明具体的实施细则和注意事项。
        """
        
        plain_chunks = splitter.split_with_metadata(
            plain_text.strip(),
            source_name="test_plain.txt",
            source_type="legal"
        )
        
        print(f"\n✅ 普通文本切分成功")
        print(f"   输入文本长度: {len(plain_text)} 字符")
        print(f"   切分块数: {len(plain_chunks)}")
        
        return True
    except Exception as e:
        print(f"❌ 文本切分测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_vector_store():
    """测试3: 验证向量库初始化"""
    print("\n" + "="*60)
    print("测试3: 验证Chroma向量库初始化")
    print("="*60)
    
    try:
        from app.services.vector_store import VectorStore
        
        # 使用测试目录
        test_db_path = "./chroma_db_test"
        vs = VectorStore(persist_directory=test_db_path)
        
        print(f"✅ 向量库初始化成功")
        print(f"   持久化目录: {vs.persist_directory}")
        print(f"   集合名称: {vs.collection_name}")
        print(f"   当前文档数: {vs.get_collection_count()}")
        
        # 获取集合信息
        info = vs.get_collection_info()
        print(f"   集合信息: {info}")
        
        return True
    except Exception as e:
        print(f"❌ 向量库初始化测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """测试4: 集成测试 - 文本切分 -> Embedding -> 向量库存储 -> 搜索"""
    print("\n" + "="*60)
    print("测试4: 集成测试 - 完整流程")
    print("="*60)
    
    try:
        from app.services.text_splitter import LawTextSplitter
        from app.services.vector_store import VectorStore
        
        # 准备测试文本
        test_text = """
# 劳动合同法

## 第一章 总则

第一条 为了完善劳动合同制度，明确劳动合同双方当事人的权利和义务，保护劳动者的合法权益，构建和发展和谐稳定的劳动关系，制定本法。

第二条 中华人民共和国境内的企业、个体经济组织、民办非企业单位等组织（以下称用人单位）与劳动者建立劳动关系，订立、履行、变更、解除或者终止劳动合同，适用本法。

## 第二章 劳动合同的订立

第三条 订立劳动合同，应当遵循合法、公平、平等自愿、协商一致、诚实信用的原则。

第四条 用人单位应当依法建立和完善劳动规章制度，保障劳动者享有劳动权利、履行劳动义务。
"""
        
        # 步骤1: 文本切分
        print("步骤1: 文本切分...")
        splitter = LawTextSplitter(chunk_size=300, chunk_overlap=30)
        chunks = splitter.split_with_metadata(
            test_text.strip(),
            source_name="劳动合同法.md",
            source_type="legal"
        )
        print(f"   ✅ 切分完成，生成 {len(chunks)} 个文本块")
        
        # 步骤2: 添加到向量库
        print("\n步骤2: 添加到向量库...")
        test_db_path = "./chroma_db_test"
        vs = VectorStore(persist_directory=test_db_path)
        
        # 先清空测试数据（如果存在）
        try:
            vs.delete_collection()
            vs = VectorStore(persist_directory=test_db_path)
        except:
            pass
        
        count = vs.add_documents(chunks, batch_size=10)
        print(f"   ✅ 成功添加 {count} 个文档")
        print(f"   向量库总文档数: {vs.get_collection_count()}")
        
        # 步骤3: 向量搜索
        print("\n步骤3: 向量相似度搜索...")
        query = "劳动合同的订立原则"
        results = vs.search(query, top_k=3)
        
        print(f"   ✅ 搜索完成")
        print(f"   查询: {query}")
        print(f"   返回结果数: {len(results)}")
        
        for i, result in enumerate(results, 1):
            print(f"\n   结果 {i}:")
            print(f"     相似度: {result['score']:.4f}")
            print(f"     内容: {result['content'][:100]}...")
            print(f"     来源: {result['metadata'].get('source_name', 'unknown')}")
        
        # 步骤4: 测试过滤搜索
        print("\n步骤4: 测试元数据过滤搜索...")
        filtered_results = vs.search(
            query="劳动合同",
            top_k=2,
            filter_metadata={"source_type": "legal"}
        )
        print(f"   ✅ 过滤搜索完成，返回 {len(filtered_results)} 个结果")
        
        return True
    except Exception as e:
        print(f"❌ 集成测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("第3天功能测试开始")
    print("="*60)
    
    # 检查环境变量
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "your-dashscope-api-key-here":
        print("\n⚠️  警告: DASHSCOPE_API_KEY未设置或使用默认值")
        print("   请在.env文件中设置DASHSCOPE_API_KEY")
        print("   获取方式: https://dashscope.console.aliyun.com/")
        response = input("\n是否继续测试? (y/n): ")
        if response.lower() != 'y':
            return
    
    results = []
    
    # 运行测试
    results.append(("Embedding服务", test_embedding_service()))
    results.append(("文本切分工具", test_text_splitter()))
    results.append(("向量库初始化", test_vector_store()))
    results.append(("集成测试", test_integration()))
    
    # 输出测试结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！第3天功能正常。")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息。")


if __name__ == "__main__":
    main()

