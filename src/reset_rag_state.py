#!/usr/bin/env python3
"""
重置 RAG 状态：
1. 删除并重建 Qdrant 集合
2. 清空 embedding/query 缓存目录
"""
import argparse
import shutil
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def reset_collection(settings):
    client = QdrantClient(host=settings.qdrant.host, port=settings.qdrant.port)
    name = settings.qdrant.collection_name

    collections = client.get_collections().collections
    if any(c.name == name for c in collections):
        client.delete_collection(collection_name=name)
        print(f"🗑️  已删除集合: {name}")

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=settings.qdrant.vector_size,
            distance=Distance.COSINE,
        ),
    )
    print(f"✅ 已重建集合: {name} (dim={settings.qdrant.vector_size})")


def clear_cache_dir(path_str: str):
    path = resolve_path(path_str)
    if not path.exists():
        return
    if path.is_file():
        path.unlink()
        print(f"🧹 已删除文件: {path}")
        return
    if path.is_dir():
        for item in path.iterdir():
            if item.is_file():
                item.unlink()
            else:
                shutil.rmtree(item)
        print(f"🧹 已清空目录: {path}")


def main():
    parser = argparse.ArgumentParser(description="重置 RAG 状态")
    parser.add_argument(
        "--config",
        default="config/config_azure.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="仅清理缓存，不操作 Qdrant",
    )
    args = parser.parse_args()

    settings = get_settings(args.config)
    if not args.skip_qdrant:
        reset_collection(settings)

    clear_cache_dir(settings.processing.cache_dir)
    clear_cache_dir("data/query_cache")
    print("✅ 重置完成")


if __name__ == "__main__":
    main()
