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
  rmSync, symlinkSync, writeFileSync, createReadStream,
} from 'node:fs'
import { createHash } from 'node:crypto'
import { tmpdir } from 'node:os'
import { isAbsolute, join, resolve } from 'node:path'
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
const RUN_TIMEOUT_MS = 600_000

const args = process.argv.slice(2)
const REAL = args.includes('--real')
const manifestPath = args.includes('--manifest')
  ? resolve(args[args.indexOf('--manifest') + 1])
  : join(E1_DIR, 'pdfs.json')
const outDir = args.includes('--out')
  ? resolve(args[args.indexOf('--out') + 1])
  : join(E1_DIR, 'results')

const { lintNotes, hasErrors } = await import(join(GUARDS_DIST, 'notes-lint.js'))
const { extractCitations } = await import(join(GUARDS_DIST, 'decisions.js'))

function die(code, message, remedy) {
  console.error(`${code}: ${message}`)
  if (remedy) console.error(`  remedy: ${remedy}`)
  process.exit(1)
}

if (!existsSync(DSH_BIN)) die('E1_DSH_MISSING', `pinned dsh launcher missing at ${DSH_BIN}`, 'cd e2e && npm ci')
if (!existsSync(join(GUARDS_DIST, 'dsh-plugin.js'))) die('E1_GUARDS_UNBUILT', 'guards/dist missing', 'cd guards && npm install && npm run build')

// --- manifest ---------------------------------------------------------------------

function sha256(path) {
  return new Promise((resolveHash, reject) => {
    const hash = createHash('sha256')
    createReadStream(path).on('data', (d) => hash.update(d)).on('end', () => resolveHash(hash.digest('hex'))).on('error', reject)
  })
}

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
  if (!process.env.DEEPSEEK_API_KEY && !process.env.ANTHROPIC_API_KEY) {
    die('E1_KEY_MISSING', 'the real lane needs DEEPSEEK_API_KEY or ANTHROPIC_API_KEY in the environment', 'export a key, or run the offline lane (no flag)')
  }
  if (!existsSync(manifestPath)) {
    die('E1_MANIFEST_MISSING', `no manifest at ${manifestPath}`, 'copy e1/pdfs.example.json to e1/pdfs.json and point it at three local PDFs (never committed)')
  }
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
  for (const entry of manifest.pdfs) {
    const path = isAbsolute(entry.path) ? entry.path : resolve(E1_DIR, entry.path)
    if (!existsSync(path)) die('E1_PDF_MISSING', `${entry.id}: no file at ${path}`)
    const digest = await sha256(path)
    if (entry.sha256 !== digest) {
      die('E1_PDF_HASH_MISMATCH', `${entry.id}: manifest sha256 ${entry.sha256} != actual ${digest}`, 'the published claim must byte-identify its inputs; update the manifest deliberately')
    }
    entry.path = path
  }
  return manifest.pdfs
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
      symlinkSync(join(SKILLS_SRC, name), join(ws, '.agents', 'skills', name))
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
  const res = spawnSync(
    process.execPath,
    [DSH_BIN, '--profile', 'awt-headless', task],
    {
      cwd: ws,
      env: {
        PATH: process.env.PATH,
        LANG: process.env.LANG ?? 'en_US.UTF-8',
        HOME: process.env.HOME,
        DSH_HOME: home,
        DSH_TELEMETRY_DISABLED: '1',
        ...(REAL
          ? {
            ...(process.env.DEEPSEEK_API_KEY ? { DEEPSEEK_API_KEY: process.env.DEEPSEEK_API_KEY } : {}),
            ...(process.env.ANTHROPIC_API_KEY ? { ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY } : {}),
          }
          : {}),
        ...extraEnv,
      },
      encoding: 'utf8',
      timeout: RUN_TIMEOUT_MS,
    },
  )
  return res
}

function referenceFor(entry) {
  if (!REAL) return readFileSync(entry.referenceTextPath, 'utf8')
  // Regenerate exactly what the read_pdf tool shows the model.
  const res = spawnSync('pdftotext', ['-layout', '-f', String(entry.firstPage), '-l', String(entry.lastPage), entry.path, '-'],
    { encoding: 'utf8', timeout: 60_000, maxBuffer: 16 * 1024 * 1024 })
  if (res.status !== 0) die('E1_PDFTOTEXT_FAILED', `pdftotext failed for ${entry.id}`)
  const pages = res.stdout.split('\f').filter((p) => p.trim() !== '')
  return pages.map((p, i) => `--- page ${entry.firstPage + i} ---\n${p.trimEnd()}`).join('\n\n')
}

function collectArtifacts(ws) {
  const notesDir = join(ws, 'literature', 'reading_notes')
  const notesFile = readdirSync(notesDir).find((f) => f.endsWith('_NOTES.md') && f !== '_template_NOTES.md')
  const chapters = readdirSync(join(ws, 'chapters'))
  const draftFile = chapters.find((f) => f.endsWith('.md'))
  return {
    notesText: notesFile ? readFileSync(join(notesDir, notesFile), 'utf8') : undefined,
    draftText: draftFile ? readFileSync(join(ws, 'chapters', draftFile), 'utf8') : undefined,
  }
}

