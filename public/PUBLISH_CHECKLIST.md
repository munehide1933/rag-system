# Publish Checklist (Public Evidence Only)

## 1) Scope Decision

- [ ] Confirm this repo/material is for capability proof only.
- [ ] Confirm core proprietary product code is excluded.

## 2) Safety Checks

- [ ] Run `python3 tools/prepublish_guard.py`.
- [ ] Verify no tracked `.env` or credential file.
- [ ] Verify no private dataset or document corpus included.
- [ ] Verify logs and reports do not contain sensitive text.

## 3) Content Review

- [ ] Architecture brief is high-level and redacted.
- [ ] Metrics report uses safe numbers and no customer identifiers.
- [ ] Demo runbook does not expose secrets.
- [ ] Interview talk track does not disclose proprietary logic.

## 4) Legal/License Decision

- [ ] Decide: private / source-available / open-source.
- [ ] Add explicit `LICENSE` if public distribution is intended.
- [ ] Ensure README states public/private boundary clearly.

## 5) Final Gate

- [ ] A second person (or delayed self-review) validates publish set.
- [ ] Tag publish version and archive a copy of reviewed files.
