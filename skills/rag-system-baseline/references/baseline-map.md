# Baseline Map

## Critical Paths

- Entry shell: `rag.sh`
- Pipeline shell: `run_rag_pipeline.sh`
- Query path: `query_v2.py`
- Ingest path: `src/ingest_qdrant_v2.py`
- Cleaning path: `src/prepare_clean_corpus.py`, `src/document_cleaner_enhanced.py`
- Embedding client: `src/azure_embedding.py`
- Evaluation: `src/eval_retrieval.py`
- Reset path: `src/reset_rag_state.py`
- Settings and config loader: `config/settings.py`, `config/config_azure.yaml`

## Baseline Checks

1. Command compatibility for `rag.sh` and `run_rag_pipeline.sh`
2. Config key compatibility for default YAML path and required env vars
3. Qdrant behavior compatibility for collection/vector settings
4. Query output compatibility for existing evaluation scripts

## Risk Focus

- Data-loss risk during reset or collection recreation
- Azure credential exposure in logs or exceptions
- Performance regressions from extra embedding/query requests
- Compatibility breaks in script flags or config keys
