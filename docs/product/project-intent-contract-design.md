# Project Intent Contract And Global Thesis Audit

## Problem

Section-level writing controls can preserve the wrong manuscript thesis. Once a
drifted framing is recorded as a section spine, local edit contracts and drift
audits may faithfully protect it. The validator has then behaved correctly at
the wrong authority level.

The failure is a project-intent blind spot:

```text
drifted or unconfirmed manuscript thesis
→ section spine
→ edit contract
→ local drift audit
```

The required control hierarchy is:

```text
author-approved project intent
→ author-approved manuscript contract
→ passed global thesis audit
→ section spine
→ edit contract
→ post-edit drift audit
```

## Design Boundary

The feature is a structural author-control gate. It does not claim that a
script can determine the scholarly meaning of a title or abstract. A human or
review agent compares the current manuscript with the recorded intent and
records the result. The validator checks that the record is complete,
versioned, internally consistent, and not bypassed by a lower-level contract.

## Durable Objects

### `project_intent.csv`

The highest-authority object records the primary domain, research object, core
research question, target venue, concepts that must remain visible, excluded
reframes, approval evidence, and version history.

There may be at most one active row. An active or superseded row must be
human-approved. Version 2 and later must identify the immediately previous row
through `supersedes_intent_id`. The previous row remains in the file with
`status=superseded`; the new row records an amendment reason. This is the
reframe gate.

### `manuscript_contracts.csv`

This object records what the current manuscript actually claims to be: title,
abstract focus, primary domain, research object, research question,
contribution scope, and structure. It has the same explicit version-lineage
rule and must reference the active project intent before it can be active.

### `global_thesis_audits.csv`

The audit compares the manuscript contract with the project intent across:

- title
- abstract
- primary domain
- research object
- research question
- contribution
- structure

Each dimension is `aligned`, `drifted`, or `not_assessed`. A passed audit
requires every dimension to be aligned, `detected_reframe=false`,
`human_decision=accept`, and active approved intent and manuscript contracts.
Recorded drift requires human review and cannot be accepted as a passed audit.
The valid responses are to revise the manuscript, roll back, or create a new
versioned project-intent amendment.

### Section And Edit Links

Each spine card records `manuscript_id`. Each edit contract records
`global_audit_id`. An approved or applied edit is executable only when the
audit is passed and covers the same active manuscript contract as the section
spine.

## Strict And Legacy Behaviour

`check_thesis_control.py --strict` requires the complete project-intent layer.
Non-strict mode remains able to inspect legacy packets without it. This keeps
old evidence readable while ensuring that a current strict release gate cannot
silently omit author intent.

`scaffold_thesis_control.py` creates schema v4 draft objects with
`AUTHOR_REVIEW_REQUIRED` content. The intent and manuscript rows are not
approved, and the global audit remains pending. This draft can pass structural
validation because no edit is executable; the author must resolve the global
objects before changing an edit contract to `approved` or `applied`.

The existing revision-tracking migration intentionally does not invent project
intent. It can still upgrade its bounded schema in isolation. A legacy project
can then run `upgrade_thesis_control_project_intent.py` to add the v4 link
columns and draft objects atomically. The helper fills every scholarly field
with `AUTHOR_REVIEW_REQUIRED`, leaves the global audit pending, and therefore
does not release existing approved or applied edits. The author must establish
the real intent and manuscript contract before the full strict gate can pass.

## Gate Invariants

1. A lower-level object never amends a higher-level object.
2. Approved or applied edits require exactly one active approved intent and
   manuscript contract.
3. The edit's global audit must cover the same manuscript contract as its spine
   card.
4. A recorded reframe or any drifted dimension cannot pass.
5. A later project intent or manuscript contract preserves explicit immediate
   lineage; no in-place overwrite authorises reframing.
6. Draft scaffolding never implies author approval.
7. The validator enforces recorded decisions but does not substitute for the
   semantic comparison.

## Acceptance Fixture

[`examples/project-intent-drift-gate/`](../../examples/project-intent-drift-gate/README.md)
contains a synthetic domain-survey failure:

- the approved intent makes visual heritage the primary domain;
- the blocked manuscript makes it a stress-test example inside a generic
  evaluation survey;
- the global audit records the project-level reframe;
- strict validation blocks the proposed edit with
  `global-thesis-gate-required`;
- the aligned packet restores the primary domain and passes.

This case tests the exact authority failure that section-only spine control
cannot catch.
