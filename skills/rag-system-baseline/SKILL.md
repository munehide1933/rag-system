---
name: rag-system-baseline
description: Baseline execution protocol for this rag-system repository (cleaning, embedding, ingest, retrieval evaluation, config, scripts). Use when modifying source code, pipeline scripts, query behavior, config files, or operational docs in this repository.
---

# RAG System Baseline

Use this skill to keep repository changes consistent, low-risk, and easy to verify.

## Apply Project Guardrails

- Keep `rag.sh` as the canonical user entrypoint for ingest/eval/run workflows.
- Keep `run_rag_pipeline.sh` behavior stable for reset, clean, ingest, and eval flow.
- Keep default config path compatibility with `config/config_azure.yaml`.
- Preserve Qdrant collection and vector-size compatibility unless explicitly requested.
- Avoid introducing blocking or redundant remote calls in embedding and query hot paths.
- Preserve existing environment variable contracts for Azure OpenAI credentials.
- Do not log secrets, API keys, or full credential-bearing URLs.

## Execute Workflow

1. Identify affected modules first.
2. Read only the minimal relevant files.
3. Apply focused edits without unrelated refactors.
4. Run targeted validation commands.
5. Report changed files, validations, and residual risks.

## Baseline Validation

Run the smallest effective set for the changed surface.

```bash
python3 -m py_compile src/*.py config/settings.py query_v2.py
bash -n rag.sh
bash -n run_rag_pipeline.sh
```

For runtime-impacting changes, run one focused smoke check with current project commands.

## Change Boundaries

- Prefer additive updates over broad rewrites.
- Preserve compatibility for existing CLI flags and config keys unless explicitly changed.
- Keep query output format stable unless a format change is requested.
- Keep ingest replacement behavior stable when `replace_existing_source` is enabled.

## Use References

Read `references/baseline-map.md` for critical paths and module-specific checkpoints.
