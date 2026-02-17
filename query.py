#!/usr/bin/env python3
"""
RAG 查询脚本 - 支持跨语言检索
用法: python query.py "你的查询"
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
from qdrant_client import QdrantClient

project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

sys.path.insert(0, str(project_root / "src"))
from azure_embedding import AzureOpenAIEmbedding

def search(query: str, top_k: int = 5):
    """执行查询"""
    qdrant = QdrantClient(host="localhost", port=6333)
    embedder = AzureOpenAIEmbedding()
    
    print(f"\n🔍 查询: {query}")
    print("="*60)
    
    # 生成查询向量
    query_vector = embedder.embed(query)
    
    # 获取所有点
    points = qdrant.scroll(
        collection_name="rag_documents",
        limit=100,
        with_payload=True,
        with_vectors=True
    )[0]
    
    if not points:
        print("❌ 向量库为空")
        return
    
    # 计算相似度
    query_vec = np.array(query_vector)
    results = []
    
    for point in points:
        if hasattr(point, 'vector') and point.vector:
            point_vec = np.array(point.vector)
            similarity = np.dot(query_vec, point_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(point_vec)
            )
            results.append((point, similarity))
    
    results.sort(key=lambda x: x[1], reverse=True)
    
    # 显示结果
    print(f"\n✅ 找到 {len(results)} 个相关文档\n")
    
    for i, (point, score) in enumerate(results[:top_k], 1):
        text = point.payload['text']
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in text[:50])
        lang = "🇨🇳" if is_chinese else "🇺🇸"
        
        print(f"[{i}] 相似度: {score:.4f} {lang}")
        print(f"    来源: {point.payload['metadata']['source']}")
        print(f"    {text[:150]}...")
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python query.py '你的查询'")
        print("\n示例:")
        print("  python query.py 'AI Agent 是什么'")
        print("  python query.py 'What is Kubernetes'")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    search(query)
