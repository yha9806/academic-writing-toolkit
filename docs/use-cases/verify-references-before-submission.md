# Verify References Before Submission

Use [`/verify-refs`](../skills/11-verify-refs.md) before submission, camera-ready packaging, or bibliography cleanup.

## Workflow

1. Export or collect BibTeX records into a `.bib` file.
2. Run offline structure checks first.
3. Add explicit online metadata checks only when network access and external API use are acceptable.

## Validate

```bash
python3 scripts/verify-refs.py --bib references.bib --json
python3 scripts/verify-refs.py --bib references.bib --json --online
```

For deterministic review or CI, use metadata fixtures:

```bash
python3 scripts/verify-refs.py --bib references.bib --json --online --metadata-dir path/to/metadata-fixtures
```

The public toolkit intentionally excludes project-specific self-citation rules and author-name assumptions.
