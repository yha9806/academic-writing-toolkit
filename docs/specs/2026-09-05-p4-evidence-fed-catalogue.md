# P4 — Evidence-Fed Catalogue

- **Status:** session 2 IMPLEMENTED (2026-09-05) — item 4 landed:
  `scripts/audit-citation-fidelity.mjs` reuses the E1 graders and the guards'
  own citation extractor and notes parser; four findings (quote-not-in-source,
  page-mismatch, notes-missing, experimental low-overlap) pinned on temp
  workspaces, plus the honesty test in which a sentence inverting its source
  in the source's own words is REQUIRED to pass without a finding while the
  output states that limit. The audit skill runs E (positioning) → F
  (fidelity) → G (prose measurement). Session 1 IMPLEMENTED — items 1–3 landed and gated
  locally: author-control promoted as Advisory assets (`a02a795`); claim
  positioning recognises Harvard/Markdown and joins the audit skill with
  prose measurement, positioning first (`55ebb63`); the pre-export gate
  `EXPORT_SOURCES_UNRESOLVED` guards a registered `export_docx` profile tool,
  red-first in the pure kernel, the testkit tier (denied and allowed), and
  the live e2e (six scenarios green); credential probe green; make test
  132/132; public-content audit clean. Session 2 (item 4, the sentence-level
  fidelity audit, and docs) is next. Originally author_approved (2026-09-05). Both ⚑ decisions taken by the
  author: item 1 → **A** (promote the lightweight author-control profile as
  Advisory assets; approval field is display, never authority); item 3 →
  **(a)+(b)** (the export gate checks notes coverage AND `.bib` parity).
  Implementation may begin; per-item truth lives in this header's
  successors (`implemented` → `verified`), never in prose.
- **Parent spec:** `2026-08-16-awt-dsh-app-v0.1-design.md` §6 (catalogue),
  §7 (enforcement), §11 (evidence classes), §12 (kill/reframe gates)
- **Inputs:** two real manuscripts finished between 2026-07 and 2026-09-01
  (a survey paper and a benchmark paper), the four `main` commits they
  produced and which were merged in `68bae2c` (`b5d1c7d`, `25a3015`,
  `1ecdb44`, `80827f8`), and issues #33–#38.

## Investment gate (recorded, not skipped)

- **Covered:** prose-style measurement and citation-key hygiene exist as
  scripts on `main` (`scripts/audit-prose-fingerprint.py`,
  `scripts/audit-claim-positioning.py`), built during the benchmark paper's
  polish and validated there.
- **Unsolved:** no tool in this repository — or found in the harness
  ecosystem survey — checks whether a *citing sentence says what its source
  says*. The survey manuscript's audit found five of seven re-read citing
  sentences wrong about their source, three of them inverted; every existing
  gate asked whether the source was read, verified, or cited, none whether
  the sentence matched. AWT's own `NOTES_MISSING` guard sits in the same
  blind spot: it is key-level (a notes file exists), not sentence-level.
- **Still differentiable:** the enforcement kernel plus a sentence-level
  fidelity audit fed by the same graders as the E1 instrument. The harness
  shell is commodity (ecosystem report); the audit kernel is not.
- **Verdict:** Go (author, 2026-09-05). **Kill:** a new standalone app — no
  external users, and the author did not use the existing app in either
  manuscript, which is stated here against interest.

## Why this phase — three lessons and one contradiction

