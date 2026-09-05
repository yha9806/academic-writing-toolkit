# Cross-document reviews, document import and recoverable jobs

Run the commands in this guide from the repository's `workbench/` directory.
See [the component README](../README.md) for installation from the repository root.

These features are in the current source checkout, not the published v0.5.0
wheel. Existing single-file workflows and saved sessions remain available.

## Start the Workbench

```sh
python -m pip install -e ".[documents]"
awt
```

Open the **跨文件 / PDF / DOCX 审阅** link from the homepage, or visit
`http://127.0.0.1:8784/project`. Set the provider and exact model ID as described
in [model provider setup](setup-model-providers.md). Importing, restoring,
previewing and comparing layout do not call a model. Click **开始审阅** to send
the selected review batches to the configured model.

The base installation keeps its zero-dependency text workflows and can extract
DOCX paragraphs, table cells and chart caches using Python's standard library.
The optional `documents` extra adds PDF extraction, page rendering and image
previews. DOCX layout rendering uses an existing LibreOffice installation;
`AWT_LIBREOFFICE` can name its executable. Alternatively, export PDFs from Word
and compare those. No provider API key is needed for local document operations.

## Materials and locators

- Select up to 20 files, 80 MB each and 160 MB in total: PDF, DOCX, TXT, MD, TEX,
  CSV, JSON or BIB. Files must have distinct names.
- PDFs support up to 1,000 pages. Extraction is bounded to 12 million characters
  and 100,000 text blocks per file. Large uploads use sequential 1 MB chunks
  with progress; the browser does not encode the entire manuscript in one request.
- Every imported file is copied locally and bound to a SHA-256 digest. Model
  references must match an actual input block and a verbatim quote.
- Text files retain line numbers. DOCX retains paragraph positions, table
  row/cell positions and the position of embedded images or chart caches.
  DOCX does not have a stable page number until it is rendered.
- With PDFium installed, PDF text retains page numbers and text rectangles in
  PDF coordinates (origin at the lower left). With only pypdf installed, AWT
  retains page text and explicitly reports that geometry is unavailable.
- Nearby same-column PDF lines are conservatively coalesced into bounded text
  regions. Their original per-line rectangles, character offsets and locators
  remain available from **查找原文、定位和未检查内容**. Coalescing keeps literal
  newlines and does not rewrite words or claim to recover semantic paragraphs.
- Scanned pages with no extractable text remain unchecked for text. There is
  no silent OCR. PDF columns, equations, table layout and graphic content need
  the page preview or an explicitly selected image review. DOCX headers,
  footers, comments, complex floating objects and revision views have extraction
  limitations shown alongside the material.
- LaTeX includes, macros, external links and external DOCX relationships are
  not followed. Only selected files are read. Chart caches are reported values,
  not independently recomputed measurements.

## Coverage and claim–evidence index

AWT first groups source blocks by document and chapter and builds bounded text
batches. Review the coverage table before starting; its chapter-category control
can correct headings such as “Chapter 4” to “Methods”.

Each completed batch adds quote-bound claims, evidence links and findings. A
transport success alone is insufficient: schema or quote validation failure
leaves the batch unchecked. A successful model review remains advisory; these
checks do not prove that the model detected every substantive problem.

For documents with more than 80 text regions, the runner adds a chapter phase
for chapters spanning at least three text batches. These reviews use original
quotes from the saved claim index. The subsequent cross-section phase compares
Abstract–Methods, Abstract–Results, Methods–Results, Results–Discussion and
Abstract–Discussion, using local lexical retrieval in both directions. Candidate
selection spans the complete document, including final chapters: at most 80
anchors per chapter and 160 per role enter retrieval. Each resulting model
request stays within the selected profile. Model claims are prioritised, with
distributed source excerpts as a fallback; generated summaries never replace
source evidence. Small jobs retain the simpler existing comparison plan.

The UI lists included and omitted regions, pending batches and missing sections.
This is bounded cross-section comparison, not an exhaustive proof of paper-wide
consistency. Unrecognised headings also receive adjacent-file comparisons when
multiple documents are present. Chapter cards, source search, claims, findings,
images and batch history are paginated; progress polling excludes manuscript
text and image data. A locator opens its full original text and available page
preview without another model call.

Text coverage and image coverage are separate. A paragraph containing a figure
caption does not establish that its figure was inspected. Quotes are validated
locally, while supports/conflicts relationships remain model judgments for the
author to assess. Unlinked claims remain visible in the index.

