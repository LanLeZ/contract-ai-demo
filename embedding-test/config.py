from pathlib import Path

"""
全局路径与配置

说明：
- 假定本文件位于项目根目录下的 embedding-test 子目录中
- 通过 PROJECT_ROOT 自动推断项目根目录
- 提供统一的数据、向量与图表输出路径
"""


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Law-Book 根目录（法律条文 Markdown）
LAW_BOOK_DIR = PROJECT_ROOT / "Law-Book"

# 实验数据与输出目录
BASE_DIR = PROJECT_ROOT / "embedding-test"
DATA_DIR = BASE_DIR / "data"
EMBEDDING_DIR = BASE_DIR / "embeddings"
EVAL_DIR = BASE_DIR / "eval"
PLOTS_DIR = BASE_DIR / "plots"

# 默认文件路径
# 业务逻辑：
# - 本轮实验聚焦 LawBench 涉及的全部法律，先在 Law-Book 中筛选出相关法律，再统一切分为 chunks
# - 评测时，所有模型都基于这一个统一的 chunks 文件（包含多个不同的法律）
# 技术说明：
# - 默认 chunks 文件命名为 lawbench_laws_chunks.jsonl，表示「LawBench 相关法律的统一切分结果」
# - 如需恢复仅民法典评测，可显式传入其他 chunks_path，或重新生成 civil_code_chunks.jsonl 并在脚本中指定
CHUNKS_PATH = DATA_DIR / "lawbench_laws_chunks.jsonl"


def ensure_directories() -> None:
    """确保所有需要的目录已创建"""
    for d in [DATA_DIR, EMBEDDING_DIR, EVAL_DIR, PLOTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# 在导入时就创建目录，避免后续脚本中重复判断
ensure_directories()


