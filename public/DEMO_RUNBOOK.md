# Demo Runbook (3-5 Minutes)

## Goal

Show end-to-end capability quickly:
clean -> ingest -> retrieval -> evaluation.

## Prerequisites

- `.env` configured (do not show key values on screen).
- Qdrant running.
- A small sample set under `documents/`.

## Demo Script

1. Explain architecture in 20-30 seconds.
2. Run ingest:

```bash
./rag.sh ingest --max-files 8
```

3. Run one query:

```bash
python3 query_v2.py "your test question" --top-k 3
```

4. Run batch evaluation:

```bash
./rag.sh eval --queries data/eval/queries_template.tsv
```

5. Show report:

```bash
cat data/reports/retrieval_eval.json
```

## What To Emphasize

- Deterministic pipeline entrypoints.
- Quality gate and retrieval evaluation.
- Practical engineering tradeoffs and limitations.

## What Not To Show

- Real API keys, private datasets, internal roadmap.
- Any proprietary model prompt or decision logic from your core product.
