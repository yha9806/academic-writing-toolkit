# Argument Level Lock

Use this reference when a project has a real broad gap but the paper's
headline, contribution list, or generalisation may be stronger than its
evidence. This is a semantic decision aid for the academic-writing assistant,
not a second argument schema or deterministic checker.

Reuse the canonical IDs, relations, evidence status, boundaries, and focus
actions owned by `$argument-governance`. Record unknowns as `unknown`; never
fill them from the importance of the topic or from a plausible story.

## Keep Four Argument Levels Separate

| Level | Question | Permitted content | Common collapse |
|---|---|---|---|
| Domain or field-level gap | What is missing in the wider field? | A bounded problem established from prior work or project context | A true broad gap is treated as something this paper has already closed. |
| Paper-level contribution | What exactly does this paper add? | A method, dataset, analysis, framework, finding, or other deliverable actually produced here | The paper's useful step is described at the scale of the whole field problem. |
| Data-level empirical finding | What was observed under the current design? | A result tied to data, denominator, estimand, method, conditions, and uncertainty | A scoped observation is rewritten as a universal or necessary principle. |
| Extrapolation-level claim | What is asserted beyond the observed setting? | Only a generalisation supported by additional direct evidence and stated transfer conditions | Portability, necessity, dominance, causality, or field-wide validity is inferred from one bounded finding. |

The levels may be connected, but they are not interchangeable. A real domain
gap does not prove that the paper closes it. A real paper contribution does not
automatically license the strongest possible headline. A finding can remain
valuable while supporting only a narrower claim.

## Write the Six-Line Paper Claim Licence

Complete these six lines before drafting or reframing prose:

1. **Broad problem:** the wider problem or field-level gap.
2. **Exact paper contribution:** the bounded step delivered by this paper.
3. **Primary empirical claim:** the most reliable and reproducible claim
   licensed by the present evidence, not merely the most striking one.
4. **Headline or extrapolative claim:** the strongest broader interpretation
   currently presented, whether supported or not.
5. **Licensed scope:** where the empirical and any supported extrapolative
   claim is licensed.
6. **Explicitly unlicensed claims:** attractive stronger claims that the
   current design does not establish.

For `Licensed scope`, inspect the applicable dimensions rather than writing a
generic qualifier:

- data source, sample, population, target population, and denominator;
- construct, task, intervention, model, comparator, and baseline;
- annotator or measurement process and its reliability;
- estimand, metric, analysis method, and uncertainty;
- setting, time, domain, transfer conditions, and external validation.

Use `unknown` when a dimension cannot be recovered. A limitation statement is
not evidence for a missing dimension.

## Audit Every Upward Inference

Inspect the full ladder:

```text
broad gap -> selected subproblem -> paper contribution
          -> research design and estimand -> empirical finding
          -> licensed claim -> extrapolation
```

Every upward transition needs its own direct evidence anchor. In particular,
do not move from “a phenomenon exists” to “the field misses this unit”, then to
“this is the necessary or dominant unit”, or finally to “it transfers across
domains” without new evidence at each step.

For every disputed transition, report:

- source level and target level;
- canonical evidence or relation IDs;
- the existing canonical evidence status, support balance, and scope-match
  values unchanged, or `unknown` when no canonical value exists;
- the missing evidence, if any;
- either `evidence_needed` or a narrower target claim.

Wording, conceptual appeal, reviewer interest, tables, guardrails, and appendix
material do not count as new evidence anchors.

## Assign One Canonical Role to Each Contribution

Reuse the `contribution_focus.csv` `current_role` values owned by
`$argument-governance`: `primary`, `secondary`, `enabling`, `boundary`,
`exploratory`, or `deprioritised`. Do not introduce another contribution-role
enum. Keep prominence separate from evidence maturity: “empirical
demonstration”, “preliminary evidence”, and “future hypothesis” may describe
the current interpretation in prose, but they are not replacement role or
evidence-status values.

The `primary` contribution should have the most complete reliable evidence
path and clearest fit to the paper's exact gap. Do not present every framework,
taxonomy, dataset, audit, finding, intervention, and generalisation as a
co-equal primary contribution. Preserve any change of focus as
`pending_author_decision` until the author approves it.

Evaluate these two judgements separately:

- **Conceptual value:** is the question, framing, or proposed distinction useful?
- **Evidential entitlement:** does the available evidence license the stated claim?

