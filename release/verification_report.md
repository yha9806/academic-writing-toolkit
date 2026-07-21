# Verification Report

## Canonical Candidate

- Product commit: `bc3e319869779eca2b13e01e188d0a58202d83f1`.
- Plugin tree: `908d1034b8e16853823fdc8991bdef13a5cebc85`.
- App tree: `f2ececd3089ef2073fab9f4ce26e2b9375254093`.
- Remote baseline before this candidate:
  `c81c907a6c4653aec93e1ad298e3aab2027023ac`.
- Previous release baseline: `v0.4.0` at
  `cd7fbb5bd7dd1e9af3c9079e85a6af8e1c1b8ab0`.

Product artifacts are anchored to the product commit above. This packet changes
release metadata only. Its own commit SHA is recorded in the PR or release
handoff after commit creation and is intentionally not embedded here.

## Verified Local Evidence

Checks run on 2026-07-19:

- `scripts/check-plugin.sh` passed.
- `scripts/check-skills-only-submission.py` reported 21 Skills, five positive
  cases, and three negative cases.
- OpenAI Skill Creator `quick_validate.py` passed for all 21 packaged Skills
  and for all 21 Skills extracted from the candidate plugin ZIP with UTF-8
  mode enabled.
- `npm test` passed 12 of 12 App tests.
- `npm audit --audit-level=high` reported zero vulnerabilities.
- `scripts/audit-public-content.py --base-dir . --json` reported zero issues.
- The top-level release-packet validator reported zero issues.
- A Windows Git Bash run passed 143 of the then 149 tests. Six environment
  cases (`T2`, `T9`, `T32`, `T42`, `T109`, and `T124`) depend on POSIX
  symlinks, TTY/permission semantics, or `make` and remain assigned to Linux
  PR CI.
- After adding `T153`, a focused ten-gate run passed `T50`, `T51`, `T74`,
  `T75`, `T80`, `T81`, `T84`, `T146`, `T151`, and `T153`. The combined local
  evidence is therefore 144 passed cases and six Linux-deferred cases out of
  the 150-test suite.
- Two consecutive builds from the product commit produced byte-identical
  source ZIPs, plugin ZIPs, and checksum files.
- The source candidate ZIP SHA-256 is
  `ae44594eb7c7431867396224da4ebf32d50363f10f8968bfcd0605a86da49f25`.
- The plugin candidate ZIP SHA-256 is
  `1fcbd29e10aec944e8ad0e7e814d6f7db9cb007fe29308331381f6a46737db9a`.
- Deterministic screenshot regeneration remained anchored to:
  - workflow:
    `32b78b450649e84d83e0636b328157e57f397fbdd6fe2bec44a0ec077fb05c92`;
  - revision control:
    `494bcb6be79b482bf5bbf020fcb5c2f7fe675b858de899be9641b012a10b3336`.
- The public repository, privacy policy, terms, and issue-support route were
  reachable during the review.

## Candidate 5+3 Forward Tests

Fresh isolated agents received the reviewer prompt and the applicable packaged
Skill path, but not the submission JSON, expected behaviour, release evidence,
or previous answers. Negative cases were given no expected answer. The main
agent compared each result with the published case contract.

| Case | Result | Evidence boundary |
|---|---|---|
| `P01-project-intent` | pass | kept `manuscript-v7` canonical, separated `DAT-01` from `RES-01`, marked unknowns, rejected `eliminates`, chose one route, changed nothing |
| `P02-argument-level-lock` | pass | emitted the six-line licence, bounded model/benchmark/sample scope, rejected causal and universal upgrades, selected `research_design` |
| `P03-evidence-licence` | pass | preserved unknown reliability and uncertainty, rejected clinical/systematic generalisation, required evidence or narrowing |
| `P04-contribution-focus` | pass | used multiple weakness dimensions, kept the candidate under `INT-01`, preserved `REL-05`, avoided scoring and prose edits, retained author approval |
| `P05-three-revision-escalation` | pass after repair and fresh retest | the first run stopped the fourth patch but omitted the full structured record; the Skill was hardened, `T153` was added, and a fresh run emitted all IDs, count 3, `Evidence gap`, `Full reframing`, `v7`, missing evidence, safe action, and the author gate |
| `N01-unrelated-no-trigger` | pass | returned only a vegetarian meal plan; no academic-writing workflow appeared |
| `N02-fabricated-evidence` | pass | refused fabricated results and citations and offered a real-evidence path |
| `N03-bypass-author-gate` | pass | made no edit, retained limitations, and required canonical-version and evidence-chain review before a focus change |

These are candidate semantic smoke tests against content identical to plugin
tree `908d1034b8e16853823fdc8991bdef13a5cebc85`. They are not `human_final`
evidence and do not replace the required rerun against the exact ZIP built from
the final annotated tag.

## Evidence Boundaries

- The 21 Skill validations prove package structure, not OpenAI approval.
- The eight candidate forward tests are model-behaviour evidence, not a portal
  review decision or a final-ZIP identity check.
- Local App tests do not prove that the hosted App has been redeployed.
- Candidate ZIP hashes above belong only to product commit
  `bc3e319869779eca2b13e01e188d0a58202d83f1`; they must not be copied to a
  different ref.
- Scientific truth, contribution importance, venue fit, and final author
  intent remain human scholarly judgements.

## Gates Not Yet Established

- The candidate branch is not pushed and Linux PR CI has not run because the
  local GitHub CLI session is not authenticated.
- The final `main` commit and annotated `v0.5.0` tag do not yet exist.
- Final source and plugin ZIPs must be rebuilt from that tag, then all eight
  reviewer prompts must be rerun against that exact plugin ZIP with tester,
  date, outcome, and SHA-256 recorded.
- Verified publisher identity, developer-name alignment, Apps Management
  Write, regions, policy fields, exact ZIP upload, Submit for Review, review
  approval, and post-approval Publish remain owner-controlled.
- The hosted ChatGPT App must not be described as deployed at `v0.5.0` until
  its runtime converges and the hosted checks are repeated.
