## Skills
### Available skills
- rag-system-baseline: Baseline execution protocol for this repository's code, scripts, config, and operational updates. (file: /Users/aranya/Projects/rag-system/skills/rag-system-baseline/SKILL.md)
- codex-delivery-playbook: End-to-end implementation delivery protocol (contract, breakdown, verification, risk, rollback). Use when the request requires structured execution planning with scope, verification, and rollback guarantees. (file: /Users/aranya/Projects/rag-system/skills/codex-delivery-playbook/SKILL.md)

### How to use skills
- Trigger rules: For any request that modifies files in this repository, use `rag-system-baseline` as the default baseline.
- Trigger rules: Use `codex-delivery-playbook` when the request requires structured delivery planning, verification strategy, and rollback guarantees.
- Coordination: For complex change requests, apply `rag-system-baseline` first, then layer `codex-delivery-playbook` for delivery contract rigor.
- Output policy: Match output complexity to problem complexity. Use a minimal contract for simple requests and a full engineering contract for complex requests.
