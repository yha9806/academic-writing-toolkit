// E1 paired-session instrument producer (P3 spec item 3, parent spec §11).
//
//   node e1/run-e1.mjs                offline lane: fixture reference text,
//                                     scripted adapter — proves the
//                                     instrument end-to-end, keylessly.
//   node e1/run-e1.mjs --real         real lane: key-gated; drives real
//                                     model sessions over the PDFs named in
//                                     e1/pdfs.json (never committed).
//
// Per manifest entry, TWO arms run the SAME two tasks on the pinned dsh
// launcher: the skills arm (canonical awt-headless profile — guards,
// skills, real read_pdf) and the plain arm (same bundles and model access,
// no guards, no skills). Artifacts are machine-graded by e1/graders.mjs
// wired to the shipped guards lint and citation extractor. The metrics
// JSON and table are written by THIS script only — a hand-authored
// comparison table is a spec violation (§11).
//
// Offline lane honesty: the scripted arms are synthetic behaviors chosen to
// exercise every grader (one conforming, one sloppy). Offline results prove
// the INSTRUMENT discriminates; they are E0 evidence about the instrument,
// never efficacy evidence about the skills.

import { spawnSync } from 'node:child_process'
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync,
  rmSync, symlinkSync, writeFileSync,
} from 'node:fs'
import { createHash } from 'node:crypto'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { parseOptions, modelRoute, readManifest, classifyRun, measuredRun } from './inputs.mjs'
import { labelPdfPages } from '../profiles/awt-headless/pdf-pages.mjs'
import { readOpeningEvidence, sessionFiles, terminalOutcome } from './evidence.mjs'
import { inspectLocalModel, localProviderPatch } from './local-provider.mjs'
import { readResume } from './resume.mjs'
import { publicContinuation } from './public-paths.mjs'
import {
  extractQuotedSpans, gradeNotesParseability, gradePageAccuracy,
  gradeQuoteFidelity, gradeUnopenedCitations, pagesFromLabeledText,
} from './graders.mjs'

const E1_DIR = resolve(import.meta.dirname)
const PRODUCT_ROOT = resolve(E1_DIR, '..')
const PROFILE_SRC = join(PRODUCT_ROOT, 'profiles', 'awt-headless')
const GUARDS_DIST = join(PRODUCT_ROOT, 'guards', 'dist')
const SKILLS_SRC = join(PRODUCT_ROOT, '.claude', 'skills')
const TEMPLATE_SRC = join(PRODUCT_ROOT, 'literature', 'reading_notes', '_template_NOTES.md')
const DSH_BIN = join(PRODUCT_ROOT, 'e2e', 'node_modules', '@deepseek-ai', 'dsh', 'lib', 'bin.js')
const PINNED_DSH = '0.1.0-rc.6'
let options
try { options = parseOptions(process.argv.slice(2)) }
catch (error) { die(error.code ?? 'E1_USAGE', error.message) }
if (options.help) {
  console.log('Usage: node e1/run-e1.mjs [--real [--check] --manifest FILE --provider deepseek|anthropic|ollama --model MODEL [--base-url LOOPBACK_URL]] [--out DIR] [--timeout-ms 1000..600000]\nNo flag runs the keyless E0 instrument. --real --check validates all inputs without model generations. Anthropic and Ollama require an explicit model. Relative PDF paths resolve beside the manifest.')
  process.exit(0)
}
const REAL = options.real
const manifestPath = resolve(options.manifest ?? join(E1_DIR, 'pdfs.json'))
const outDir = resolve(options.out ?? join(E1_DIR, 'results'))
let route
try { route = modelRoute(options.provider, options.model, process.env, options.baseURL) }
catch (error) { die(error.code, error.message) }

function die(code, message, remedy) {
  console.error(`${code}: ${message}`)
  if (remedy) console.error(`  remedy: ${remedy}`)
  process.exit(1)
}

