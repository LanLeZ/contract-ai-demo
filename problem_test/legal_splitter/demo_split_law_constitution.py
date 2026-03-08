import os
import sys
import json

# demo_split_law_constitution.py
#
# 使用 backend.app.services.legal_splitter.LegalTextSplitter
# 对 Law-Book/1-宪法/宪法.md 进行切分，并将结果保存为 JSON 文件

# 把项目根目录 E:\cp 和 backend 目录加到 sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
for p in (BASE_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.services.legal_splitter import LegalTextSplitter


def load_markdown_text(path: str) -> str:
    """读取 Markdown 文件为字符串"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    # 1) 读取宪法 Markdown 文件
    law_path = os.path.join(BASE_DIR, "Law-Book", "1-宪法", "宪法.md")
    if not os.path.exists(law_path):
        raise FileNotFoundError(f"找不到宪法文件: {law_path}")

    text = load_markdown_text(law_path)

    # 2) 初始化新版法律切分器
    splitter = LegalTextSplitter(
        chunk_size=200,      # 与后端默认配置保持一致
        chunk_overlap=60,
        min_chunk_size=50,
    )

    # 3) 调用主接口进行切分（带上与你线上一致的元数据字段）
    chunks = splitter.split_with_metadata(
        text=text,
        source_name="宪法.md",
        user_id=0,
        contract_id=None,
    )

    # 4) 将结果保存为 JSON 文件，方便比对和查看
    output_path = os.path.join(
        BASE_DIR,
        "problem_test",
        "legal_splitter",
        "law_split_constitution_result.json",
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"总共切出 {len(chunks)} 个 chunk")
    print(f"已将结果写入: {output_path}")


if __name__ == "__main__":
    main()

import os
import json
import re
from typing import List, Dict, Any

# 直接使用 langchain 的分割工具
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


class LawTextSplitter:
    """
    简化版法律文本切分器，只实现本测试需要的 split_with_metadata
    - Markdown：先按标题切，再对超长块用法律递归规则细分
    - 普通文本：直接用法律递归规则
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100, min_chunk_size: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Markdown 按标题切分（兼容你 law_ai 的写法）
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "header_1"),
                ("##", "header_2"),
                ("###", "header_3"),
                ("####", "header_4"),
            ]
        )

        # 法律条文专用递归切分器：优先在条款边界和句号处切
        self.legal_recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n第",  # 空行后条款
                "\n第",   # 行首条款
                "。",     # 句号
                "；",     # 分号
                "\n\n",   # 双换行
                "\n",     # 单换行
            ],
        )

    def _normalize_chunk(self, content: str, metadata: Dict = None) -> Dict:
        if metadata is None:
            metadata = {}
        return {
            "content": content.strip(),
            "metadata": metadata.copy(),
        }

    def _is_valid_content(self, content: str) -> bool:
        """简单过滤：去掉全空白、只有分隔符的行等"""
        text = content.strip()
        if not text:
            return False
        # 可以按需要再加规则
        return True

    def _filter_and_merge_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """过滤无效内容 + 尝试合并过小块"""
        if not chunks:
            return []

        valid_chunks = []
        for ch in chunks:
            c = (ch.get("content") or "").strip()
            if c and self._is_valid_content(c):
                valid_chunks.append(ch)

        if not valid_chunks:
            return []

        result: List[Dict] = []
        i = 0
        while i < len(valid_chunks):
            cur = valid_chunks[i]
            content = (cur.get("content") or "").strip()
            length = len(content)

            if length < self.min_chunk_size:
                # 尝试与后一个合并
                if i + 1 < len(valid_chunks):
                    nxt = valid_chunks[i + 1]
                    nxt_c = (nxt.get("content") or "").strip()
                    merged = content + "\n\n" + nxt_c
                    if len(merged) <= self.chunk_size:
                        md = cur["metadata"].copy()
                        md.update(nxt["metadata"])
                        md["merged"] = True
                        md["original_chunk_count"] = 2
                        result.append(
                            {
                                "content": merged,
                                "metadata": md,
                            }
                        )
                        i += 2
                        continue
                # 合并不了就保留并打标
                cur.setdefault("metadata", {})
                cur["metadata"]["is_small_chunk"] = True
                cur["metadata"]["chunk_size"] = length
                result.append(cur)
            else:
                result.append(cur)

            i += 1

        return result

    def _split_by_legal_recursive(self, text: str) -> List[Dict]:
        """使用法律递归切分器"""
        text = text or ""
        if not text.strip():
            return []

        if len(text) <= self.chunk_size:
            return [self._normalize_chunk(text, {"split_method": "legal_recursive"})]

        parts = self.legal_recursive_splitter.split_text(text)
        out: List[Dict] = []
        for idx, p in enumerate(parts):
            if p.strip():
                out.append(
                    self._normalize_chunk(
                        p,
                        {
                            "chunk_index": idx,
                            "split_method": "legal_recursive",
                        },
                    )
                )
        return out

    def _split_by_article(self, text: str, base_metadata: Dict) -> List[Dict]:
        """
        按“第X条”切分成一条一条，语义类似 law_ai 里的
        separators = [r"第\\S*条 "] + is_separator_regex=True
        """
        # 兼容全角/半角空格
        pattern = re.compile(r"(第\S*条[ 　])")
        parts = pattern.split(text)

        chunks: List[Dict] = []

        # parts 结构: [前言, "第一条 ", 第一条内容, "第二条 ", 第二条内容, ...]
        prefix = parts[0].strip() if parts else ""
        if prefix:
            md = base_metadata.copy()
            md["split_method"] = "article_preface"
            chunks.append(self._normalize_chunk(prefix, md))

        for i in range(1, len(parts), 2):
            title = parts[i].strip()                  # 例如 "第一条"
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if not body:
                continue

            content = f"{title} {body}".strip()
            md = base_metadata.copy()
            md.update(
                {
                    "article_title": title,
                    "split_method": "article",
                }
            )
            chunks.append(self._normalize_chunk(content, md))

        return chunks

    def _split_markdown(self, text: str) -> List[Dict]:
        """
        Markdown：
        1) 先按标题（宪法名、章节名）切
        2) 每个章节内部再按“第X条”切成条文
        3) 对极长条文再用递归规则细分
        """
        if not text.strip():
            return []

        # 1) Markdown 标题切分
        docs = self.markdown_splitter.split_text(text)
        article_level_chunks: List[Dict] = []

        for d in docs:
            c = d.page_content.strip()
            if not c:
                continue

            base_md = d.metadata.copy()

            # 如果这一块里包含“第X条”，就按条文再拆
            if re.search(r"第\S*条", c):
                article_chunks = self._split_by_article(c, base_md)
                article_level_chunks.extend(article_chunks)
            else:
                # 否则保持整块
                article_level_chunks.append(self._normalize_chunk(c, base_md))

        # 2) 对过长的条文再用法律递归规则细分（一般用不到，但保底）
        refined: List[Dict] = []
        for ch in article_level_chunks:
            content = (ch["content"] or "").strip()
            if len(content) <= self.chunk_size:
                refined.append(ch)
                continue

            subs = self._split_by_legal_recursive(content)
            for sub in subs:
                md = ch["metadata"].copy()
                md.update(sub.get("metadata", {}))
                md["is_sub_chunk"] = True
                refined.append(
                    {
                        "content": sub["content"],
                        "metadata": md,
                    }
                )

        return refined

    def split_with_metadata(
        self,
        text: str,
        source_name: str,
        source_type: str = "legal",
        **extra_metadata: Any,
    ) -> List[Dict]:
        """
        主入口：返回 [{"content": "...", "metadata": {...}}, ...]
        """
        if not text.strip():
            return []

        # 简单判断是不是 Markdown（以 # 开头 或 存在多级标题）
        is_markdown = text.strip().startswith("#")
        if not is_markdown:
            import re

            if re.search(r"^#{1,4}\s+", text, re.MULTILINE):
                is_markdown = True

        if is_markdown:
            chunks = self._split_markdown(text)
        else:
            chunks = self._split_by_legal_recursive(text)

        # 统一过滤 + 合并
        chunks = self._filter_and_merge_chunks(chunks)

        # 统一追加元数据
        for ch in chunks:
            ch.setdefault("metadata", {})
            ch["metadata"].update(
                {
                    "source_name": source_name,
                    "source_type": source_type,
                    **extra_metadata,
                }
            )

        return chunks


