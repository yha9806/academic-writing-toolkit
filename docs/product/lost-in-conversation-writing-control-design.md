# Lost-in-Conversation Writing Control Design

## Summary

Academic Writing Toolkit should treat multi-turn AI writing drift as a control problem, not as a prompt-length problem. The first product move is a small benchmark-style evaluation, `Lost-in-Conversation Writing Control Bench`, but the first implementation should stay narrow: use the existing `/thesis-control` artifacts to turn scattered writing discussion into an explicit edit contract before prose changes are applied.

The design follows the finding from `LLMs Get Lost In Multi-Turn Conversation`: multi-turn underspecified conversations substantially increase unreliability because models make early assumptions, attempt answers too soon, and then fail to recover. Thesis writing has the same risk profile: the user's intent, claims, caveats, evidence boundaries, and adjacent-section constraints are often revealed over several turns. The toolkit should help the author recover control by consolidating that fragmented intent into reviewable artifacts.

References:

- Microsoft Research publication page: <https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/>
- arXiv paper page: <https://arxiv.org/abs/2505.06120>

## Product Thesis

Multi-turn AI writing is risky because authorship becomes sharded:

- the first request names a local writing problem;
- later turns add claim boundaries, evidence limits, supervisor context, or chapter-spine constraints;
- the model may preserve the conversational surface while silently changing the actual argument;
- the author loses track of what was authorised, what changed, and whether the result should be accepted.

Academic Writing Toolkit should not optimise for a longer conversation. It should convert messy multi-turn writing intent into durable author-control objects:

- `spine_cards.csv` records the section purpose and claim boundary;
- `edit_contracts.csv` records what the next edit is allowed to change;
- `drift_audits.csv` records whether the edit preserved the contract;
- a short review packet lets the author decide accept, partial accept, revise, or rollback.

## Goals

1. Show, with a small realistic evaluation, why normal multi-turn writing assistance causes loss of author control.
2. Demonstrate that `/thesis-control` can reduce that loss by requiring a pre-edit contract and a post-edit drift audit.
3. Use desensitised thesis-style sections rather than purely generic samples, so the evaluation reflects real writing complexity without exposing private manuscript content.
4. Keep the first implementation local-first, file-based, and compatible with the existing skill and validator structure.

## Non-Goals

- Do not build a hosted benchmark platform.
- Do not add model-evaluation infrastructure or new runtime dependencies in the first pass.
- Do not expose private thesis text in public docs, fixtures, screenshots, or hosted app surfaces.
- Do not expand the ChatGPT App into local thesis-file access. The full workflow remains a local agent / Codex plugin workflow.
- Do not claim that the evaluation proves general model superiority or scientific validity. It is a product-control evaluation.

## Evaluation Design

Use a small set of desensitised thesis-style sections. Each sample should preserve the real structure of academic writing: section purpose, core claims, evidence anchors, caveats, adjacent-section relationship, and revision pressure. It should remove names, unpublished findings, private supervisor comments, sensitive datasets, and any text that should not become a public fixture.

Run the same writing task through three workflows:

1. **Baseline A: normal multi-turn chat edit**
   - The user provides revision constraints over several turns.
   - The assistant edits as the conversation evolves.
   - The expected failure mode is local fluency with possible claim drift, scope creep, or lost caveats.

2. **Baseline B: consolidated single-turn edit**
   - The scattered instructions are consolidated into one complete prompt before editing.
   - This tests the paper's practical recommendation to consolidate before retrying.
   - It should reduce some drift, but still lacks durable author-control records.

3. **Treatment: `/thesis-control` edit**
   - The same scattered instructions are converted into a control packet.
   - The edit can proceed only after an explicit contract states allowed changes, forbidden changes, adjacent context, and acceptance checks.
   - The result is audited against the contract before the author accepts it.

## Metrics

Use human-readable rubric scores rather than automated quality claims in the first pass.

| Metric | Question | Evidence |
| --- | --- | --- |
| Spine preservation | Did the edited unit still serve the same section function? | compare original spine card, edit output, drift audit |
| Claim drift | Were core claims broadened, softened, reversed, or reframed? | compare `core_claims`, changed prose, audit row |
| Evidence boundary | Did the edit introduce claims not supported by the source anchors? | inspect evidence references and new assertions |
| Scope discipline | Did the edit stay within the authorised file range and change scope? | compare contract scope and final diff |
| Author control recovery | Can the author decide accept, partial accept, revise, or rollback without rereading the whole conversation? | review packet and human decision |

Each workflow should receive a short review note. The treatment workflow must produce real `spine_cards.csv`, `edit_contracts.csv`, and `drift_audits.csv` files.

## First Implementation Shape

The first implementation should land in the existing `/thesis-control` workflow, not as a separate product surface.

Add a design-backed workflow convention:

1. A multi-turn writing request is treated as a source of draft intent, not as edit approval.
2. Before editing, the agent consolidates the conversation into an explicit contract.
3. The contract is stored or mirrored in `edit_contracts.csv`.
4. The source unit has a spine card before any substantive edit.
5. After editing, the drift audit records claim changes, boundary changes, unsupported claims, missed adjacent updates, and human-review requirement.

The existing validator remains structural. It should not judge prose quality or scholarly truth. If later work adds more checks, they should validate control integrity first: paths, identifiers, required fields, human gates, and contract-audit consistency.

## Data Flow

