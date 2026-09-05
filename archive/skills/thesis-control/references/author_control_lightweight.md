# Lightweight Author-Control Profile

Use this profile when one manuscript needs durable author control but the
seven-table `thesis_control/` packet would add more administration than the
revision risk warrants. It preserves the same authority hierarchy in three
human-readable Markdown files:

```text
00_AUTHOR_INTENT.md
01_EVIDENCE_AND_CLAIMS.md
02_REVISION_LOG.md
```

Copy the bundled files from `assets/`, or run:

```bash
python {skill_dir}/scripts/scaffold_author_control.py <project_root>
python {skill_dir}/scripts/check_author_control.py <project_root> --strict
```

The scaffold never overwrites an existing control file. Structural validation
checks headings, explicit approval state, and unresolved template markers. It
does not decide whether the recorded intent is scientifically sound or whether
the manuscript is semantically aligned; those remain human judgements.

## Authority And Profile Selection

In the lightweight profile, `00_AUTHOR_INTENT.md` is the highest authority and
must be author-approved before substantive editing. The evidence file cannot
redefine the intent, and a revision-log entry cannot amend either file.
Append revision entries; do not rewrite earlier decisions. When the author
approves a higher-level intent change, increment `Intent version`, name the
superseded version, and preserve the old-versus-new decision in the revision
log before replacing the active card. Archive the earlier card when the project
requires exact historical recovery.

Use the full `thesis_control/` packet instead when the work needs multiple
simultaneous edit contracts, machine-checked cross-file IDs, several active
manuscript versions, or a formal fourth-edit escalation gate. If both profiles
exist, declare one as canonical. Default to the full packet as the executable
gate and treat the three Markdown files as a readable mirror whose baseline
fields name the active intent and manuscript IDs. Never maintain two competing
authorities.

## Keep Application Purpose And Evidence Conclusion Separate

Record these levels independently:

| Level | Question |
| --- | --- |
| Real-world problem | Who ultimately needs help with what task? |
| Intended use | What future application motivates the work? |
| Method task | What does the present software, method, or workflow output? |
| Scientific question | What comparison or test does this paper perform? |
| Empirical finding | What did the current design actually establish? |
| Evidence boundary | What hardware, clinical, causal, deployment, or transfer outcome remains unvalidated? |

Narrow evidence narrows the empirical and headline claims. It does not erase a
legitimate application problem or convert intended use into something the
paper has already validated. A missing deployment study is not permission to
rewrite an application-motivated paper as an abstract metric study.

## Admit Analyses By Argument Function

Before a new experiment or analysis enters the manuscript, record:

1. whether it directly answers the core scientific question;
2. whether the main conclusion survives if it is removed;
3. its single argumentative function;
4. its default destination; and
5. the author decision.

Use these default roles:

| Role | Default destination |
| --- | --- |
| `primary` — directly answers the core question | Main text |
| `explanatory` — explains a primary result | Main text when needed, otherwise Supplementary |
| `robustness` — checks sensitivity without carrying the main conclusion | Supplementary |
| `development_record` — failed or superseded method development | Internal record or Supplementary when scientifically informative |
| `out_of_scope` — performs no distinct work for the approved question | Exclude |

Completion alone is not an admission criterion. An author may override a
default destination, but must record the rationale and resulting prominence
change. Do not promote an auxiliary analysis merely because it is complete or
auditable.

## Freeze Evidence And Argument Separately

Every revision entry records both:

- **Evidence baseline:** the version, ref, result table, dataset, experiment
  configuration, or frozen numbers inherited by the revision.
- **Argument baseline:** the author-approved intent/manuscript version from
  which the title, question, contribution order, application explanation, and
  evidence boundary are inherited.

A frozen evidence baseline does not authorise inheritance of an unapproved
narrative. Conversely, an approved argument baseline does not authorise new or
changed numerical claims.

## Classify The Edit Before Applying It

Use `local_patch`, `section_restructure`, or `full_reframe`.

A change to the title, abstract thesis, research object, core question,
primary experiment, contribution order, evidence chain, application purpose,
or paper-wide structure is a `full_reframe`, even when described as polishing.
Before editing, show an old-versus-proposed spine comparison and obtain an
explicit author decision. Do not infer approval from a request to make the
paper more academic, rigorous, concise, or venue-appropriate.

## Run The Expanded Drift Audit

After editing, answer:

- Did the research object change?
- Was the real-world task or intended use deleted, generalised, or demoted?
- Did the core scientific question change?
- Was an auxiliary analysis promoted?
- Did an evidence boundary become the new research topic?
- Was any unsupported conclusion added?
- Did caution remove the paper's application meaning?
- Do the title, abstract, Introduction, Results, and Conclusion still describe
  the same paper?

Any material change requires the author's decision: `accept`,
`partial_accept`, `revise`, or `rollback`. A smoother draft is not evidence of
alignment.

## Add Two Post-Spine Gates When Relevant

After the research spine is stable:

1. Use `/logic-review` for an argument-function pass. Label passages as
   problem, gap, method, evidence, interpretation, or boundary, then remove
   duplicated functions rather than generating synonymous disclaimers.
2. Use `/self-review` to prepare the restricted unfamiliar-reader packet. Only
   actual responses from an unfamiliar human can pass that human gate; a model
   simulation remains advisory.

Scope must remain aligned throughout the paper, but explicit limitation prose
does not need to be repeated after every result. Keep essential local
qualifiers next to the claims they bound; concentrate fuller study-boundary
language in the abstract ending, Methods boundary, Discussion/Limitations, and
conclusion as appropriate.
