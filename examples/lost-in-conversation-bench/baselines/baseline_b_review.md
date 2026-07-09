# Baseline B Review: Consolidated Single-Turn Edit

## Workflow

The scattered requirements are consolidated before editing. This reduces the chance that the editor over-relies on an early assumption, but the output is still not bound to a durable author-control record.

## Metric Review

| Metric | Review |
| --- | --- |
| Spine preservation | Better than Baseline A because the spine is stated before editing. |
| Claim drift | Lower risk than Baseline A, but the author still needs to inspect the final prose manually. |
| Evidence boundary | Lower risk because the prompt names the source boundary explicitly. |
| Scope discipline | Lower risk because implementation details are explicitly forbidden. |
| Author control recovery | Partial. The consolidated prompt is reviewable, but there is no CSV contract, applied status, or post-edit audit. |

## Control Finding

Consolidation helps, but it remains a prompt technique. It does not create the reviewable artifacts needed for accepting, partially accepting, revising, or rolling back the edit.
