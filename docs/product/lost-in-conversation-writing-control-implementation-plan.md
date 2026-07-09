# Lost-in-Conversation Writing Control Implementation Plan

> **For implementers:** Execute this plan task-by-task with strict red-green TDD,
> focused commits, and review gates. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Build a small local benchmark fixture that demonstrates how `/thesis-control` turns scattered multi-turn writing intent into reviewable edit-control artifacts.

**Architecture:** Keep the implementation local-first and file-based. Add a public-safe benchmark fixture under `examples/`, a small structural checker under `scripts/`, and one regression test that proves the fixture produces valid thesis-control artifacts. Do not add runtime dependencies or expand the hosted ChatGPT App surface.

**Tech Stack:** Markdown fixtures, CSV control packets, Bash regression harness, Python 3 standard library.

**Current extension:** The initial single-case fixture has been expanded into a three-case fixture. `scripts/check_lost_in_conversation_bench.py` validates the root case plus `cases/*`, T73 runs strict `/thesis-control` validation for every case treatment packet, and T74 requires the skill to stop and diagnose repeated revisions instead of applying a fourth prose patch.

**Revision escalation architecture:** Keep revision escalation inside `/thesis-control`. The skill groups unsuccessful contract versions under one revision issue, stops after three, allows earlier escalation for high-risk control failures, and routes the author to a corrected local contract, section restructure, evidence-boundary decision, approved-version restore, or full reframing. The validator enforces structural attempt and approval gates without claiming to judge semantic convergence.

**Execution-layer extension:** Track one unresolved problem across contract versions with `revision_issue_id` and `attempt_no`. Add `revision_escalations.csv` as the durable diagnosis and author-approval record. Strict validation must require a distinct exact-match escalation record after each group of three unsuccessful applied contracts with resolved failed audits, and must reject a later `approved` or `applied` contract until that escalation is human-approved. Non-strict validation remains compatible with legacy packets.

## Schema v3 Hardening Extension

**Approved design:**
[`thesis-control-revision-escalation-v3-hardening-design.md`](thesis-control-revision-escalation-v3-hardening-design.md)

**Goal:** Eliminate premature escalation approval, ambiguous CSV parsing, and
partial writes while preserving the structural-only checker boundary.

**Architecture:** Add `escalation_kind` and `approved_after_attempt` to strict
escalation records. Route checker, scaffold, and migration CSV handling through
one canonical `thesis_control_io.py` module. Build complete candidate outputs in
memory and commit them through a staged batch writer only after all validation
passes.

### Task E: Introduce Strict Shared CSV I/O

**Files:**
- Create `.claude/skills/thesis-control/scripts/thesis_control_io.py`
- Modify `.claude/skills/thesis-control/scripts/check_thesis_control.py`
- Modify `.claude/skills/thesis-control/scripts/scaffold_thesis_control.py`
- Modify `.claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py`
- Modify `scripts/test.sh`

- [x] Add T91 proving duplicate headers, including conflicting
  `human_approved` columns, fail in each control CSV.
- [x] Add T92 proving extra, missing, truncated, and invalid quoted cells return
  structured checker issues without a traceback.
- [x] Implement strict header and row-width parsing with
  `csv.reader(..., strict=True)`.
- [x] Make checker parsing failures issue records and helper parsing failures
  concise `ValueError` messages.
- [x] Preserve named extension columns in migration and reject unsupported
  extension columns before scaffold mutation.
- [x] Run the full suite; T2-T90 and T91-T92 must pass.

### Task F: Enforce Schema v3 Escalation Semantics

**Files:**
- Modify `.claude/skills/thesis-control/scripts/check_thesis_control.py`
- Modify `.claude/skills/thesis-control/scripts/scaffold_thesis_control.py`
- Modify all public `revision_escalations.csv` fixtures
- Modify `scripts/test.sh`

- [x] Add T93 proving non-strict mode reads v2 packets but strict mode requires
  `escalation_kind` and `approved_after_attempt`.
- [x] Add T94 proving an approved three-trigger record is invalid before its
  trigger contracts form a completed unsuccessful group.
- [x] Add T95 proving `early_diagnostic` remains non-closing after later
  failures and a distinct `cycle_gate` is required.
- [x] Add T96 covering oversized, cross-issue, duplicate, shifted, and repeated
  cycle-gate trigger sets.
- [x] Accept `early_diagnostic` only with one or two unique triggers and an
  empty approval boundary.
- [x] Accept an effective `cycle_gate` only with exactly three failed applied
  triggers, an exact completed group, and `approved_after_attempt` equal to the
  group's maximum attempt.
- [x] Run strict validation for every public fixture and the full suite.

### Task G: Make Scaffold Writes Failure-Atomic

**Files:**
- Modify `.claude/skills/thesis-control/scripts/thesis_control_io.py`
- Modify `.claude/skills/thesis-control/scripts/scaffold_thesis_control.py`
- Modify `scripts/test.sh`

- [x] Add T97 proving malformed existing headers cause no file or directory
  changes.
- [x] Add T98 proving excerpt, spine, contract, and review-packet collisions
  cause no byte changes when the command fails.
