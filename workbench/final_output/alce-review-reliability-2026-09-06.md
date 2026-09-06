# ALCE review reliability: complete execution, quality gate still open

The final candidate completed the 24-page ALCE PDF in **53 local model calls**:
44 text batches, 4 chapter batches and 5 cross-section batches. All 5,787 extracted
text blocks appeared exactly once, in source order, in completed text batches.
Every completed batch contains a nonempty source-bound observation. The model
used was the same local `awt-e1-qwen3vl4b-32k:20260905` (4B) as the earlier attempt.
This is an agent-operated technical experiment, not a completed real-author cycle.

## What changed

- Models choose request-local source IDs. AWT resolves them to unchanged offered
  text and canonical locators; no fuzzy quote repair or invented replacement text.
- Empty or whitespace observations and unknown IDs are rejected. Model-written
  whole-paper summaries are replaced by a deterministic, batch-scoped heading
  followed by the model's source-bound observations.
- Observations carry their original source anchors into chapter/cross planning,
  including when the model extracts no claims. Retrieval remains bounded.
- Local Ollama uses native JSON schema for new jobs unless explicitly overridden.
  Source-ID protocol v2 permits 1–2 observations, at most two claims and findings,
  and two limitations. Notes have 64-character limits, finding messages 96.
  This reduces output truncation without raising the 1,600-token output budget.
- Rejected complete JSON objects and available usage remain in checkpoints.
  Malformed JSON is not represented as an original empty response. Compact
  progress responses omit the stored raw choices. Old completed results stay
  historical; their protocol is not silently upgraded or reused under a new key.

## Retained experiments

All roots and output files were new. No checkpoint or earlier experiment was
overwritten, no automatic retry occurred, and no hosted provider was called.
These are development iterations on the same paper, not independent replications.

| Candidate | Calls | Completed text / chapter / cross | Outcome |
|---|---:|---|---|
| [Previous planning change](alce-planning-optimisation-2026-09-05.json) | 12 | 11 / 0 / 0 | Invalid quote; ten earlier empty reports |
| [Source IDs v1, prompt transport](alce-review-reliability-2026-09-06.json) | 16 | 15 / 0 / 0 | Required observation-array length rejected |
| [Source IDs v1, native schema](alce-review-reliability-constrained-2026-09-06.json) | 52 | 44 / 4 / 3 | Cross output truncated at the output limit |
| [Source IDs v2, bounded native schema](alce-review-reliability-bounded-2026-09-06.json) | **53** | **44 / 4 / 5** | **Complete technical execution** |

Four earlier development calls used batches 1, 10, 12 and 40 with short source
IDs and a free summary. All selected existing IDs; some summaries still claimed
whole-paper coverage. That observation motivated removing the free summary from
the wire schema. These four calls are separate from the full-paper runs above.

The final run took 130.141 seconds on this local machine. The provider reported
274,040 prompt tokens and 6,258 completion tokens (280,298 total), with usage
present for all 53 calls. Conservative token reservation was 463,851 against
an 800,000 total-token / 80-call ceiling. Input estimate and output caps were
8,000 and 1,600 per call. The two failed intermediate trials each lack provider
usage for their final rejected/truncated request; those calls remain reserved
and are not treated as free. Timings are a single local run, not a latency claim.

The final report contains the source, Python runtime-file hashes, runner hash,
per-call source-map and canonical model-choice hashes, usage and explicit role
overrides. The same source PDF was unchanged after the run. The runner is
[check-review-reliability.py](../scripts/check-review-reliability.py); it requires
a fresh output path and checkpoint root and calls only the named local Ollama.

All 6,670 original PDF region texts and coordinates independently matched the
original attempt. Their canonical SHA-256 remains
`b45b252f803ee30b5220ab705840e1baddba736ef4ec91214d5a55e1976fd7da`.
The final completed-run JSON SHA-256 is
`4905f181ec29d1fc5f1246e51da456a1882762f51fd17ec58edfcdd71be0b1c2`.

Local validation discovered 90 tests: 89 pass / 1 platform skip with PDF extras,
and 80 pass / 10 optional/platform skips in both the no-extras and tokenizer-only
environments. Thirteen new tests cover source choice, duplicate source text,
unknown IDs at all anchor positions, empty and overlong observations, exact
excerpt boundaries, production transport, rejected-response accounting, malformed
JSON handling, output format selection and carrying observations to later stages.

## Source check and remaining limitations

The model returned 105 observations, zero extracted claims and five issue flags.
An agent compared all five flags with their quoted sources; **none was accepted
as a confirmed correction request**. This is an agent screen, not a human rating:

| Flag | Source check |
|---|---|
| Multi-hop scenarios not covered | The cited limitation already acknowledges this; no demonstrated contradiction. |
| Referenced papers not expanded in this context | Bibliography fragments do not establish a manuscript defect. |
| Oracle leads in recall | A reported observation, not an inconsistency or correction. |
| ELI5 failure rate consistent between abstract and conclusion | The selected conclusion excerpts do not contain the claimed matching rate; the cross inference is unsupported. |
| MAUVE/NLI limitations stated | A description of disclosed limitations, not a correction. |

Source choice proves where an excerpt came from, not that the model interpreted
it correctly. Tables remain fragmented in places. Automatic section detection
also groups some appendix material under References. The agent explicitly
classified the visible task/evaluation/modeling sections as methods, human
evaluation as results and limitations as discussion; the JSON lists every override.
These assignments enabled all five configured role pairs, without claiming all
appendix relationships were correctly classified or exhaustively compared.

The five cross batches included 48 / 31 / 61 / 31 / 18 source anchors, with
894 / 456 / 1,334 / 450 / 10 role-pair blocks omitted respectively. These are
overlapping pair-specific counts, not unique unseen text blocks. All text was
sent in the text stage; many possible cross relationships remain unexamined.

A real author still needs to assess usefulness, missed issues and misleading
flags, then perform a revision/review cycle. DeepSeek remains unmeasured here.
PR #41 stays draft, and the root README product-surface table remains unchanged.
Gemini diff review was attempted but unavailable (`fetch failed`); it is not
counted as independent review.

## Publication handling

The public JSON files contain hashes, counters and provider metadata, without
machine paths, Codex task metadata, PDF source text or full model responses.
Original source and complete checkpoints remain local. Earlier frozen evidence
files are unchanged; this follow-up does not turn their failures into successes.
