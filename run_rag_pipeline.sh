#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_DIR="documents"
CLEAN_DIR="data/clean_documents"
REPORT_PATH="data/reports/clean_report.json"
EVAL_OUTPUT="data/reports/retrieval_eval.json"
CONFIG_PATH="config/config_azure.yaml"
MIN_CHARS=200
MAX_CHARS_PER_FILE=300000
MAX_FILES=0
RUN_RESET=1
RUN_CLEAN=1
RUN_INGEST=1
RUN_EVAL=0
USE_RERANK=1
START_QDRANT=1
PYTHON_BIN=".venv/bin/python"
EVAL_QUERIES=""

usage() {
  cat <<'EOF'
Usage:
  ./run_rag_pipeline.sh [options]

Options:
  --input DIR                 Raw source directory (default: documents)
  --clean-output DIR          Cleaned corpus directory (default: data/clean_documents)
  --clean-report FILE         Cleaning report path (default: data/reports/clean_report.json)
  --config FILE               Config file for ingest/reset (default: config/config_azure.yaml)
  --min-chars N               Min chars per cleaned file (default: 200)
  --max-chars-per-file N      Max chars per cleaned file (default: 300000)
  --max-files N               Max files to process (default: 0, unlimited)
  --skip-reset                Do not reset qdrant/cache before pipeline
  --skip-clean                Skip clean step, ingest directly from --input
  --skip-ingest               Skip ingest step
  --no-qdrant-start           Do not auto start/create qdrant container
  --eval-queries FILE         TSV queries file; enable retrieval evaluation
  --eval-output FILE          Eval result JSON (default: data/reports/retrieval_eval.json)
  --no-rerank                 Disable rerank during evaluation
  --python BIN                Python executable path (default: .venv/bin/python)
  --help                      Show this help

Examples:
  ./run_rag_pipeline.sh --max-files 12
  ./run_rag_pipeline.sh --skip-reset --max-files 8
  ./run_rag_pipeline.sh --eval-queries data/eval/queries_template.tsv
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT_DIR="$2"; shift 2 ;;
    --clean-output) CLEAN_DIR="$2"; shift 2 ;;
    --clean-report) REPORT_PATH="$2"; shift 2 ;;
    --config) CONFIG_PATH="$2"; shift 2 ;;
    --min-chars) MIN_CHARS="$2"; shift 2 ;;
    --max-chars-per-file) MAX_CHARS_PER_FILE="$2"; shift 2 ;;
    --max-files) MAX_FILES="$2"; shift 2 ;;
    --skip-reset) RUN_RESET=0; shift ;;
    --skip-clean) RUN_CLEAN=0; shift ;;
    --skip-ingest) RUN_INGEST=0; shift ;;
    --no-qdrant-start) START_QDRANT=0; shift ;;
    --eval-queries) EVAL_QUERIES="$2"; RUN_EVAL=1; shift 2 ;;
    --eval-output) EVAL_OUTPUT="$2"; shift 2 ;;
    --no-rerank) USE_RERANK=0; shift ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python is not available."
    exit 1
  fi
fi

mkdir -p "$(dirname "$REPORT_PATH")" "$(dirname "$EVAL_OUTPUT")"

start_qdrant_if_needed() {
  if [[ "$START_QDRANT" -eq 0 ]]; then
    return
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "docker not found, skip qdrant auto start."
    return
  fi

  if docker ps --format '{{.Names}}' | grep -qx "qdrant"; then
    return
  fi
  if docker ps --format '{{.Names}}' | grep -qx "rag-qdrant"; then
    return
  fi

  if docker ps -a --format '{{.Names}}' | grep -qx "qdrant"; then
    echo "[pipeline] starting existing container: qdrant"
    docker start qdrant >/dev/null
  elif docker ps -a --format '{{.Names}}' | grep -qx "rag-qdrant"; then
    echo "[pipeline] starting existing container: rag-qdrant"
    docker start rag-qdrant >/dev/null
  else
    echo "[pipeline] creating container: qdrant"
    mkdir -p data/qdrant_storage
    docker run -d \
      --name qdrant \
      -p 6333:6333 \
      -v "$SCRIPT_DIR/data/qdrant_storage:/qdrant/storage" \
      qdrant/qdrant >/dev/null
  fi
}

print_collection_stats() {
  "$PYTHON_BIN" - <<'PY'
import json

try:
    from qdrant_client import QdrantClient
    client = QdrantClient(host="localhost", port=6333)
    name = "rag_documents"
    col = client.get_collection(name)
    print("[pipeline] collection stats:")
    print(json.dumps({
        "collection": name,
        "points_count": col.points_count,
        "vectors_count": getattr(col, "vectors_count", None),
        "status": str(getattr(col, "status", "unknown")),
    }, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"[pipeline] failed to read collection stats: {e}")
PY
}

echo "[pipeline] starting"
echo "[pipeline] python: $PYTHON_BIN"

start_qdrant_if_needed

if [[ "$RUN_RESET" -eq 1 ]]; then
  echo "[pipeline] reset qdrant and cache"
  "$PYTHON_BIN" src/reset_rag_state.py --config "$CONFIG_PATH"
fi

INGEST_DIR="$INPUT_DIR"
if [[ "$RUN_CLEAN" -eq 1 ]]; then
  echo "[pipeline] clean corpus"
  "$PYTHON_BIN" src/prepare_clean_corpus.py \
    --input "$INPUT_DIR" \
    --output "$CLEAN_DIR" \
    --report "$REPORT_PATH" \
    --min-chars "$MIN_CHARS" \
    --max-chars-per-file "$MAX_CHARS_PER_FILE" \
    --max-files "$MAX_FILES"
  INGEST_DIR="$CLEAN_DIR"
else
  echo "[pipeline] skip clean, ingest from $INGEST_DIR"
fi

if [[ "$RUN_INGEST" -eq 1 ]]; then
  echo "[pipeline] ingest to qdrant"
  "$PYTHON_BIN" src/ingest_qdrant_v2.py "$INGEST_DIR" --config "$CONFIG_PATH"
fi

if [[ "$RUN_EVAL" -eq 1 ]]; then
  echo "[pipeline] run retrieval evaluation"
  EVAL_ARGS=(src/eval_retrieval.py --queries "$EVAL_QUERIES" --output "$EVAL_OUTPUT")
  if [[ "$USE_RERANK" -eq 0 ]]; then
    EVAL_ARGS+=(--no-rerank)
  fi
  "$PYTHON_BIN" "${EVAL_ARGS[@]}"
fi

if [[ "$RUN_INGEST" -eq 1 ]]; then
  print_collection_stats
else
  echo "[pipeline] skip collection stats (ingest not run)"
fi
echo "[pipeline] done"