- [x] Add T99 proving attempts 1 and 2 default to distinct `-001` and `-002`
  contract IDs and produce a strict-valid family.
- [x] Add T100 covering force replacement and multiple issue families without
  mutation on an invalid candidate.
- [x] Preflight all targets, render the full candidate packet in memory, stage
  every output, and use rollback-capable batch replacement.
- [x] Run T97-T100 and the full suite.

### Task H: Make Migration Deterministic And Failure-Atomic

**Files:**
- Modify `.claude/skills/thesis-control/scripts/thesis_control_io.py`
- Modify `.claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py`
- Modify `scripts/test.sh`

- [x] Add T101 proving malformed escalation input leaves the legacy contract
  file byte-identical.
- [x] Add T102 proving partial revision schemas stop without mutation and give
  an author-actionable message.
- [x] Add T103 proving deterministic v2-to-v3 conversion produces a
  strict-valid packet for both early diagnostics and completed cycle gates.
- [x] Add T104 proving ambiguous, oversized, and non-completed v2 escalation
  rows stop without mutation.
- [x] Add T105 proving complete valid revision metadata and extension columns
  are preserved and repeated migration is idempotent.
- [x] Validate every candidate table and escalation classification before the
  staged batch writer replaces any target.
- [x] Run T101-T105 and the full suite.

### Task I: Adversarial Audit, Documentation, And Packaging

**Files:**
- Modify `.claude/skills/thesis-control/SKILL.md`
- Modify `README.md`
- Modify `docs/product/lost-in-conversation-writing-control-design.md`
- Modify `docs/skills/15-thesis-control.md`
- Create `docs/product/thesis-control-v3-adversarial-matrix.md`
- Regenerate `plugins/academic-writing-toolkit/skills/thesis-control/`
- Modify `scripts/test.sh` when an audit case exposes an uncovered defect

- [x] Add T106-T111 for multiple-audit, trigger-order, candidate-integrity,
  path-boundary, rollback, encoding, legacy/non-strict, and retry combinations.
- [x] Record each adversarial case, expected exit and issue kind, observed
  result, and regression-test mapping.
- [x] Synchronise skill, public docs, fixtures, and generated plugin copies.
- [x] Run the complete test, plugin, ChatGPT App, public-content, release-packet,
  syntax, sync, and diff gates.
- [x] Obtain two independent full-range reviews and resolve every Critical and
  Important finding.
- [x] Commit and push verified changes, update PR #22 evidence, and confirm
  GitHub Actions passes while leaving the PR open and unmerged.

## PR #22 Review-Fix Extension

**Goal:** Close the merge-review gaps in escalation-cycle matching, failed-attempt counting, scaffolded attempt sequencing, and public documentation.

**Architecture:** Keep the existing CSV schema. Allow early diagnostic escalation, but let a completed three-contract group close only through one unique exact-match approved escalation. Count only resolved failures from applied contracts, and reject scaffold writes that would leave one revision issue with duplicate or non-sequential attempts. Preserve non-strict legacy compatibility and regenerate the packaged plugin from the canonical skill.

**Tech Stack:** Python 3 standard library, Bash regression harness, Markdown documentation, CSV fixtures.

### Task A: Make Escalation Cycles One-To-One

**Files:**
- Modify `.claude/skills/thesis-control/scripts/check_thesis_control.py`
- Modify `scripts/test.sh`

**Interface:** A completed three-contract group is satisfied only by one escalation whose unique trigger set equals that group exactly. An early escalation with fewer than three triggers remains valid but cannot close or pre-authorise a later completed group.

- [ ] Add T86 with six failed applied contracts, a seventh applied contract, and one approved escalation listing all six failures.
- [ ] Run `bash scripts/test.sh`; expect only T86 to fail because the oversized escalation currently unlocks both groups.
- [ ] Replace subset matching with exact trigger-set matching:

```python
matching = [
    escalation
    for escalation in escalations_by_issue.get(revision_issue_id, [])
    if required_triggers == escalation["triggers"]
]
```

- [ ] Re-run `bash scripts/test.sh`; expect T86 and the existing suite to pass.
- [ ] Add T89 and T90 to reject duplicate trigger IDs within one row and duplicate escalation rows for the same issue and trigger set.
- [ ] Reject repeated trigger tokens and repeated `(revision_issue_id, trigger set)` keys before cycle approval is evaluated.
- [ ] Re-run `bash scripts/test.sh`; expect T89, T90, and the existing suite to pass.

### Task B: Exclude Unexecuted Proposals From Failure Counts

**Files:**
- Modify `.claude/skills/thesis-control/scripts/check_thesis_control.py`
- Modify `scripts/test.sh`

**Interface:** A contract becomes an unsuccessful attempt only when it is `applied` and has a resolved `revise` or `rollback` audit with `status=failed`.

- [ ] Add T87 with three non-applied contracts carrying failed audits and a fourth applied accepted contract.
- [ ] Run `bash scripts/test.sh`; expect only T87 to fail because the non-applied contracts currently trigger escalation.
- [ ] Add the contract-state condition to unsuccessful-attempt collection:

```python
if (
    decision in {"revise", "rollback"}
    and status == "failed"
    and contract_statuses.get(contract_id) == "applied"
):
    unsuccessful_contracts.add(contract_id)
```

- [ ] Re-run `bash scripts/test.sh`; expect T87 and the existing suite to pass.

### Task C: Keep Scaffolded Attempts Strict-Valid

**Files:**
- Modify `.claude/skills/thesis-control/scripts/scaffold_thesis_control.py`
- Modify `scripts/test.sh`

**Interface:** `validate_revision_attempt(path, contract_id, revision_issue_id, attempt_no, force)` reads existing contract rows before any output mutation, simulates replacing the same contract when `force=true`, and requires the target issue's candidate attempts to equal `1..N` with no duplicates.

- [ ] Add T88 proving that a standalone attempt 2 is rejected, attempts 1 then 2 succeed, and the resulting packet passes strict validation.
- [ ] Run `bash scripts/test.sh`; expect T88 to fail because the scaffold currently accepts standalone attempt 2.
- [ ] Add the sequence validator and call it before copying source text or writing CSV rows:

```python
candidate_attempts = sorted(existing_attempts + [attempt_no])
expected_attempts = list(range(1, candidate_attempts[-1] + 1))
if candidate_attempts != expected_attempts:
    raise ValueError(
        f"revision issue {revision_issue_id} attempts must be unique and sequential from 1"
    )
```

- [ ] Re-run `bash scripts/test.sh`; expect T88 and the existing suite to pass.

### Task D: Synchronise Contracts, Documentation, And Release Gates

**Files:**
- Modify `.claude/skills/thesis-control/SKILL.md`
- Modify `docs/product/lost-in-conversation-writing-control-design.md`
- Modify `docs/product/lost-in-conversation-writing-control-implementation-plan.md`
- Modify `docs/skills/15-thesis-control.md`
- Regenerate `plugins/academic-writing-toolkit/skills/thesis-control/`

**Interface:** Every public definition states that only applied contracts with resolved failed revise/rollback audits count; pending reviews and unexecuted proposals do not count; each later group of three needs one unique exact-match escalation; and early escalation does not close a later completed group.

- [ ] Update the design and plan text, including the `revision_issue_id` acceptance criterion and T83-T90 sequence.
- [ ] Update scaffold review-packet guidance to use the same resolved-failure wording.
- [ ] Run `bash scripts/sync-plugin.sh` and verify `bash scripts/sync-plugin.sh --check`.
- [ ] Run `bash scripts/test.sh`, `make plugin-check`, `make chatgpt-app-check`, `python3 scripts/audit-public-content.py --base-dir . --json`, the release-packet validator, and `git diff --check`.
- [ ] Obtain independent diff review before committing and pushing the repaired branch.

## Revision Escalation Execution Extension

### File Map

- Modify `.claude/skills/thesis-control/scripts/check_thesis_control.py`: validate revision families, attempts, escalation records, and the fourth-edit gate.
- Modify `.claude/skills/thesis-control/scripts/scaffold_thesis_control.py`: emit revision identity fields and an empty escalation CSV.
- Create `.claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py`: upgrade legacy packets without inferring historical revision families.
- Modify `.claude/skills/thesis-control/SKILL.md`: document durable attempt recording and the strict checker gate.
- Modify `scripts/test.sh`: add red-green tests for schema requirements, blocking, approval, scaffold output, and legacy migration.
- Modify `examples/lost-in-conversation-bench/**/thesis_control/*.csv`: move all strict public fixtures to the revision-tracking schema.
- Create `examples/thesis-control-revision-escalation/`: preserve blocked and approved four-attempt packets for direct human and checker review.
- Regenerate `plugins/academic-writing-toolkit/skills/thesis-control/` with `make plugin-sync`.

### Checker Contract

- A revision issue id is a safe identifier shared by contracts for the same unresolved problem.
- Attempt numbers are positive, unique, and sequential within one issue.
- A contract counts as unsuccessful once only when it is `applied` and a linked audit resolves to `revise` or `rollback` with `status=failed`.
- Three unsuccessful contracts require a linked escalation row.
- Every later group of three unsuccessful contracts requires a new escalation row whose trigger set exactly matches that group.
- A later draft or rejected contract is inspectable, but a later approved or applied contract requires a matching human-approved escalation.
- Only one escalation row for an issue may use the exact trigger set for a completed group, and trigger IDs may not repeat within the row.
- An early escalation with fewer than three triggers is valid, but it cannot close or pre-authorise a later completed group.

### Test Sequence

