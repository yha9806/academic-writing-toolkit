# OpenAI Skills-Only Plugin Submission Packet

This is the canonical handoff for submitting Academic Writing Toolkit `v0.5.0`
as a **skills-only plugin**. It intentionally separates this submission from
the repository's optional MCP-based ChatGPT App.

Official references:

- [Build plugins](https://learn.chatgpt.com/docs/build-plugins)
- [Submit plugins](https://learn.chatgpt.com/docs/submit-plugins)
- Submission portal: <https://platform.openai.com/plugins>

OpenAI currently accepts skills-only plugins. An MCP server, hosted endpoint,
domain challenge, or app tool scan is not required for this route.

## Candidate Identity

- Listing name: `Academic Writing Toolkit`
- Package name: `academic-writing-toolkit`
- Submission type: `Skills only`
- Candidate version: `0.5.0`
- Repository: <https://github.com/yha9806/academic-writing-toolkit>
- Plugin root: `plugins/academic-writing-toolkit/`
- Manifest: `plugins/academic-writing-toolkit/.codex-plugin/plugin.json`
- Final release ref: annotated tag `v0.5.0`, created only after the exact
  candidate passes CI and the local release gates
- Machine-checkable portal packet:
  `submission/openai/skills-only-submission.json`

Do not upload a working branch or reuse the historical `v0.4.0` archive. The
final ZIP, Git tag, checksum, release notes, and verification record must all
refer to the same tested tree.

## Listing Fields

| Portal field | Candidate value |
|---|---|
| Name | Academic Writing Toolkit |
| Short description | Organise research, govern claims and evidence, and revise without drift. |
| Category | Productivity |
| Website | <https://github.com/yha9806/academic-writing-toolkit> |
| Support | <https://github.com/yha9806/academic-writing-toolkit/issues> |
| Privacy | <https://github.com/yha9806/academic-writing-toolkit/blob/main/docs/privacy.md> |
| Terms | <https://github.com/yha9806/academic-writing-toolkit/blob/main/docs/terms.md> |
| Availability | All supported regions, pending final owner confirmation |

The long description and release notes live in
`submission/openai/skills-only-submission.json` and must match the final portal
copy.

## Starter Prompts

Each prompt is non-empty and no longer than 128 characters:

1. `Map my research gap, claims, evidence, contributions, and innovation before revising.`
2. `锁定论文论证层级和证据许可，判断贡献侧重，再选择下一项受控工作流。`
3. `After three failed revisions, stop and diagnose drift before another edit.`

`make plugin-check` rejects prompt-count, prompt-length, or submission-packet
drift.

## Included Skills

The package contains exactly 21 Skills:

1. `academic-writing-assistant`
2. `argument-governance`
3. `audit`
4. `evidence-review`
5. `export`
6. `human-eval-handoff-repair`
7. `integrate`
8. `logic-review`
9. `manuscript-reframe`
10. `map`
11. `note`
12. `peer-review`
13. `progress`
14. `read`
15. `release-governance`
16. `revision-escalation`
17. `self-review`
18. `style`
19. `thesis-control`
20. `verify`
21. `verify-refs`

The canonical sources are under `.claude/skills/`. The plugin copies are
generated with `make plugin-sync`; do not edit the copies independently.

## Reviewer Test Cases

The exact reviewer prompts, expected behaviours, fixture declarations, and
result shapes are stored in
`submission/openai/skills-only-submission.json`.

The five positive cases cover:

| ID | Coverage | Expected primary Skill |
|---|---|---|
| `P01-project-intent` | canonical project state and one controlled route | `argument-governance` |
| `P02-argument-level-lock` | field gap, paper contribution, finding, and extrapolation | `argument-governance` |
| `P03-evidence-licence` | strongest licensed claim and missing research evidence | `argument-governance` |
| `P04-contribution-focus` | evidence-balanced focus review and author gate | `argument-governance` |
| `P05-three-revision-escalation` | stop before a fourth patch and diagnose the failure | `revision-escalation` |

The three negative cases cover:

| ID | Mode | Expected boundary |
|---|---|---|
| `N01-unrelated-no-trigger` | `no_trigger` | unrelated meal planning does not invoke the plugin |
| `N02-fabricated-evidence` | `safe_fallback` | no fabricated results or citations |
| `N03-bypass-author-gate` | `safe_fallback` | no unapproved focus change or boundary deletion |

The static validator confirms exactly five positive and three negative cases,
unique coverage, valid Skill references, inline public-safe fixtures, and
absence of private local paths. The maintainer must still forward-test all
eight prompts against the final ZIP and record the date and outcome.

## Data And Policy Boundary

- The plugin operates on files the user selects in the current local project.
- It requires no Academic Writing Toolkit account or hosted service.
- It does not treat generated reviewer text, invented references, or missing
  values as scholarly evidence.
- Online reference verification is optional and runs only when the user
  explicitly requests it.
- Project reframing, contribution-focus changes, and post-escalation edits keep
  an explicit author gate.
- Privacy and terms must continue to match the final bundle behaviour.

The machine-checkable policy statements are in the submission JSON. OpenAI's
review remains authoritative; this repository validator does not certify
policy approval.

## Account And Owner Gates

These cannot be completed by repository automation:

- [ ] The submitting account has **Apps Management Write** access.
- [ ] The publisher has a verified individual or business identity.
- [ ] `author.name`, `interface.developerName`, and the portal publisher name
      match the verified identity.
- [ ] The owner confirms the final region selection.
- [ ] The owner confirms the policy declarations in the portal.
- [ ] The owner uploads the exact tested ZIP and submits it manually.
- [ ] After approval, the owner manually publishes the approved version.

The earlier MCP App record stated that Business verification was incomplete.
That is historical App evidence, not proof of the current skills-only account
state. Re-check the current plugin portal rather than copying the old status.

## Verification And Artifacts

Run from the repository root:

```bash
make plugin-sync
make plugin-check
make chatgpt-app-check
make test
python3 scripts/audit-public-content.py --base-dir . --json
```

Before tagging, also run the Skill Creator `quick_validate.py` against every
packaged Skill with UTF-8 mode enabled.

The final GitHub release must contain:

- `academic-writing-toolkit-v0.5.0.zip`
- `academic-writing-toolkit-openai-plugin-v0.5.0.zip`
- `SHA256SUMS`

Generate all three from the final tested `main` commit. Record the exact SHA,
test results, ZIP contents, and checksums in
`docs/product/v0.5.0-release-readiness.md` and `release/`.

## Separate MCP App Surface

`apps/chatgpt-academic-writing-toolkit/` remains a separate tool-only MCP App
with its own five-tool and 5+3 test packet. It is not imported into this
skills-only submission.

As observed on 2026-07-18, the hosted Hugging Face `/health` endpoint reported
`0.3.2`, so it must not be described as a live `v0.5.0` deployment. Redeploying
and resubmitting that App is a separate owner-controlled release.
