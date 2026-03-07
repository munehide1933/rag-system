#!/usr/bin/env python3
"""
批量召回评估脚本。

queries 文件格式（TSV）：
query_text<TAB>expected_source_substring

expected_source_substring 可选；为空时仅导出结果，不计命中率。
"""
import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from query_v2 import search


@dataclass
class QueryEval:
    query: str
    expected: Optional[str]
    hit: Optional[bool]
    top_sources: List[str]
    top_scores: List[float]


def load_queries(path: Path):
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            q, expected = line.split("\t", 1)
            queries.append((q.strip(), expected.strip() or None))
        else:
            queries.append((line, None))
    return queries


def main():
    parser = argparse.ArgumentParser(description="批量评估 RAG 召回结果")
    parser.add_argument("--queries", required=True, help="查询 TSV 文件路径")
    parser.add_argument("--output", required=True, help="评估结果 JSON 文件路径")
    parser.add_argument("--top-k", type=int, default=5, help="每条查询返回数量")
    parser.add_argument("--no-rerank", action="store_true", help="禁用 rerank")
    args = parser.parse_args()

    queries_path = Path(args.queries).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    items = load_queries(queries_path)
    if not items:
        raise ValueError(f"queries file is empty: {queries_path}")

    eval_rows: List[QueryEval] = []
    hit_count = 0
    expected_count = 0

    for query, expected in items:
        results = search(
            query=query,
            top_k=args.top_k,
            use_rerank=not args.no_rerank,
            verbose=False,
        )

        top_sources = [r.get("source_path") or r.get("source") or "" for r in results]
        top_scores = [float(r.get("rerank_score") if r.get("rerank_score") is not None else r.get("vector_score", 0.0)) for r in results]

        hit = None
        if expected:
            expected_count += 1
            expected_lower = expected.lower()
            hit = any(expected_lower in s.lower() for s in top_sources)
            if hit:
                hit_count += 1

        eval_rows.append(
            QueryEval(
                query=query,
                expected=expected,
                hit=hit,
                top_sources=top_sources,
                top_scores=top_scores,
            )
        )

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queries_file": str(queries_path),
        "top_k": args.top_k,
        "use_rerank": not args.no_rerank,
        "total_queries": len(eval_rows),
        "queries_with_expected": expected_count,
        "hit_count": hit_count,
        "hit_rate": (hit_count / expected_count) if expected_count else None,
    }

    payload = {
        "summary": summary,
        "rows": [asdict(r) for r in eval_rows],
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✅ 评估完成")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"📄 结果文件: {output_path}")


if __name__ == "__main__":
    main()
