# Review gap closure: implementation plan

Spec: `docs/specs/2026-09-25-review-gap-closure.md` (draft). Each step lands with a probe or test that was run on the
code before the change and failed there, and a `redcheck.py` mutation for its central rule.

| Step | Spec | What | Verified by |
|---|---|---|---|
| 1 | 4.1, 4.2 | Probe harness `engine/tests/probes/` + `test_probes.py`; the sentence gate judges removed sentences (`--carriers`, numbers, qualifiers); the loop passes the ledger's `必须出现` patterns as carriers and keys a removal by its old text | probe `deleted-question` red before, green after; mutation of the removal rule turns it red; gate text names a removal |
| 2 | 4.3 | Reader packet: `--aux` resolves `\ref`; without it `§(number omitted)` and the instructions say so | probe `packet-refs`: no `§x` in the packet |
| 3 | 4.3 | `check-reader-output.py`: a string `remember` is named as such; `tally-readers.py` refuses to count an unregistered panel | unit tests red before |
| 4 | 4.3 | `tally-readers.py`: repeat-run spread per point, `--compare` inside the noise, recall rank, model-family grouping, blank reader | unit tests on synthetic outputs |
| 5 | 4.3 | Judging: fact sheet and a misattributed grade in the readers skill; an injected set checked before judging | unit test of the injected-set checker |
| 6 | 4.3 | Mechanical repetition between the abstract and the first introduction paragraph; copyable directed questions flagged | unit tests |
| 7 | 4.2, 4.4 | After `feat/scan-coverage` lands: scoped `必须出现`, `承载` listing, universal-negation and "A sig, B not" flags, method sentences beside remaining cues | probes red before |
| 8 | 4.5 | Ring stage `analysis` behind a flag | ring tests; the notch checked at eight stages before the flag is on |
| 9 | 5 | Full writing-loop suite, `scripts/test.sh`, Python 3.8; installed copy checked; pull request | CI on the pull request |

Pushing and opening the pull request wait for the author.
