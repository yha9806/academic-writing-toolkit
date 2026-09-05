# Prepare A Release-Governance Packet

> **Status**: the standing `/release-governance` skill was retired in the
> v0.1 catalogue triage; its evidence vocabulary lives on as
> [references/evidence-vocabulary.md](../../references/evidence-vocabulary.md),
> and the archived validator remains under `archive/skills/release-governance/`.

Use [`/release-governance`](../../archive/docs/skills/13-release-governance.md) when preparing release, rebuttal, artifact, or camera-ready materials that need explicit evidence-state control.

## Workflow

1. Define the release scope.
2. Record canonical references and local assets.
3. Anchor claims to artifacts.
4. Record evidence gates and human-final confirmations when required.
5. Run the release packet validator.

## Validate

```bash
python3 .claude/skills/release-governance/scripts/check_release_packet.py . --json
```

The validator checks required files, columns, evidence states, parseability, local path leakage, and unresolved working markers. It does not judge scientific validity or venue compliance.
