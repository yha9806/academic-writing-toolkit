# Audit Thesis Citations

Use citation auditing before major drafts, supervisor review, submission, or release.

## Workflow

1. Confirm the citation style in `CLAUDE.md`.
2. Use [`/audit`](../skills/06-audit.md) for citation pairing, style-format checks, terminology, numbers, and cross-references.
3. Use [`/style`](../skills/09-style.md) when British English consistency matters.
4. Use [`/logic-review`](../skills/10-logic-review.md) to inspect paragraph flow and repeated transitions.

## Validate

Run deterministic checks directly when needed:

```bash
python3 scripts/audit-citations.py --base-dir . --style harvard --json
python3 scripts/audit-british-english.py --base-dir . --json
python3 scripts/audit-logic.py --base-dir . --json
```

Safe fixers are intentionally narrow. Review suggested edits before applying them to thesis prose.
