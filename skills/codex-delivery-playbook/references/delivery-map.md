# Delivery Map

## Purpose

Route implementation tasks into consistent planning, verification, and rollback decisions.

## Module Routing Checklist

1. Backend API changes
2. Frontend UI/state changes
3. Config/env changes
4. Script/runtime changes
5. Data/memory changes
6. Docs/contracts changes

## Verification Matrix

1. Syntax/static check command pattern
2. Runtime smoke check pattern
3. Failure-mode check pattern
4. Interface regression check pattern

## Risk Matrix

### High-risk signals

- Data schema mutation
- Auth boundary change
- Production config modification
- Backward-incompatible API contract change

Required actions:
1. Explicit blast radius
2. Explicit rollback path
3. Post-rollback verification checklist

### Medium-risk signals

- Non-breaking API behavior change
- Runtime dependency/config tuning
- Multi-module refactor without contract change

Required actions:
1. Regression checks
2. Failure-mode check
3. Residual risk statement

### Low-risk signals

- Internal refactor with no behavior change
- Docs-only engineering contract updates
- Logging clarity improvements without sensitive data impact

Required actions:
1. Static/syntax validation
2. Brief compatibility note

## Rollback Template

1. Rollback preconditions
2. Revert path
3. Data safety notes
4. Post-rollback verification checklist
