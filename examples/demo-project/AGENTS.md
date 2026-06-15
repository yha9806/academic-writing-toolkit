# Demo Academic Writing Project

Follow `CLAUDE.md` for the demo workflow. Use the repository-level Academic Writing Toolkit skills when available.

## Checks

Run these from the repository root when validating the demo:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```
