# Three-source local E1 pilot: protocol fixed before generation

This is an exploratory execution of issue #36, not the author-operated E2
chapter cycle. Source selection, page windows, model and the existing four
graders were fixed before viewing any model-generated notes or drafts.

## Inputs

Three public ACL papers about citation support and factuality were chosen
for their relevance to AWT's reading and citation tasks and their extractable
PDF text. They form a convenience sample from a single field and year.
Each arm sees physical PDF pages 1-5 of each paper; printed proceedings page
numbers are different. No author manuscript or private source is included.

| ID | Publisher record | SHA-256 of downloaded PDF |
| --- | --- | --- |
| gao2023-alce | [Gao et al. (2023), Enabling Large Language Models to Generate Text with Citations](https://aclanthology.org/2023.emnlp-main.398/) | ae9868f07f0f7ffaae5346778f79b7827d9ec6b13b1e6aae4dff6b2ffc37a2e1 |
| min2023-factscore | [Min et al. (2023), FActScore](https://aclanthology.org/2023.emnlp-main.741/) | 8486fe22a15aaf3fe2e1d7043d169000600205dde9c601c9fd31c0dd6f7380e9 |
| liu2023-verifiability | [Liu et al. (2023), Evaluating Verifiability in Generative Search Engines](https://aclanthology.org/2023.findings-emnlp.467/) | 2ca08791359f27082d6210b4dec0ed84fe8c7ad6dc70fa57030f1d0066a28c87 |

PDFs and the runnable `e1/pdfs.json` remain local and gitignored. Only the
selected PDF and the ordinary blank notes template enter each fresh
experimental workspace. Preparation metadata and previous results do not.

## Model and environment

- Harness: published `@deepseek-ai/dsh@0.1.0-rc.6`, with locked dependencies.
- Backend: local Ollama 0.33.2, OpenAI-compatible Chat Completions through
  the existing dsh pi-ai adapter; no substitute scripted model.
- Installed base: `qwen3-vl:4b-instruct`, 4.4B, Q4_K_M, advertised tool support.
- Experiment alias: `awt-e1-qwen3vl4b-32k:20260905`.
- Alias manifest digest:
  `690ec27bb8e35303029f8bfa1f6f55816f7a63499caf3062d64b671fee001dcd`.
- Explicit server parameters: `num_ctx 32768`, `num_predict 4096`,
  `temperature 0.2`, `seed 20260905`; inherited `top_k 20`, `top_p 0.95`.
- Endpoint: `http://127.0.0.1:11434/v1`. The local alias reuses installed
  weights; it does not change the base model or download a new model.
- Operating system: Windows; Node 24.15.0; local Poppler 26.07.0.

## Procedure and analysis

Run the producer's existing two tasks (notes, then approximately 300-word
draft) once in each arm for each source: three sources, two arms, two
headless sessions per arm, at most 12 sessions. Each arm gets a fresh
workspace and DSH_HOME. Both use the same actual model and fixed input.
The skills arm includes the AWT persona, guards and catalogue; the plain
arm excludes them. This measures the combined AWT profile, not an isolated
causal effect of skill wording.

The source order is Gao, Min, Liu; skills precedes plain for each source.
This is not randomised or blinded. Model sampling uses the same fixed seed
and parameter configuration in both arms. There are no replications or
significance tests; do not generalise from the three pairs to all papers,
models, or authors, or interpret latency as a controlled performance test.

Use the existing machine graders without post-outcome changes: normalised
verbatim quotation matches, physical-page matches, shipped notes lint, and
the conservative citation extractor's unopened-source count. The quote
extractor has limited syntax coverage; retain uncited spans and the full
artifacts for interpretation. Zero detected quotations or citations is not
perfect fidelity. These metrics do not judge semantic entailment or whether
the paper's argument is sound.

The producer alone writes the measured table and metrics JSON. Preserve all
session logs, drafts, notes, input/model digests and implementation hashes.
An execution failure stops the run and yields diagnostic evidence with no
E1 classification. Do not selectively rerun a poor model outcome. If a
transport or harness defect requires repair, preserve that failed run, name
the repair, and begin a fresh full comparison. Per-session timeout is 600
seconds; the local provider retry count is zero.

```powershell
node e1/run-e1.mjs --real --check --provider ollama --model awt-e1-qwen3vl4b-32k:20260905
node e1/run-e1.mjs --real --provider ollama --model awt-e1-qwen3vl4b-32k:20260905
```
