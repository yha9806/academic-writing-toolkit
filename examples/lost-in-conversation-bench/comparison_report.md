# Lost-in-Conversation Bench Comparison Report

## Summary

This report compares three outputs from the same desensitised thesis-style section and the same revision pressure. Baseline A represents ordinary multi-turn chat editing. Baseline B represents a consolidated single-turn prompt. Treatment represents `/thesis-control`, where the edit is bound to a spine card, edit contract, and drift audit before acceptance.

The comparison is not a model benchmark. It is an author-control review: can the author inspect what changed, decide whether the edit stayed inside scope, and choose accept, partial accept, revise, or rollback without reconstructing the whole conversation?

## Three-Way Metric Comparison

| Metric | Baseline A | Baseline B | Treatment |
| --- | --- | --- | --- |
| Spine preservation | Weak. The output shifts from motivating edit boundaries to warning that conversational revision is not enough to prevent drift. | Good. The output keeps the section focused on evidence boundaries and visible edit controls. | Strong. The output is explicitly checked against a spine card before acceptance. |
| Claim drift | High. The output broadens into claims that AI writing tools can become unsafe and that revised paragraphs should be treated as unreliable unless the workflow can prove preservation. | Low. The output keeps the narrower claim that workflows need explicit controls. | Low and audited. The drift audit records `changed_claims=none`. |
| Evidence boundary | Weak. Source A and Source B are treated as support for model unreliability entering thesis prose, which is stronger than the stated source boundary. | Good. The source boundary remains visible and rejects universal model-safety claims. | Strong. The source boundary is encoded in `core_claims`, `forbidden_changes`, and the final audit. |
| Scope discipline | Weak. The output invites the next subsection to describe implementation, but also starts to imply a control workflow solution inside the motivation section. | Good. Product architecture remains outside this section. | Strong. The edit contract forbids product architecture and points adjacent implementation details to the next subsection. |
| Author control recovery | Weak. The author must infer what drift occurred by rereading the edited prose and the conversation. | Partial. The consolidated prompt helps review, but there is no durable applied contract or audit. | Strong. The author can inspect the spine card, applied contract, edited section, and drift audit. |

## Human Review Decision

| Workflow | Decision | Reason |
| --- | --- | --- |
| Baseline A | revise | The prose is fluent, but it broadens the claim and weakens the evidence boundary. |
| Baseline B | partial_accept | The prose preserves the core argument, but the author still needs to manually verify the output against the original requirements. |
| Treatment | accept_after_author_check | The control packet makes the edit scope, forbidden changes, and drift decision inspectable. The audit reports no high-risk drift, but the final acceptance remains an author decision. |

## Control Finding

Baseline A demonstrates the lost-in-conversation risk: later constraints are present, but the edited output still broadens the argument. Baseline B shows that consolidation helps, but it remains a prompt technique. Treatment shows the product claim: `/thesis-control` does not merely produce smoother prose; it produces inspectable control artifacts that let the author decide whether the edit should be accepted, revised, or rolled back.
