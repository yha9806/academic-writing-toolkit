# Thesis-Control Revision Escalation v3 Hardening Design

## Decision

Revision escalation will move to a strict packet schema v3. The schema keeps
`revision_escalations.csv` as the single escalation record, but separates early
diagnosis from cycle-closing approval and records the attempt boundary at which
an approval becomes valid.

The implementation will also introduce one shared CSV I/O boundary for the
checker, scaffold, and migration helper. That boundary will reject ambiguous
CSV shapes and will stage multi-file changes before replacing project files.

## Problem Statement

Schema v2 can validate an exact trigger set, but it cannot distinguish an
early diagnostic record from a record intended to close a completed failure
cycle. A three-trigger row can therefore be approved before its contracts have
all failed and become effective later without a new author decision.

The current scripts also trust `csv.DictReader` to resolve duplicate headers
and incomplete rows. Duplicate human-approval columns can be interpreted using
the final value, while truncated rows can raise an exception instead of
producing a structural issue. The scaffold and migration helper write files in
sequence, so a later error can leave a partially changed packet.

These are control-integrity defects. They must be fixed without turning the
checker into a judge of prose quality or scholarly truth.

## Goals

1. Make early diagnosis structurally incapable of closing a failure cycle.
2. Require each cycle-closing approval to identify one completed group of
   three unsuccessful applied contracts and its final attempt number.
3. Reject ambiguous or malformed CSV input consistently across all four
   control files.
4. Make scaffold and migration failures leave existing files byte-for-byte
   unchanged.
5. Preserve non-strict legacy inspection while making strict validation use
   the v3 escalation contract.
6. Keep the author as the owner of approval, merge, and release decisions.

## Non-Goals And Trust Boundary

- The checker does not decide whether an argument is true, well supported, or
  well written.
- The checker does not cryptographically prove when a local file was edited.
  It verifies that the current packet contains an explicit post-attempt
  approval boundary consistent with the current contract and audit records.
- The design does not add a fifth control CSV, a database, a hosted service, or
  a new runtime dependency.
- The design does not merge the pull request or publish a release.

## Schema v3

Strict packets use this escalation header:

```text
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
```

The two new fields are:

- `escalation_kind`: `early_diagnostic` or `cycle_gate`;
- `approved_after_attempt`: empty for early diagnosis and a positive integer
  for a cycle gate.

### Early Diagnostic Rules

An `early_diagnostic` row:

- references one or two unique contracts from one `revision_issue_id`;
- keeps `approved_after_attempt` empty;
- may become author-approved as a diagnosis or next-action decision;
- is never considered when deciding whether a later contract may become
  `approved` or `applied`.

An early diagnostic row cannot be converted into a cycle-closing approval by
the passage of later attempts. Closing a cycle requires a distinct
`cycle_gate` row with its own `escalation_id`.

### Cycle Gate Rules

A `cycle_gate` row:

- references exactly three unique contracts;
- references contracts from one revision issue;
- matches exactly one completed failure group in attempt order;
- uses `approved_after_attempt` equal to the greatest `attempt_no` in that
  group;
- becomes effective only when `human_approved=true` and `status=approved`;
- becomes effective only when all three trigger contracts are `applied` and
  each has a resolved `revise` or `rollback` audit with `status=failed`.

A draft cycle-gate row may be prepared before approval, but it cannot satisfy
the execution gate. A row with `status=approved` before the trigger group is
complete is structurally invalid. Trigger sets larger than three are invalid.

Each completed group has one unique cycle gate. A later group of three failures
requires a different exact trigger set and a different escalation row.

## Shared CSV I/O Boundary

Create `.claude/skills/thesis-control/scripts/thesis_control_io.py` and import
it from the checker, scaffold, and migration scripts. The plugin copy is
generated from the canonical skill.

The reader will use `csv.reader(..., strict=True)` before constructing row
dictionaries. It will return field names and string-valued rows only after
checking:

- the header exists and contains no empty or duplicate names;
- every required column occurs exactly once;
- every data row has exactly the same number of cells as the header;
- no row has extra cells, missing cells, or an invalid quoted-field shape;
- empty data files are accepted only where the caller explicitly allows them.

The checker converts reader failures into structured issues containing a kind,
location, and message. The scaffold and migration helper convert the same
failures into concise `ValueError` messages. None of the three commands may
emit a Python traceback for malformed user CSV input.

The checker accepts named extension columns when their headers are unique and
their row widths are valid. Migration preserves extension columns and values
unchanged. The scaffold refuses to mutate a table with extension columns it
does not own. No helper silently drops a named column.

## Failure-Atomic Writes

The shared I/O module will provide a batch writer that accepts complete target
contents only after all semantic validation has finished.

The write sequence is:

1. Read and validate every existing input and output target.
2. Check identifiers, attempt families, collisions, replacement permissions,
   review-packet paths, and candidate packet semantics in memory.
