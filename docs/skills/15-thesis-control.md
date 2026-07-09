# /thesis-control

Use `/thesis-control` when AI-assisted editing may make a thesis draft smoother but less faithful to the author's intended argument.

## What It Does

- Builds spine cards for chapters, sections, or paragraph clusters.
- Requires an edit contract before substantive rewriting.
- Separates mechanical fixes from argument, structure, evidence, and claim changes.
- Runs a post-edit drift audit for changed claims, changed boundaries, new unsupported claims, and missed adjacent updates.
- Tracks repeated contracts under one revision issue and blocks a fourth applied revision until escalation is author-approved.
- Separates non-closing early diagnosis from cycle-closing schema-v3 gates.
- Requires human review for high-risk changes.
- Blocks strict validation while an applied edit remains `needs_review`.
- Provides an optional validator for durable `thesis_control/` packets.

## Control Files

Durable projects can keep:

- `thesis_control/spine_cards.csv`
- `thesis_control/edit_contracts.csv`
- `thesis_control/drift_audits.csv`
- `thesis_control/revision_escalations.csv`

Validate them with:

```bash
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py . --strict
```

Use `needs_review` only while the author decision is pending. Record accepted or
partially accepted audits as `passed`; record `revise` or `rollback` outcomes as
`failed`. Only applied contracts with resolved failed audits count towards
revision escalation; pending reviews and non-applied contracts do not count.

Upgrade a legacy packet before strict validation:

```bash
python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py .
```

The helper requires a complete packet. It preserves named extension columns,
but stops without mutation when revision metadata is partial or a legacy
escalation cannot be classified from the current contracts and resolved audits.

Create a draft packet from a real Markdown section with:

```bash
python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py . \
  --source chapters/ch1_introduction.md \
  --start-line 71 \
  --end-line 104 \
  --revision-issue-id ri-ch1-gap-clarity \
  --attempt-no 1 \
  --copy-source
```

The scaffold is intentionally conservative: it creates a draft spine card and
edit contract with `human_approved=false`. Replace `AUTHOR_REVIEW_REQUIRED`
fields with concrete author judgement before changing thesis prose. It rejects
attempt numbers that would make a revision issue duplicate or non-sequential,
validates the full candidate packet, and commits outputs through a
rollback-capable batch write. The default contract id includes the padded
attempt number.

Reuse the same `revision_issue_id` and increment `attempt_no` when a new
contract retries the same unresolved problem. After three applied contracts
receive resolved `revise` or `rollback` outcomes with `status=failed`, record
and approve one unique `cycle_gate` whose trigger list exactly matches those
three contracts in attempt order. Set `approved_after_attempt` to the final
attempt in the group. Do not repeat a trigger ID within a row or create multiple
rows for the same issue and trigger set. Record earlier escalation as
`early_diagnostic` with one or two triggers and an empty approval boundary; it
may guide the author, but it never closes or pre-authorises a future group.

Multiple failed audits of one contract count once. A contract with both passed
and failed resolved audits is structurally conflicting and must be resolved by
the author before the packet can pass.

## Typical Prompts

```text
Use /thesis-control before editing this section. Do not modify prose yet.
```

```text
Create an edit contract for this paragraph cluster and identify what must not change.
```

```text
Run a drift audit on the last edit and tell me whether the change should be accepted, revised, or rolled back.
```

## Key Guardrail

Do not accept fluent rewritten prose until changed claims, changed boundaries, unsupported additions, and missed adjacent updates have been checked.
