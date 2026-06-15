# Write A Literature Review

Use the local agent skills when your agent can read and write the project folder.

## Workflow

1. Use [`/read`](../skills/01-read.md) to inspect source PDFs or source text.
2. Use [`/note`](../skills/02-note.md) to create one notes file per source.
3. Use [`/map`](../skills/04-map.md) to see coverage against chapters.
4. Use [`/evidence-review`](../skills/12-evidence-review.md) to build evidence matrices, claim registers, citation plans, and overclaim checks.
5. Use [`/integrate`](../skills/05-integrate.md) to propose chapter edits from completed notes.

## Validate

Run the evidence-review package checker when a review packet exists:

```bash
python3 .claude/skills/evidence-review/scripts/check_review_package.py . --strict
```

The checker validates package structure and parseability. It does not replace human judgement about the literature.
