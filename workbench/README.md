# AWT long-document Workbench

An optional local component for thesis-scale document import, bounded model
reviews, recoverable jobs, revision reuse, page comparisons and submission
checks. This development package is `0.5.1.dev0`; it has not been released.
The parent repository also contains the dsh app and its nine skills.

## Install and open

From the repository root, preferably in a dedicated Python 3.9+ environment:

```sh
python -m pip install -e "./workbench[documents]"
awt-workbench --list-providers
awt-workbench
```

Open `http://127.0.0.1:8784/project` for the long-document workflow. The `awt`
command remains an alias for existing Workbench users. The dsh scaffold is
invoked separately with `node scaffold/awt.mjs` from the repository root.

For source-local checks, run these from `workbench/`:

```sh
python -B -m unittest discover -s tests/runtime -p "test_*.py"
python scripts/check-model-compatibility.py
python scripts/check-thesis-scale.py --pages 200 --run-fixture --layout --output final_output/thesis-scale-replication.json
```

The last command also needs `reportlab` for its fictional PDF. It uses a
deterministic mock review and real local page rendering; it never calls a
model API. Provider checks are generation-free unless `--live` is supplied.

## Use and evidence

- [超长文档使用说明](docs/thesis-scale-review.md): uploads, budgets, checkpoints,
  chapter coverage, same-file revision reuse and page comparison.
- [Document import and review](docs/setup-project-review.md): PDF/DOCX locators,
  limitations and explicitly selected image review.
- [Provider configuration](docs/setup-model-providers.md): configurable API
  transports and small-context presets, without automatic model escalation.
- [投稿前校验](docs/setup-submission-checks.md): local manuscript/outline/material
  checks, stale-report detection and recorded human decisions.
- [Original 200-page evidence](final_output/thesis-scale-verification-2026-09-05.md)
  and [submission-check evidence](final_output/submission-checks-verification-2026-09-05.md)
  are historical records from the contributing checkout; their original
  test counts and timings are not results of this integration.
- [Integration decision](../docs/specs/2026-09-05-long-document-integration.md)
  documents the package boundary and current verification.

The configured PDF ceiling is 1,000 pages; the completed scale experiment
uses 200 synthetic pages. Batching and file completion do not prove review
quality. Scans have no automatic OCR, and complex figures/layouts still
need page inspection. The Workbench's review suggestions are **Advisory**.
Its local schema, quote, hash and budget checks do not mount dsh's guard or
author-approval event system. The separate E1 dsh pilot and its negative
results remain at `e1/published/2026-09-05-local-qwen/` in the parent repo.
Neither this synthetic benchmark nor agent-operated checks satisfy E2.

`INTEGRATION.json` records the selected input files and their hashes before
packaging edits. The original contributor's working directory is preserved.
