# Workbench PR review verification — 2026-09-05

This proposal starts from `main` at `8e5f116`. It contains no E1, Windows dsh
or reference-licence changes from PR #40 and does not change the root
README's supported-product table. The Workbench remains subject to the
section 13 retirement and the pending product decision in #39.

## Reproducing the two reported failures

The original `5abe446` tests passed without a tokenizer on Windows. Installing
`tiktoken 0.14.0` with `o200k_base` reproduced both reported failures on the
same machine, without installing document extras:

- A one-paragraph revision reused 285 regions, failing the fixed `> 290`
  assertion. The changed batch contained 39 regions, so reusing exactly
  `324 - 39 = 285` was correct. All 323 unchanged source regions were mapped,
  but the other 38 regions in the changed batch still required a new check.
- Every chapter had complete text coverage, 81/81. The abstract fitted in
  two text batches and therefore did not receive a separate chapter summary
  under the existing three-batch aggregation rule. The combined assertion
  incorrectly required such a summary from every chapter.

The [structured reproduction](pr-review-tokenizer-reproduction-2026-09-05.json)
records those counts. These are deterministic mock reviews, not model quality
measurements. No runtime implementation was changed for these failures.

The revised tests check the exact reusable set implied by the unchanged
batches, use an explicit smaller request budget when exercising chapter
aggregation, check full source coverage separately from summary availability,
and cover both efficient token estimates and jobs needing no extra chapter
aggregation. No smaller arbitrary reuse threshold replaces the old one.

## Local checks

| Environment | Result |
| --- | --- |
| Python 3.12, no document extras or tokenizer | 72 tests; 63 passed, 9 optional/platform skips |
| Python 3.12, tiktoken, no document extras | 72 tests; 63 passed, 9 optional/platform skips |
| Python 3.12, PDF dependencies, no tokenizer | 72 tests; 71 passed, 1 Windows POSIX-permission skip |
| Runtime source files | 17 files match the originally reviewed source bytes |
| JavaScript syntax | Both browser scripts passed Node syntax checks |
| Public metadata | Local task title/ID removed; three machine-specific path fields redacted |

The two sanitised historical installation reports retain their measured
result values and now identify their redacted fields. `INTEGRATION.json`
describes source hashes as pre-packaging hashes, not current artifact hashes.
Historical screenshots are retained; no new visual acceptance is claimed.
The configured Gemini advisory call was unavailable (`fetch failed`).

The revised CI matrix includes Ubuntu Python 3.9 and 3.11 without document
extras, macOS Python 3.11 without extras, an explicit tokenizer leg, and
Linux/Windows document-extras legs. Current results are attached to the PR;
local results alone do not assert that remote CI passed.

## Real-paper attempt

The complete 24-page ALCE PDF was imported and reviewed with the actual local
Qwen model under a declared 24-call budget. The [attempt record](alce-real-document-attempt-2026-09-05.json)
reports `budget_paused`: 24 text batches checked 1,056 of 5,822 regions from
a 486-batch initial text plan. No chapter or cross-section pass was completed,
no bad outcome was retried, and there are no author quality judgements.
This practical fragmentation/budget limitation is a reason to keep the PR
as a proposal. It does not complete the real-user acceptance gate in #39.
