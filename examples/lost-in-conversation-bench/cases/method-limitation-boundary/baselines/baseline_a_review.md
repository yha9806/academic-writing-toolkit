# Baseline A Review

## Workflow

Baseline A simulates ordinary multi-turn chat editing. The author first asks for confidence, then adds caveats and adjacent-section constraints across later turns.

## Metric Review

| Metric | Review |
| --- | --- |
| Spine preservation | Weak. The subsection still discusses method limitations, but it starts to sell the corpus as a benchmark rather than explaining a bounded design choice. |
| Claim drift | High. The output changes a local analytic claim into claims about recurring patterns across academic contexts and broader risks in thesis practice. |
| Evidence boundary | Weak. Three anonymised drafting sessions are treated as enough to show wider AI-supported writing risks. |
| Scope discipline | Weak. The output begins to report and interpret findings that belong in the next chapter. |
| Author control recovery | Weak. The author must manually notice that later caveats were acknowledged in the conversation but diluted in the final prose. |

## Control Finding

Baseline A is fluent, but it weakens the limitation that the edit was supposed to preserve. The lost-in-conversation failure is visible because the final version keeps some caveat words while changing the claim strength.
