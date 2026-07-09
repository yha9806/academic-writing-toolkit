# Method Limitation Boundary Comparison Report

## Summary

This report compares three outputs for a methods limitation that the author wanted to make more confident without losing its caveat. The pressure is realistic: later turns add the non-representative sample boundary after the assistant has already been asked to strengthen the prose.

## Three-Way Metric Comparison

| Metric | Baseline A | Baseline B | Treatment |
| --- | --- | --- | --- |
| Spine preservation | Weak. The subsection becomes partly promotional and starts to frame the corpus as a benchmark. | Good. The subsection remains a methods limitation. | Strong. The spine card protects the limitation before editing. |
| Claim drift | High. A local analytic claim becomes a broader claim about recurring risks across academic contexts. | Low. The output keeps local analytic visibility separate from representative generalisation. | Low and audited. The drift audit records `changed_claims=none`. |
| Evidence boundary | Weak. Three sessions are made to carry wider claims than they can support. | Good. The output states that the corpus cannot support prevalence or causality claims. | Strong. Evidence limits are encoded in `core_claims` and `forbidden_changes`. |
| Scope discipline | Weak. Results-like language leaks into the methods subsection. | Good. Pattern examples remain in the next chapter. | Strong. Adjacent context is explicitly checked in the contract. |
| Author control recovery | Weak. The author must reread the conversation to locate the diluted caveat. | Partial. The prompt is easier to inspect but no durable audit exists. | Strong. The author has a spine card, applied contract, edited output, and audit row. |

## Human Review Decision

| Workflow | Decision | Reason |
| --- | --- | --- |
| Baseline A | revise | The prose is stronger, but the limitation is materially weakened. |
| Baseline B | partial_accept | The claim boundary is mostly preserved, but the author must still manually verify the result. |
| Treatment | accept_after_author_check | The protected caveat and adjacent-section boundary are inspectable before and after editing. |

## Control Finding

The case shows that making prose more confident is risky when the confidence request arrives before the limitation boundary is fully specified. `/thesis-control` helps because it turns that late caveat into an explicit contract rather than relying on the model to remember it.