3. Render every target to bytes in memory.
4. Write all candidates to temporary files before replacing any target.
5. Preserve the bytes and modes of existing targets for rollback.
6. Replace targets using same-filesystem atomic replacement.
7. If replacement fails, restore every replaced target, remove newly created
   targets, and report the original failure plus any rollback failure.

Temporary staging artifacts and directories are removed on success and failure.
Known validation failures occur before target directories or files are created.

## Scaffold Behaviour

The scaffold will preflight all four CSVs, the copied excerpt, the spine row,
the contract row, and the review packet before it writes anything.

Default contract IDs will include the attempt number:

```text
ec-<unit-id>-<attempt-no padded to three digits>
```

Attempt 1 therefore retains the existing `-001` shape, while attempt 2 defaults
to `-002`. A retry still reuses an explicit `revision_issue_id` so the scaffold
does not guess that two edits address the same unresolved problem.

Force replacement is simulated in memory. It may replace the same contract but
must leave every revision family unique and sequential. A rejected operation
must leave all pre-existing bytes unchanged.

## Migration Behaviour

Migration distinguishes four inputs:

1. **Legacy contracts with neither revision column:** assign each contract a
   unique `revision_issue_id` and `attempt_no=1`.
2. **Complete revision columns:** preserve them only after validating safe issue
   IDs and positive, unique, sequential attempts.
3. **Partial revision columns or partial values:** stop without writing and
   explain that historical grouping or ordering needs an author decision.
4. **Malformed CSV or ambiguous escalation data:** stop without writing and
   report the exact structural problem.

For an existing v2 escalation file:

- an empty file receives the v3 header;
- a one- or two-trigger row becomes `early_diagnostic` with an empty
  `approved_after_attempt`;
- a three-trigger row becomes `cycle_gate` only when the current contracts and
  resolved audits prove that it exactly matches a completed failure group;
- oversized, cross-issue, incomplete, or otherwise ambiguous rows stop the
  migration without changing any file.

Migration validates the full candidate packet before committing it. A command
that exits unsuccessfully leaves the original packet unchanged.

Non-strict checking continues to read packets without revision columns and v2
escalation fields for legacy inspection. It does not treat a v2 escalation as
v3 post-attempt approval evidence. Strict checking requires both v3 escalation
columns and applies the complete execution gate.

## Checker Data Flow

```text
strict CSV shape read
        |
        v
contract and audit validation
        |
        v
unsuccessful applied contracts ordered by revision issue and attempt
        |
        +--> early_diagnostic rows: validate only; never unlock
        |
        +--> cycle_gate rows: exact group + approved_after_attempt check
        |
        v
later approved/applied contracts blocked until matching cycle gate is effective
```

Multiple audits of one contract count that contract at most once. A pending
audit never counts as unsuccessful. Contradictory resolved outcomes remain
invalid. Adding or removing a failed audit may change group boundaries, so all
cycle gates are rechecked against the current ordered groups.

## Test And Adversarial Matrix

The existing T2-T90 suite remains intact. New tests begin at T91 and cover:

- pre-approved future trigger groups;
- early diagnostics that remain non-closing after later failures;
- oversized, duplicate, cross-issue, and shifted trigger sets;
- duplicate headers, including conflicting human-approval values;
- extra, missing, truncated, and invalid quoted cells in all four control CSVs;
- structured checker errors without tracebacks;
- scaffold collisions, force replacement, multiple issue families, malformed
  headers, and byte-for-byte failure atomicity;
- migration failure atomicity, partial schemas, complete v2 preservation,
  deterministic v2-to-v3 escalation conversion, ambiguous-row rejection, and
  idempotence;
- attempt-aware default contract IDs;
- multiple-audit, approval/status, legacy/non-strict, cycle-shifting,
  identifier, and path-boundary combinations.

The final adversarial report records each case, the expected exit status and
issue kind, and the observed result. It is evidence for the pull request, not a
claim of exhaustive correctness outside the documented trust boundary.

## Documentation And Packaging

Implementation updates remain aligned across:

- `.claude/skills/thesis-control/` as the canonical source;
- `docs/product/` design and implementation-plan material;
- `docs/skills/15-thesis-control.md` and `README.md`;
- public-safe examples and their CSV headers;
- `plugins/academic-writing-toolkit/skills/thesis-control/`, regenerated by
  `scripts/sync-plugin.sh`.

Canonical and plugin files must be byte-identical after generation. Public
documentation must retain the structural-only and author-owned boundaries.

## Completion Criteria

The hardening work is complete only when:

- every new red test has been observed failing for the intended reason and is
  green after implementation;
- the complete automated suite and every project release gate pass;
- the adversarial matrix has no unexplained result;
- Gemini smart-diff review passes;
- two independent full-range reviews have no unresolved Critical or Important
  finding;
- the verified branch is pushed, the pull-request evidence is updated, and
  GitHub Actions passes;
- the pull request remains open and unmerged for the author.