if (!existsSync(DSH_BIN)) die('E1_DSH_MISSING', `pinned dsh launcher missing at ${DSH_BIN}`, 'cd e2e && npm ci')
if (!existsSync(join(GUARDS_DIST, 'dsh-plugin.js'))) die('E1_GUARDS_UNBUILT', 'guards/dist missing', 'cd guards && npm install && npm run build')
const installedVersion = JSON.parse(readFileSync(join(dirname(DSH_BIN), '..', 'package.json'), 'utf8')).version
if (installedVersion !== PINNED_DSH) die('E1_PIN_MISMATCH', `installed harness ${installedVersion} differs from ${PINNED_DSH}`)
const { lintNotes, hasErrors } = await import(pathToFileURL(join(GUARDS_DIST, 'notes-lint.js')).href)
const { extractCitations } = await import(pathToFileURL(join(GUARDS_DIST, 'decisions.js')).href)

// --- manifest ---------------------------------------------------------------------

const sha256 = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')

async function loadEntries() {
  if (!REAL) {
    return [{
      id: 'fixture-smith2024',
      referenceTextPath: join(E1_DIR, 'fixtures', 'reference.txt'),
      firstPage: 12,
      lastPage: 13,
      source: { surname: 'smith', year: '2024' },
    }]
  }
  try { return readManifest(manifestPath) }
  catch (error) { die(error.code ?? 'E1_MANIFEST_INVALID', error.message) }
}

// --- workspace / profile synthesis ------------------------------------------------

const scratchRoots = []
function scratch(prefix) {
  const dir = mkdtempSync(join(tmpdir(), prefix))
  scratchRoots.push(dir)
  return dir
}

function buildWorkspace(arm) {
  const ws = scratch(`awt-e1-ws-${arm}-`)
  mkdirSync(join(ws, 'chapters'), { recursive: true })
  mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  mkdirSync(join(ws, 'contracts'), { recursive: true })
  cpSync(TEMPLATE_SRC, join(ws, 'literature', 'reading_notes', '_template_NOTES.md'))
  if (arm === 'skills') {
    mkdirSync(join(ws, '.agents', 'skills'), { recursive: true })
    for (const name of readdirSync(SKILLS_SRC)) {
      symlinkSync(join(SKILLS_SRC, name), join(ws, '.agents', 'skills', name), process.platform === 'win32' ? 'junction' : 'dir')
    }
  }
  return ws
}

const PLAIN_PATCH = `# E1 plain arm: identical bundles and model access, no guards, no skills.
- id: agent-default-model
  config:
    provider: deepseek
    model: deepseek-v4-flash

- id: llm-pi-ai
  config:
    providers:
      deepseek:
        apiKeyEnv: DEEPSEEK_API_KEY
      anthropic:
        apiKeyEnv: ANTHROPIC_API_KEY

# Same isolation as the skills arm: no user-level catalogue in either arm.
- id: skill-filesystem
  config:
    dshHome: !!js dshHomePath('awt-no-user-skills')
    agentsHome: !!js dshHomePath('awt-no-user-skills')

- insert:
    - id: awt-read-pdf
      name: './awt-read-pdf.plugin.mjs'
`

