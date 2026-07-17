# Project-Intent Drift Gate

This public-safe fixture demonstrates the failure mode in which a locally
coherent manuscript moves its approved primary domain into a secondary example.
The checker does not infer that semantic change. The global thesis audit records
the comparison, and strict validation enforces the author gate.

- `blocked/` records a specialist visual-heritage survey that has drifted into
  a general multimodal-evaluation survey. Its proposed edit contract cannot be
  approved while the audit remains unresolved.
- `aligned/` records the manuscript after its primary domain and research object
  are restored. The global audit passes and the edit contract is structurally
  executable.

Run:

```sh
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py \
  examples/project-intent-drift-gate/blocked --strict --json

python3 .claude/skills/thesis-control/scripts/check_thesis_control.py \
  examples/project-intent-drift-gate/aligned --strict --json
```

The blocked command should exit `1` with `global-thesis-gate-required`. The
aligned command should exit `0`. This fixture is synthetic and contains no
private manuscript text or source claims.
