#!/usr/bin/env bash
# 兼容入口：处理文档并在完成后归档（默认会询问）

set -euo pipefail

INPUT_DIR="documents"
ASK_ARCHIVE=1
DO_ARCHIVE=0
SKIP_RESET=1
MAX_FILES=0

usage() {
  cat <<'EOF'
Usage:
  ./process_and_archive.sh [options]

Options:
  --input DIR         输入目录（默认: documents）
  --archive           处理后直接归档（不询问）
  --no-archive        处理后不归档（不询问）
  --reset             处理前重置向量库和缓存
  --max-files N       最多处理文件数（0 表示不限制）
  --help              显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT_DIR="$2"; shift 2 ;;
    --archive) ASK_ARCHIVE=0; DO_ARCHIVE=1; shift ;;
    --no-archive) ASK_ARCHIVE=0; DO_ARCHIVE=0; shift ;;
    --reset) SKIP_RESET=0; shift ;;
    --max-files) MAX_FILES="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$INPUT_DIR" ]]; then
  echo "❌ 输入目录不存在: $INPUT_DIR"
  exit 1
fi

if ! find "$INPUT_DIR" -type f \( -name "*.pdf" -o -name "*.txt" -o -name "*.md" -o -name "*.html" -o -name "*.htm" \) -print -quit | grep -q .; then
  echo "❌ $INPUT_DIR 目录为空，没有文档需要处理"
  exit 0
fi

echo "📂 发现待处理文档（前10个）"
find "$INPUT_DIR" -type f \( -name "*.pdf" -o -name "*.txt" -o -name "*.md" -o -name "*.html" -o -name "*.htm" \) | head -10

PIPELINE_ARGS=(--input "$INPUT_DIR" --max-files "$MAX_FILES")
if [[ "$SKIP_RESET" -eq 1 ]]; then
  PIPELINE_ARGS+=(--skip-reset)
fi

echo ""
echo "🔄 开始处理（清洗 + 入库）..."
./run_rag_pipeline.sh "${PIPELINE_ARGS[@]}"

if [[ "$ASK_ARCHIVE" -eq 1 ]]; then
  echo ""
  read -r -p "✅ 处理完成！是否归档已处理文档? (y/n) " REPLY
  if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
    DO_ARCHIVE=1
  fi
fi

if [[ "$DO_ARCHIVE" -eq 1 ]]; then
  ARCHIVE_DIR="archives/processed_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$ARCHIVE_DIR"
  echo "📦 归档文档到: $ARCHIVE_DIR"

  while IFS= read -r -d '' src_file; do
    rel_path="${src_file#"$INPUT_DIR"/}"
    target_path="$ARCHIVE_DIR/$rel_path"
    mkdir -p "$(dirname "$target_path")"
    mv "$src_file" "$target_path"
  done < <(
    find "$INPUT_DIR" -type f \
      \( -name "*.pdf" -o -name "*.txt" -o -name "*.md" -o -name "*.html" -o -name "*.htm" \) \
      -print0
  )

  # 删除归档后空目录（保留顶层 input 目录）
  find "$INPUT_DIR" -mindepth 1 -type d -empty -delete || true

  echo "✅ 归档完成"
  echo "   归档位置: $ARCHIVE_DIR"
else
  echo "⚠️ 文档保留在 $INPUT_DIR"
fi

echo ""
echo "📊 当前向量库统计:"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" << 'PYEOF'
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
collection = client.get_collection("rag_documents")
print(f"   向量数量: {collection.points_count}")
PYEOF