function buildHome(arm) {
  const home = scratch(`awt-e1-home-${arm}-`)
  const profile = join(home, 'profiles', 'awt-headless')
  mkdirSync(profile, { recursive: true })

  let patch
  if (arm === 'skills') {
    cpSync(join(PROFILE_SRC, 'package.json'), join(profile, 'package.json'))
    cpSync(join(PROFILE_SRC, 'awt-brand.plugin.mjs'), join(profile, 'awt-brand.plugin.mjs'))
    cpSync(join(PROFILE_SRC, 'awt-export.plugin.mjs'), join(profile, 'awt-export.plugin.mjs'))
    cpSync(GUARDS_DIST, join(profile, 'awt-guards'), { recursive: true })
    patch = readFileSync(join(PROFILE_SRC, 'cordis.patch.yml'), 'utf8')
  } else {
    writeFileSync(join(profile, 'package.json'), JSON.stringify({
      name: 'dsh-profile-awt-headless', private: true, type: 'module',
      dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-headless'] } },
    }, null, 2))
    patch = PLAIN_PATCH
  }
  cpSync(join(PROFILE_SRC, 'awt-read-pdf.plugin.mjs'), join(profile, 'awt-read-pdf.plugin.mjs'))
  cpSync(join(PROFILE_SRC, 'pdf-pages.mjs'), join(profile, 'pdf-pages.mjs'))

  if (REAL) {
    // Both arms receive exactly the chosen route. Supplying only an Anthropic
    // key must never leave the profile pointed at the default DeepSeek model.
    patch = patch.replace('provider: deepseek', `provider: ${route.provider}`)
      .replace('model: deepseek-v4-flash', `model: ${JSON.stringify(route.model)}`)
    if (route.provider === 'ollama') {
      const providerBlock = /- id: llm-pi-ai\r?\n  config:\r?\n    providers:\r?\n(?:[ \t].*(?:\r?\n|$))+/
      if (!providerBlock.test(patch)) throw new Error('E1 provider profile block is missing')
      patch = patch.replace(providerBlock, localProviderPatch(route))
    }
  }

  if (!REAL) {
    // Offline overlay: scripted default model, scripted adapter row, and the
    // fixture read_pdf (swapped in place of the pdftotext plugin file so the
    // model provably reads the reference text).
    patch = patch
      .replace('provider: deepseek', 'provider: scripted')
      .replace('model: deepseek-v4-flash', 'model: scripted-1')
    patch += `
- insert:
    - id: awt-e1-scripted-llm
      name: './awt-e1-scripted-llm.plugin.mjs'
`
    cpSync(join(E1_DIR, 'plugins', 'awt-e1-scripted-llm.plugin.mjs'), join(profile, 'awt-e1-scripted-llm.plugin.mjs'))
    cpSync(join(E1_DIR, 'plugins', 'awt-e1-read-pdf-fixture.plugin.mjs'), join(profile, 'awt-read-pdf.plugin.mjs'))
  }
  // Identical observable storage in both arms. The harness otherwise writes
  // zstd logs, which a JSONL reader must not silently treat as missing.
  patch += `
- id: session-persistence-jsonl
  config:
    root: !!js dshHomePath('sessions')
    compression: none
`
  writeFileSync(join(profile, 'cordis.patch.yml'), patch)
  return home
}

// --- offline scripts --------------------------------------------------------------

function offlineScripts(entry, arm, ws) {
  const reference = readFileSync(entry.referenceTextPath, 'utf8')
  const goodQuote = 'the archive is not a neutral container of the past'
  const notesPath = `literature/reading_notes/${entry.source.surname}${entry.source.year}_NOTES.md`
  const readCall = {
    kind: 'tool-call', name: 'read_pdf',
    args: { file_path: 'literature/source.pdf', first_page: entry.firstPage, last_page: entry.lastPage },
  }
  if (arm === 'skills') {
    const notes = `# Reading Notes: Smith — The Archive as Author (2024)

**Source**: Smith, J. (2024) The archive as author. *Example Press*.
**Date read**: 2026-08-16
**Status**: completed
**Relevance**: Ch3 S3.1 — archives as curation
**Evidence status**: full_text

---

## Key Arguments

- Archival selection is a form of authorship, not neutral storage.

## Detailed Notes

### p.12–13: Curation as authorship

> "${goodQuote}" (p.12)

Digital archives relocate judgement into ranking and retention policy.

## Key Terms

| Term | Translation | Definition in context |
|------|-------------|----------------------|
| curation | — | selection constituting authorship |

## Thesis Connections

| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|
| curation as authorship | Ch3 | S3.1 | supports |

## Questions & Follow-ups

- How does retention policy differ from archivist judgement?

---
*Last updated: 2026-08-16*
`
    const draft = `Smith (2024) argues that "${goodQuote}" (p.12), a claim this section extends to retention policy. The relocation of judgement, rather than its removal, is the mechanism this thesis traces.`
    return {
      notes: [readCall, { kind: 'tool-call', name: 'write', args: { file_path: notesPath, content: notes } }, { kind: 'text', text: 'notes complete' }],
      draft: [{ kind: 'tool-call', name: 'write', args: { file_path: 'chapters/draft_section.md', content: draft } }, { kind: 'text', text: 'draft complete' }],
    }
  }
  // Plain arm: fabricated quote, wrong page, non-conforming notes, unopened citation.
  const notes = `# Notes on Smith\n\n"archives always mirror reality without judgement" (p.7)\n`
  const draft = `As earlier work shows (Jones, 2021), archives distort. Smith (2024) even says "archives always mirror reality without judgement" (p.7).`
  return {
    notes: [readCall, { kind: 'tool-call', name: 'write', args: { file_path: notesPath, content: notes } }, { kind: 'text', text: 'done' }],
    draft: [{ kind: 'tool-call', name: 'write', args: { file_path: 'chapters/draft_section.md', content: draft } }, { kind: 'text', text: 'done' }],
  }
}