## Older models and API costs

The job runner uses a small JSON contract in the prompt, a single user input and
ordinary non-streaming API requests. It requires neither tool calling nor
native JSON Schema support, background requests, steering APIs, embeddings or
a second model. Codex still uses its existing CLI schema support.

For a model served only through Chat Completions, choose that protocol
explicitly instead of leaving the OpenAI preset on Responses. For example,
with your account's exact compatible model ID and existing `OPENAI_API_KEY`:

```powershell
$env:AWT_PROVIDER = 'openai'
$env:AWT_PROTOCOL = 'chat-completions'
$env:AWT_MODEL = 'your-account-model-id'
$env:AWT_RESPONSE_FORMAT = 'prompt'
$env:AWT_MAX_OUTPUT_TOKENS = '800'
$env:AWT_SUPPORTS_IMAGES = '0'
awt
```

The Chat Completions adapter sends `max_tokens`. Choose a model/endpoint that
accepts that contract. AWT does not infer protocol support or change it after
a failed request. The cross-document route always uses the prompt JSON
contract; `AWT_RESPONSE_FORMAT` also configures existing single-file reviews.

| Budget profile | Approximate input ceiling per call | Output token limit | Initial call limit | Total token reservation limit |
|---|---:|---:|---:|---:|
| Small context (`legacy`) | 2,400 | 800 | 8 | 26,000 |
| Economy (`economy`, default) | 4,000 | 1,200 | 12 | 65,000 |
| Balanced (`balanced`) | 8,000 | 2,200 | 24 | 250,000 |

These are workload profiles, not model rankings or live-tested compatibility
claims. The configured model must have room for input, output and any
provider-specific overhead. A lower existing `AWT_MAX_OUTPUT_TOKENS` value is
respected. API adapters send the output cap; the Codex CLI route cannot enforce
the same API token cap and records this limitation.

- Scheduling is sequential, and a Workbench task directory admits one active
  job worker. No automatic paid retry, provider fallback or stronger-model
  escalation occurs.
- A checkpoint reserves the call and its estimated input/output allowance
  **before** dispatch. Failed or uncertain attempts remain in the budget.
- Reaching a budget pauses the task. Increasing the total cap and continuing
  does not repeat completed batches or reset earlier usage.
- The initial limits above remain deliberately small. A thesis can use an
  explicitly raised total cap, up to 5,000 calls / 20 million estimated tokens.
  The initial plan estimates text batches; later chapter/cross-section batches
  are planned from saved results and consume the same budget. A smaller per-call
  profile can require more calls; it does not inherently mean a cheaper full job.
- Optional per-million input/output prices estimate the reserved cost in the
  currency you use. Prices are entered by the author, not maintained as a
  supposedly current price list. Available provider usage is retained.
- Local token estimates vary by tokenizer. Images reserve an approximate
  allowance, and CLI overhead is not resolved locally. The provider's invoice
  remains the billing authority; the numeric budget is not a guaranteed
  currency spend cap.

## Optional figure-versus-text review

First configure an API model that actually accepts images, then set:

```powershell
$env:AWT_SUPPORTS_IMAGES = '1'
awt
```

Create a new task and explicitly select the images or PDF pages under the
coverage table before the first run (up to 200 selections). Each selected image gets a separate batch
with a bounded selection of captions, tables, results and conclusion text.
Only those selected images are sent. AWT currently accepts PNG/JPEG images and
renders PDF pages locally; it resizes images to at most 1280 pixels per side.
Fine print or dense graphs may need a separately supplied clearer crop.

Image support is an explicit configuration, not inferred from a marketing
model name. Older text-only models retain the full text workflow and show
figures as unchecked. Clear `AWT_SUPPORTS_IMAGES` or set it to `0` when returning
to a text model or Codex. The image transports cover Responses, Anthropic
Messages and compatible Chat Completions; hosted-model behaviour still needs
account-specific testing.

## Pause, cancel, restart and amend requirements

Every batch has a durable pre-dispatch reservation and a post-validation
checkpoint. A page refresh or reopening the Workbench restores the job without
a model call. Finished batches, request history, original hashes, limits and
the chosen provider/model are retained.

Pause/cancel stops new dispatches. An in-flight synchronous request can finish
and be checkpointed before the worker stops, and it may still be charged. This
is cooperative cancellation at batch boundaries, not a promise to cancel the
provider's remote computation or refund it.