```text
desensitised thesis excerpt
        |
        v
multi-turn writing requirements
        |
        +--> Baseline A: direct multi-turn edits
        |
        +--> Baseline B: consolidated single-turn prompt
        |
        +--> Treatment: /thesis-control packet
                  |
                  +--> spine_cards.csv
                  +--> edit_contracts.csv
                  +--> bounded edit
                  +--> drift_audits.csv
                  +--> author decision
```

## Error Handling And Stop Conditions

The treatment workflow must stop instead of editing when:

- the section spine cannot be stated clearly;
- the requested edit would broaden a claim without evidence;
- a local edit requires adjacent changes outside the approved scope;
- the desensitised sample has lost too much structure to evaluate real drift;
- prior AI edits cannot be distinguished from author-approved prose;
- the author has not approved a high-risk contract.

If any of these occur during the bench run, the outcome should be recorded as a control success rather than an execution failure: refusing to edit is the correct behaviour when author control is insufficient.

### Revision Escalation

Three unsuccessful attempts against the same revision issue are an operational stop threshold, not a research claim that every task fails after three turns. Contract versions remain in the same issue family through `revision_issue_id`. Only author rejection or a `revise` or `rollback` drift decision counts as an unsuccessful attempt; clarification and unexecuted proposals do not count. At that point the workflow must not apply a fourth prose patch.

The workflow may escalate earlier when claim drift, an evidence gap, an unclear spine, loss of the latest author-approved version, or version contamination is already visible. Before any further edit, it consolidates the valid requirements, compares them with the control packet and approved source, classifies the problem, and asks the author to approve the next action.

The diagnosis separates underspecified or conflicting intent, local execution failure, structural mismatch, evidence gap, and version contamination. It also distinguishes a local patch, section-level restructure, and full reframing. A new branch or manuscript version is an isolation mechanism for approved structural work, not a substitute for repairing an unclear specification.

### Revision Escalation Execution Layer

The instruction rule is not sufficient on its own. Strict thesis-control packets must make revision attempts and escalation approval structurally inspectable.

`edit_contracts.csv` adds two fields:

- `revision_issue_id` groups multiple contract versions that address the same unresolved writing problem;
- `attempt_no` is a positive, unique, sequential number within that issue.

An unsuccessful attempt is one contract whose audit decision is `revise` or `rollback`. Author rejection must be recorded as one of those two decisions so the outcome is durable and countable. Multiple audits for one contract still count as one attempt.

`revision_escalations.csv` records:

```text
escalation_id,revision_issue_id,trigger_contracts,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
```

The execution gate is:

1. Find the first three unsuccessful contracts in one `revision_issue_id` family.
2. Require a revision-escalation row that references those trigger contracts.
3. Permit draft planning, but reject any later contract marked `approved` or `applied` until a matching escalation row has `human_approved=true` and `status=approved`.
4. Keep early escalation available with fewer than three trigger contracts; it does not weaken the three-strike gate.
5. Treat every later group of three unsuccessful contracts as a new escalation cycle; an earlier approval does not permanently unlock the issue.

The checker remains structural. It can verify identities, attempt order, audit outcomes, escalation linkage, and human approval. It cannot decide whether feedback is semantically ambiguous, whether evidence is academically sufficient, or whether a full reframing is intellectually correct.

For compatibility, non-strict checking continues to accept legacy packets without revision-tracking columns. Strict checking requires the new fields and escalation file. A local migration helper adds the new schema without guessing historical issue relationships: each legacy contract starts as its own issue and authors may explicitly regroup known revision families.

The public-safe executable fixture at `examples/thesis-control-revision-escalation/` keeps blocked and approved packets side by side. It demonstrates the same fourth contract failing without an escalation record and passing only after a matching escalation receives explicit author approval.

## Acceptance Criteria

The design is ready for implementation planning when:

- at least three public-safe cases are selected or prepared;
- the evaluation task is written once and reused across all three workflows;
- the treatment workflow produces valid `spine_cards.csv`, `edit_contracts.csv`, and `drift_audits.csv`;
- the comparison report identifies at least one concrete difference between normal chat editing and contract-bounded editing;
- the final review answers whether the treatment improved author control, not merely whether the prose sounded better.
- repeated revisions trigger diagnosis after three unsuccessful attempts on the same contract, or earlier when a high-risk control failure is visible.

## Public Communication Boundary

Public copy may say the toolkit is inspired by multi-turn reliability research and helps authors keep AI-assisted thesis edits bounded, inspectable, and reversible. It must not claim that the toolkit solves all multi-turn reliability failures, prevents hallucinations, or proves model correctness.

The safe public claim is:

```text
Academic Writing Toolkit turns scattered multi-turn writing intent into thesis-control artifacts before substantive edits are applied, helping authors inspect claim drift, evidence boundaries, and acceptance decisions.
```

## Implementation Pointer

The first implementation uses the public-safe fixture in `examples/lost-in-conversation-bench/` and the structural checker `scripts/check_lost_in_conversation_bench.py`. The fixture includes actual edited outputs for Baseline A, Baseline B, and Treatment, plus `comparison_report.md` for inline human review. The checker validates a three-case minimum through `cases/index.md` and requires each case to carry the same comparison and treatment-control artifacts. The treatment packets should also validate with:

```sh
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/treatment --strict --json
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/cases/method-limitation-boundary/treatment --strict --json
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/cases/evidence-boundary-literature/treatment --strict --json
```