1. **Claim form beats search quality.** The survey's contribution narrowed six
   times in four days because it was a negative existence claim ("no one has
   done X"), which better searching always falsifies; more engineering made it
   worse. The fix is to state what was built. `audit-claim-positioning.py`
   (unsourced-keyword, uncited-method, dangling-entry, bare-novelty) is that
   lesson as a tool — but it recognises citations only as LaTeX `\cite{}`;
   on a Markdown/Harvard thesis workspace every term reads as unsourced.
2. **A citation key and a sentence are separate objects.** See "Unsolved"
   above. The closest existing code is the E1 quote-fidelity grader
   (`e1/graders.mjs`), which already string-matches quoted spans against the
   text the model was shown.
3. **Measure prose; never judge it by feel.** Distribution over count, the
   manuscript's own bibliography as the only baseline, stop at the boundary,
   re-measure everything after every round. This is Advisory by nature and
   stays so.

**Contradiction to resolve:** `80827f8` added a lightweight author-control
profile (three Markdown files, scaffold + structural checker) whose
*approval state lives in agent-editable Markdown*. v0.1 §1.3 rejected exactly
that as a gate after an agent self-approved a full packet. Both things are
now in the tree (the profile under `archive/skills/thesis-control/`), so the
disposition must be explicit.

## Scope, in order

1. **Author-control disposition — decided: A.** promote the
   lightweight profile as *Advisory assets* — templates to
   `references/author-control/`, the checker to
   `scripts/check-author-control.py` (stdlib), and one paragraph in
   `edit-contract` naming `00_AUTHOR_INTENT.md` as the project-level intent
   card above per-edit spine cards. Its approval field is *display*, never
   authority; in the app, authority stays harness approval events. **B**:
   keep it archived, reference-only. Either way it is never a gate on the
   skills surface, and no new skill is created.
2. **Audits join the `audit` skill** as categories E (claim positioning) and
   F (prose fingerprint — only when a baseline corpus of the project's own
   references exists), in that order: positioning before style, because
   style is repairable after review and positioning is not. Add
   `references/prose-polish-method.md`, the tool-neutral distillation of the
   polish method (preconditions, order, stop rules), with no project names.
   The two scripts **stay in `scripts/`**: the author's live polish playbook
   depends on that path.
   - Prerequisite: `audit-claim-positioning.py` gains Harvard author-year
     recognition for Markdown (the same two forms the guards' extractor
     accepts), red-first tested, so category E is meaningful on a thesis
     workspace and not only on a LaTeX paper.
3. **Enforced pre-export gate (app surface) — decided: (a)+(b).** Export becomes a profile
   tool (`export_docx`, wrapping the existing `convert_to_docx.py`) so a
   guard can gate it deterministically — shell-command inspection is not a
   seam. Denial `EXPORT_SOURCES_UNRESOLVED` fires when (a) any author-year
   citation under `chapters/**` lacks a lint-conforming notes file
   (whole-corpus notes-before-chapters), or (b) a `.bib` exists and has
   dangling or uncited entries. On the skills surface the `export` skill
   runs the same check first and says plainly that there it is Advisory.
4. **Sentence-level citation fidelity audit** —
   `scripts/audit-citation-fidelity.mjs`, reusing `e1/graders.mjs` so the
   audit and the instrument measure the same thing and cannot drift. Per
   citing sentence: quoted spans must appear verbatim in the source's notes
   (or its `pdftotext` when present); page references must land on the
   cited page; a sentence sharing no key term with the source's notes is
   flagged **low-confidence**. That flag ships labelled *experimental*
   until a false-positive rate has been measured on real notes — a proxy
   metric is not evidence until it has been hand-sampled. **What it does
   not do:** detect semantic inversion. The survey's three inverted
   sentences would pass a verbatim check; catching those still requires
   reading, and the tool must say so in its own output.

## Gates (E0 unless marked)

- Red-first tests: the export guard denial in the testkit tier plus one
  live e2e scenario; author-year recognition in the positioning audit; the
  fidelity audit's grader reuse, plus a fixture containing a known inversion
  that the tool is *required to miss* — an honesty test pinning the
  documented limit.
- Catalogue invariants hold: 9 skills, description-collision test green,
  T50 single-tree test green, `.claude/skills` has exactly nine entries
  after every merge (the `68bae2c` merge silently revived a retired
  directory; this is now a checked condition, not a hope).
- Docs: `guards/README.md` gains the export row with its "what this does
  not do"; the `audit` skill documents category order and why.
- The low-confidence flag's false-positive measurement needs the author's
  real notes (author-dependent); until it exists the flag stays
  experimental and no README sentence implies otherwise.

## Explicitly outside P4

- #33 (skill discovery scope) and #34 (guard root per session): app
  correctness, tracked on their own, not charged to this budget.
- #35 (E2) and #36 (E1 real lane): author-executed evidence; P4 changes
  nothing about them and claims nothing from them.
- #37 (structured-fact writer): still behind the harness-pin tripwire.
- No new skill; no standalone app; no relocation of the two audit scripts;
  no claim that any audit judges scientific soundness or catches inversion.

## Sessions and budget

Session 1: items 1–3. Session 2: item 4 and docs. Two sessions; the §12
standing rule applies — thesis progress outranks toolkit progress, and E2
(#35) remains the gate that decides the product's shape, not this phase.