// --- run one arm ------------------------------------------------------------------

function runHeadless(home, ws, task, extraEnv) {
  const before = new Set(sessionFiles(home))
  const res = spawnSync(
    process.execPath,
    [DSH_BIN, '--profile', 'awt-headless', task],
    {
      cwd: ws,
      env: {
        PATH: process.env.PATH ?? process.env.Path,
        LANG: process.env.LANG ?? 'en_US.UTF-8',
        HOME: process.env.HOME,
        ...Object.fromEntries(['SystemRoot', 'WINDIR', 'USERPROFILE', 'TEMP', 'TMP', 'COMSPEC'].filter((key) => process.env[key]).map((key) => [key, process.env[key]])),
        DSH_HOME: home,
        DSH_TELEMETRY_DISABLED: '1',
        ...(REAL
          ? {
            [route.keyEnv]: route.provider === 'ollama' ? 'ollama' : process.env[route.keyEnv],
          }
          : {}),
        ...extraEnv,
      },
      encoding: 'utf8',
      timeout: options.timeoutMs,
      maxBuffer: 16 * 1024 * 1024,
    },
  )
  const logs = sessionFiles(home).filter((file) => !before.has(file)).map((file) => readFileSync(file, 'utf8'))
  return { ...res, outcome: terminalOutcome(logs) }
}

function referenceFor(entry) {
  if (!REAL) return readFileSync(entry.referenceTextPath, 'utf8')
  // Regenerate exactly what the read_pdf tool shows the model.
  const res = spawnSync('pdftotext', ['-layout', '-f', String(entry.firstPage), '-l', String(entry.lastPage), entry.path, '-'],
    { encoding: 'utf8', timeout: 60_000, maxBuffer: 16 * 1024 * 1024 })
  if (res.error?.code === 'ENOENT') die('E1_PDFTOTEXT_MISSING', 'pdftotext is not on PATH', 'select a working Poppler installation before running the real lane')
  if (res.status !== 0) die('E1_PDFTOTEXT_FAILED', `pdftotext failed for ${entry.id}`, 'check the PDF and select a working Poppler executable on PATH')
  const labeled = labelPdfPages(res.stdout, entry.firstPage)
  if (pagesFromLabeledText(labeled).size !== entry.lastPage - entry.firstPage + 1) die('E1_PAGE_RANGE', `${entry.id}: PDF does not contain the complete requested page range`)
  if (!res.stdout.replace(/[\s\f]/g, '')) die('E1_PDF_TEXT_MISSING', `${entry.id}: selected pages contain no extractable text`)
  return labeled
}

