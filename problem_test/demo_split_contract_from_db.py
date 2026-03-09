import os
import sys
import json

# demo_split_contract_from_db.py
#
# 从数据库里读取指定合同（user_id=5, contract_id=28）的 file_content，
# 走一遍 ContractTextSplitter，打印 / 落盘切分结果，方便人工检查。

# 把项目根目录 E:\cp 和 backend 目录加到 sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
for p in (BASE_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.database import SessionLocal  # type: ignore
from backend.app import models  # type: ignore
from backend.app.services.contract_splitter import ContractTextSplitter  # type: ignore


def main():
    # 目标合同
    target_user_id = 5
    target_contract_id = 29

    db = SessionLocal()
    try:
        contract = (
            db.query(models.Contract)
            .filter(
                models.Contract.id == target_contract_id,
                models.Contract.user_id == target_user_id,
            )
            .first()
        )
        if not contract:
            print(f"找不到合同：user_id={target_user_id}, contract_id={target_contract_id}")
            return

        text = (contract.file_content or "").strip()
        if not text:
            print(
                f"合同存在，但 file_content 为空：user_id={target_user_id}, contract_id={target_contract_id}"
            )
            return

        splitter = ContractTextSplitter()
        chunks = splitter.split_with_metadata(
            text=text,
            source_name=contract.filename or f"contract_{contract.id}",
            user_id=contract.user_id,
            contract_id=contract.id,
        )

        print(f"✅ 合同 id={contract.id}, user_id={contract.user_id}")
        print(f"文件名: {contract.filename}")
        print(f"总共切出 {len(chunks)} 个 chunk\n")

        # 控制台预览前若干条
        preview_n = min(10, len(chunks))
        for i, c in enumerate(chunks[:preview_n]):
            md = c.get("metadata", {})
            print("=" * 80)
            print(f"Chunk #{i}")
            print(
                f"clause_index={md.get('clause_index')}, "
                f"clause_marker={md.get('clause_marker')}, "
                f"chunk_index={md.get('chunk_index')}"
            )
            content = (c.get("content") or "").strip()
            print(f"内容长度: {len(content)}")
            print("- 内容预览 -")
            print(content[:400])
            if len(content) > 400:
                print("... [截断，仅显示前400字符]")

        # 全量结果写入文件
        output_dir = os.path.join(BASE_DIR, "problem_test", "split_results")
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(
            output_dir, f"user{target_user_id}_contract{target_contract_id}_chunks.json"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        print(f"\n切分结果已写入文件：{output_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()