1. Add T75 and verify strict validation rejects a fourth applied contract without escalation.
2. Add T76 and verify a correctly linked, human-approved escalation permits the fourth contract.
3. Add T77 and verify malformed attempt families and escalation references fail.
4. Add T78 and verify the scaffold emits revision identity plus the escalation header.
5. Add T79 and verify the migration helper preserves legacy rows while adding isolated issue identities.
6. Add T80 and verify the persistent fixture blocks the fourth edit before escalation and accepts it after author approval.
7. Add T81 and verify each later group of three unsuccessful contracts requires a new escalation cycle.
8. Add T82 and verify non-strict legacy compatibility while strict mode requires migration.
9. Add T83-T85 and verify pending human-review blocking plus resolved audit-outcome consistency.
10. Add T86-T88 and verify exact cycle matching, exclusion of non-applied contracts, and strict-valid scaffold sequences.
11. Add T89-T90 and verify duplicate trigger IDs and duplicate rows for one trigger set are rejected.
12. Run `make plugin-sync`, `make test`, public-content audit, and `git diff --check`.

---

## Scope And File Map

Create a public-safe fixture:

- Create `examples/lost-in-conversation-bench/README.md`: explains the bench purpose, three workflows, and privacy boundary.
- Create `examples/lost-in-conversation-bench/chapters/desensitized_section.md`: desensitised thesis-style section used by all workflows.
- Create `examples/lost-in-conversation-bench/requirements/multi_turn_requirements.md`: sharded multi-turn writing requirements.
- Create `examples/lost-in-conversation-bench/requirements/consolidated_prompt.md`: consolidated single-turn equivalent.
- Create `examples/lost-in-conversation-bench/baselines/baseline_a_review.md`: review of normal multi-turn chat editing.
- Create `examples/lost-in-conversation-bench/baselines/baseline_b_review.md`: review of consolidated single-turn editing.
- Create `examples/lost-in-conversation-bench/treatment/source_excerpts/lost-conversation-section.md`: copied source excerpt used by the treatment packet.
- Create `examples/lost-in-conversation-bench/treatment/edited_section.md`: bounded edited result for the treatment workflow.
- Create `examples/lost-in-conversation-bench/treatment/thesis_control/spine_cards.csv`: treatment spine card.
- Create `examples/lost-in-conversation-bench/treatment/thesis_control/edit_contracts.csv`: treatment edit contract.
- Create `examples/lost-in-conversation-bench/treatment/thesis_control/drift_audits.csv`: treatment drift audit.
- Create `examples/lost-in-conversation-bench/treatment/review_report.md`: human-readable treatment review.

Add validation and documentation:

- Create `scripts/check_lost_in_conversation_bench.py`: validates required files, required review sections, and treatment control packet shape.
- Modify `scripts/test.sh`: add T73 to run the new checker and existing thesis-control validator.
- Modify `README.md`: mention the bench in the demo/check section without overclaiming.
- Modify `docs/product/lost-in-conversation-writing-control-design.md`: add a short implementation pointer to the fixture and checker.

## Task 1: Add The Failing Regression Test

**Files:**
- Modify: `scripts/test.sh`

- [ ] **Step 1: Update the test-suite header**

Change the first comment block so the count includes the new bench test.

```bash
# scripts/test.sh — runs the regression test suite (70 automated tests: T2-T18 toolkit + T19-T32 citation/env + T33-T44 public toolkit features + T45-T49 reference metadata + T50-T53 plugin packaging + T54-T58 release governance + T59 docs consistency + T60 Markdown BibTeX + T61-T63 productization + T64-T72 thesis control + T73 lost-in-conversation bench) for academic-writing-toolkit.
```

- [ ] **Step 2: Add `test_T73` after `test_T72`**

Insert this function immediately after the existing `test_T72` function.

```bash
test_T73() {
    local bench="$REPO_ROOT/examples/lost-in-conversation-bench"

    [[ -f "$bench/README.md" ]] || return 1
    [[ -f "$bench/chapters/desensitized_section.md" ]] || return 1
    [[ -f "$bench/requirements/multi_turn_requirements.md" ]] || return 1
    [[ -f "$bench/requirements/consolidated_prompt.md" ]] || return 1
    [[ -f "$bench/baselines/baseline_a_review.md" ]] || return 1
    [[ -f "$bench/baselines/baseline_b_review.md" ]] || return 1
    [[ -f "$bench/treatment/source_excerpts/lost-conversation-section.md" ]] || return 1
    [[ -f "$bench/treatment/edited_section.md" ]] || return 1
    [[ -f "$bench/treatment/review_report.md" ]] || return 1

    python3 scripts/check_lost_in_conversation_bench.py "$bench" >/dev/null || return 1
    python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$bench/treatment" --strict >/dev/null || return 1
}
```

- [ ] **Step 3: Register T73 in the run list**

Add this line immediately after the existing T72 `run_test` line.

```bash
run_test "T73 lost-in-conversation bench validates" test_T73
```

- [ ] **Step 4: Run the failing test**

Run:

```bash
make test
```

Expected: the suite fails at `T73 lost-in-conversation bench validates` because `examples/lost-in-conversation-bench/` and `scripts/check_lost_in_conversation_bench.py` do not exist yet.

- [ ] **Step 5: Commit the failing test**

```bash
git add scripts/test.sh
git commit -m "test: add lost-in-conversation bench guard"
```

## Task 2: Add The Bench Checker

**Files:**
- Create: `scripts/check_lost_in_conversation_bench.py`

- [ ] **Step 1: Create the checker**

