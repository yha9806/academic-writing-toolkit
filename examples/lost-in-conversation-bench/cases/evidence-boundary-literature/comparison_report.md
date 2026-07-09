# Evidence Boundary Literature Comparison Report

## Summary

This report compares three outputs for a literature paragraph that needs a clearer link between source background and evidence-review motivation. The risk is that a forceful edit may turn background sources into proof or import checklist details from the next subsection.

## Three-Way Metric Comparison

| Metric | Baseline A | Baseline B | Treatment |
| --- | --- | --- | --- |
| Spine preservation | Partial. The motivation remains visible but becomes a stronger reliability claim. | Good. The paragraph still motivates a local evidence-review step. | Strong. The spine card keeps the paragraph inside its motivation role. |
| Claim drift | High. The output claims that citation-tracking tools can verify truth and that unreviewed revised text cannot be treated as reliable. | Low. The output preserves the narrower claim. | Low and audited. The drift audit records `changed_claims=none`. |
| Evidence boundary | Weak. Source C and Source D are overstated beyond their described support. | Good. Source roles are separated and bounded. | Strong. Source boundaries are encoded in the spine card and contract. |
| Scope discipline | Weak. Checklist items leak into the motivation paragraph. | Good. Checklist details remain in the next subsection. | Strong. Adjacent context is explicitly checked. |
| Author control recovery | Weak. The author must manually compare every sentence against source limits. | Partial. Consolidation helps but leaves no applied audit. | Strong. The author can inspect source roles, forbidden changes, and the audit decision. |

## Human Review Decision

| Workflow | Decision | Reason |
| --- | --- | --- |
| Baseline A | revise | The paragraph is forceful but overstates the sources and leaks next-subsection content. |
| Baseline B | partial_accept | The source boundary is preserved, but the author still has to manually verify the edit. |
| Treatment | accept_after_author_check | The source roles, forbidden changes, and scope boundary are inspectable before acceptance. |

## Control Finding

This case shows that literature paragraphs are especially vulnerable to lost-in-conversation drift because "make it stronger" can silently become "make the sources prove more." `/thesis-control` counters that by turning source roles and forbidden overclaims into reviewable artifacts.
