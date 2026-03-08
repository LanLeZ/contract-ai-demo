"""
测试合同对比 + LLM 分析完整流程

流程：
1. 从 testa.docx 和 testb.docx 提取文本
2. 使用 ContractTextSplitter 切分合同
3. 按 clause_marker 对齐并找出差异
4. 调用 LLM 对差异进行分析
5. 保存结果到文件
"""
import os
import sys
import json
from docx import Document

# 把项目根目录和 backend 目录加到 sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
for p in (BASE_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.services.contract_compare import _build_clause_marker_diff
from backend.app.services.llm import attach_contract_compare_llm_analysis


class MockContract:
    """模拟 Contract 模型对象，提供 contract_compare 需要的属性"""
    def __init__(self, filename: str, file_content: str, contract_id: int = None, contract_type: str = None):
        self.filename = filename
        self.file_content = file_content
        self.id = contract_id
        self.contract_type = contract_type


def load_docx_text(path: str) -> str:
    """从 .docx 文件提取纯文本"""
    try:
        doc = Document(path)
        text = ""
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"读取 DOCX 文件失败 {path}: {str(e)}")


def main():
    """主测试函数"""
    # 1. 读取两个合同文件
    test_dir = os.path.dirname(os.path.abspath(__file__))
    path_a = os.path.join(test_dir, "testa.docx")
    path_b = os.path.join(test_dir, "testb.docx")
    
    print(f"[1/5] 读取合同文件...")
    print(f"  左侧合同: {path_a}")
    print(f"  右侧合同: {path_b}")
    
    text_a = load_docx_text(path_a)
    text_b = load_docx_text(path_b)
    
    print(f"  左侧合同文本长度: {len(text_a)} 字符")
    print(f"  右侧合同文本长度: {len(text_b)} 字符")
    
    # 创建模拟的 Contract 对象
    left_contract = MockContract(filename="testa.docx", file_content=text_a)
    right_contract = MockContract(filename="testb.docx", file_content=text_b)
    
    # 2. 使用 contract_compare 的逻辑进行对比
    print(f"\n[2/5] 执行合同切分与差异对比...")
    result_obj = _build_clause_marker_diff(
        left_contract=left_contract,
        right_contract=right_contract,
    )
    
    summary = result_obj.get("summary", {})
    print(f"  只在左侧存在的条款数: {summary.get('only_in_left_count', 0)}")
    print(f"  只在右侧存在的条款数: {summary.get('only_in_right_count', 0)}")
    print(f"  双方共有的条款数: {summary.get('in_both_count', 0)}")
    print(f"  内容有差异的条款数: {summary.get('changed_in_both_count', 0)}")
    
    # 3. 调用 LLM 进行差异分析
    print(f"\n[3/5] 调用 LLM 进行差异分析与风险提示...")
    print("  (如果 LLM 调用失败，会静默降级，不影响基础对比结果)")
    
    try:
        attach_contract_compare_llm_analysis(
            base_result=result_obj,
            left_contract=left_contract,
            right_contract=right_contract,
            # max_clauses=20,  # 最多分析前20条差异
        )
        
        if "llm_comment" in result_obj:
            llm_comment = result_obj["llm_comment"]
            print(f"  ✓ LLM 分析完成，评论长度: {len(llm_comment)} 字符")
            print(f"  评论预览（前200字符）: {llm_comment[:200]}...")
        else:
            print(f"  ⚠ LLM 分析未返回结果（可能失败或跳过）")
    except Exception as e:
        print(f"  ⚠ LLM 分析过程出现异常: {str(e)}")
        print(f"  (继续保存基础对比结果)")
    
    # 4. 保存结果到文件
    print(f"\n[4/5] 保存结果到文件...")
    output_path = os.path.join(test_dir, "contract_compare_with_llm_result.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_obj, f, ensure_ascii=False, indent=2)
    
    print(f"  ✓ 结果已保存到: {output_path}")
    
    # 5. 打印简要统计
    print(f"\n[5/5] 结果摘要:")
    print(f"  - 只在左侧: {result_obj.get('only_in_left', [])}")
    print(f"  - 只在右侧: {result_obj.get('only_in_right', [])}")
    print(f"  - 有差异的条款编号: {[c.get('clause_marker') for c in result_obj.get('changed_clauses', [])]}")
    
    if "llm_comment" in result_obj:
        print(f"\n  LLM 分析结果:")
        print(f"  {'=' * 60}")
        print(f"  {result_obj['llm_comment']}")
        print(f"  {'=' * 60}")
    
    print(f"\n✓ 测试完成！")


if __name__ == "__main__":
    main()

