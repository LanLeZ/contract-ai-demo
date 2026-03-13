"""
测试 ContractTextSplitter 的层级追踪功能

用法：
    python test_hierarchy_split.py                          # 使用内置示例
    python test_hierarchy_split.py path/to/contract.docx   # 指定 docx 文件
    python test_hierarchy_split.py path/to/contract.txt     # 指定 txt 文件

输出：
    - 终端打印每个 chunk 的层级信息
    - 输出 JSON 文件到 split_results/ 目录
"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 切换到后端目录以便正确导入
os.chdir(project_root / "backend")
sys.path.insert(0, str(project_root / "backend"))

from app.services.contract_splitter import ContractTextSplitter


def read_file_content(file_path: str) -> str:
    """读取文件内容，支持 txt 和 docx"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == '.txt':
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    elif suffix == '.docx':
        try:
            from docx import Document
            doc = Document(path)
            return '\n'.join([para.text for para in doc.paragraphs])
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def _example_text() -> str:
    """内置示例合同文本"""
    return """房屋租赁合同

甲方（出租人）：李四
乙方（承租人）：王五

一、租赁物及用途
甲方将位于北京市朝阳区某小区1号楼101室的房屋出租给乙方使用。
乙方承租该房屋仅用于居住，不得擅自改变用途。

二、租赁期限
1、租赁期限为一年，自2024年1月1日起至2024年12月31日止。
2、租赁期满后，如乙方需要续租，应提前一个月书面通知甲方。

三、租金及支付方式
（1）租金标准：该房屋月租金为人民币叁仟元整（¥3000元/月）。
（2）支付方式：乙方应于每月的第五日前将当月租金支付至甲方指定账户。
（3）押金：乙方在签订本合同之日向甲方支付押金人民币陆仟元整。

四、房屋维修
1、在租赁期间，房屋及附属设施的维修责任由甲方负责。
2、因乙方使用不当造成房屋及设施损坏的，由乙方承担维修费用。

五、违约责任
（1）任何一方提前解除本合同，应提前一个月书面通知对方，并支付对方一个月租金作为违约金。
（2）乙方逾期支付租金的，每逾期一日，应按未付租金的千分之五向甲方支付违约金。

六、争议解决
1、本合同在履行过程中发生的争议，由双方协商解决。
2、协商不成的，任何一方均可向甲方所在地人民法院提起诉讼。

七、其他约定
① 本合同未尽事宜，由双方另行协商签订补充协议。
② 本合同一式两份，甲乙双方各执一份，具有同等法律效力。
"""


def print_hierarchy_info(chunks: list):
    """打印层级信息"""
    print("\n" + "=" * 80)
    print("Split Result - Hierarchy Info")
    print("=" * 80)

    for i, chunk in enumerate(chunks):
        meta = chunk.get('metadata', {})
        marker = meta.get('clause_marker', '')
        parent = meta.get('parent_marker', '')
        level = meta.get('hierarchy_level', 0)

        # 缩进显示层级
        indent = "  " * (level - 1) if level > 0 else "  [Intro]"

        print(f"\n[{i+1}] {indent} marker: {marker}")
        print(f"      parent_marker: {parent}")
        print(f"      hierarchy_level: {level}")
        content_preview = chunk.get('content', '')[:30].replace('\n', ' ').encode('gbk', errors='ignore').decode('gbk')
        print(f"      content preview: {content_preview}...")

    print("\n" + "=" * 80)
    print(f"Total chunks: {len(chunks)}")
    print("=" * 80)


def main():
    splitter = ContractTextSplitter(chunk_size=200, chunk_overlap=60, min_chunk_size=30)

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"从文件加载: {file_path}")
        text = read_file_content(file_path)
        source_name = Path(file_path).name
    else:
        print("未指定文件，使用内置示例合同文本进行测试\n")
        text = _example_text()
        source_name = "example_contract.txt"

    # 执行切分
    chunks = splitter.split_with_metadata(
        text=text,
        source_name=source_name,
        user_id=999,
        contract_id=999
    )

    # 打印层级信息
    print_hierarchy_info(chunks)

    # 输出 JSON 文件
    output_dir = Path(__file__).parent / "split_results"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"test_hierarchy_{Path(source_name).stem}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"\nJSON 结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
