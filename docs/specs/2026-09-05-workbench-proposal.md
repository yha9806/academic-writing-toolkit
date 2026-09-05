# Workbench evaluation proposal — 2026-09-05

Status: proposal retained; product surface remains retired under the maintainer's
decision in [#39](https://github.com/yha9806/academic-writing-toolkit/issues/39).
This branch is independent of the E1/Windows/reference follow-up in
[PR #40](https://github.com/yha9806/academic-writing-toolkit/pull/40).
It does not change the supported-surface table in the root README or
override the parent specification's section 13 decommission.

## Why consider it now?

The candidate problem is reviewing a manuscript whose chapters, tables and
revisions are spread across multiple files and more text than one bounded
model request can contain. A user needs to see which source regions were
sent, which remain unchecked, where requests stopped, and what a revision
invalidates. The Workbench proposes a local visual interface to those tasks.
The dsh app remains the supported author-control workflow; code for another
interface alone is not evidence that the repository should maintain it.

## Who and which documents?

Candidate users are researchers and thesis authors who want to navigate
their own manuscript's cross-section checks, with an author making the final
decision on each finding. The first proposed public evaluation document is
Gao et al. (2023), *Enabling Large Language Models to Generate Text with
Citations* ([ALCE](https://aclanthology.org/2023.emnlp-main.398/)), using the
complete PDF rather than the E1 pilot's five-page source window. It is a
candidate usability case, not a representative long-thesis sample.

A first cycle should import the paper, set a bounded review request, run
the text/chapter/cross-section stages, inspect source-linked findings, and
record accepted, rejected and unsupported findings. A labelled local copy
with one controlled revision can then test invalidation and reuse. Model
execution, source coverage and the author's appraisal must be reported
separately. An agent may collect execution records but cannot fabricate
the author's judgement or call that E2 acceptance.

An [agent-operated technical attempt](../../workbench/final_output/alce-real-document-attempt-2026-09-05.json)
has now imported all 24 pages and called the local Qwen model. It stopped
at the declared 24-call budget after checking 1,056 of 5,822 extracted
regions; the initial text plan contained 486 requests. Chapter and
cross-section stages were not reached. This exposes a practical
fragmentation/budget problem on a real PDF despite the synthetic benchmark.
It is an incomplete attempt, with no retries, no human quality ratings and
no product-acceptance claim. A complete real-user cycle is still required.

A subsequent [planning optimisation](../../workbench/final_output/alce-planning-optimisation-2026-09-05.md)
fixes false headings and packs consecutive sections within the existing input
budget. On the identical source it reduces the 8,000-input-token text plan
from 486 to 44 requests, with all 6,670 original PDF region texts and coordinates
preserved. A new 12-call live attempt stopped on an invalid model quote after
11 completed text batches; ten completed responses were empty. Chapter and
cross-section stages were not reached. This is evidence of a planning
improvement, not a completed useful review or a reason to restore the surface.

## Decision gate

- Complete and report one real-paper use cycle, including failures and
  actual call/token usage where the provider exposes them.
- Have a real user evaluate usefulness, missed issues and misleading
  findings against the source; name that user only with their permission.
- Pass remote no-extras and document-extras tests on the declared platforms.
- Resolve maintenance scope and the product decision in #39 before adding
  a supported-product entry to the root README.

The 200-page synthetic benchmark tests batching, checkpoints, revision reuse
and rendering. It does not establish review quality. The configured
1,000-page ceiling is not a completed 1,000-page experiment. Workbench
suggestions are advisory; its local validators do not emit dsh author
approval events. DeepSeek has not been measured by this proposal; the
planned deepseek-v4-flash E1 run belongs to the maintainer's follow-up after
PR #40 is merged and must retain the local Qwen results alongside it.
