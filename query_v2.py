#!/usr/bin/env python3
"""
RAG 查询脚本 v2 — 两阶段检索 + Cross-Encoder 重排序
------------------------------------------------
Stage 1: Qdrant HNSW ANN 向量检索（召回 top_k * recall_multiplier 个候选）
Stage 2: BAAI/bge-reranker-v2-m3 Cross-Encoder 精排（返回 top_k 个结果）

性能提升：
  - 用 qdrant.search() 替代 scroll + 手算余弦，利用 HNSW 索引加速
  - 只传输候选文本，不传输所有向量
  - Cross-Encoder 模型首次加载后缓存，后续查询极快
"""
import sys
import time
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent / "src"))

from azure_embedding import AzureOpenAIEmbedding
from utils.helpers import DiskCache

logging.basicConfig(level=logging.WARNING)  # 屏蔽底层库的 INFO 日志
logger = logging.getLogger("RAGQuery")

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────
COLLECTION      = "rag_documents"
RERANKER_MODEL  = "BAAI/bge-reranker-v2-m3"   # 支持中英文，~2.3GB
RECALL_MULT     = 3    # 召回倍数：top_k=5 时召回 15 个候选（从 20 降到 15）
MIN_SCORE       = 0.0  # 向量检索阶段最低分
RERANKER_MAX_LEN = 256 # 中文语义密度高，256 token ≈ 200+ 字，截断影响极小
PROJECT_ROOT = Path(__file__).parent.resolve()
QUERY_CACHE_DIR = PROJECT_ROOT / "data/query_cache"


# ──────────────────────────────────────────────
# 设备自动检测
# ──────────────────────────────────────────────
def _best_device() -> str:
    """
    自动选择最优计算设备：
      Apple Silicon (M 系列) → MPS  (Metal GPU，速度约 CPU 的 3-5x)
      NVIDIA GPU             → CUDA
      其他                   → CPU
    """
    try:
        import torch
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


# ──────────────────────────────────────────────
# Reranker 懒加载（只在首次查询时初始化）
# ──────────────────────────────────────────────
_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            device = _best_device()
            device_label = {
                "mps":  "Apple Metal GPU ⚡",
                "cuda": "NVIDIA CUDA ⚡",
                "cpu":  "CPU",
            }.get(device, device)
            print(f"⏳ 首次加载 Reranker 模型（{RERANKER_MODEL}）...")
            print(f"   计算设备: {device_label}")
            t0 = time.time()
            _reranker = CrossEncoder(RERANKER_MODEL, max_length=RERANKER_MAX_LEN, device=device)

            # MPS/CUDA 预热：触发一次编译，避免首次真实查询时的冷启动延迟
            if device in ("mps", "cuda"):
                _reranker.predict([("warmup", "warmup")], show_progress_bar=False)

            print(f"✅ Reranker 加载完成（{time.time()-t0:.1f}s）\n")
        except ImportError:
            print("⚠️  sentence-transformers 未安装，跳过重排序")
            print("   安装命令: pip install sentence-transformers\n")
    return _reranker


