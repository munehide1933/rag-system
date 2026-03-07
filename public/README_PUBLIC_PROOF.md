# Public Proof Pack

This folder is a public-facing evidence pack for interviews and capability proof.
It is designed to show engineering quality without exposing core implementation.

## Files

- `ARCHITECTURE_BRIEF_TEMPLATE.md`: one-page architecture narrative template.
- `METRICS_EVIDENCE_TEMPLATE.md`: metrics and before/after evidence template.
- `DEMO_RUNBOOK.md`: short demo flow and expected output checkpoints.
- `INTERVIEW_TALK_TRACK.md`: 60-second / 3-minute / 10-minute talk tracks.
- `PUBLIC_PRIVATE_BOUNDARY.md`: what can be shared vs must remain private.
- `PUBLISH_CHECKLIST.md`: pre-publication safety checklist.

## Usage

1. Fill templates with redacted, verifiable information.
2. Record one short demo (3 to 5 minutes).
3. Run `python3 tools/prepublish_guard.py` before publishing.
4. Publish only this evidence pack and selected docs, not sensitive data/code.
