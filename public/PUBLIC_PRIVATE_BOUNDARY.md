# Public vs Private Boundary

Use this table before sharing anything externally.

## Safe To Share

- Architecture diagrams and module boundaries.
- High-level design decisions and tradeoffs.
- Redacted metrics (latency, hit-rate, cost trends).
- Demo commands and non-sensitive outputs.
- General engineering lessons learned.

## Keep Private

- API keys, tokens, private endpoints, and credentials.
- Proprietary datasets and raw customer documents.
- Core model prompts, ranking logic variants, or internal heuristics from your main product.
- Internal roadmap, customer names, and commercial terms.
- Any file containing sensitive environment values.

## Redaction Rules

- Replace real identifiers with placeholders.
- Strip dataset names and file paths that reveal client context.
- Remove exact infrastructure account IDs and tenant IDs.
- Use percentage deltas where absolute numbers are sensitive.