Create `scripts/check_lost_in_conversation_bench.py` with this exact content:

```python
#!/usr/bin/env python3
"""Validate the lost-in-conversation writing-control bench fixture.

The checker is structural. It verifies that the public-safe fixture contains
the three comparison workflows and that the treatment workflow records the
control artifacts needed for author review. It does not judge prose quality.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, List


REQUIRED_FILES = [
    "README.md",
    "chapters/desensitized_section.md",
    "requirements/multi_turn_requirements.md",
    "requirements/consolidated_prompt.md",
    "baselines/baseline_a_review.md",
    "baselines/baseline_b_review.md",
    "treatment/source_excerpts/lost-conversation-section.md",
    "treatment/edited_section.md",
    "treatment/review_report.md",
    "treatment/thesis_control/spine_cards.csv",
    "treatment/thesis_control/edit_contracts.csv",
    "treatment/thesis_control/drift_audits.csv",
]

REQUIRED_METRICS = [
    "Spine preservation",
    "Claim drift",
    "Evidence boundary",
    "Scope discipline",
    "Author control recovery",
]

REQUIRED_REVIEW_HEADINGS = [
    "## Workflow",
    "## Metric Review",
    "## Control Finding",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add_issue(issues: List[dict], kind: str, location: str, message: str) -> None:
    issues.append({"kind": kind, "location": location, "message": message})


def read_csv_rows(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_required_files(root: Path, issues: List[dict]) -> None:
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if not path.is_file():
            add_issue(issues, "missing-file", rel_path, "required bench file is missing")


def validate_prompt_files(root: Path, issues: List[dict]) -> None:
    multi_turn = root / "requirements/multi_turn_requirements.md"
    consolidated = root / "requirements/consolidated_prompt.md"
    if multi_turn.is_file():
        text = read_text(multi_turn)
        for label in ["Turn 1", "Turn 2", "Turn 3", "Turn 4", "Turn 5"]:
            if label not in text:
                add_issue(issues, "missing-turn", str(multi_turn.relative_to(root)), f"missing {label}")
    if consolidated.is_file():
        text = read_text(consolidated)
        for metric in REQUIRED_METRICS:
            if metric not in text:
                add_issue(
                    issues,
                    "missing-consolidated-metric",
                    str(consolidated.relative_to(root)),
                    f"consolidated prompt does not name {metric}",
                )


def validate_review(path: Path, root: Path, issues: List[dict]) -> None:
    if not path.is_file():
        return
    text = read_text(path)
    rel = str(path.relative_to(root))
    for heading in REQUIRED_REVIEW_HEADINGS:
        if heading not in text:
            add_issue(issues, "missing-review-heading", rel, f"review is missing heading {heading}")
    for metric in REQUIRED_METRICS:
        if metric not in text:
            add_issue(issues, "missing-review-metric", rel, f"review does not address {metric}")


def validate_treatment_packet(root: Path, issues: List[dict]) -> None:
    treatment = root / "treatment"
    spine_path = treatment / "thesis_control" / "spine_cards.csv"
    contract_path = treatment / "thesis_control" / "edit_contracts.csv"
    audit_path = treatment / "thesis_control" / "drift_audits.csv"
    if not (spine_path.is_file() and contract_path.is_file() and audit_path.is_file()):
        return

    spine_rows = read_csv_rows(spine_path)
    contract_rows = read_csv_rows(contract_path)
    audit_rows = read_csv_rows(audit_path)
    if len(spine_rows) != 1:
        add_issue(issues, "unexpected-spine-count", str(spine_path.relative_to(root)), "bench treatment should have exactly one spine row")
    if len(contract_rows) != 1:
        add_issue(issues, "unexpected-contract-count", str(contract_path.relative_to(root)), "bench treatment should have exactly one contract row")
    if len(audit_rows) != 1:
        add_issue(issues, "unexpected-audit-count", str(audit_path.relative_to(root)), "bench treatment should have exactly one audit row")
    if contract_rows:
        row = contract_rows[0]
        if row.get("status", "").strip().lower() != "applied":
            add_issue(issues, "contract-not-applied", str(contract_path.relative_to(root)), "treatment contract must be status=applied")
        if row.get("human_approved", "").strip().lower() != "true":
            add_issue(issues, "contract-not-approved", str(contract_path.relative_to(root)), "treatment contract must have human_approved=true")
    if audit_rows:
        row = audit_rows[0]
        if row.get("drift_decision", "").strip().lower() not in {"accept", "partial_accept", "revise", "rollback"}:
            add_issue(issues, "invalid-treatment-decision", str(audit_path.relative_to(root)), "treatment audit needs a valid drift_decision")
        if row.get("status", "").strip().lower() not in {"passed", "needs_review", "failed"}:
            add_issue(issues, "invalid-treatment-status", str(audit_path.relative_to(root)), "treatment audit needs a valid status")


def validate_bench(root: Path) -> dict:
    issues: List[dict] = []
    validate_required_files(root, issues)
    validate_prompt_files(root, issues)
    validate_review(root / "baselines" / "baseline_a_review.md", root, issues)
    validate_review(root / "baselines" / "baseline_b_review.md", root, issues)
    validate_review(root / "treatment" / "review_report.md", root, issues)
    validate_treatment_packet(root, issues)
    return {
        "schema_version": 1,
        "bench_root": str(root),
        "issues": issues,
        "issue_count": len(issues),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the lost-in-conversation writing-control bench fixture.")
    parser.add_argument("bench_root", nargs="?", default="examples/lost-in-conversation-bench")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.bench_root).resolve()
    payload = validate_bench(root)
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    elif payload["issues"]:
        print(f"Lost-in-conversation bench root: {root}")
        for issue in payload["issues"]:
            print(f"- {issue['location']}: {issue['kind']}: {issue['message']}")
    else:
        print(f"Lost-in-conversation bench root: {root}")
        print("- no bench issues detected")
    return 1 if payload["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make the checker executable**

Run:

```bash
chmod +x scripts/check_lost_in_conversation_bench.py
```

- [ ] **Step 3: Run the checker and verify it fails for missing files**

Run:

```bash
python3 scripts/check_lost_in_conversation_bench.py --json
```

Expected: exit code `1`, JSON output with `issue_count` greater than `0`, and at least one `missing-file` issue.

- [ ] **Step 4: Commit the checker**

```bash
git add scripts/check_lost_in_conversation_bench.py
git commit -m "test: add lost-in-conversation bench checker"
```

## Task 3: Add The Public-Safe Bench Fixture

**Files:**
- Create: all files under `examples/lost-in-conversation-bench/`

- [ ] **Step 1: Create the fixture directories**

```bash
mkdir -p examples/lost-in-conversation-bench/chapters
mkdir -p examples/lost-in-conversation-bench/requirements
mkdir -p examples/lost-in-conversation-bench/baselines
mkdir -p examples/lost-in-conversation-bench/treatment/source_excerpts
mkdir -p examples/lost-in-conversation-bench/treatment/thesis_control
```

- [ ] **Step 2: Create the bench README**

Create `examples/lost-in-conversation-bench/README.md`:

```markdown
# Lost-in-Conversation Writing Control Bench

