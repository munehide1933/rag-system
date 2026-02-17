from qdrant_client import QdrantClient
from pathlib import Path
from dotenv import load_dotenv
import sys
import numpy as np

project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

sys.path.insert(0, str(project_root / "src"))
from azure_embedding import AzureOpenAIEmbedding

print("🔧 初始化...")
qdrant = QdrantClient(host="localhost", port=6333)
embedder = AzureOpenAIEmbedding()

# 检查集合
collection = qdrant.get_collection("rag_documents")
print(f"\n📊 向量数量: {collection.points_count}")

if collection.points_count == 0:
    print("\n❌ 向量库为空，请先运行:")
    print("   python src/ingest_qdrant_v2.py documents/")
    sys.exit(1)

# 测试多个查询
test_queries = [
    ("中文查询", "AI Agent 是什么?"),
    ("英文查询", "What is AI Agent?"),
    ("中文查询 K8s", "Kubernetes 有什么特点?"),
    ("英文查询 K8s", "What are Kubernetes features?")
]

for test_name, query in test_queries:
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print(f"🔍 查询: {query}")
    print(f"{'='*60}")
    
    # 生成查询向量
    query_vector = embedder.embed(query)
    
    # 获取所有点
    points = qdrant.scroll(
        collection_name="rag_documents",
        limit=50,
        with_payload=True,
        with_vectors=True
    )[0]
    
    if not points:
        print("❌ 没有找到任何文档")
        continue
    
    # 计算相似度
    query_vec = np.array(query_vector)
    results = []
    
    for point in points:
        if hasattr(point, 'vector') and point.vector:
            point_vec = np.array(point.vector)
            # 余弦相似度
            similarity = np.dot(query_vec, point_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(point_vec)
            )
            results.append((point, similarity))
    
    # 排序
    results.sort(key=lambda x: x[1], reverse=True)
    
    # 显示 top 3
    print(f"\n✅ 找到 {len(results)} 个文档，显示 top 3:\n")
    
    for i, (point, score) in enumerate(results[:3], 1):
        text = point.payload['text']
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in text[:50])
        lang = "🇨🇳 中文" if is_chinese else "🇺🇸 英文"
        
        print(f"结果 {i}:")
        print(f"  📊 相似度: {score:.4f}")
        print(f"  🌍 语言: {lang}")
        print(f"  📁 来源: {point.payload['metadata']['source']}")
        print(f"  🏷️  类别: {point.payload['metadata']['category']}")
        print(f"  📝 内容: {text[:120]}...")
        print()

print("\n" + "="*60)
print("✅ 测试完成！")
print("="*60)
print("\n💡 观察:")
print("  • 如果中文查询找到了英文文档（相似度高）")
print("  • 或英文查询找到了中文文档（相似度高）")
print("  • 说明 text-embedding-3-large 的跨语言检索工作正常！")
print()
