# RAG System (Public Snapshot)

## 日本語

### 概要

このリポジトリは、ローカル実行の RAG パイプライン（クレンジング -> 埋め込み -> Qdrant 登録 -> 検索評価）を示す公開スナップショットです。

目的は以下です。

- 実装能力を対外的に証明する
- 再現可能な最小ワークフローを提供する
- コア製品の機密ロジックは公開しない

### 公開範囲と非公開範囲

公開される内容:

- パイプライン実装（`src/`）
- 実行スクリプト（`rag.sh`, `run_rag_pipeline.sh`, `query_v2.py`）
- 設定ローダーとサンプル設定（`config/`）
- 面接/公開用の証跡パック（`public/`）
- 公開前チェックツール（`tools/prepublish_guard.py`）

公開されないローカルデータ:

- `.env`
- `documents/`
- `data/`
- `logs/`
- `archives/`

上記は `.gitignore` により除外されています。

### 主要な公開構成（非網羅）

```text
rag-system/
├── README.md
├── AGENTS.md
├── rag.sh
├── run_rag_pipeline.sh
├── query_v2.py
├── requirements.txt
├── requirements_enhanced.txt
├── config/
│   ├── __init__.py
│   ├── config.yaml
│   ├── config_azure.yaml
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── azure_embedding.py
│   ├── document_cleaner_enhanced.py
│   ├── ingest_qdrant_v2.py
│   ├── prepare_clean_corpus.py
│   ├── eval_retrieval.py
│   ├── reset_rag_state.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── public/
│   ├── README_PUBLIC_PROOF.md
│   ├── ARCHITECTURE_BRIEF_TEMPLATE.md
│   ├── METRICS_EVIDENCE_TEMPLATE.md
│   ├── DEMO_RUNBOOK.md
│   ├── INTERVIEW_TALK_TRACK.md
│   ├── PUBLIC_PRIVATE_BOUNDARY.md
│   └── PUBLISH_CHECKLIST.md
├── skills/
│   ├── rag-system-baseline/
│   └── codex-delivery-playbook/
└── tools/
    └── prepublish_guard.py
```

### クイックスタート

1. 依存関係をインストール

```bash
pip install -r requirements.txt
```

2. 環境変数を設定（ローカルのみ）

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
```

3. Qdrant を起動

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v "$(pwd)/data/qdrant_storage:/qdrant/storage" \
  qdrant/qdrant
```

4. ローカル評価用 TSV を作成（`data/` は公開対象外）

```bash
mkdir -p data/eval
cat > data/eval/queries_template.tsv <<'TSV'
What is this repository?	rag-system
TSV
```

5. 実行

```bash
./rag.sh ingest --max-files 8
./rag.sh eval --queries data/eval/queries_template.tsv
```

### 公開前チェック

```bash
python3 tools/prepublish_guard.py
```

---

## English

### Overview

This repository is a public snapshot of a local RAG pipeline:
cleaning -> embedding -> Qdrant ingest -> retrieval evaluation.

Goals:

- Demonstrate engineering capability externally
- Provide a reproducible minimum workflow
- Keep proprietary core product logic private

### Public vs Local-Only

Included in public upload:

- Pipeline implementation (`src/`)
- Runtime scripts (`rag.sh`, `run_rag_pipeline.sh`, `query_v2.py`)
- Config loader and sample configs (`config/`)
- Interview/public proof pack (`public/`)
- Pre-publish guard (`tools/prepublish_guard.py`)

Local-only (not uploaded):

- `.env`
- `documents/`
- `data/`
- `logs/`
- `archives/`

These paths are excluded by `.gitignore`.

### Key Public Layout (Non-Exhaustive)

```text
rag-system/
├── README.md
├── AGENTS.md
├── rag.sh
├── run_rag_pipeline.sh
├── query_v2.py
├── requirements.txt
├── requirements_enhanced.txt
├── config/
│   ├── __init__.py
│   ├── config.yaml
│   ├── config_azure.yaml
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── azure_embedding.py
│   ├── document_cleaner_enhanced.py
│   ├── ingest_qdrant_v2.py
│   ├── prepare_clean_corpus.py
│   ├── eval_retrieval.py
│   ├── reset_rag_state.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── public/
│   ├── README_PUBLIC_PROOF.md
│   ├── ARCHITECTURE_BRIEF_TEMPLATE.md
│   ├── METRICS_EVIDENCE_TEMPLATE.md
│   ├── DEMO_RUNBOOK.md
│   ├── INTERVIEW_TALK_TRACK.md
│   ├── PUBLIC_PRIVATE_BOUNDARY.md
│   └── PUBLISH_CHECKLIST.md
├── skills/
│   ├── rag-system-baseline/
│   └── codex-delivery-playbook/
└── tools/
    └── prepublish_guard.py
```

### Quick Start

1. Install dependencies

```bash
pip install -r requirements.txt
```

2. Set environment variables (local only)

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
```

3. Start Qdrant

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v "$(pwd)/data/qdrant_storage:/qdrant/storage" \
  qdrant/qdrant
```

4. Create local evaluation TSV (`data/` is not part of public upload)

```bash
mkdir -p data/eval
cat > data/eval/queries_template.tsv <<'TSV'
What is this repository?	rag-system
TSV
```

5. Run pipeline and evaluation

```bash
./rag.sh ingest --max-files 8
./rag.sh eval --queries data/eval/queries_template.tsv
```

### Pre-Publish Check

```bash
python3 tools/prepublish_guard.py
```
