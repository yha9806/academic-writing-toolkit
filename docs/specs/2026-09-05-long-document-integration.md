# Long-document integration — 2026-09-05

The user requested integration of the other task's thesis-scale Workbench
with the current dsh/E1 work. The inputs were based on different repository
generations: the Workbench changes used `80827f8`; the dsh experiment delivery
used `5a6c3698d5a9d56e735d3725bd5ec53be4203e07`.

## Integration decision

`workbench/` is an optional Python package containing the long-document
implementation and its provider, import, revision, layout and submission
dependencies. The nine-skill catalogue, dsh profiles, E1 producer and frozen
results remain at their existing paths. The prior working directory and
selected source snapshot are preserved. Input hashes are recorded in
[`workbench/INTEGRATION.json`](../../workbench/INTEGRATION.json).

This is an explicit user-requested exception to the original §13 Workbench
decommission. It does not restore the retired packaged Codex plugin or
ChatGPT App. Workbench reviews are Advisory; local validators do not grant
dsh authority or generate author-approval events. No automatic session-state
conversion or shared cache is introduced.

The package version is `0.5.1.dev0`, with `awt-workbench` as an explicit
entry point and `awt` retained as the historical alias. Installation starts
from `workbench/pyproject.toml`; the repository root keeps its dsh install
workflow. The obsolete test coupling the Python version to the retired
plugin and App manifests was removed. Wheel/CLI installation checks verify
the component's own version and assets.

## Verification and evidence boundaries

The imported reports under `workbench/final_output/` retain their original
bytes and describe the contributing task's earlier checks. Integration
replications are separately named and do not overwrite those reports.

The scale benchmark measures 200 synthetic PDF pages, conservative line
coalescing, deterministic mock reviews, incremental cache reuse and actual
page rendering. A configured 1,000-page input ceiling is not a completed
1,000-page performance or quality test. Model compatibility fixtures do
not establish account access or hosted review quality.

The existing E1 pilot remains a real local-model comparison with
negative/inconclusive results. Workbench mock calls cannot repair or
upgrade that E1 result. E2 still requires a real author-operated chapter
cycle; no such acceptance is implied by this integration.

The optional component has its own runtime/install CI workflow. Existing
dsh CI jobs are retained. Local verification and the final integration
report record what was actually run; adding a workflow is not a remote CI
pass or a publication.
