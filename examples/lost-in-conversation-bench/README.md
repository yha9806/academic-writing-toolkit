# Lost-in-Conversation Writing Control Bench

This fixture demonstrates a local, public-safe evaluation for AI-assisted thesis editing drift.

The bench compares three workflows across multiple desensitised thesis-style sections:

1. Baseline A: normal multi-turn chat editing.
2. Baseline B: a consolidated single-turn prompt.
3. Treatment: `/thesis-control` with a spine card, edit contract, bounded edit, drift audit, and author decision.

The fixture is not a model benchmark and does not claim scientific validity. It is a product-control check: can the author inspect what changed, decide whether the edit stayed inside scope, and choose accept, partial accept, revise, or rollback without rereading a long chat history?

Review the root case files in this order:

1. [`chapters/desensitized_section.md`](chapters/desensitized_section.md) records the original section.
2. [`requirements/multi_turn_requirements.md`](requirements/multi_turn_requirements.md) records the sharded multi-turn requirements.
3. [`baselines/baseline_a_edited_section.md`](baselines/baseline_a_edited_section.md) shows a normal multi-turn edit with claim and evidence-boundary drift.
4. [`baselines/baseline_b_edited_section.md`](baselines/baseline_b_edited_section.md) shows the consolidated-prompt output.
5. [`treatment/edited_section.md`](treatment/edited_section.md) shows the `/thesis-control` bounded edit.
6. [`comparison_report.md`](comparison_report.md) compares all three workflows across the control metrics.
7. [`treatment/thesis_control/`](treatment/thesis_control/) stores the spine card, edit contract, drift audit, and revision-escalation schema.

Then review [`cases/index.md`](cases/index.md) and the two additional cases:

- [`cases/method-limitation-boundary`](cases/method-limitation-boundary)
- [`cases/evidence-boundary-literature`](cases/evidence-boundary-literature)

Run from the repository root:

```bash
python3 scripts/check_lost_in_conversation_bench.py examples/lost-in-conversation-bench --json
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/treatment --strict --json
```
