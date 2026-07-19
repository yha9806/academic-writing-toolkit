# Verification Report

## Canonical Candidate

- Product commit: `d0dbd625e0724597189eff86e7d23a74c3bbd5d8`.
- Plugin tree: `8cec435b8454eb99d4162bf741cb550b8d1cc6bd`.
- App tree: `f2ececd3089ef2073fab9f4ce26e2b9375254093`.
- Remote baseline before this candidate: `c81c907a6c4653aec93e1ad298e3aab2027023ac`.
- Previous release baseline: `v0.4.0` at `cd7fbb5bd7dd1e9af3c9079e85a6af8e1c1b8ab0`.

Product artifacts are anchored to the product commit above. This packet changes
release metadata only. Its own commit SHA is recorded in the PR or release
handoff after commit creation and is intentionally not embedded here.

## Verified Local Evidence

Checks run on 2026-07-18:

- `scripts/check-plugin.sh` passed.
- `scripts/check-skills-only-submission.py` reported 21 Skills, five positive
  cases, and three negative cases.
- OpenAI Skill Creator `quick_validate.py` passed for all 21 packaged Skills
  and again for all 21 Skills extracted from the candidate plugin ZIP.
- `npm test` passed 12 of 12 App tests, including the Windows/POSIX Python
  interpreter resolver.
- `npm audit --omit=dev --audit-level=high` reported zero vulnerabilities.
- `scripts/audit-public-content.py --base-dir . --json` reported zero issues.
- Demo citation, reference, evidence-review, release-packet, and thesis-control
  validators reported no blocking issues.
- Segmented Windows Git Bash runs passed 142 non-platform regression cases.
  Seven symlink or TTY-sensitive cases (`T2`, `T9`, `T10`, `T32`, `T42`,
  `T109`, and `T124`) require the Linux PR workflow.
- `T152` passed and confirmed that two consecutive builds from one immutable
  ref produce byte-identical source and plugin archives.
- The source candidate ZIP SHA-256 is
  `08c5a7ee3b2683765a382caff77304bec55cd038d514d88c1a6c582b14361802`.
- The plugin candidate ZIP SHA-256 is
  `3dd9d6f07d6c3a5d93c49d1b0bd4924c11e541b1009c805cab524a72cd3b3f21`.
- Deterministic screenshot regeneration reproduced:
  - workflow:
    `32b78b450649e84d83e0636b328157e57f397fbdd6fe2bec44a0ec077fb05c92`;
  - revision control:
    `494bcb6be79b482bf5bbf020fcb5c2f7fe675b858de899be9641b012a10b3336`.
- Independent diff reviews passed. The remaining production-drift warning is
  that the hosted App was observed at version `0.3.2`, not `0.5.0`.

The 21 Skill validations are package-structure evidence, not OpenAI approval.
The five positive and three negative rows are statically valid case
definitions, not completed forward-test outcomes. Local App tests do not prove
that the hosted App has been redeployed.

## Gates Not Yet Established

- The candidate branch is not pushed and Linux PR CI has not run because the
  local GitHub CLI session is not authenticated.
- The final `main` commit and annotated `v0.5.0` tag do not yet exist.
- Final source and plugin ZIPs must be rebuilt from that tag. Candidate hashes
  above describe the product commit and must not be copied to a different ref.
- The eight reviewer prompts have not been forward-tested against the exact
  final ZIP with tester, date, and SHA-256 recorded.
- Verified publisher identity, developer-name alignment, Apps Management
  Write, regions, policy fields, exact ZIP upload, Submit for Review, review
  approval, and post-approval Publish remain owner-controlled.
- The hosted ChatGPT App must not be described as deployed at `v0.5.0` until
  its runtime converges and the hosted checks are repeated.