After a process crash, a saved in-flight request becomes **结果不明**. It is never
silently replayed. Continuing requires the explicit retry checkbox because
the provider might already have billed it.

Updating requirements pauses the task and creates a new instruction revision.
Old outputs remain in checkpoint history; their coverage becomes stale. Resume
explicitly to review against the new requirements, within the remaining total
budget. If a crash occurs while a requirements update is pending, reopening
applies the saved new requirements and stays paused; the old in-flight attempt
is retained as outcome-unknown in history and remains in the budget.
This intentionally supports ordinary/older APIs rather than requiring
model-native mid-turn steering. OpenAI's optional [background API](https://developers.openai.com/api/docs/guides/background)
is a separate provider capability and is not used by this implementation.

Jobs are saved under `AWT_SESSION_DIR/review-projects` (or beneath the default
session directory). Keep the full directory for recovery; it contains selected
source copies and model outputs, but no API key values. It is private local
working material, not a public sharing bundle. JSON report exports contain
quotes and extracted text previews; inspect them before sharing.

Extracted material is saved once in a hash-verified manifest, separate from
changing progress checkpoints. Current checkpoints read earlier schema-1 jobs
as well as schema-2 manifests. Keep both the checkpoints and materials/source
copies when moving or backing up a task.

## Recheck a revised thesis without repeating unchanged work

Pause the job, open **替换修改文件，只复查受影响部分**, and upload changed files
with the same filenames. Inspect the resulting reuse and pending-work counts,
then explicitly continue. An identical file hash is a no-op.

A text result is reused only when the complete batch content and ordering,
requirements, model configuration, section roles and review contract still
match. Quotes are remapped to current locators and revalidated. An insertion
inside a batch invalidates that batch; unchanged neighbouring batches can
survive. Chapter and cross-section results additionally depend on full chapter
content hashes, so a changed section invalidates related checks even when a
selected excerpt itself did not change. Previous outputs and billed/reserved
attempts remain in history. Changing the goal makes old coverage stale and
requires a fresh review under the new goal.

Image results for a replaced file are invalidated. To send its revised images
for model inspection, create a new task and explicitly select them; local
page previews and layout comparison remain available in the existing task.

## Layout verification after editing

Select an imported PDF/DOCX as the baseline and upload the modified PDF/DOCX.
AWT renders both locally, records both source hashes and render hashes, and
shows before/after pages with page-count changes, changed pixels, blank-page
flags and possible text outside the page. Workbench comparisons support up to
1,000 pages, either the whole document or a selected original page range.
There is no need to export separate 60-page files. Conversion runs once;
rendering then processes and saves one before/after page pair at a time.
Pause, cancel, restart and continue retain completed pages. The page selector
loads only the requested pair, and saved human checks survive navigation and
restart. The old in-memory Python helper retains its 60-page bound; the
Workbench no longer uses it.

Changes are prompts for inspection, not automatic layout defects. Inspect
figure/table clipping, overlap, fonts and pagination, then save the page-level
human checks. Those checks are bound to that exact modified-file hash. The
original file is never overwritten. LibreOffice rendering may differ from
Word; use Word-exported PDFs when Word's exact layout is authoritative.

The project review produces a review/index/report. It does not directly rewrite
PDF or DOCX. The existing single-file workflow remains available for author-
confirmed, exact text replacements and a new modified copy.

## Verification

```sh
python -m unittest discover -s tests/runtime -p 'test_*.py' -v
```

The tests use fictional documents and local HTTP fixtures. Optional rendering
tests run when their dependencies are available. They exercise source/quote
binding, all three API image payloads, text-only rejection of image requests,
budget pauses, checkpoint continuation, uncertain outcomes, cancellation,
steering revisions, PDF/DOCX locators and hash-bound layout checks.

To reproduce the 200-page planning, incremental-review and actual local layout
benchmark, install the document extra plus `reportlab`, then run from this
checkout:

```sh
python scripts/check-thesis-scale.py --pages 200 --run-fixture --layout --output final_output/thesis-scale.json
```

The benchmark uses deterministic mock model outputs and fictional single-column
text. It measures local workload and recovery, not hosted latency, real bills
or academic review quality. See the [Chinese thesis workflow](thesis-scale-review.md)
for the measured example and daily operating steps.

The extraction/rendering interfaces follow the primary documentation for
[pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) and
[pypdfium2](https://pypdfium2-team.github.io/pypdfium2/python_api.html). Local
software verification is separate from real-provider compatibility and
academic review-quality evaluation.
