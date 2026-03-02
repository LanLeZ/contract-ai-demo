"""
验证文本切分质量脚本
检查合同文档的分词是否合理，确保语义完整性

用法:
    python scripts/verify_text_splitting.py --file uploads/2/internship1.docx
    python scripts/verify_text_splitting.py --file uploads/2/internship1.docx --chunk-size 500 --overlap 50
"""
import sys
import io
import argparse
import re
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.document_parser import DocumentParser
from app.services.text_splitter import LawTextSplitter


class TextSplittingVerifier:
    """文本切分质量验证器"""
    
    # 中文句子结束符
    SENTENCE_ENDINGS = ['。', '！', '？', '；', '\n\n']
    # 英文句子结束符
    ENGLISH_ENDINGS = ['.', '!', '?', ';']
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化验证器
        Args:
            chunk_size: chunk大小
            chunk_overlap: chunk重叠大小
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.parser = DocumentParser()
        self.splitter = LawTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    def verify(self, file_path: str, source_name: str = None) -> Dict:
        """
        业务含义：
            - 针对单个合同或法律文档做“切分质量体检”，用于上线前参数调优和回归检查；
            - 目标是尽量让 chunk 边界贴合句子 / 条款边界，减少问答阶段出现大量断句或语义残缺。

        技术实现：
            - 使用 DocumentParser 解析原始文件，得到完整的原始文本；
            - 调用 LawTextSplitter.split_with_metadata() 生成带 metadata 的 chunks，
              其中 source_type 固定为 'contract'（用以区分法律条文）；
            - 通过 _analyze_chunks 统计 chunk 大小分布、重叠区间等基础特征；
            - 通过 _check_semantic_integrity 检查 chunk 边界是否大量落在句子/段落中间，
              并估算句子完整性比例；
            - 最终由 _generate_report 生成详细报告（包含质量分数和等级），便于人工评审和调参。

        Args:
            file_path: 文档路径
            source_name: 来源名称（如果为 None，则使用文件名）

        Returns:
            包含质量分数、统计信息与语义完整性检查结果的字典
        """
        print("=" * 80)
        print(f"📄 验证文档: {file_path}")
        print("=" * 80)
        
        # 1. 解析文档
        print("\n[1/5] 解析文档...")
        try:
            text_content = self.parser.parse(file_path)
            if not text_content.strip():
                raise ValueError("文档内容为空")
            print(f"   ✅ 文档解析成功")
            print(f"   文档总长度: {len(text_content)} 字符")
            print(f"   文档行数: {len(text_content.splitlines())} 行")
        except Exception as e:
            print(f"   ❌ 文档解析失败: {str(e)}")
            return {"error": str(e)}
        
        # 2. 切分文本
        print("\n[2/5] 切分文本...")
        if source_name is None:
            source_name = Path(file_path).name
        
        chunks = self.splitter.split_with_metadata(
            text=text_content,
            source_name=source_name,
            source_type="contract"
        )
        
        if not chunks:
            print("   ❌ 文本切分失败")
            return {"error": "文本切分失败"}
        
        print(f"   ✅ 切分完成，共 {len(chunks)} 个chunks")
        
        # 3. 分析切分质量
        print("\n[3/5] 分析切分质量...")
        analysis = self._analyze_chunks(text_content, chunks)
        
        # 4. 检查语义完整性
        print("\n[4/5] 检查语义完整性...")
        semantic_check = self._check_semantic_integrity(text_content, chunks)
        
        # 5. 生成报告
        print("\n[5/5] 生成验证报告...")
        report = self._generate_report(text_content, chunks, analysis, semantic_check)
        
        return report
    
    def _analyze_chunks(self, original_text: str, chunks: List[Dict]) -> Dict:
        """分析chunks的基本统计信息"""
        chunk_sizes = [len(chunk['content']) for chunk in chunks]
        
        # 计算重叠区域
        overlaps = []
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]['content']
            next_chunk = chunks[i + 1]['content']
            
            # 查找重叠部分（简单方法：检查末尾和开头是否相同）
            overlap = self._calculate_overlap(current_chunk, next_chunk)
            overlaps.append(overlap)
        
        analysis = {
            "total_chunks": len(chunks),
            "chunk_sizes": {
                "min": min(chunk_sizes) if chunk_sizes else 0,
                "max": max(chunk_sizes) if chunk_sizes else 0,
                "avg": sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0,
                "median": sorted(chunk_sizes)[len(chunk_sizes) // 2] if chunk_sizes else 0
            },
            "overlaps": {
                "avg": sum(overlaps) / len(overlaps) if overlaps else 0,
                "min": min(overlaps) if overlaps else 0,
                "max": max(overlaps) if overlaps else 0
            },
            "size_distribution": self._get_size_distribution(chunk_sizes)
        }
        
        return analysis
    
    def _calculate_overlap(self, chunk1: str, chunk2: str) -> int:
        """计算两个chunk之间的重叠字符数"""
        # 检查chunk1的末尾和chunk2的开头有多少字符相同
        max_overlap = min(len(chunk1), len(chunk2), self.chunk_overlap * 2)
        
        for i in range(max_overlap, 0, -1):
            if chunk1[-i:] == chunk2[:i]:
                return i
        
        return 0
    
    def _get_size_distribution(self, sizes: List[int]) -> Dict:
        """获取chunk大小分布"""
        if not sizes:
            return {}
        
        # 定义大小区间
        bins = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, float('inf')]
        distribution = {}
        
        for size in sizes:
            for i in range(len(bins) - 1):
                if bins[i] <= size < bins[i + 1]:
                    label = f"{bins[i]}-{bins[i+1] if bins[i+1] != float('inf') else '+'}"
                    distribution[label] = distribution.get(label, 0) + 1
                    break
        
        return distribution
    
    def _check_semantic_integrity(self, original_text: str, chunks: List[Dict]) -> Dict:
        """检查语义完整性"""
        issues = []
        sentence_breaks = []
        paragraph_breaks = []
        
        # 找到所有chunk在原文中的位置
        chunk_positions = []
        current_pos = 0
        
        for chunk in chunks:
            content = chunk['content']
            # 在原文中查找chunk的位置
            pos = original_text.find(content, current_pos)
            if pos == -1:
                # 如果找不到精确匹配，尝试模糊匹配（可能是由于空格/换行差异）
                # 简化处理：使用前几个字符匹配
                if len(content) > 10:
                    search_text = content[:50]
                    pos = original_text.find(search_text, current_pos)
            
            if pos != -1:
                chunk_positions.append({
                    "start": pos,
                    "end": pos + len(content),
                    "chunk_index": chunk['metadata'].get('chunk_index', 0),
                    "content": content
                })
                current_pos = pos + len(content) // 2  # 更新搜索起始位置
        
        # 检查每个chunk的边界
        for i, chunk_pos in enumerate(chunk_positions):
            start = chunk_pos["start"]
            end = chunk_pos["end"]
            content = chunk_pos["content"]
            
            # 检查chunk开始位置
            if start > 0:
                char_before = original_text[start - 1]
                # 检查是否在句子中间开始（除非是段落开始）
                if char_before not in ['\n', '\r'] and char_before not in self.SENTENCE_ENDINGS:
                    # 检查是否在句子中间
                    if not self._is_sentence_start(original_text, start):
                        issues.append({
                            "type": "chunk_start_in_sentence",
                            "chunk_index": chunk_pos["chunk_index"],
                            "position": start,
                            "char_before": char_before,
                            "severity": "medium"
                        })
            
            # 检查chunk结束位置
            if end < len(original_text):
                char_after = original_text[end] if end < len(original_text) else ''
                # 检查是否在句子中间结束
                if not self._is_sentence_end(content):
                    issues.append({
                        "type": "chunk_end_in_sentence",
                        "chunk_index": chunk_pos["chunk_index"],
                        "position": end,
                        "char_after": char_after,
                        "severity": "high",
                        "content_end": content[-50:] if len(content) > 50 else content
                    })
                    sentence_breaks.append({
                        "chunk_index": chunk_pos["chunk_index"],
                        "position": end,
                        "content_end": content[-30:]
                    })
            
            # 检查是否在段落中间切分
            if i < len(chunk_positions) - 1:
                next_start = chunk_positions[i + 1]["start"]
                between_text = original_text[end:next_start].strip()
                if between_text and '\n\n' not in between_text:
                    # 检查是否跨越了段落边界
                    if '\n\n' in original_text[max(0, start-100):end+100]:
                        paragraph_breaks.append({
                            "chunk_index": chunk_pos["chunk_index"],
                            "position": end
                        })
        
        # 统计完整性指标
        total_sentence_breaks = len(sentence_breaks)
        total_paragraph_breaks = len(paragraph_breaks)
        total_issues = len(issues)
        
        # 计算句子完整性比例
        # 简单估算：统计原文中的句子数
        sentence_count = len(re.split(r'[。！？；\n\n]+', original_text))
        completeness_ratio = 1 - (total_sentence_breaks / max(sentence_count, 1))
        
        return {
            "total_issues": total_issues,
            "sentence_breaks": total_sentence_breaks,
            "paragraph_breaks": total_paragraph_breaks,
            "completeness_ratio": completeness_ratio,
            "issues": issues[:20],  # 只显示前20个问题
            "sentence_break_details": sentence_breaks[:10],  # 只显示前10个
            "paragraph_break_details": paragraph_breaks[:10]
        }
    
    def _is_sentence_start(self, text: str, position: int) -> bool:
        """检查位置是否是句子开始"""
        if position == 0:
            return True
        
        # 检查前面是否有句子结束符
        before_text = text[max(0, position - 10):position]
        for ending in self.SENTENCE_ENDINGS + self.ENGLISH_ENDINGS:
            if ending in before_text:
                return True
        
        # 检查是否是段落开始
        if position > 0 and text[position - 1] in ['\n', '\r']:
            return True
        
        return False
    
    def _is_sentence_end(self, text: str) -> bool:
        """检查文本是否以句子结束符结尾"""
        text = text.strip()
        if not text:
            return True
        
        # 检查是否以句子结束符结尾
        for ending in self.SENTENCE_ENDINGS + self.ENGLISH_ENDINGS:
            if text.endswith(ending):
                return True
        
        # 检查是否以换行结尾（可能是段落结束）
        if text.endswith('\n'):
            return True
        
        return False
    
    def _generate_report(self, original_text: str, chunks: List[Dict], 
                        analysis: Dict, semantic_check: Dict) -> Dict:
        """生成验证报告"""
        print("\n" + "=" * 80)
        print("📊 验证报告")
        print("=" * 80)
        
        # 1. 基本统计
        print("\n【基本统计】")
        print(f"  文档总长度: {len(original_text):,} 字符")
        print(f"  Chunk数量: {analysis['total_chunks']}")
        print(f"  平均Chunk大小: {analysis['chunk_sizes']['avg']:.1f} 字符")
        print(f"  Chunk大小范围: {analysis['chunk_sizes']['min']} - {analysis['chunk_sizes']['max']} 字符")
        print(f"  中位数大小: {analysis['chunk_sizes']['median']} 字符")
        
        # 2. 重叠统计
        print("\n【重叠统计】")
        print(f"  平均重叠: {analysis['overlaps']['avg']:.1f} 字符")
        print(f"  重叠范围: {analysis['overlaps']['min']} - {analysis['overlaps']['max']} 字符")
        print(f"  预期重叠: {self.chunk_overlap} 字符")
        
        # 3. 大小分布
        print("\n【Chunk大小分布】")
        for size_range, count in sorted(analysis['size_distribution'].items()):
            percentage = (count / analysis['total_chunks']) * 100
            bar = "█" * int(percentage / 2)
            print(f"  {size_range:15s}: {count:3d} ({percentage:5.1f}%) {bar}")
        
        # 4. 语义完整性
        print("\n【语义完整性检查】")
        completeness = semantic_check['completeness_ratio'] * 100
        print(f"  句子完整性: {completeness:.1f}%")
        print(f"  句子中间截断: {semantic_check['sentence_breaks']} 处")
        print(f"  段落中间切分: {semantic_check['paragraph_breaks']} 处")
        print(f"  总问题数: {semantic_check['total_issues']}")
        
        # 5. 问题详情
        if semantic_check['issues']:
            print("\n【问题详情（前10个）】")
            for i, issue in enumerate(semantic_check['issues'][:10], 1):
                print(f"\n  问题 {i}:")
                print(f"    类型: {issue['type']}")
                print(f"    严重程度: {issue['severity']}")
                print(f"    Chunk索引: {issue['chunk_index']}")
                if 'content_end' in issue:
                    print(f"    内容结尾: ...{issue['content_end']}")
        
        # 6. 示例Chunks
        print("\n【Chunk示例（前3个）】")
        for i, chunk in enumerate(chunks[:3], 1):
            content = chunk['content']
            print(f"\n  Chunk {i} (索引: {chunk['metadata'].get('chunk_index', i-1)}, 长度: {len(content)} 字符):")
            print(f"  {'-' * 76}")
            # 显示前100字符和后50字符
            if len(content) > 150:
                preview = content[:100] + "\n    ... [中间省略] ...\n    " + content[-50:]
            else:
                preview = content
            # 每行添加缩进
            for line in preview.split('\n'):
                print(f"    {line}")
            print(f"  {'-' * 76}")
        
        # 7. 评估结果
        print("\n【评估结果】")
        
        # 计算质量分数（0-100）
        quality_score = 100
        
        # 扣分项
        if semantic_check['sentence_breaks'] > 0:
            # 每个句子截断扣2分
            penalty = min(semantic_check['sentence_breaks'] * 2, 30)
            quality_score -= penalty
        
        if semantic_check['paragraph_breaks'] > 0:
            # 每个段落切分扣1分
            penalty = min(semantic_check['paragraph_breaks'] * 1, 20)
            quality_score -= penalty
        
        # 检查chunk大小是否合理
        avg_size = analysis['chunk_sizes']['avg']
        if avg_size < self.chunk_size * 0.5:
            quality_score -= 10  # 平均大小太小
        elif avg_size > self.chunk_size * 1.5:
            quality_score -= 10  # 平均大小太大
        
        quality_score = max(0, quality_score)
        
        # 质量等级
        if quality_score >= 90:
            grade = "优秀 ✅"
        elif quality_score >= 75:
            grade = "良好 ✓"
        elif quality_score >= 60:
            grade = "一般 ⚠️"
        else:
            grade = "需要改进 ❌"
        
        print(f"  质量分数: {quality_score:.1f}/100")
        print(f"  质量等级: {grade}")
        
        if quality_score < 75:
            print("\n  💡 改进建议:")
            if semantic_check['sentence_breaks'] > 0:
                print(f"    - 有 {semantic_check['sentence_breaks']} 个chunk在句子中间截断，建议调整切分策略")
            if semantic_check['paragraph_breaks'] > 0:
                print(f"    - 有 {semantic_check['paragraph_breaks']} 个chunk跨越段落边界，建议优先在段落边界切分")
            if avg_size < self.chunk_size * 0.5:
                print(f"    - 平均chunk大小 ({avg_size:.1f}) 偏小，可能切分过细")
            elif avg_size > self.chunk_size * 1.5:
                print(f"    - 平均chunk大小 ({avg_size:.1f}) 偏大，可能超过模型限制")
        
        print("\n" + "=" * 80)
        
        return {
            "quality_score": quality_score,
            "grade": grade,
            "analysis": analysis,
            "semantic_check": semantic_check,
            "total_chunks": len(chunks)
        }


def main():
    parser = argparse.ArgumentParser(
        description="验证文档文本切分质量",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 验证文档（使用默认参数）
  python scripts/verify_text_splitting.py --file uploads/2/internship1.docx
  
  # 指定chunk大小和重叠
  python scripts/verify_text_splitting.py --file uploads/2/internship1.docx --chunk-size 500 --overlap 50
        """
    )
    
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="要验证的文档路径"
    )
    
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Chunk大小（默认: 500）"
    )
    
    parser.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Chunk重叠大小（默认: 50）"
    )
    
    parser.add_argument(
        "--source-name",
        type=str,
        default=None,
        help="来源名称（默认使用文件名）"
    )
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ 错误: 文件不存在: {args.file}")
        sys.exit(1)
    
    # 创建验证器并验证
    verifier = TextSplittingVerifier(
        chunk_size=args.chunk_size,
        chunk_overlap=args.overlap
    )
    
    result = verifier.verify(str(file_path), args.source_name)
    
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()


