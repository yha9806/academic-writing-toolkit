# Thesis-scale Workbench verification — 2026-09-05

Status: implemented and locally verified in the current source checkout.
This is not a published release, hosted-model compatibility certification or
academic review-quality evaluation. No real manuscript or paid model was used.

## Implemented behaviour

- 1 MB staged uploads, 80 MB per file / 160 MB total, up to 20 files;
  PDF input and Workbench layout ranges support up to 1,000 pages.
- Conservative nearby-line coalescing with every original PDF line rectangle,
  locator and character span retained. Source blocks stay within small-model
  request budgets.
- Chapter navigation, quote-grounded chapter reviews and bounded local lexical
  retrieval for cross-section comparisons. Missing and omitted regions remain
  separately visible from text-batch completion.
- Paginated source, claim/evidence, finding, image and history endpoints;
  compact progress responses exclude the manuscript and image payloads.
- Hash-bound material manifests are separate from changing checkpoints.
  At most four material versions are retained in memory, including after
  repeated classification/revision; older versions remain on disk.
- Same-filename revision reuse validates complete batch content/order,
  requirements, model settings, section roles, review contract and remapped
  quotes. Chapter/cross-section reuse additionally depends on full chapter
  hashes. Previous attempts and costs stay in history.
- Local page-at-a-time layout rendering with durable progress, pause/cancel,
  restart continuation, numeric page navigation and hash-bound page checks.
- Existing provider presets and zero-dependency text workflows remain
  available. The default workload budgets stay small; higher lifetime budgets
  require an explicit setting. No automatic paid retry or model escalation.

## Automated and installation checks

| Check | Result |
|---|---|
| Source runtime suite with optional PDF dependencies | 54 tests: 53 passed, 1 Windows POSIX-permissions skip |
| Final thesis-scale regression suite | 11 passed, including repeated-manifest cache bounds |
| Fresh base wheel in isolated Windows venv | 54 tests: 47 passed, 6 optional-PDF skips, 1 Windows skip |
| Wheel contents | Exactly 14 runtime files; every packaged byte matched the current source |
| Installed HTTP routes | HTML/JS, staged upload, import, compact status, pagination and restore passed with zero calls |
| Installed access boundaries | Non-local Host and Origin each returned HTTP 403 |
| Installed CLI preflight | Local Ollama-style configuration checked without contacting a model |
| Frontend / install script / whitespace | Node syntax, Bash syntax and `git diff --check` passed |

The CLI fixture now clears inherited `AWT_*` settings before its Codex-specific
check, so another configured provider does not change the test's intended path.
The new cache regression changes section roles repeatedly, verifies the memory
bound, closes the manager and confirms the final classification after restart.

Recovery tests cover budget pauses, request uncertainty, explicit retries,
in-flight cancellation, revised requirements, source hashes, same-file no-ops,
paragraph insertions, dependency invalidation and completed-result reuse.
The 200-page layout recovery test stops at page 2, reopens the manager and
checks that pages 1–2 are not rendered again. Its page renderer is mocked;
separate tests and the benchmark render real PDF pages.

## Actual 200-page benchmark

The fictional single-column PDF contains 42 lines per page and 742,046
extracted characters. Comparison isolates line coalescing with the same
planner and budgets on both sides.

| Profile | Unmerged text batches | Coalesced text batches | Input/output reservation estimate before → after |
|---|---:|---:|---:|
| Legacy | 435 | 226 | 1,373,776 → 684,514 |
| Economy | 207 | 100 | 1,066,188 → 508,748 |
| Balanced | 92 | 44 | 915,244 → 434,441 |

All 8,600 original line rectangles survive within 1,000 coalesced regions.
Initial compact status was 2,081 bytes. Import and planning took 0.902 seconds
on the local test machine; these timings do not include hosted inference.

An economy-profile run used 151 deterministic mock calls including chapter
and cross-section stages. Replacing one passage on page 199 reused 991 source
regions / 99 text batches and required 21 additional mock calls. Cache reuse
also retained unaffected chapter/cross-section results.

Actual local rendering completed all 200 before/after page pairs in 18.334
seconds, identified only page 199 as changed, and made zero model calls.
The 1,000-page input limit is a configured ceiling; this record does not claim
a 1,000-page performance test, OCR accuracy or complex-layout extraction quality.

Raw results:

- [200-page benchmark](thesis-scale-200-2026-09-05.json), SHA-256
  `BF2A2259E619F40084543E990A574CF93055FAE36CD10515FFBCF494071D7FFF`
- [HTTP/browser outcome](thesis-ui-verification-2026-09-05.json), SHA-256
  `375EDBC5BA0311FFF87BD377AD146F86BB037CE4777C738D4667A14DA5167B66`

## Browser evidence

The isolated loopback Workbench used the `offline-ui-fixture` runner.

- A one-call cap paused after one saved batch. The UI raised the cap and
  continued to 151 completed batches without repeating the first call.
- Searching the final passage on page 200 returned its full text and the
  original per-line locator spans. Claim-index pagination operated normally.
- Real PDF bytes passed through the staged HTTP upload endpoints for layout
  and same-filename revision. Native file-picker operation was not revalidated;
  the earlier automation limitation remains documented in the previous report.
- The UI displayed 200 saved layout pages, navigated to page 199 and enlarged
  the changed passage. Saving page 199's fixture check, navigating to page 200
  and reopening preserved exactly one checked page.
- After replacement the UI showed 991 reused regions and a paused recheck
  plan. Continuing completed the revision at 172 cumulative mock calls. The
  final view showed zero pending calls and distinguished the initial recheck
  plan from current completion.

Screenshots:

- [Page 200 source and line locators](thesis-source-page-200-2026-09-05.jpg)
- [200-page layout result](thesis-layout-page-199-2026-09-05.jpg)
- [Enlarged modified page](thesis-layout-enlarged-2026-09-05.jpg)
- [Incremental revision plan](thesis-revision-qa-2026-09-05.jpg)
- [Completed incremental revision](thesis-revision-completed-2026-09-05.jpg)

Gemini's generic plan/design advisory calls failed with `fetch failed`.
The screenshot visual gate returned `visual gate blocked before Gemini`
despite a locally readable JPEG. Screenshots were inspected locally; no
independent Gemini visual review was obtained. The temporary QA server and
test browser tab were closed after verification.

For operation and cost planning, see
[毕业论文与超长文档使用说明](../docs/thesis-scale-review.md).