This fixture demonstrates a local, public-safe evaluation for AI-assisted thesis editing drift.

The bench compares three workflows on the same desensitised thesis-style section:

1. Baseline A: normal multi-turn chat editing.
2. Baseline B: a consolidated single-turn prompt.
3. Treatment: `/thesis-control` with a spine card, edit contract, bounded edit, drift audit, and author decision.

The fixture is not a model benchmark and does not claim scientific validity. It is a product-control check: can the author inspect what changed, decide whether the edit stayed inside scope, and choose accept, partial accept, revise, or rollback without rereading a long chat history?

Run from the repository root:

```bash
python3 scripts/check_lost_in_conversation_bench.py examples/lost-in-conversation-bench --json
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/treatment --strict --json
```
```

- [ ] **Step 3: Create the desensitised section**

Create `examples/lost-in-conversation-bench/chapters/desensitized_section.md`:

```markdown
# Section 2.3: Evidence Boundaries In Assisted Revision

The chapter argues that AI-assisted thesis revision is useful only when the author can inspect how local edits affect the section's claim boundary. A revision may improve sentence flow while also weakening the distinction between what the sources show and what the author infers from them. This matters because the section is not trying to prove that all AI-assisted writing is unreliable. It is trying to show why revision workflows need explicit controls around claims, caveats, and evidence use.

The current section draws on two source notes. Source A describes a writing-support workflow where notes, claims, and revision decisions are kept as separate records. Source B discusses multi-turn assistant use and warns that later clarifications can be folded into earlier assumptions. Together, these sources support a bounded claim: thesis writers need visible edit boundaries when using AI across several turns. They do not support a stronger claim that any particular model is unsafe for all writing tasks.

The next subsection will discuss implementation, so this section should not introduce product architecture in detail. Its role is to motivate the control problem and define what must not drift during revision. The key caveat is that the concern is not fluency by itself. The concern is whether a smoother paragraph still preserves the author's intended claim, the evidence boundary, and the relationship to neighbouring sections.
```

- [ ] **Step 4: Copy the treatment source excerpt**

Create `examples/lost-in-conversation-bench/treatment/source_excerpts/lost-conversation-section.md` with the same content as `examples/lost-in-conversation-bench/chapters/desensitized_section.md`.

- [ ] **Step 5: Create the multi-turn requirements**

Create `examples/lost-in-conversation-bench/requirements/multi_turn_requirements.md`:

```markdown
# Multi-Turn Requirements

## Turn 1

Please make this section clearer and less repetitive.

## Turn 2

Do not make the claim broader. The section should not say that all AI writing is unreliable.

## Turn 3

Keep the evidence boundary visible: Source A and Source B support the need for visible edit controls, not a universal model-safety claim.

## Turn 4

Do not move into product architecture yet because the next subsection handles implementation.

## Turn 5

After editing, tell me whether the section spine, claim boundary, and caveat survived.
```

- [ ] **Step 6: Create the consolidated prompt**

Create `examples/lost-in-conversation-bench/requirements/consolidated_prompt.md`:

```markdown
# Consolidated Prompt