const NOTES_TASK = (entry) => REAL
  ? `Read pages ${entry.firstPage}-${entry.lastPage} of ${entry.path} using the read_pdf tool, then write a reading-notes file literature/reading_notes/${entry.id}_NOTES.md following literature/reading_notes/_template_NOTES.md exactly. Quote at least two passages verbatim with their page numbers.`
  : 'E1 offline notes task'
const DRAFT_TASK = () => REAL
  ? 'Write chapters/draft_section.md: a ~300-word thesis section arguing from the source you have read, quoting evidence verbatim with page numbers and Harvard citations.'
  : 'E1 offline draft task'

async function runArm(entry, arm) {
  const ws = buildWorkspace(arm)
  const home = buildHome(arm)
  const scripts = REAL ? undefined : offlineScripts(entry, arm, ws)
  const scriptEnv = (script) => {
    if (script === undefined) return {}
    const path = join(scratch('awt-e1-script-'), 'script.json')
    writeFileSync(path, JSON.stringify(script))
    return { AWT_E1_SCRIPT: path, AWT_E1_REFERENCE: entry.referenceTextPath }
  }

  const runs = []
  runs.push(runHeadless(home, ws, NOTES_TASK(entry), scriptEnv(scripts?.notes)))
  runs.push(runHeadless(home, ws, DRAFT_TASK(entry), scriptEnv(scripts?.draft)))
  for (const [i, res] of runs.entries()) {
    if (res.status !== 0) {
      const tail = `${res.stderr ?? ''}`.trim().split('\n').slice(-4).join(' | ')
      console.error(`  ${arm} run ${i + 1} exited ${res.status}: ${tail}`)
    }
  }

  const { notesText, draftText } = collectArtifacts(ws)
  const referenceText = referenceFor(entry)
  const pages = pagesFromLabeledText(referenceText)
  const spans = [
    ...extractQuotedSpans(notesText ?? ''),
    ...extractQuotedSpans(draftText ?? ''),
  ]
  return {
    arm,
    quoteFidelity: gradeQuoteFidelity(spans, referenceText),
    pageAccuracy: gradePageAccuracy(spans, pages),
    notes: gradeNotesParseability(notesText, lintNotes, hasErrors),
    unopenedCitations: gradeUnopenedCitations(draftText, [entry.source], extractCitations),
    runExitCodes: runs.map((r) => r.status),
  }
}

// --- main -------------------------------------------------------------------------

const lane = REAL ? 'real' : 'offline'
const entries = await loadEntries()
const results = []
try {
  for (const entry of entries) {
    console.log(`E1 ${lane}: ${entry.id}`)
    for (const arm of ['skills', 'plain']) {
      const graded = await runArm(entry, arm)
      results.push({ id: entry.id, ...graded })
      console.log(`  ${arm}: quotes ${graded.quoteFidelity.matched}/${graded.quoteFidelity.quotes} verbatim, pages ${graded.pageAccuracy.correct}/${graded.pageAccuracy.cited} correct, notes ${graded.notes.parseable ? 'parseable' : 'NOT parseable'}, unopened citations ${graded.unopenedCitations.unopened.length}`)
    }
  }
} finally {
  for (const dir of scratchRoots.splice(0)) rmSync(dir, { recursive: true, force: true })
}

mkdirSync(outDir, { recursive: true })
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
const payload = {
  lane,
  generatedAt: new Date().toISOString(),
  harness: `@deepseek-ai/dsh@${PINNED_DSH}`,
  producer: 'e1/run-e1.mjs',
  note: lane === 'offline'
    ? 'Offline lane: scripted synthetic arms. Proves the instrument discriminates (E0 about the instrument); NOT efficacy evidence about the skills.'
    : 'Real lane: paired sessions over the manifest PDFs. E1 evidence per §11.',
  results,
}
const jsonPath = join(outDir, `e1-${lane}-${stamp}.json`)
writeFileSync(jsonPath, JSON.stringify(payload, null, 2))

const rows = results.map((r) =>
  `| ${r.id} | ${r.arm} | ${r.quoteFidelity.matched}/${r.quoteFidelity.quotes} | ${r.pageAccuracy.correct}/${r.pageAccuracy.cited} | ${r.notes.parseable ? 'yes' : 'no'} | ${r.unopenedCitations.unopened.length} |`)
const table = [
  `# E1 ${lane} results (${payload.generatedAt})`,
  '',
  payload.note,
  '',
  '| source | arm | verbatim quotes | correct pages | notes parseable | unopened citations |',
  '| --- | --- | --- | --- | --- | --- |',
  ...rows,
  '',
  `Producer: \`${payload.producer}\` against \`${payload.harness}\`. Metrics JSON: \`${jsonPath}\`.`,
].join('\n')
const mdPath = join(outDir, `e1-${lane}-${stamp}.md`)
writeFileSync(mdPath, table)
console.log(`\n${table}`)
