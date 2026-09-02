---
name: self-review
description: Review the user's own manuscript, paper, thesis chapter, rebuttal, or release packet with clean-room anti-contamination controls and, when needed, an unfamiliar-reader comprehension gate. Use for internal review, readiness checks, reviewer simulation, or claim-evidence self-audit where prior chat memory and unstated context must not become evidence.
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
---

# /self-review - Clean-Room Manuscript Self-Review

## Purpose

Audit the user's own work without letting memory, prior chats, unstated project knowledge, or the model's background knowledge become evidence.

The governing rule is:

```text
self-review truth = explicit review packet + source anchor
```

Use `/argument-governance` first when the manuscript needs a formal intent, contribution, claim, and evidence map.

## Codex-Only Baseline

Complete self-review with Codex, the review manifest, allowed sources, and the bundled packet checker. Do not require Gemini, gemini-agent, a second model, or a subagent. If an external review is available, keep it in `Reviewer-risk inference` or advisory notes and never use it as source support.

If `/argument-governance` is unavailable, manually extract the same clean-room argument spine from manifest-listed sources only.

## Enhanced Advisory Mode

If the manifest and the user explicitly allow an API-key-backed advisory review, Codex may run or incorporate a second-model pass after the clean-room self-review packet is valid.

Rules:

- the base clean-room review must be possible without the external call
- API keys must be read from environment variables only
- the manifest may name `api_key_env_var`, but must never store the key value
- only manifest-approved source subsets may be sent externally
- external findings must be placed under `Reviewer-risk inference` or advisory notes
- external findings must be re-grounded against allowed sources before becoming revision actions
- unsupported external comments stay unsupported

## Core Rules

1. Use only files listed in the review manifest.
2. Treat prior chat memory, unstated project assumptions, model background knowledge, and unlisted notes as forbidden evidence.
3. Split every finding into `Supported by packet`, `Not supported by packet`, or `Reviewer-risk inference`.
4. Every supported finding must include a source anchor.
5. Do not repair missing evidence by remembering earlier conversations.
6. Do not treat generated reviews, agent drafts, or reviewer simulations as final evidence.
7. Do not edit the manuscript until the user approves specific revision actions.
8. Do not treat an unavailable external review tool as a blocker.

## Required Packet

The preferred layout is:

```text
review_packet/
  review_manifest.yaml
  manuscript.md or manuscript.pdf
  references.bib
  evidence/
  figures/
  tables/
  claims/
```

Read `references/clean_room_protocol.md` before reviewing. Read `references/self_review_packet_schema.md` before creating or validating a packet.

## Workflow

### 1. Validate The Clean-Room Packet

Resolve the bundled helper at `scripts/check_self_review_packet.py` relative to this `SKILL.md`, then run:

```bash
python3 {skill_dir}/scripts/check_self_review_packet.py review_packet --json
```

If the packet is missing or invalid, report the issue before reviewing.

### 2. Build The Source-Bounded Reading List

Read only manifest-listed files. If a needed file is not listed, ask whether to add it to the manifest or mark the issue as unsupported.

### 3. Extract The Argument Spine

From the packet only, extract:

- stated intent
- named gap
- contributions
- main claims
- evidence anchors
- limitations
- reviewer-risk areas

### 4. Run Self-Review Checks

Check:

- gap-contribution alignment
- claim hierarchy
- claim-evidence fit
- evidence balance
- unsupported or overextended claims
- missing limitations
- reviewer attacks with weak defenses
- internal consistency and submission blockers

### 4.5 Run The Unfamiliar-Reader Gate When Required

For an important version, submission-readiness claim, or revision contract that
requires a comprehension check, read
`references/reader_comprehension_gate.md`. Prepare a packet containing only the
title, abstract, Figure 1, and main Results summary table, all of which must be
manifest-listed. Record the unfamiliar human reader's answers to the five
questions and compare them with the author-approved intent and argument
baseline.

Only an actual unfamiliar human response can produce `passed`. A model
simulation, author explanation, or response from a collaborator with prior
project knowledge remains `advisory_only`. If no eligible response exists,
record `not_run`; do not claim that the human gate passed.

### 5. Write A Clean-Room Report

The report must separate:

- `Supported by packet`
- `Not supported by packet`
- `Reviewer-risk inference`

Do not merge these categories.

## Output Pattern

```text
## Clean-Room Self-Review

### Packet Boundary
- Manifest:
- Allowed sources:
- Forbidden sources:

### Supported By Packet
| Finding | Source anchor | Severity | Action |

### Not Supported By Packet
| Claim or need | Missing source | Risk | Action |

### Reviewer-Risk Inference
| Risk | Basis in packet | Why it matters | Action |

### Unfamiliar-Reader Gate
- Packet:
- Reader independence:
- Decision: passed / failed / not_run / advisory_only
- Misunderstood or missing functions:
- Required next action:

### Revision Actions
| Priority | Action | Requires new evidence? |
```

## Stop Conditions

Stop and report a blocker if:

- no review manifest is provided
- the user asks to rely on previous chat or memory for evidence
- a central claim needs a source not listed in the manifest
- the packet validator reports missing allowed files
- the user asks to mark unsupported claims as supported
- a required unfamiliar-reader gate lacks an eligible human response but the manuscript is being described as having passed it
