"""
Chunk Size 测试配置
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 测试数据目录
BASE_DIR = PROJECT_ROOT / "chunk-size-test"
DATA_DIR = BASE_DIR / "data"
EMBEDDING_DIR = BASE_DIR / "embeddings"
RESULTS_DIR = BASE_DIR / "results"
LAW_BOOK_DIR = PROJECT_ROOT / "Law-Book"

# 测试文件列表（相对Law-Book目录的路径）
TEST_FILES = [
    "3-民法典/民法典.md",
    "3-民法商法/合伙企业法（2006-08-27）.md",
    "4-行政法/食品安全法（2021-04-29）.md",
    "1-宪法/宪法.md",
]

# 测试配置
TEST_CONFIGS = [
    {"chunk_size": 500, "overlap": 50},
    {"chunk_size": 800, "overlap": 100},
    {"chunk_size": 1000, "overlap": 100},
    {"chunk_size": 1200, "overlap": 150},
]

# 评估指标配置
EVAL_TOP_K = [3, 5, 10]

# 查询数据集路径（使用现有的）
QUERIES_PATH = PROJECT_ROOT / "embedding-test" / "eval" / "queries.jsonl"


def ensure_directories():
    """确保所有需要的目录已创建"""
    for d in [DATA_DIR, EMBEDDING_DIR, RESULTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


ensure_directories()