High conceptual value does not repair low evidential entitlement, and low
entitlement does not imply that the underlying problem lacks value.

## Diagnose the Repair Layer Before Editing

| Repair layer | Diagnostic | Permitted next action |
|---|---|---|
| `wording` | The evidence licenses a bounded claim, but title, abstract, contribution wording, result heading, or conclusion overstates it. | Use a bounded edit contract, or a paper-wide reframe if several spine sections must change. |
| `argument_design` | Claim hierarchy, denominator, estimand, evidence mapping, uncertainty, contribution role, or generalisation level is unclear or misaligned. | Run `$argument-governance`; repair the map before prose. |
| `research_design` | Construct validity, reliability, sampling, baseline, power, comparison, or external validation is insufficient for the intended claim. | Stop language repair. Specify `evidence_needed`, or ask the author to approve a narrower claim. |

Do not route a research-design deficit to prose polishing. Rewriting can reveal
or honestly narrow a deficit; it cannot remove it.

## Apply the Late-Framing Upgrade Gate

When a higher-level framing appears after the experiments were designed:

1. Record the old framing and proposed new framing.
2. State the new construct, estimand, denominator, comparator, sample, and
   generalisation evidence the new framing requires.
3. Compare those requirements with the actual research design and evidence.
4. If matched evidence is absent, keep the framing as `motivation`,
   `bounded_interpretation`, or `future_hypothesis`.
5. Promote it to a primary contribution only after the required evidence is
   present and the author approves the focus change.

A stronger narrative discovered late can be intellectually useful. It is not
retroactive evidence that the original experiment tested that narrative.

## Propagate the Boundary Through the Paper

Treat scope as an active paper-wide constraint. Audit at least:

| Location | Boundary question |
|---|---|
| Title | Does it name or imply a population, task, mechanism, or reach beyond the licensed scope? |
| Research question | Can the present design answer it as written? |
| Sampling and denominator | Is the target population explicit and aligned with the claim? |
| Estimand and experiment | Does the measured quantity answer the intended question? |
| Abstract | Are contribution and result statements no stronger than the evidence licence? |
| Contribution list | Does each item have the right role and evidence path? |
| Result headings | Do labels describe observed results rather than inferred universals? |
| Conclusion | Does it stop where the current evidence stops? |
| Limitations and appendix | Do they clarify residual uncertainty without serving as disclaimers for stronger claims elsewhere? |

If the limitations are careful but the title, abstract, or conclusion remains
stronger, report `scope_propagation_failure`. Boundary language hidden in one
section does not cancel an overclaim elsewhere.

## Reject Defensive Complexity as a Substitute

Additional tables, ledgers, taxonomies, warnings, qualifiers, sensitivity
analyses, guardrails, or appendices can improve transparency. They cannot by
themselves repair missing construct validity, reliability, representative
sampling, denominator definition, baseline comparison, statistical power, or
portability evidence.

If an addition does not shorten the claim-evidence distance, do not treat it as
claim support. Choose one of two honest actions:

1. add a decisive study, comparison, calibration, or validation that closes the
   named evidence gap; or
2. narrow or reclassify the headline claim and contribution role.

For external feedback, distinguish a misunderstanding from a valid inferential
concern. Clarification can address the first. The second requires evidence or
claim narrowing; rebuttal language alone cannot close it.

## Report Template

Add this compact block to the `Research Project Navigation Report`:

```text
### Argument Level Lock
- Broad problem:
- Exact paper contribution:
- Primary empirical claim:
- Headline or extrapolative claim:
- Licensed scope:
- Explicitly unlicensed claims:

### Claim Licence Audit
| Transition | Evidence or relation IDs | evidence_status | support_balance | scope_match | Missing evidence | Decision |

### Repair Diagnosis
- Issue layer: wording / argument_design / research_design
- Conceptual value:
- Evidential entitlement:
- Late-framing upgrade status:
- Boundary propagation status:
- Evidence-needed or claim-narrowing decision:
```

Stop before prose editing when the four levels cannot be separated, a headline
claim has no direct evidence anchor, licensed scope is unknown, a late framing
upgrade lacks a matching design, a boundary appears only in limitations, a
research-design problem is being presented as a wording task, or the proposed
repair only adds defensive complexity. Also retain the existing author focus
gate and three-revision rule.
