---
name: codex-delivery-playbook
description: End-to-end implementation delivery protocol for turning requirements into shippable changes with explicit scope, decision log, test gates, risk controls, and rollback steps. Use when Codex must produce structured execution planning with scope, verification, and rollback guarantees across backend, frontend, scripts, config, or docs. Do not activate for trivial edits, pure text operations, translations, or cosmetic-only changes.
---

# Codex Delivery Playbook

Use this skill to produce predictable, reviewable, and low-risk engineering delivery outcomes.

## Activation Boundaries

Activate when the request requires structured execution planning with explicit scope, verification, and rollback guarantees.

Do not activate for:
- Pure text tasks
- Translation
- Single-line or trivial fixes
- Cosmetic-only refactors

## Execute Workflow

1. Define the delivery contract first.
2. Lock goal, non-goals, and acceptance criteria.
3. Map affected files, interfaces, and dependencies.
4. Choose MVP-first approach before optional optimization.
5. Implement in small, auditable slices.
6. Verify with targeted checks and failure-case tests.
7. Report exact change set, risks, and rollback path.

## Define Delivery Contract

Always state:

- Goal
- Non-goals
- Constraints
- Success criteria
- In-scope files
- Out-of-scope files

Never begin implementation planning without explicitly stating the delivery contract.
If the delivery contract is unclear, explicitly state assumptions before proceeding.

## Plan Implementation

Use this order:

1. Interface and schema impact
2. Data flow and control flow
3. Edge cases and failure modes
4. Backward compatibility
5. Observability and logs
6. Rollback strategy

Prefer additive changes over rewrites unless rewrite is explicitly requested.

## Apply Quality Gates

Require the smallest effective validation set:

1. At least one concrete executable validation step
2. Syntax/static check for changed files
3. Happy-path runtime check (real or synthetic)
4. At least one failure-mode or boundary check
5. Interface regression check if public contract is touched

If any validation is skipped, explicitly justify and state residual risk.

## Enforce Output Contract

Every substantial response must include:

- Recommendation and rationale
- Step-by-step implementation plan
- Test plan
- Risks
- Rollback
- Next executable TODOs

Keep output complexity proportional to task complexity.

## Handle Risk and Rollback

Before defining rollback, explicitly list all affected files and contract surfaces.

For any risky change, explicitly include:

1. Risk trigger conditions
2. Blast radius
3. Detection signal
4. Immediate mitigation
5. Rollback command/path
6. Post-rollback verification

## Scope Discipline

Do not expand scope beyond the stated delivery contract.

## Keep Collaboration Efficient

1. Ask only high-impact clarification questions.
2. Prefer explicit assumptions over open ambiguity.
3. Mark assumptions so reviewers can confirm or override.
4. Avoid unrelated refactors in delivery-oriented tasks.

## Use References

Read `references/delivery-map.md` when a task touches multiple modules, release safety, or verification routing.
