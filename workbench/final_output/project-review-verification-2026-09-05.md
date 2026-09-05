# AWT project review verification — 2026-09-05

Status: locally implemented and verified in the current source checkout.
No hosted review-model request, paid model evaluation, commit, push or release
was performed. Existing unrelated skill/plugin edits were preserved.

## Runtime and installation

| Check | Observed result |
|---|---|
| Full runtime suite with document dependencies | 43 tests: 42 passed, 1 Windows/POSIX permission skip |
| Fresh wheel installed in a separate, dependency-free virtual environment | 43 tests: 39 passed, 3 optional PDF-rendering skips, 1 Windows/POSIX permission skip |
| Wheel runtime allowlist | Exactly 12 runtime files; new HTML, JavaScript and job runner matched source bytes |
| Installed HTTP routes | Project HTML/JS served; local import and restore returned zero reserved calls |
| Installed request boundaries | Non-local Host and Origin returned HTTP 403 |
| Frontend and install-script syntax | Node `--check` and Bash `-n` passed |
| Git whitespace validation | `git diff --check` passed |

The suite covers source-hash binding, verbatim quote validation, five section
pairs, explicit missing/omitted coverage, legacy output caps, budget stops,
completed-batch reuse, cooperative cancellation, crash uncertainty, amended
requirements, and a crash while an amendment is pending. Image payload fixtures
cover Responses, Anthropic Messages and Chat Completions; unselected pages and
text-only configurations do not receive visual-review coverage.

The dedicated document-review CI job was added; no remote CI run is claimed.
The existing minimal Python 3.9/3.11 CI matrix remains in place. Local testing
does not establish that every vendor model accepts the request or returns a
useful academic review.

## Browser and document evidence

An isolated loopback server used a deterministic offline model fixture and
fictional documents. Its configured model label was `offline-ui-fixture`.

- Four chapter files: a one-call cap paused after one saved batch. Increasing
  the cap continued to nine completed batches without repeating the first.
  Refreshing retained the nine-call count.
- Real DOCX/PDF bytes were imported through the HTTP endpoint. DOCX extraction
  retained paragraphs and table cells; PDF extraction retained page rectangles.
- Actual LibreOffice conversion rendered a fictional DOCX before/after pair.
  The 90%/70% change appeared in both text and table. The UI showed the changed
  page, supported enlarged viewing, and persisted the page-check record after
  refresh. These checks are software fixtures, not author approval of a paper.
- Browser automation's native Windows file chooser supplied zero-byte files
  and raised `NotReadableError`. UI text-import testing therefore used synthetic
  browser `File` objects; binary DOCX/PDF import was separately tested with real
  bytes through HTTP. Native file-picker end-to-end verification remains open.

Screenshots:

- [Budget pause](project-review-budget-qa-2026-09-05.jpg)
- [Before/after layout](project-review-layout-qa-2026-09-05.jpg)
- [Enlarged document page](project-review-zoom-qa-2026-09-05.jpg)

The Gemini plan/design advisory calls failed with `fetch failed`. The visual
gate returned `visual gate blocked before Gemini` despite locally readable
screenshots. Screenshot inspection was performed locally; an independent
Gemini visual review was not obtained.

## Practical limits

The job runner supports ordinary synchronous APIs using a local background
worker. Pause/cancel stops later batches; an already-sent request may finish
and be billed. Cross-section comparisons select bounded anchors and list the
omissions. Text review does not establish image review, and pixel changes do
not automatically establish a layout defect. DOCX page geometry depends on
the renderer; Word-exported PDFs remain an option for Word-specific layout.

Token reservations estimate workload and are not a guaranteed currency cap.
Imports, checkpoint restore, previews and layout comparison make no model
requests. Failed and uncertain requests remain in the reserved budget; there
is no automatic paid retry or model upgrade.

See [setup and older-model configuration](../docs/setup-project-review.md).