# ──────────────────────────────────────────────
# 核心查询函数
# ──────────────────────────────────────────────
def search(
    query: str,
    top_k: int = 5,
    use_rerank: bool = True,
    verbose: bool = True,
) -> list[dict]:
    """
    两阶段 RAG 检索

    Args:
        query:      查询文本
        top_k:      最终返回结果数
        use_rerank: 是否启用重排序
        verbose:    是否打印结果

    Returns:
        结果列表，每项包含 text / source / score / rerank_score
    """
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant   = QdrantClient(host=qdrant_host, port=qdrant_port)
    embedder = AzureOpenAIEmbedding()
    query_cache = DiskCache(str(QUERY_CACHE_DIR))
    query_cache_namespace = (
        f"query_embedding:{embedder.deployment_name}:{embedder.api_version}"
    )

    total_start = time.time()

    # ── Stage 1: 向量检索 ──────────────────────
    t0 = time.time()
    query_vector = query_cache.get(query, namespace=query_cache_namespace)
    if query_vector is None:
        query_vector = embedder.embed(query)
        query_cache.set(query, query_vector, namespace=query_cache_namespace)
    embed_time   = time.time() - t0

    recall_n = top_k * RECALL_MULT if use_rerank else top_k

    t0 = time.time()
    # qdrant-client >= 1.10 用 query_points()，旧版用 search()
    try:
        from qdrant_client.models import QueryRequest
        response = qdrant.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            limit=recall_n,
            score_threshold=MIN_SCORE,
            with_payload=True,
            with_vectors=False,
        )
        hits = response.points
    except AttributeError:
        hits = qdrant.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            limit=recall_n,
            score_threshold=MIN_SCORE,
            with_payload=True,
            with_vectors=False,
        )
    search_time = time.time() - t0

    if not hits:
        print("❌ 未找到相关文档")
        return []

    # ── Stage 2: Cross-Encoder 重排序 ──────────
    rerank_time = 0.0

    if use_rerank:
        reranker = get_reranker()
    else:
        reranker = None

    if reranker and len(hits) > 1:
        t0 = time.time()

        valid_hits = []
        pairs = []
        for h in hits:
            payload = h.payload or {}
            text = payload.get("text")
            if not text:
                continue
            valid_hits.append(h)
            pairs.append((query, text))

        if not valid_hits:
            if verbose:
                print("❌ 候选结果缺少文本字段，无法重排序")
            return []

        # batch_size=4 在 MPS/Apple Silicon 上实测最优（减少 CPU↔GPU 搬运开销）
        scores = reranker.predict(pairs, batch_size=4, show_progress_bar=False)

        # 将 rerank 分数附加到命中结果上
        ranked = sorted(
            zip(valid_hits, scores),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        rerank_time = time.time() - t0
        results = [
            {
                "text":         hit.payload.get("text", ""),
                "source":       hit.payload.get("metadata", {}).get("source", "unknown"),
                "source_path":  hit.payload.get("metadata", {}).get("source_path"),
                "category":     hit.payload.get("metadata", {}).get("category", "—"),
                "chunk_index":  hit.payload.get("metadata", {}).get("chunk_index"),
                "vector_score": round(float(hit.score), 4),
                "rerank_score": round(float(score), 4),
            }
            for hit, score in ranked
        ]
    else:
        # 不重排序，直接取向量分数 top_k
        results = [
            {
                "text":         h.payload.get("text", ""),
                "source":       h.payload.get("metadata", {}).get("source", "unknown"),
                "source_path":  h.payload.get("metadata", {}).get("source_path"),
                "category":     h.payload.get("metadata", {}).get("category", "—"),
                "chunk_index":  h.payload.get("metadata", {}).get("chunk_index"),
                "vector_score": round(float(h.score), 4),
                "rerank_score": None,
            }
            for h in hits[:top_k]
        ]

    total_time = time.time() - total_start

    # ── 输出 ──────────────────────────────────
    if verbose:
        _print_results(query, results, embed_time, search_time, rerank_time, total_time, recall_n)

    return results


# ──────────────────────────────────────────────
# 输出格式
# ──────────────────────────────────────────────
def _lang_flag(text: str) -> str:
    return "🇨🇳" if any("\u4e00" <= c <= "\u9fff" for c in text[:80]) else "🇺🇸"


def _print_results(query, results, embed_time, search_time, rerank_time, total_time, recall_n):
    print(f"\n{'='*62}")
    print(f"🔍 查询: {query}")
    print(f"{'='*62}")

    # 耗时统计
    has_rerank = rerank_time > 0
    print(f"⏱  Embedding: {embed_time*1000:.0f}ms  |  "
          f"向量检索(top{recall_n}): {search_time*1000:.0f}ms"
          + (f"  |  Rerank: {rerank_time*1000:.0f}ms" if has_rerank else "")
          + f"  |  总计: {total_time*1000:.0f}ms")
    print()

    for i, r in enumerate(results, 1):
        lang = _lang_flag(r["text"])

        # 分数显示
        score_str = f"向量: {r['vector_score']:.4f}"
        if r["rerank_score"] is not None:
            score_str += f"  →  Rerank: {r['rerank_score']:.4f}"

        print(f"[{i}] {lang}  {score_str}")
        print(f"    📁 {r['source']}   🏷  {r['category']}")
        print(f"    {r['text'][:160].strip()}...")
        print()


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="RAG 查询工具 v2（向量检索 + Rerank）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python query_v2.py "多智能体系统"
  python query_v2.py "What is Kubernetes" --top-k 3
  python query_v2.py "AI Agent" --no-rerank          # 仅向量检索，对比效果
        """,
    )
    parser.add_argument("query",      help="查询文本")
    parser.add_argument("--top-k",    type=int, default=5, help="返回结果数（默认 5）")
    parser.add_argument("--no-rerank",action="store_true",  help="禁用重排序（仅向量检索）")

    args = parser.parse_args()
    search(args.query, top_k=args.top_k, use_rerank=not args.no_rerank)


if __name__ == "__main__":
    main()
