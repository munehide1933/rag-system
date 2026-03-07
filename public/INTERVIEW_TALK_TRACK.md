# Interview Talk Track

## 60-Second Version

I built a local RAG pipeline focused on data quality and measurable retrieval.
The flow is: document cleaning, chunking, embedding, Qdrant ingest, retrieval with optional rerank, and batch hit-rate evaluation.
My contribution was end-to-end engineering: pipeline orchestration, quality gate, caching/dedup, and evaluation tooling.
I intentionally keep core proprietary product code private, but I can show architecture and verifiable outputs.

## 3-Minute Version

1. Problem
- Needed a controllable RAG workflow with measurable retrieval quality, not just a demo chat UI.

2. Approach
- Built a CLI-first pipeline with stable entrypoints.
- Added cleaning/chunking strategies with fallback behavior.
- Added caching and dedup to reduce cost and noise.
- Added batch evaluation so quality is measured, not guessed.

3. Results
- System can process mixed document formats and produce repeatable retrieval reports.
- It supports iterative tuning with explicit quality and performance checkpoints.

4. Engineering quality
- Structured config, reset flow, reproducible scripts, and risk-aware handling of secrets.

5. Boundary
- Public evidence is architecture plus metrics; core proprietary product logic stays private.

## 10-Minute Version

1. Context and constraints
- Data heterogeneity, cost sensitivity, and reliability requirements.

2. Architecture walkthrough
- Cleaning/chunking choices and why fallback matters.
- Embedding and vector index design.
- Retrieval + rerank flow and cost/latency tradeoff.
- Quality gate and evaluation loop.

3. Key tradeoffs
- Why this design favors controllability and observability over feature breadth.
- What was intentionally deferred for faster delivery.

4. Risks and mitigations
- API rate limit, noisy documents, stale vectors, and reset safety.

5. What I would ship next
- Service layer, test automation, and production observability.