function collectArtifacts(ws, entry) {
  const notesDir = join(ws, 'literature', 'reading_notes')
  const notesFile = join(notesDir, `${REAL ? entry.id : entry.source.surname + entry.source.year}_NOTES.md`)
  const draftFile = join(ws, 'chapters', 'draft_section.md')
  return {
    notesText: existsSync(notesFile) ? readFileSync(notesFile, 'utf8') : undefined,
    draftText: existsSync(draftFile) ? readFileSync(draftFile, 'utf8') : undefined,
  }
}

const NOTES_TASK = (entry) => REAL
  ? `Read pages ${entry.firstPage}-${entry.lastPage} of literature/source.pdf using the read_pdf tool, then write a reading-notes file literature/reading_notes/${entry.id}_NOTES.md following literature/reading_notes/_template_NOTES.md exactly. Quote at least two passages verbatim with their page numbers.`
  : 'E1 offline notes task'
const DRAFT_TASK = () => REAL
  ? 'Write chapters/draft_section.md: a ~300-word thesis section arguing from the source you have read, quoting evidence verbatim with page numbers and Harvard citations.'
  : 'E1 offline draft task'

async function runArm(entry, arm, runDir) {
  const saved = resume?.arms.find((item) => item.id === entry.id && item.arm === arm)
  if (saved?.processes.length === 2) {
    cpSync(saved.artifactDir, join(runDir, entry.id, arm), { recursive: true })
    console.log(`  reusing both recorded ${entry.id}/${arm} outcomes; no model retry`)
    return { ...saved.result, ...classifyRun('real', saved.processes, saved.result.sourceOpened, true), processes: saved.processes }
  }
  const ws = buildWorkspace(arm)
  const home = buildHome(arm)
  if (REAL) cpSync(entry.path, join(ws, 'literature', 'source.pdf'))
  const scripts = REAL ? undefined : offlineScripts(entry, arm, ws)
  const scriptEnv = (script) => {
    if (script === undefined) return {}
    const path = join(scratch('awt-e1-script-'), 'script.json')
    writeFileSync(path, JSON.stringify(script))
    return { AWT_E1_SCRIPT: path, AWT_E1_REFERENCE: entry.referenceTextPath }
  }

  const runs = []
  if (saved?.processes.length === 1) {
    for (const tree of ['chapters', 'contracts']) cpSync(join(saved.artifactDir, tree), join(ws, tree), { recursive: true })
    cpSync(join(saved.artifactDir, 'reading_notes'), join(ws, 'literature', 'reading_notes'), { recursive: true })
    mkdirSync(join(home, 'sessions', 'preserved-prefix'), { recursive: true })
    for (const [index, log] of saved.savedLogs.entries()) cpSync(log.file, join(home, 'sessions', 'preserved-prefix', `${index}.jsonl`))
    runs.push(...saved.processes)
    console.log(`  reusing recorded ${entry.id}/${arm} notes outcome; no model retry`)
  } else {
    runs.push(runHeadless(home, ws, NOTES_TASK(entry), scriptEnv(scripts?.notes)))
  }
  // A recorded model-budget exhaustion remains in the sample. Only an
  // unobserved or infrastructure failure stops subsequent tasks.
  if (runs.length === 1 && measuredRun(runs[0])) runs.push(runHeadless(home, ws, DRAFT_TASK(entry), scriptEnv(scripts?.draft)))
  for (const [i, res] of runs.entries()) {
    if (res.status !== 0) {
      const tail = `${res.stderr ?? ''}`.trim().split('\n').slice(-4).join(' | ')
      console.error(`  ${arm} run ${i + 1} exited ${res.status} (${res.outcome ?? 'unobserved'}): ${tail}`)
    }
  }

  const artifactDir = join(runDir, entry.id, arm)
  mkdirSync(artifactDir, { recursive: true })
  for (const tree of ['chapters', 'contracts']) cpSync(join(ws, tree), join(artifactDir, tree), { recursive: true, dereference: false })
  cpSync(join(ws, 'literature', 'reading_notes'), join(artifactDir, 'reading_notes'), { recursive: true, dereference: false })
  // dsh names session directories after the absolute workspace. Keep the log
  // bytes, but do not copy that encoded machine path into a portable artifact.
  mkdirSync(join(artifactDir, 'sessions'), { recursive: true })
  for (const file of sessionFiles(home)) {
    cpSync(file, join(artifactDir, 'sessions', `sha256-${sha256(file)}.jsonl`))
  }
  const processes = runs.map((run) => ({ status: run.status, signal: run.signal, outcome: run.outcome, error: run.error ? { code: run.error.code ?? 'SPAWN_ERROR' } : null }))
  writeFileSync(join(artifactDir, 'processes.json'), JSON.stringify(processes, null, 2))

  const { notesText, draftText } = collectArtifacts(ws, entry)
  const opening = readOpeningEvidence(home, ws, entry)
  const { referenceText } = opening
  const pages = pagesFromLabeledText(referenceText)
  const spans = [
    ...extractQuotedSpans(notesText ?? ''),
    ...extractQuotedSpans(draftText ?? ''),
  ]
  return {
    arm,
    ...classifyRun(REAL ? 'real' : 'offline', runs, opening.sourceOpened, opening.files.length >= runs.length),
    artifacts: `${entry.id}/${arm}`,
    quoteFidelity: gradeQuoteFidelity(spans, referenceText),
    pageAccuracy: gradePageAccuracy(spans, pages),
    notes: gradeNotesParseability(notesText, lintNotes, hasErrors),
    unopenedCitations: gradeUnopenedCitations(draftText, opening.sourceOpened ? [entry.source] : [], extractCitations),
    runExitCodes: runs.map((r) => r.status),
    processes,
  }
}

