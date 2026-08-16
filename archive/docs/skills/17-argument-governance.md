# /argument-governance

Build and audit a manuscript's argument system:

```text
intent -> gap -> contribution -> claim hierarchy -> evidence -> boundary -> reviewer risk
```

Use this skill when a paper or thesis chapter needs explicit control over whether the contribution answers a real gap, whether claims are hierarchical rather than flat, and whether evidence is neither too thin nor citation-padded.

## Codex-Only Baseline

Codex can complete this workflow using local files, the CSV schemas, and the bundled checker. Gemini, gemini-agent, external reviewers, subagents, or other model calls are optional advisory inputs only.

## Enhanced Advisory Mode

With explicit user approval and an API key stored in an environment variable, Codex may request an external second opinion after the local argument packet exists. This is the high-assurance mode, not the baseline. External output remains advisory and must not become evidence.

## Creates Or Updates

Under `evidence/`:

- `intent_register.csv`
- `contribution_chain.csv`
- `claim_hierarchy.csv`
- `argument_system_map.csv`
- `reviewer_attack_matrix.csv`

## Main Checks

- Every contribution answers a named gap.
- Every main claim belongs to a contribution or the paper-level thesis.
- Every lower-level claim supports a parent claim.
- Every claim has the right type and amount of evidence.
- Background, method, workflow, or governance evidence is not promoted into empirical, causal, outcome, or deployment validation.
- High-risk reviewer attacks have adequate defenses or revision actions.

## Deterministic Helper

```bash
python3 .claude/skills/argument-governance/scripts/check_argument_governance.py . --json
```

The helper checks files, columns, enums, ID links, tree cycles, evidence links, and weak reviewer defenses. It does not judge scientific novelty.

## Typical Output

```text
## Argument Governance Report

### Paper Spine
### Alignment Issues
### Claim-Evidence Balance
### Reviewer Risks
### Next Actions
```

Use `/evidence-review` for detailed evidence status and citation-role planning. Use `/peer-review` or `/self-review` after the argument skeleton is explicit.
