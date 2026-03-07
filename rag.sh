#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

INPUT_DIR="documents"
CONFIG_PATH="config/config_azure.yaml"
MAX_FILES=0
RESET=1
SKIP_CLEAN=0
START_QDRANT=1
QUERIES_FILE="data/eval/queries_template.tsv"
EVAL_OUTPUT="data/reports/retrieval_eval.json"
TOP_K=5
NO_RERANK=0

usage() {
  cat <<'EOF'
Usage:
  ./rag.sh <command> [options]

Commands:
  ingest    清洗 + 向量化 + 入库
  eval      批量召回评估
  run       一键执行 ingest + eval

Common options:
  --input DIR               输入文档目录（默认: documents）
  --config FILE             配置文件（默认: config/config_azure.yaml）
  --max-files N             最多处理 N 个文件（默认: 0=不限制）
  --no-reset                ingest 时不重置库和缓存（默认会重置）
  --skip-clean              ingest 时跳过清洗（不建议）
  --no-qdrant-start         不自动启动 Qdrant（你已手动启动时使用）

Eval options:
  --queries FILE            查询 TSV（默认: data/eval/queries_template.tsv）
  --eval-output FILE        评估输出 JSON（默认: data/reports/retrieval_eval.json）
  --top-k N                 每条查询返回数量（默认: 5）
  --no-rerank               评估时禁用 rerank

Examples:
  ./rag.sh ingest --max-files 12
  ./rag.sh eval --queries data/eval/queries_template.tsv
  ./rag.sh run --max-files 12 --queries data/eval/queries_template.tsv
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --input) INPUT_DIR="$2"; shift 2 ;;
      --config) CONFIG_PATH="$2"; shift 2 ;;
      --max-files) MAX_FILES="$2"; shift 2 ;;
      --no-reset) RESET=0; shift ;;
      --skip-clean) SKIP_CLEAN=1; shift ;;
      --no-qdrant-start) START_QDRANT=0; shift ;;
      --queries) QUERIES_FILE="$2"; shift 2 ;;
      --eval-output) EVAL_OUTPUT="$2"; shift 2 ;;
      --top-k) TOP_K="$2"; shift 2 ;;
      --no-rerank) NO_RERANK=1; shift ;;
      --help|-h) usage; exit 0 ;;
      *)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
  done
}

cmd_ingest() {
  local args=(--input "$INPUT_DIR" --config "$CONFIG_PATH" --max-files "$MAX_FILES")
  if [[ "$RESET" -eq 0 ]]; then
    args+=(--skip-reset)
  fi
  if [[ "$SKIP_CLEAN" -eq 1 ]]; then
    args+=(--skip-clean)
  fi
  if [[ "$START_QDRANT" -eq 0 ]]; then
    args+=(--no-qdrant-start)
  fi
  ./run_rag_pipeline.sh "${args[@]}"
}

cmd_eval() {
  mkdir -p "$(dirname "$EVAL_OUTPUT")"
  local args=(src/eval_retrieval.py --queries "$QUERIES_FILE" --output "$EVAL_OUTPUT" --top-k "$TOP_K")
  if [[ "$NO_RERANK" -eq 1 ]]; then
    args+=(--no-rerank)
  fi
  "$PYTHON_BIN" "${args[@]}"
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

COMMAND="$1"
shift
parse_args "$@"

case "$COMMAND" in
  ingest)
    cmd_ingest
    ;;
  eval)
    cmd_eval
    ;;
  run)
    cmd_ingest
    cmd_eval
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $COMMAND"
    usage
    exit 1
    ;;
esac