// --- main -------------------------------------------------------------------------

const lane = REAL ? 'real' : 'offline'
const entries = await loadEntries()
// Check every source before launching any model session. No PDF is sent to
// a provider during this preflight; pdftotext operates locally.
for (const entry of entries) referenceFor(entry)
if (REAL && route.provider === 'ollama') {
  try { route.localInfo = await inspectLocalModel(route) }
  catch (error) { die(error.code ?? 'E1_LOCAL_UNAVAILABLE', error.message) }
}
let resume
if (options.resume) {
  try { resume = readResume(options.resume, entries, route, `@deepseek-ai/dsh@${PINNED_DSH}`, PRODUCT_ROOT, options.retryLocalTransport) }
  catch (error) { die(error.code ?? 'E1_RESUME_INVALID', error.message) }
}
if (REAL && options.check) {
  console.log(JSON.stringify({ status: route.keyPresent ? 'ready' : 'blocked', code: route.keyPresent ? null : 'E1_KEY_MISSING', sources: entries.length, provider: route.provider, model: route.model, keyEnv: route.keyEnv, keyPresent: route.keyPresent, localModel: route.localInfo, modelRequests: 0 }, null, 2))
  process.exitCode = route.keyPresent ? 0 : 1
} else {
  await runExperiment()
}

