# Thesis-Control Revision Escalation Fixture

This public-safe fixture demonstrates the executable three-strike gate for one repeated thesis-editing problem.

Both packets contain four contract versions under `revision_issue_id=ri-traceability-clarity`:

1. attempt 1 broadens the scope and receives `revise`;
2. attempt 2 adds an unsupported quality claim and receives `rollback`;
3. attempt 3 misses an adjacent update and receives `revise`;
4. attempt 4 is marked `applied`.

The `blocked/` packet has no revision-escalation row. Strict validation rejects the fourth applied contract. The `approved/` packet contains a human-approved escalation that references the first three contracts, so strict validation accepts the fourth contract.

Run from the repository root:

```bash
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/thesis-control-revision-escalation/blocked --strict --json
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/thesis-control-revision-escalation/approved --strict --json
```

The first command should exit 1 with `missing-revision-escalation` and `revision-escalation-required`. The second should exit 0 with `issue_count=0`.