Revise `chapters/desensitized_section.md` for clarity and reduced repetition while preserving the section's current role.

Required controls:

- Spine preservation: the section must still argue that AI-assisted thesis revision needs visible edit boundaries because fluency can hide claim drift.
- Claim drift: do not broaden the claim into a statement that all AI writing or all models are unreliable.
- Evidence boundary: Source A and Source B support the need for visible edit controls; they do not support universal model-safety claims.
- Scope discipline: do not add product architecture or implementation details because the next subsection handles implementation.
- Author control recovery: after revising, report whether the spine, claim boundary, evidence boundary, and caveat survived.
```

- [ ] **Step 7: Create Baseline A review**

Create `examples/lost-in-conversation-bench/baselines/baseline_a_review.md`:

```markdown
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
```

- [ ] **Step 8: Create Baseline B review**

Create `examples/lost-in-conversation-bench/baselines/baseline_b_review.md`:

```markdown
# Baseline B Review: Consolidated Single-Turn Edit

## Workflow

The scattered requirements are consolidated before editing. This reduces the chance that the editor over-relies on an early assumption, but the output is still not bound to a durable author-control record.

## Metric Review

| Metric | Review |
| --- | --- |
| Spine preservation | Better than Baseline A because the spine is stated before editing. |
| Claim drift | Lower risk than Baseline A, but the author still needs to inspect the final prose manually. |
| Evidence boundary | Lower risk because the prompt names the source boundary explicitly. |
| Scope discipline | Lower risk because implementation details are explicitly forbidden. |
| Author control recovery | Partial. The consolidated prompt is reviewable, but there is no CSV contract, applied status, or post-edit audit. |

## Control Finding

Consolidation helps, but it remains a prompt technique. It does not create the reviewable artifacts needed for accepting, partially accepting, revising, or rolling back the edit.
```

- [ ] **Step 9: Create the treatment edited section**

Create `examples/lost-in-conversation-bench/treatment/edited_section.md`:

```markdown
# Section 2.3: Evidence Boundaries In Assisted Revision

This section argues that AI-assisted thesis revision is useful only when the author can inspect how a local edit affects the section's claim boundary. A paragraph can become smoother while also blurring the difference between what the sources show and what the author infers from them. The point is therefore narrow: the section does not claim that all AI-assisted writing is unreliable. It shows why revision workflows need explicit controls around claims, caveats, and evidence use.

The section relies on two source notes. Source A describes a writing-support workflow that keeps notes, claims, and revision decisions as separate records. Source B discusses multi-turn assistant use and warns that later clarifications can be absorbed into earlier assumptions. Together, these sources support a bounded claim: thesis writers need visible edit boundaries when they use AI across several turns. They do not support the stronger claim that any particular model is unsafe for every writing task.

The next subsection turns to implementation, so this section keeps product architecture out of scope. Its role is to define the control problem and state what must not drift during revision. The key caveat is that fluency is not the target by itself. The target is a revision process in which smoother prose still preserves the author's intended claim, the evidence boundary, and the relationship to neighbouring sections.
```

- [ ] **Step 10: Create `spine_cards.csv`**

Create `examples/lost-in-conversation-bench/treatment/thesis_control/spine_cards.csv`:

```csv
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
lost-conversation-section,source_excerpts/lost-conversation-section.md,Evidence Boundaries In Assisted Revision,This unit argues that AI-assisted thesis revision needs visible edit boundaries because fluent local edits can hide claim and evidence-boundary drift.,Motivate the writing-control problem only; do not introduce product architecture or universal model-safety claims.,Thesis writers need visible edit boundaries when using AI across several turns; Source A and Source B support workflow-control need rather than universal model unreliability.,Do not claim all AI writing is unreliable; do not claim any specific model is unsafe for every writing task; do not move implementation architecture into this section.
```

- [ ] **Step 11: Create `edit_contracts.csv`**

Create `examples/lost-in-conversation-bench/treatment/thesis_control/edit_contracts.csv`:

```csv
contract_id,unit_id,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-lost-conversation-section-001,lost-conversation-section,Revise the three-paragraph section for clarity and reduced repetition while preserving the motivation role.,Improve sentence flow; reduce repeated phrasing; make the caveat and source boundary easier to inspect.,Do not broaden into universal AI-writing unreliability; do not add product architecture; do not introduce new evidence or model-safety claims.,Check that the next subsection remains responsible for implementation details.,Spine is preserved; claim remains bounded; evidence boundary is explicit; no unsupported universal claim is added.,true,applied
```

- [ ] **Step 12: Create `drift_audits.csv`**

Create `examples/lost-in-conversation-bench/treatment/thesis_control/drift_audits.csv`:

```csv
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-lost-conversation-section-001,ec-lost-conversation-section-001,none,none,none,none,accept,false,passed
```

- [ ] **Step 13: Create the treatment review report**

Create `examples/lost-in-conversation-bench/treatment/review_report.md`:

```markdown
# Treatment Review: Thesis-Control Edit

