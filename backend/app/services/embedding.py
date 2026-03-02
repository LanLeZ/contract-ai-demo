"""
通义千问Embedding服务封装（支持中转平台API）
"""
import os
import logging
import time
import requests
from typing import List
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(dotenv_path=project_root / ".env")

# 配置日志
logger = logging.getLogger(__name__)

try:
    from dashscope import TextEmbedding
except ImportError:
    TextEmbedding = None
    logger.warning("dashscope未安装，请运行: pip install dashscope")


class DashScopeEmbedder:
    """通义千问Embedding服务（支持DashScope SDK和HTTP API）"""
    
    def __init__(self, model: str = None):
        """
        初始化Embedding服务
        Args:
            model: 模型名称，默认从环境变量 EMBEDDING_MODEL 读取，如果未设置则使用 qwen3-embedding-8b（1024维）
        """
        # 优先从环境变量读取模型名称，如果没有则使用默认值
        if model is None:
            model = os.getenv("EMBEDDING_MODEL", "qwen3-embedding-8b")
        self.model = model
        
        # 检查是否使用中转平台 API
        self.api_base_url = os.getenv("EMBEDDING_API_BASE_URL") or os.getenv("DASHSCOPE_API_BASE_URL")
        self.api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "未找到 API Key。请在.env文件中设置：\n"
                "- EMBEDDING_API_KEY=your-key（使用中转平台时）\n"
                "- 或 DASHSCOPE_API_KEY=your-key（使用 DashScope SDK 时）"
            )
        
        # 如果设置了 API_BASE_URL，使用 HTTP 请求方式（中转平台）
        if self.api_base_url:
            self._use_http_api = True
            logger.info(f"🌐 使用中转平台 API: {self.api_base_url}")
            logger.info(f"📌 模型名称: {self.model}")
        else:
            # 使用 DashScope SDK
            self._use_http_api = False
            if TextEmbedding is None:
                raise ImportError("dashscope未安装，请运行: pip install dashscope")
            logger.info(f"🔧 使用 DashScope SDK")
    
    def _embed_via_http_api(self, texts: List[str]) -> List[List[float]]:
        """
        通过 HTTP API 调用中转平台进行 embedding
        
        Args:
            texts: 文本列表（最多10条）
        Returns:
            向量列表（二维列表）
        """
        url = self.api_base_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 中转平台 API 请求体
        payload = {
            "input": texts,
            "model": self.model
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_detail = response.json()
                except:
                    error_detail = response.text
                raise Exception(f"API 返回错误 {response.status_code}: {error_detail}")
            
            response.raise_for_status()
            result = response.json()
            
            # 解析响应（兼容多种格式）
            if "output" in result and "embeddings" in result["output"]:
                # DashScope 格式: {"output": {"embeddings": [{"embedding": [...]}, ...]}, "status_code": 200}
                embeddings = [item["embedding"] for item in result["output"]["embeddings"]]
            elif "data" in result:
                # OpenAI 兼容格式: {"data": [{"embedding": [...]}, ...]}
                embeddings = [item["embedding"] for item in result["data"]]
            elif "embeddings" in result:
                # 其他格式: {"embeddings": [[...], [...]]}
                embeddings = result["embeddings"]
            else:
                raise ValueError(f"无法解析 API 响应格式: {list(result.keys())}")
            
            return embeddings
            
        except requests.exceptions.HTTPError as e:
            # 如果是 HTTPError，尝试获取响应内容
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                except:
                    error_detail = e.response.text
                raise Exception(f"HTTP API 请求失败: {str(e)}\n响应详情: {error_detail}")
            raise Exception(f"HTTP API 请求失败: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"HTTP API 请求失败: {str(e)}")
        except (KeyError, ValueError) as e:
            raise Exception(f"解析 API 响应失败: {str(e)}")
    
    def embed_documents(self, texts: List[str], max_retries: int = 3, retry_delay: float = 1.0) -> List[List[float]]:
        """
        批量embedding文档
        注意：通义千问API限制每批最多10条文本，本方法会自动分批处理
        
        Args:
            texts: 文本列表（可以超过10条，会自动分批）
            max_retries: 最大重试次数（默认3次，仅用于DashScope SDK）
            retry_delay: 重试延迟（秒，默认1秒，仅用于DashScope SDK）
        Returns:
            向量列表，每个向量是1024维（qwen3-embedding-8b）
        """
        if not texts:
            return []
        
        # 过滤空文本
        valid_texts = [text for text in texts if text and text.strip()]
        if len(valid_texts) != len(texts):
            logger.warning(f"过滤了 {len(texts) - len(valid_texts)} 个空文本")
        
        if not valid_texts:
            logger.warning("所有文本都为空，返回空向量列表")
            return []
        
        # 通义千问API限制：每批最多10条
        MAX_BATCH_SIZE = 10
        
        # 如果使用 HTTP API（中转平台），直接调用
        if self._use_http_api:
            if len(valid_texts) <= MAX_BATCH_SIZE:
                return self._embed_via_http_api(valid_texts)
            
            # 分批处理
            total_batches = (len(valid_texts) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
            logger.info(f"自动分批处理: {len(valid_texts)} 条文本，分 {total_batches} 批（每批最多 {MAX_BATCH_SIZE} 条）")
            
            all_embeddings = []
            for i in range(0, len(valid_texts), MAX_BATCH_SIZE):
                batch = valid_texts[i:i + MAX_BATCH_SIZE]
                batch_num = i // MAX_BATCH_SIZE + 1
                
                try:
                    batch_embeddings = self._embed_via_http_api(batch)
                    all_embeddings.extend(batch_embeddings)
                    if total_batches > 1:
                        logger.debug(f"第 {batch_num}/{total_batches} 批完成 ({len(batch)} 条)")
                except Exception as e:
                    logger.error(f"第 {batch_num} 批embedding失败: {str(e)}")
                    raise Exception(f"Embedding失败（第 {batch_num} 批）: {str(e)}")
            
            return all_embeddings
        
        # 使用 DashScope SDK（原有逻辑）
        all_embeddings = []
        
        # 如果文本数量 <= 10，直接处理
        if len(valid_texts) <= MAX_BATCH_SIZE:
            return self._embed_batch_with_retry(valid_texts, max_retries, retry_delay)
        
        # 如果文本数量 > 10，分批处理
        total_batches = (len(valid_texts) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
        logger.info(f"自动分批处理: {len(valid_texts)} 条文本，分 {total_batches} 批（每批最多 {MAX_BATCH_SIZE} 条）")
        
        for i in range(0, len(valid_texts), MAX_BATCH_SIZE):
            batch = valid_texts[i:i + MAX_BATCH_SIZE]
            batch_num = i // MAX_BATCH_SIZE + 1
            
            try:
                batch_embeddings = self._embed_batch_with_retry(batch, max_retries, retry_delay)
                all_embeddings.extend(batch_embeddings)
                if total_batches > 1:
                    logger.debug(f"第 {batch_num}/{total_batches} 批完成 ({len(batch)} 条)")
            except Exception as e:
                logger.error(f"第 {batch_num} 批embedding失败: {str(e)}")
                raise Exception(f"Embedding失败（第 {batch_num} 批）: {str(e)}")
        
        return all_embeddings
    
    def _embed_batch_with_retry(self, texts: List[str], max_retries: int = 3, retry_delay: float = 1.0) -> List[List[float]]:
        """
        带重试机制的批量embedding
        
        Args:
            texts: 文本列表（最多10条）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        Returns:
            向量列表
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = TextEmbedding.call(
                    model=self.model,
                    input=texts,
                    api_key=self.api_key
                )
                
                if response.status_code == 200:
                    embeddings = [item['embedding'] for item in response.output['embeddings']]
                    if len(embeddings) != len(texts):
                        logger.warning(f"返回的向量数量({len(embeddings)})与输入文本数量({len(texts)})不匹配")
                    return embeddings
                else:
                    error_msg = f"Embedding API错误: {response.message} (状态码: {response.status_code})"
                    logger.warning(f"第 {attempt + 1} 次尝试失败: {error_msg}")
                    last_exception = Exception(error_msg)
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"第 {attempt + 1} 次尝试失败: {error_msg}")
                last_exception = e
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # 指数退避
        
        # 所有重试都失败，抛出异常
        raise Exception(f"Embedding失败（已重试 {max_retries} 次）: {str(last_exception)}")
    
    def embed_query(self, text: str) -> List[float]:
        """
        单个查询文本embedding
        Args:
            text: 查询文本
        Returns:
            向量（1024维）
        """
        if not text or not text.strip():
            raise ValueError("查询文本不能为空")
        
        result = self.embed_documents([text])
        if not result:
            raise ValueError("Embedding返回空结果")
        return result[0]
    
    def get_embedding_dimension(self) -> int:
        """
        获取向量维度
        Returns:
            向量维度（qwen3-embedding-8b返回1024）
        """
        if self.model == "qwen3-embedding-8b":
            return 1024
        elif self.model == "text-embedding-v3":
            return 1024
        elif self.model == "text-embedding-v2":
            return 1536
        elif self.model == "text-embedding-v4":
            return 1024  # text-embedding-v4 默认1024维
        else:
            return 1024  # 默认值

