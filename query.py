#!/usr/bin/env python3
"""
兼容入口：默认复用 query_v2（向量召回 + 可选 rerank）。
用法: python query.py "你的查询"
"""
import argparse
from query_v2 import search


def main():
    parser = argparse.ArgumentParser(description="RAG 查询兼容入口（内部调用 query_v2）")
    parser.add_argument("query", help="查询文本")
    parser.add_argument("--top-k", type=int, default=5, help="返回结果数")
    parser.add_argument("--no-rerank", action="store_true", help="禁用重排序")
    args = parser.parse_args()

    search(args.query, top_k=args.top_k, use_rerank=not args.no_rerank, verbose=True)


if __name__ == "__main__":
    main()
