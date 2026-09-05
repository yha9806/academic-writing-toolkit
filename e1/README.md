# Paired-source evidence instrument

The offline lane checks the instrument with scripted synthetic arms (E0).
Real model sessions over three chosen PDFs produce E1 results. Neither is
the author's E2 chapter cycle. Model quality is reported as observed; a
transport or process failure is an incomplete run, not a favourable model
result. A durable `max-tokens`, `EMPTY_RESPONSE` or guard `blocked` terminal outcome is a
measured model failure and remains in the sample, with its task outcome
displayed beside the four metrics.

## Install and run offline

Requires Node 22.12+ or 24+ and the exact dependencies in the lockfiles:

```sh
npm ci --prefix guards
npm run build --prefix guards
npm ci --prefix e2e
node e1/run-e1.mjs
```

## Run with real sources

1. Copy `pdfs.example.json` to `pdfs.json` and identify exactly three
   different PDFs by SHA-256. IDs must be unique, lowercase and path-safe.
   Paths resolve relative to the manifest file. Select 1–15 physical PDF
   pages per source, not the page numbers printed inside an article.
2. Install Poppler's `pdftotext` on PATH. Scans with no extractable text
   need an author-prepared text/OCR source; the producer does not invent it.
3. Select a provider and set only its credential locally. DeepSeek uses
   `DEEPSEEK_API_KEY`; Anthropic uses `ANTHROPIC_API_KEY` and requires an
   explicit `--model` value. The existing DeepSeek profile default is
   `deepseek-v4-flash`; `--model` can select another available model.
4. Run the keyless preflight (it checks whether a key exists but makes no
   model request), inspect its result, then run the real lane:

```sh
node e1/run-e1.mjs --real --check --manifest e1/pdfs.json --provider deepseek
node e1/run-e1.mjs --real --manifest e1/pdfs.json --provider deepseek
```

For Anthropic, append `--provider anthropic --model <chosen-model>` to
both commands. No key is read from a project file or requested in chat.

An already installed, tool-capable Ollama model can run the same real lane
locally. Select it explicitly with `--provider ollama --model <local-tag>`;
`--base-url` defaults to `http://127.0.0.1:11434/v1` and accepts only loopback
HTTP endpoints. Preflight checks the server version, installed model digest,
tool capability and actual `num_ctx`/`num_predict` configuration without a
generation. Create a dedicated local alias with `num_ctx` at least 16384 and
an explicit `num_predict` of at least 1024, below the context limit. Merely
declaring a large client context does not enlarge the server's context.
The adapter receives a content-free local placeholder credential; no cloud
key is inherited. Cloud-backed Ollama models are refused. Local model and
server details are retained in the result; this evidence describes that
model, not untested cloud routes.

Both arms use the same chosen model and exclude user-level skills. Each
source has a notes task and a draft task in each arm: up to 12 headless
sessions in total. Each session can make multiple provider requests;
`--timeout-ms` (1000–600000, default 600000 per session) is a time bound,
not a currency or token cap. An infrastructure failure stops subsequent sessions;
there is no automatic paid retry.

`--resume <saved-run-directory>` supports one narrow continuation: a run
that stopped during its first skills arm with durable model-failure
outcomes. It verifies identical inputs, model settings and grader/reader
hashes, reuses the original log and file state, and runs only the remaining
tasks. It never re-generates those failed observations. Both result directories
are retained and the continuation records the original evidence hashes.

## Inspect and share results

Every run creates a new `results/e1-<lane>-<timestamp>/` directory:

- `metrics.json` and `results.md` are produced by the script.
- Each source/arm retains its notes, draft, process statuses and plaintext
  session logs. The source PDF is not copied into the result package.
- Input hashes, page windows, selected model, pinned harness and
  implementation-file hashes bind the comparison to what actually ran.
- Source opening is established from successful `read_pdf` results in the
  logs. Quotes are checked against the returned text. Merely listing a PDF
  in the manifest does not count as reading it.
- An incomplete run exits nonzero and has `evidenceClass: null`. Keep it
  visible as a diagnostic result; do not mix it into an efficacy table.

The directory is gitignored. Logs and outputs may contain source text and
local paths: review them before sharing. Publish measured results with the
exact producer revision and harness version; do not hand-edit metric tables.
The offline script deliberately writes contrasting fixture outputs. Its
numbers are not evidence that AWT improves real academic work.
