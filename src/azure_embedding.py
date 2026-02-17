#!/usr/bin/env python3
"""
Azure OpenAI Embedding 客户端 - 加强验证版
"""
import os
from typing import List, Union
import requests
from pathlib import Path
import time
import logging
import re

logger = logging.getLogger("AzureEmbedding")

from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")


class AzureOpenAIEmbedding:
    """Azure OpenAI Embedding 客户端"""
    
    def __init__(
        self,
        endpoint: str = None,
        api_key: str = None,
        deployment_name: str = None,
        api_version: str = "2024-02-01",
        max_retries: int = 3,
        timeout: int = 60,
        batch_size: int = 20,
        model: str = None,
        **kwargs
    ):
        self.endpoint = endpoint or os.getenv('AZURE_OPENAI_ENDPOINT')
        self.api_key = api_key or os.getenv('AZURE_OPENAI_API_KEY')
        self.deployment_name = deployment_name or os.getenv('AZURE_EMBEDDING_DEPLOYMENT')
        self.api_version = api_version
        self.max_retries = max_retries
        self.timeout = timeout
        self.default_batch_size = batch_size
        
        if not all([self.endpoint, self.api_key, self.deployment_name]):
            raise ValueError("❌ 缺少必需的环境变量")
        
        self.url = f"{self.endpoint.rstrip('/')}/openai/deployments/{self.deployment_name}/embeddings?api-version={self.api_version}"
        self.headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }
        
        logger.info(f"✅ Azure OpenAI 客户端初始化")
        logger.info(f"   Endpoint: {self.endpoint}")
        logger.info(f"   Deployment: {self.deployment_name}")
    
    def validate_and_clean_text(self, text: str) -> str:
        """
        验证和清理文本
        
        Args:
            text: 输入文本
            
        Returns:
            清理后的文本
        """
        if not text or not text.strip():
            return "empty"
        
        # 移除 null 字符和其他控制字符
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
        
        # 截断过长文本
        # text-embedding-3-large: 8191 tokens ≈ 32,000 字符
        # 使用 30,000 作为安全值
        max_chars = 30000
        if len(text) > max_chars:
            logger.warning(f"⚠️  文本过长 ({len(text)} 字符)，截断到 {max_chars}")
            text = text[:max_chars]
        
        text = text.strip()
        return text if text else "empty"
    
    def embed(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """生成 embedding - 带验证"""
        is_single = isinstance(text, str)
        texts = [text] if is_single else text
        
        # 验证和清理所有文本
        texts = [self.validate_and_clean_text(t) for t in texts]
        
        payload = {"input": texts}
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 10))
                    logger.warning(f"⚠️  速率限制，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                    continue
                
                # 如果是 400 错误，记录详细信息
                if response.status_code == 400:
                    logger.error(f"❌ 400 错误详情:")
                    logger.error(f"   响应: {response.text[:500]}")
                    logger.error(f"   文本数量: {len(texts)}")
                    logger.error(f"   文本长度: {[len(t) for t in texts]}")
                
                response.raise_for_status()
                
                data = response.json()
                embeddings = [item['embedding'] for item in data['data']]
                
                return embeddings[0] if is_single else embeddings
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 10))
                    time.sleep(retry_after)
                    if attempt < self.max_retries - 1:
                        continue
                
                logger.error(f"❌ HTTP 错误: {e}")
                if attempt == self.max_retries - 1:
                    raise
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"⚠️  尝试 {attempt + 1}/{self.max_retries}: {e}")
                    time.sleep(wait)
                else:
                    raise
        
        raise Exception("Max retries exceeded")
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = None,
        show_progress: bool = True
    ) -> List[List[float]]:
        """批量生成 embeddings"""
        if batch_size is None:
            batch_size = self.default_batch_size
        
        try:
            from utils.helpers import batch_iterator, show_progress as progress_bar
        except ImportError:
            def batch_iterator(items, size):
                for i in range(0, len(items), size):
                    yield items[i:i + size]
            def progress_bar(items, **kwargs):
                return items
        
        all_embeddings = []
        batches = list(batch_iterator(texts, batch_size))
        
        iterator = progress_bar(
            batches,
            desc="Embedding",
            total=len(batches),
            disable=not show_progress
        )
        
        request_count = 0
        start_minute = time.time()
        failed_count = 0
        
        for i, batch in enumerate(iterator):
            if request_count >= 50:
                elapsed = time.time() - start_minute
                if elapsed < 60:
                    wait = 60 - elapsed + 5
                    logger.info(f"⏱️  速率保护: 等待 {wait:.0f} 秒...")
                    time.sleep(wait)
                    start_minute = time.time()
                    request_count = 0
            
            try:
                embeddings = self.embed(batch)
                all_embeddings.extend(embeddings)
                request_count += 1
                time.sleep(2.0)
                
            except Exception as e:
                error_msg = str(e).lower()
                
                if "rate limit" in error_msg or "429" in error_msg:
                    logger.warning(f"⚠️  速率限制，等待 30 秒...")
                    time.sleep(30)
                    try:
                        embeddings = self.embed(batch)
                        all_embeddings.extend(embeddings)
                    except:
                        logger.error(f"❌ 批次 {i+1} 重试失败，跳过")
                        # 用零向量填充
                        all_embeddings.extend([[0.0] * 3072 for _ in batch])
                        failed_count += 1
                
                elif "400" in error_msg or "model_error" in error_msg:
                    logger.error(f"❌ 批次 {i+1} 有问题，尝试单独处理...")
                    # 单独处理每个文本
                    for text in batch:
                        try:
                            emb = self.embed(text)
                            all_embeddings.append(emb)
                            time.sleep(1)
                        except:
                            logger.error(f"❌ 单个文本也失败，使用零向量")
                            all_embeddings.append([0.0] * 3072)
                            failed_count += 1
                else:
                    raise
        
        if failed_count > 0:
            logger.warning(f"⚠️  {failed_count} 个文本块使用了零向量占位")
        
        return all_embeddings
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            embedding = self.embed("test")
            if embedding and len(embedding) > 0:
                logger.info(f"✅ 连接成功，维度: {len(embedding)}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            return False


if __name__ == "__main__":
    print("🧪 测试 Azure OpenAI Embedding\n")
    embedder = AzureOpenAIEmbedding()
    
    if embedder.test_connection():
        print("✅ 连接正常\n")
        
        # 测试边界情况
        print("📝 测试特殊情况...")
        test_cases = [
            "正常文本",
            "",  # 空文本
            "x" * 40000,  # 过长文本
            "包含特殊字符\x00的文本"
        ]
        
        embeddings = embedder.embed_batch(test_cases, batch_size=2)
        print(f"✅ 处理了 {len(embeddings)} 个文本（包括边界情况）")