## Workflow

The same multi-turn requirements are converted into a spine card, edit contract, bounded edit, and drift audit before the final prose is accepted.

## Metric Review

| Metric | Review |
| --- | --- |
| Spine preservation | Strong. The spine card states the section function before editing, and the edited section keeps that function. |
| Claim drift | Strong. The edit preserves the bounded claim and avoids universal AI-writing unreliability. |
| Evidence boundary | Strong. The edit keeps Source A and Source B tied to workflow-control need rather than broad model-safety claims. |
| Scope discipline | Strong. Product architecture remains outside this motivation section. |
| Author control recovery | Strong. The author can inspect `spine_cards.csv`, `edit_contracts.csv`, and `drift_audits.csv` without reconstructing the full chat history. |

## Control Finding

The treatment improves author control because the approval decision is tied to explicit artifacts: the spine card, applied edit contract, and drift audit. The prose is not accepted merely because it reads better.
```

- [ ] **Step 14: Run the new checker**

Run:

```bash
python3 scripts/check_lost_in_conversation_bench.py examples/lost-in-conversation-bench --json
```

Expected: exit code `0` and `"issue_count": 0`.

- [ ] **Step 15: Run the thesis-control validator on the treatment packet**

Run:

```bash
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/treatment --strict --json
```

Expected: exit code `0` and `"issue_count": 0`.

- [ ] **Step 16: Run the regression test**

Run:

```bash
make test
```

Expected: all tests pass, including `T73 lost-in-conversation bench validates`.

- [ ] **Step 17: Commit the fixture**

```bash
git add examples/lost-in-conversation-bench
git commit -m "docs: add lost-in-conversation writing bench fixture"
```

## Task 4: Link The Bench From Product Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/product/lost-in-conversation-writing-control-design.md`

- [ ] **Step 1: Add a README bench note**

In `README.md`, near the existing demo/check section, add:

```markdown
The repository also includes a small public-safe writing-control fixture at [`examples/lost-in-conversation-bench`](examples/lost-in-conversation-bench). It compares normal multi-turn editing, consolidated prompting, and `/thesis-control` artifacts for author-control review.
```

- [ ] **Step 2: Add an implementation pointer to the design doc**

Append this section to `docs/product/lost-in-conversation-writing-control-design.md`:

````markdown
## Implementation Pointer

The first implementation should use the public-safe fixture in `examples/lost-in-conversation-bench/` and the structural checker `scripts/check_lost_in_conversation_bench.py`. The treatment packet should also validate with:

```sh
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/treatment --strict --json
```
````

- [ ] **Step 3: Run documentation and public-surface checks**

Run:

```bash
python3 scripts/audit-public-content.py --base-dir . --json
git diff --check
make test
```

Expected:

- public-content audit returns `"issue_count": 0`;
- `git diff --check` exits `0`;
- `make test` exits `0`.

- [ ] **Step 4: Commit the docs links**

```bash
git add README.md docs/product/lost-in-conversation-writing-control-design.md
git commit -m "docs: link lost-in-conversation bench"
```

## Task 5: Final Verification And Release-Ready Review

**Files:**
- Inspect: `git status`
- Inspect: `git log`

- [ ] **Step 1: Run final verification**

Run:

```bash
python3 scripts/audit-public-content.py --base-dir . --json
git diff --check
make test
python3 scripts/check_lost_in_conversation_bench.py examples/lost-in-conversation-bench --json
python3 .claude/skills/thesis-control/scripts/check_thesis_control.py examples/lost-in-conversation-bench/treatment --strict --json
```

Expected:

- public-content audit has `"issue_count": 0`;
- whitespace check exits `0`;
- full regression suite passes;
- bench checker has `"issue_count": 0`;
- thesis-control checker has `"issue_count": 0`.

- [ ] **Step 2: Inspect final status**

Run:

```bash
git status --short --branch
git log --oneline -5 --decorate
```

Expected: working tree clean and latest commits include the T73 guard, bench checker, bench fixture, and docs link commits.

- [ ] **Step 3: Push**

```bash
git push origin main
```

Expected: `main` pushes successfully.

## Self-Review

Spec coverage:

- Small realistic evaluation: covered by `examples/lost-in-conversation-bench`.
- Three workflows: covered by `requirements/`, `baselines/`, and `treatment/`.
- Treatment uses real `/thesis-control` artifacts: covered by `treatment/thesis_control/*.csv` and strict validator.
- Author-control metrics: required by `scripts/check_lost_in_conversation_bench.py`.
- Local-first boundary: no hosted surface, no new runtime dependency, no ChatGPT App expansion.

Placeholder scan:

- The plan contains no unresolved replacement markers.
- Every file creation step includes exact content.
- Every validation step includes a concrete command and expected result.

Type and name consistency:

- The bench root is consistently `examples/lost-in-conversation-bench`.
- The checker is consistently `scripts/check_lost_in_conversation_bench.py`.
- The treatment unit id is consistently `lost-conversation-section`.
- The contract id is consistently `ec-lost-conversation-section-001`.
- The audit id is consistently `da-lost-conversation-section-001`.
