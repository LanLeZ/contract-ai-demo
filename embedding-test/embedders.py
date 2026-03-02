"""
Embedding 实现（仅保留 DashScope 系列模型，用于本次评测）
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from dotenv import load_dotenv
import requests

# 加载项目根目录的 .env 文件
project_root = Path(__file__).parent.parent
load_dotenv(dotenv_path=project_root / ".env")


class BaseEmbedder(ABC):
    """统一的 Embedding 接口"""
    
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量向量化文档"""
        pass
    
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """向量化单个查询"""
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """获取向量维度"""
        pass


class DashScopeEmbedder(BaseEmbedder):
    """通义千问 Embedding 服务（支持 DashScope SDK 和 HTTP API）"""
    
    def __init__(self, model: str = "text-embedding-v3"):
        """
        初始化 Embedding 服务
        Args:
            model: 模型名称，支持：
                - text-embedding-v3（1024维）
                - text-embedding-v2（1536维）
                - text-embedding-v4（1024维，默认）
                - qwen3-embedding-8b（1024维）
        """
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
            print(f"🌐 使用中转平台 API: {self.api_base_url}")
            print(f"📌 模型名称: {self.model}")
        else:
            # 使用 DashScope SDK
            self._use_http_api = False
            try:
                from dashscope import TextEmbedding
                self._text_embedding = TextEmbedding
            except ImportError:
                raise ImportError("dashscope未安装，请运行: pip install dashscope")
            print(f"🔧 使用 DashScope SDK")
    
    def _embed_via_http_api(self, texts: List[str]) -> List[List[float]]:
        """
        通过 HTTP API 调用中转平台进行 embedding
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
            
            # 如果请求失败，打印详细错误信息
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_detail = response.json()
                except:
                    error_detail = response.text
                raise Exception(f"API 返回错误 {response.status_code}: {error_detail}")
            
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应（兼容 DashScope 格式）
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
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量embedding文档
        注意：通义千问API限制每批最多10条文本，本方法会自动分批处理
        """
        if not texts:
            return []
        
        MAX_BATCH_SIZE = 10
        
        # 如果使用 HTTP API（中转平台），直接调用
        if self._use_http_api:
            if len(texts) <= MAX_BATCH_SIZE:
                return self._embed_via_http_api(texts)
            
            # 分批处理
            total_batches = (len(texts) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
            print(f"  自动分批处理: {len(texts)} 条文本，分 {total_batches} 批（每批最多 {MAX_BATCH_SIZE} 条）")
            
            all_embeddings = []
            for i in range(0, len(texts), MAX_BATCH_SIZE):
                batch = texts[i:i + MAX_BATCH_SIZE]
                batch_num = i // MAX_BATCH_SIZE + 1
                
                try:
                    batch_embeddings = self._embed_via_http_api(batch)
                    all_embeddings.extend(batch_embeddings)
                    if total_batches > 1:
                        print(f"    第 {batch_num}/{total_batches} 批完成 ({len(batch)} 条)")
                except Exception as e:
                    raise Exception(f"Embedding失败（第 {batch_num} 批）: {str(e)}")
            
            return all_embeddings
        
        # 使用 DashScope SDK（原有逻辑）
        all_embeddings = []
        
        if len(texts) <= MAX_BATCH_SIZE:
            try:
                response = self._text_embedding.call(
                    model=self.model,
                    input=texts,
                    api_key=self.api_key
                )
                
                if response.status_code == 200:
                    embeddings = [item['embedding'] for item in response.output['embeddings']]
                    return embeddings
                else:
                    raise Exception(f"Embedding API错误: {response.message}")
            except Exception as e:
                raise Exception(f"Embedding失败: {str(e)}")
        
        # 分批处理
        total_batches = (len(texts) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
        print(f"  自动分批处理: {len(texts)} 条文本，分 {total_batches} 批（每批最多 {MAX_BATCH_SIZE} 条）")
        
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i:i + MAX_BATCH_SIZE]
            batch_num = i // MAX_BATCH_SIZE + 1
            
            try:
                response = self._text_embedding.call(
                    model=self.model,
                    input=batch,
                    api_key=self.api_key
                )
                
                if response.status_code == 200:
                    batch_embeddings = [item['embedding'] for item in response.output['embeddings']]
                    all_embeddings.extend(batch_embeddings)
                    if total_batches > 1:
                        print(f"    第 {batch_num}/{total_batches} 批完成 ({len(batch)} 条)")
                else:
                    raise Exception(f"Embedding API错误（第 {batch_num} 批）: {response.message}")
            except Exception as e:
                raise Exception(f"Embedding失败（第 {batch_num} 批）: {str(e)}")
        
        return all_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """单个查询文本embedding"""
        if not text:
            raise ValueError("查询文本不能为空")
        
        result = self.embed_documents([text])
        return result[0] if result else []
    
    def get_embedding_dimension(self) -> int:
        """获取向量维度"""
        if self.model == "text-embedding-v3":
            return 1024
        elif self.model == "text-embedding-v2":
            return 1536
        elif self.model == "text-embedding-v4":
            return 1024  # text-embedding-v4 默认1024维（支持多种维度，默认1024）
        elif self.model == "qwen3-embedding-8b":
            return 1024  # qwen3-embedding-8b，默认1024维（如实际不同请调整）
        else:
            return 1024  # 默认值


def create_embedder(model_type: str, model_name: str = None) -> BaseEmbedder:
    """
    创建 Embedder 实例的工厂函数
    
    业务逻辑：
    - 为当前实验统一管理 DashScope embedding 模型的创建逻辑
    - 通过 model_type 和 model_name 指定具体模型（仅支持 DashScope）
    - 为 DashScope 提供合理的默认值

    技术实现：
    - 根据 model_type 参数选择对应的 Embedder 类
    - 如果未指定 model_name，使用 DashScope 默认模型 text-embedding-v3
    - 抛出明确的错误信息，便于调试
    
    Args:
        model_type: 模型类型（当前仅支持 "dashscope"）：
            - "dashscope": DashScope 模型（text-embedding-v3, text-embedding-v2, text-embedding-v4, qwen3-embedding-8b）
        model_name: 具体模型名称，如果为 None 则使用默认值
    
    Returns:
        BaseEmbedder 实例
    
    Raises:
        ValueError: 如果 model_type 不支持
    """
    if model_type == "dashscope":
        return DashScopeEmbedder(model=model_name or "text-embedding-v3")

    raise ValueError(
        f"不支持的模型类型: {model_type}，当前仅支持 dashscope（通义千问 embedding 模型）"
    )