async function runExperiment() {
  if (REAL && !route.keyPresent) die('E1_KEY_MISSING', `set ${route.keyEnv} locally for the explicitly selected ${route.provider} route`)
  mkdirSync(outDir, { recursive: true })
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const runDir = join(outDir, `e1-${lane}-${stamp}`)
  // Resolve provenance before any generation: cross-volume paths cannot be
  // published as relative references and must fail before a model request.
  const continuation = resume ? publicContinuation(resume.provenance, runDir, resume.provenance.run) : undefined
  mkdirSync(runDir)
  const results = []
  let failure
  try {
    for (const entry of entries) {
      console.log(`E1 ${lane}: ${entry.id}`)
      for (const arm of ['skills', 'plain']) {
        let graded
        try { graded = await runArm(entry, arm, runDir) }
        catch (error) { failure = { code: error.code ?? 'E1_RUN_FAILED', id: entry.id, arm }; break }
        results.push({ id: entry.id, ...graded })
        console.log(`  ${arm}: quotes ${graded.quoteFidelity.matched}/${graded.quoteFidelity.quotes} verbatim, pages ${graded.pageAccuracy.correct}/${graded.pageAccuracy.cited} correct, notes ${graded.notes.parseable ? 'parseable' : 'NOT parseable'}, unopened citations ${graded.unopenedCitations.unopened.length}`)
        if (graded.status !== 'completed') { failure = { code: 'E1_SESSION_INCOMPLETE', id: entry.id, arm }; break }
      }
      if (failure) break
    }
  } finally {
    for (const dir of scratchRoots.splice(0)) {
      if (dirname(resolve(dir)) !== resolve(tmpdir()) || !basename(dir).startsWith('awt-e1-')) throw new Error('E1 scratch cleanup target is outside the allocated temporary roots')
      rmSync(dir, { recursive: true, force: true })
    }
  }

  const payload = {
    lane,
    status: failure ? 'incomplete' : 'completed',
    evidenceClass: failure ? null : (REAL ? 'E1' : 'E0'),
    failure: failure ?? null,
    generatedAt: new Date().toISOString(),
    harness: `@deepseek-ai/dsh@${PINNED_DSH}`,
    producer: 'e1/run-e1.mjs',
    producerSha256: sha256(join(E1_DIR, 'run-e1.mjs')),
    implementationSha256: Object.fromEntries([
      'e1/run-e1.mjs', 'e1/inputs.mjs', 'e1/evidence.mjs', 'e1/local-provider.mjs', 'e1/resume.mjs', 'e1/public-paths.mjs', 'e1/graders.mjs',
      'profiles/awt-headless/cordis.patch.yml', 'profiles/awt-headless/awt-read-pdf.plugin.mjs',
      'profiles/awt-headless/pdf-pages.mjs', 'guards/dist/notes-lint.js', 'guards/dist/decisions.js',
    ].map((path) => [path, sha256(join(PRODUCT_ROOT, path))])),
    inputs: entries.map(({ path, referenceTextPath, ...entry }) => ({ ...entry, sha256: entry.sha256 ?? sha256(referenceTextPath) })),
    model: REAL ? { provider: route.provider, id: route.model, ...(route.localInfo ? { local: route.localInfo } : {}) } : { provider: 'scripted', id: 'scripted-1' },
    ...(resume ? { continuation } : {}),
    note: failure ? 'Incomplete execution: diagnostic results only; no E1 efficacy claim. Inspect retained session logs and process statuses before a deliberate new run.' : lane === 'offline'
      ? 'Offline lane: scripted synthetic arms. Proves the instrument discriminates (E0 about the instrument); NOT efficacy evidence about the skills.'
      : 'Real lane: paired sessions over the manifest PDFs. E1 evidence per §11.',
    results,
  }
  const jsonPath = join(runDir, 'metrics.json')
  writeFileSync(jsonPath, JSON.stringify(payload, null, 2))

  const rows = results.map((r) =>
    `| ${r.id} | ${r.arm} | ${r.quoteFidelity.matched}/${r.quoteFidelity.quotes} | ${r.pageAccuracy.correct}/${r.pageAccuracy.cited} | ${r.notes.parseable ? 'yes' : 'no'} | ${r.unopenedCitations.unopened.length} | ${r.taskOutcomes.join(' / ')} |`)
  const table = [
    `# E1 ${lane} results (${payload.generatedAt})`,
    '',
    payload.note,
    '',
    '| source | arm | verbatim quotes | correct pages | notes parseable | unopened citations | notes / draft outcomes |',
    '| --- | --- | --- | --- | --- | --- | --- |',
    ...rows,
    '',
    `Producer: \`${payload.producer}\` against \`${payload.harness}\`. Metrics JSON: \`metrics.json\`. Logs and model outputs are retained per source/arm beside it; review before sharing.`,
  ].join('\n')
  const mdPath = join(runDir, 'results.md')
  writeFileSync(mdPath, table)
  console.log(`\n${table}`)
  console.log(`\nSaved: ${runDir}`)
  if (failure) process.exitCode = 1
}
