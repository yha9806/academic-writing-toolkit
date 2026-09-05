# Long-document integration verification — 2026-09-05

The optional `workbench/` package is integrated with the dsh/E1 branch as
development version `0.5.1.dev0`. The input snapshot contains 57 selected
files from the other task, including the long-document implementation and
its provider, revision, layout and submission-check dependencies. The
original working directory was preserved.

## Checks run for this integration

| Check | Observed result |
| --- | --- |
| Workbench runtime with PDF dependencies, Python 3.12 | 70 tests: 69 passed, one Windows POSIX-permission skip |
| Fresh base-wheel install, without optional PDF dependencies | 70 tests: 61 passed, nine platform/optional-dependency skips |
| dsh guard tests | 111 passed, zero skipped |
| Published dsh launcher | Six typed-outcome scenarios passed |
| Wheel contents | 17 runtime files, byte-matched to the integrated source |
| Installed HTTP app | Assets, import, local submission checks/export and stale-report detection passed; non-local Host/Origin returned 403 |
| Provider fixture plan | Generation-free dry run; no hosted-model compatibility claim |
| Syntax and content | Python 3.9 syntax parsed; two JavaScript files checked; public-content audits for parent and component passed |
| Frozen E1 evidence | All six recorded file hashes preserved |

The former test requiring Python, retired plugin and retired App versions
to match was removed. No retained runtime assertion was weakened. The
new optional CI workflow was added but has not run remotely.

## 200-page replication

See the [machine-generated result](thesis-scale-integration-2026-09-05.json).
The synthetic single-column PDF has 742,046 extracted characters. Its
8,600 original line rectangles are retained in 1,000 coalesced regions.
The economy plan changed from 207 to 100 text batches. Initial review used
151 mock calls including later chapter/cross-section stages. A one-passage
revision reused 99 text batches / 991 regions and used 21 additional mock
calls. Actual local rendering processed 200 before/after pairs and found
only page 199 changed, with zero model calls for rendering.

The first concurrent run stopped with a generic checkpoint/material error,
and a recovery test stopped at page 142. Subsequent diagnostic checks passed,
including another concurrent runtime-suite and 200-page execution. The
initial underlying exception was not captured, so its cause is unresolved;
this integration does not claim to have fixed that intermittent failure.
Initial and diagnostic logs are retained in the local integration handoff.

## Installation and boundaries

[Installed-app receipt](integration-install-2026-09-05.json) records the
HTTP checks and clean in-process server shutdown. The final wheel SHA-256 is
`43eae49a1e71f95e999f6ac86fed91b1e1a84e395831644490654419271a90e8`.
Only line endings changed between the first installed-suite run and this
final wheel; runtime content and assertions are otherwise identical.

The original UI source assets were carried over without layout changes.
The earlier screenshots remain historical evidence; this integration
verified installed assets and HTTP behaviour rather than claiming a new
visual acceptance. Independent Gemini advisory was unavailable (`fetch failed`).

The 1,000-page setting is an input ceiling, not a completed 1,000-page test.
Mock review results and local submission rules do not establish academic
review quality. The real-model E1 pilot remains negative/inconclusive, and
E2 author-operated acceptance is still unexecuted. No remote publication,
PR, release or issue comment was made during this integration.
