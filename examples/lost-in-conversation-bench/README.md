# Lost-in-Conversation Writing Control Bench

This fixture demonstrates a local, public-safe evaluation for AI-assisted thesis editing drift.

The bench compares three workflows on the same desensitised thesis-style section:

1. Baseline A: normal multi-turn chat editing.
2. Baseline B: a consolidated single-turn prompt.
3. Treatment: `/thesis-control` with a spine card, edit contract, bounded edit, drift audit, and author decision.

The fixture is not a model benchmark and does not claim scientific validity. It is a product-control check: can the author inspect what changed, decide whether the edit stayed inside scope, and choose accept, partial accept, revise, or rollback without rereading a long chat history?

Run from the repository root:

```bash
python3 scripts/check_lost_in_conversation_bench.py examples/lost-in-conversation-bench --json
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/treatment --strict --json
```