def load_markdown_text(path: str) -> str:
    """读取 .md 法律条文文件为纯文本"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> None:
    # 项目根目录（假定与原来一样：E:\cp）
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1) 读取宪法 Markdown 文件
    law_path = os.path.join(BASE_DIR, "Law-Book", "1-宪法", "宪法.md")
    if not os.path.exists(law_path):
        raise FileNotFoundError(f"未找到宪法文件: {law_path}")

    text = load_markdown_text(law_path)

    # 2) 使用本文件里定义的 LawTextSplitter
    splitter = LawTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )

    chunks: List[Dict[str, Any]] = splitter.split_with_metadata(
        text=text,
        source_name="宪法.md",
        source_type="legal",
        user_id=0,
        contract_id=None,
    )

    print(f"总共切出 {len(chunks)} 个法律条文 chunk")

    # 简单预览前若干条
    preview_n = min(5, len(chunks))
    for i in range(preview_n):
        c = chunks[i]
        print("=" * 80)
        print(f"Chunk #{i}")
        print("Metadata:", c.get("metadata", {}))
        print("- 内容预览 -")
        print((c.get("content") or "")[:200].replace("\n", "\\n"))

    # 3) 写出 JSON 结果到 problem_test 目录下
    out_path = os.path.join(BASE_DIR, "problem_test", "law_split_constitution_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"\n切分结果已写入: {out_path}")


if __name__ == "__main__":
    main()