# Baseline A Review: Normal Multi-Turn Chat Edit

## Workflow

The editor receives the requirements over five turns and revises as the conversation evolves. This represents ordinary chat-based writing assistance where later constraints may arrive after an early answer attempt.

## Metric Review

| Metric | Review |
| --- | --- |
| Spine preservation | Medium risk. The section can become clearer while losing the narrow function of motivating edit boundaries. |
| Claim drift | High risk. The request to make the prose stronger can broaden the claim into a general criticism of AI writing. |
| Evidence boundary | High risk. Source A and Source B may be treated as support for model unreliability rather than workflow-control need. |
| Scope discipline | Medium risk. Later requests can pull implementation architecture into a motivation section. |
| Author control recovery | Weak. The author must reread the conversation to reconstruct what was allowed and what changed. |

## Control Finding

This workflow is useful for fluency but weak for author control. It does not produce a durable contract or drift audit.
