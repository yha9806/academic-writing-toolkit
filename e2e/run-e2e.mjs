#!/usr/bin/env node
// P1 closing gate: live end-to-end proof that the AWT guard plugin denies
// forbidden tool calls inside a real DeepSeek Harness (dsh) headless run.
//
// For each scenario this script:
//   1. builds a fresh thesis-workspace fixture in a temp dir (chapters/ch1.md
//      with a quotation span, one conforming notes file for smith 2024, an
//      active edit contract in contracts/),
//   2. builds a fresh $DSH_HOME containing the `awt-headless` profile
//      (dsh-base + dsh-headless bundles, the profile patch in profile/, the
//      SHIPPED guards/dist build mounted on ctx.tools.guard, the scripted
//      LLM adapter, and the read_pdf stub),
//   3. launches the published `dsh` 0.1.0-rc.6 launcher once
//      (`dsh --profile awt-headless "<task>"`) with the scenario's scripted
//      tool call in $AWT_E2E_TOOLCALL,
//   4. asserts the expected typed denial appears in the persisted session
//      log under $DSH_HOME/sessions (and that the negative control's write
//      actually succeeded on disk with no denial at all).
//
// Exit 0 only when every assertion holds. The evidence table at the end is
// real output from the runs, never predicted.
import { spawnSync } from 'node:child_process'
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync,
  statSync, writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const E2E_DIR = resolve(import.meta.dirname)
const GUARDS_DIR = resolve(E2E_DIR, '..', 'guards')
const GUARDS_DIST = join(GUARDS_DIR, 'dist')
const DSH_PKG = join(E2E_DIR, 'node_modules', '@deepseek-ai', 'dsh')
const DSH_BIN = join(DSH_PKG, 'lib', 'bin.js')
const PINNED_DSH_VERSION = '0.1.0-rc.6'
const RUN_TIMEOUT_MS = 180_000
const TODAY = new Date().toISOString().slice(0, 10)

const DENIAL_CODES = [
  'CONTRACT_SCOPE',
  'NOTES_MISSING',
  'QUOTE_SPAN_MODIFIED',
  'PAGE_RANGE_EXCEEDED',
  'PAGE_BUDGET_EXCEEDED',
]

// --- scenarios ---------------------------------------------------------------
// `mayChange` parameterizes the active contract per scenario: the quote-span
// scenario needs chapters/ch1.md inside the contract scope, otherwise the
// (deliberately first-in-order) CONTRACT_SCOPE guard would mask the
// QUOTE_SPAN_MODIFIED denial this scenario isolates.
const SCENARIOS = [
  {
    key: 'contract-scope',
    label: 'write chapters/ch5.md citing Jones (2021), contract scopes ch3 only',
    expect: 'CONTRACT_SCOPE',
    mayChange: 'chapters/ch3.md',
    call: (ws) => ({
      tool: 'write',
      args: {
        file_path: join(ws, 'chapters', 'ch5.md'),
        content: 'Jones (2021) argues that memory is contested terrain.',
      },
    }),
    mustNotExist: (ws) => join(ws, 'chapters', 'ch5.md'),
  },
  {
    key: 'notes-missing',
    label: 'write chapters/ch3.md citing Jones (2021), no notes for jones 2021',
    expect: 'NOTES_MISSING',
    mayChange: 'chapters/ch3.md',
    call: (ws) => ({
      tool: 'write',
      args: {
        file_path: join(ws, 'chapters', 'ch3.md'),
        content: 'Jones (2021) argues that memory is contested terrain.',
      },
    }),
    mustNotExist: (ws) => join(ws, 'chapters', 'ch3.md'),
  },
  {
    key: 'quote-span',
    label: 'edit chapters/ch1.md altering text inside a quotation span',
    expect: 'QUOTE_SPAN_MODIFIED',
    mayChange: 'chapters/ch1.md, chapters/ch3.md',
    call: (ws) => ({
      tool: 'edit',
      args: {
        file_path: join(ws, 'chapters', 'ch1.md'),
        old_string: 'not a neutral container',
        new_string: 'not a passive container',
      },
    }),
    unchanged: (ws) => ({
      path: join(ws, 'chapters', 'ch1.md'),
      mustContain: 'not a neutral container',
    }),
  },
  {
    key: 'allowed-write',
    label: 'negative control: write chapters/ch3.md citing Smith (2024)',
    expect: 'ALLOWED',
    mayChange: 'chapters/ch3.md',
    call: (ws) => ({
      tool: 'write',
      args: {
        file_path: join(ws, 'chapters', 'ch3.md'),
        content: 'Smith (2024) shows that archives shape collective memory.',
      },
    }),
    mustExist: (ws) => ({
      path: join(ws, 'chapters', 'ch3.md'),
      mustContain: 'Smith (2024)',
    }),
  },
  {
    key: 'page-range',
    label: 'stretch: read_pdf 16 pages in one invocation (limit 15)',
    expect: 'PAGE_RANGE_EXCEEDED',
    stretch: true,
    mayChange: 'chapters/ch3.md',
    call: (ws) => ({
      tool: 'read_pdf',
      args: {
        file_path: join(ws, 'literature', 'smith2024.pdf'),
        first_page: 1,
        last_page: 16,
      },
    }),
  },
]

// --- fixture -------------------------------------------------------------------

function buildWorkspace(mayChange) {
  const ws = mkdtempSync(join(tmpdir(), 'awt-e2e-ws-'))
  mkdirSync(join(ws, 'chapters'), { recursive: true })
  mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  mkdirSync(join(ws, 'contracts'), { recursive: true })

  writeFileSync(join(ws, 'chapters', 'ch1.md'), `# Chapter 1: Introduction

As Smith (2024) argues, "the archive is not a neutral container of the past" (Smith, 2024, p. 12).
`)

  // Conforming notes file for exactly one source (smith 2024), built from
  // literature/reading_notes/_template_NOTES.md and passing the notes lint.
  writeFileSync(join(ws, 'literature', 'reading_notes', 'smith2024_NOTES.md'), `# Reading Notes: Smith — The Archive and Memory (2024)

**Source**: Smith, J. (2024) The archive and memory. *Example Press*.
**Date read**: ${TODAY}
**Status**: completed
**Relevance**: Ch3 S3.1 — supports argument about archives
**Evidence status**: full_text

---

## Key Arguments

- Archives actively shape collective memory rather than passively storing it.

## Detailed Notes

### p.10–15: The archive as agent

> "the archive is not a neutral container of the past" (p.12)

Smith frames archival practice as a form of authorship.

## Key Terms

| Term | Translation | Definition in context |
|------|-------------|----------------------|
| archive | — | institutionally curated memory store |

## Thesis Connections

| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|
| archive as agent | Ch3 | S3.1 | supports |

## Questions & Follow-ups

- How does this apply to digital archives?

---
*Last updated: ${TODAY}*
`)

  // Active edit contract: the unchecked attempt box makes it active.
  writeFileSync(join(ws, 'contracts', `${TODAY}-ch3-integration.md`), `# Edit Contract: integrate smith2024 into chapter 3

- Spine: Ch3 argues archives are agents of memory.
- May change: ${mayChange}
- Must not change: chapters/ch2.md

## Attempts
- [ ] Attempt 1: ${TODAY} — pending
`)

  // Placeholder target for the read_pdf stub; the guard denies before the
  // tool body ever opens it.
  writeFileSync(join(ws, 'literature', 'smith2024.pdf'), 'placeholder: guard denies before the tool body runs\n')
  return ws
}

function buildHome() {
  const home = mkdtempSync(join(tmpdir(), 'awt-e2e-home-'))
  const profile = join(home, 'profiles', 'awt-headless')
  mkdirSync(profile, { recursive: true })
  cpSync(join(E2E_DIR, 'profile', 'package.json'), join(profile, 'package.json'))
  cpSync(join(E2E_DIR, 'profile', 'cordis.patch.yml'), join(profile, 'cordis.patch.yml'))
  cpSync(join(E2E_DIR, 'plugins', 'awt-scripted-llm.plugin.mjs'), join(profile, 'awt-scripted-llm.plugin.mjs'))
  cpSync(join(E2E_DIR, 'plugins', 'awt-read-pdf-stub.plugin.mjs'), join(profile, 'awt-read-pdf-stub.plugin.mjs'))
  cpSync(GUARDS_DIST, join(profile, 'awt-guards'), { recursive: true })
  return home
}

// --- session-store scan --------------------------------------------------------

function sessionFiles(home) {
  const root = join(home, 'sessions')
  if (!existsSync(root)) return []
  const files = []
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const p = join(dir, entry)
      if (statSync(p).isDirectory()) walk(p)
      else files.push(p)
    }
  }
  walk(root)
  return files
}

function grepSessions(home, needle) {
  const hits = []
  for (const file of sessionFiles(home)) {
    const lines = readFileSync(file, 'utf8').split('\n')
    lines.forEach((line, i) => {
      if (line.includes(needle)) hits.push({ file, lineNo: i + 1, line })
    })
  }
  return hits
}

// --- run one scenario ----------------------------------------------------------

function runScenario(scenario) {
  const ws = buildWorkspace(scenario.mayChange)
  const home = buildHome()
  const call = scenario.call(ws)
  const failures = []

  const res = spawnSync(
    process.execPath,
    [DSH_BIN, '--profile', 'awt-headless', `AWT guards e2e scenario ${scenario.key}`],
    {
      cwd: ws,
      env: {
        ...process.env,
        DSH_HOME: home,
        DSH_TELEMETRY_DISABLED: '1',
        AWT_E2E_WORKSPACE: ws,
        AWT_E2E_TOOLCALL: JSON.stringify(call),
      },
      encoding: 'utf8',
      timeout: RUN_TIMEOUT_MS,
    },
  )

  if (res.error) failures.push(`dsh failed to spawn: ${res.error.message}`)
  if (res.status !== 0) {
    failures.push(`dsh exited ${res.status ?? `signal ${res.signal}`}; stderr tail: ${(res.stderr ?? '').split('\n').filter(Boolean).slice(-5).join(' | ')}`)
  }
  if (!(res.stdout ?? '').includes('AWT-E2E COMPLETE')) {
    failures.push(`stdout missing scripted completion marker; got: ${JSON.stringify((res.stdout ?? '').slice(0, 200))}`)
  }

  let evidence = ''
  if (scenario.expect === 'ALLOWED') {
    for (const code of DENIAL_CODES) {
      const hits = grepSessions(home, code)
      if (hits.length > 0) failures.push(`unexpected denial ${code} in session log: ${hits[0].file}:${hits[0].lineNo}`)
    }
    const target = scenario.mustExist(ws)
    if (!existsSync(target.path)) {
      failures.push(`negative control did not write ${target.path}`)
    } else if (!readFileSync(target.path, 'utf8').includes(target.mustContain)) {
      failures.push(`${target.path} exists but does not contain ${JSON.stringify(target.mustContain)}`)
    }
    const success = grepSessions(home, '"type":"tool/result"').find((h) => h.line.includes('"isError":false') && h.line.includes('awt-e2e-call-1'))
    if (!success) failures.push('no successful tool/result event for the scripted call in the session log')
    else evidence = `${success.file}:${success.lineNo}`
  } else {
    const hits = grepSessions(home, scenario.expect)
    if (hits.length === 0) failures.push(`expected ${scenario.expect} not found in session log under ${join(home, 'sessions')}`)
    else evidence = `${hits[0].file}:${hits[0].lineNo}`
    for (const code of DENIAL_CODES) {
      if (code === scenario.expect) continue
      const other = grepSessions(home, code)
      if (other.length > 0) failures.push(`unexpected extra denial ${code} in session log`)
    }
    if (scenario.mustNotExist && existsSync(scenario.mustNotExist(ws))) {
      failures.push(`denied call still mutated the workspace: ${scenario.mustNotExist(ws)} exists`)
    }
    if (scenario.unchanged) {
      const { path, mustContain } = scenario.unchanged(ws)
      if (!readFileSync(path, 'utf8').includes(mustContain)) {
        failures.push(`denied edit still mutated ${path}`)
      }
    }
  }

  // The human-readable denial text as the model saw it, for the table.
  let observed = scenario.expect === 'ALLOWED' ? '(no denial; file written)' : ''
  if (scenario.expect !== 'ALLOWED') {
    const hit = grepSessions(home, `Error: ${scenario.expect}`)[0]
    if (hit) {
      // The session-log line is JSON; unescape \" so the full denial text is
      // readable in the table, then trim at the JSON string boundary.
      const unescaped = hit.line.replace(/\\"/g, "'")
      const m = unescaped.match(/Error: [A-Z_]+: [^"]{0,200}/)
      observed = m ? m[0] : `Error: ${scenario.expect}`
    }
  }

  return { scenario, ws, home, failures, evidence, observed }
}

// --- main ----------------------------------------------------------------------

const installedVersion = JSON.parse(readFileSync(join(DSH_PKG, 'package.json'), 'utf8')).version
if (installedVersion !== PINNED_DSH_VERSION) {
  console.error(`FATAL: installed @deepseek-ai/dsh is ${installedVersion}, expected exactly ${PINNED_DSH_VERSION}; run npm install in e2e/ first`)
  process.exit(1)
}

console.log(`dsh: @deepseek-ai/dsh@${installedVersion} (real published launcher, ${DSH_BIN})`)
console.log('building guards kernel: npm run build in guards/ ...')
const build = spawnSync('npm', ['run', 'build'], { cwd: GUARDS_DIR, encoding: 'utf8' })
if (build.status !== 0) {
  console.error(`FATAL: guards build failed:\n${build.stdout}\n${build.stderr}`)
  process.exit(1)
}
if (!existsSync(join(GUARDS_DIST, 'dsh-plugin.js'))) {
  console.error('FATAL: guards/dist/dsh-plugin.js missing after build')
  process.exit(1)
}

const results = []
for (const scenario of SCENARIOS) {
  process.stdout.write(`running ${scenario.key} ... `)
  const result = runScenario(scenario)
  console.log(result.failures.length === 0 ? 'PASS' : 'FAIL')
  for (const f of result.failures) console.log(`    ! ${f}`)
  results.push(result)
}

console.log('\n=== evidence table (scenario -> denial code -> session-log line) ===')
const width = Math.max(...results.map((r) => r.scenario.key.length))
for (const r of results) {
  const status = r.failures.length === 0 ? 'PASS' : 'FAIL'
  console.log(`${status}  ${r.scenario.key.padEnd(width)}  ${r.scenario.expect.padEnd(20)}  ${r.evidence || '(no evidence line)'}`)
  console.log(`      ${' '.repeat(width)}  observed: ${r.observed || '(none)'}`)
}

const requiredFailures = results.filter((r) => !r.scenario.stretch && r.failures.length > 0)
const stretchFailures = results.filter((r) => r.scenario.stretch && r.failures.length > 0)
if (stretchFailures.length > 0) {
  console.log(`\nstretch scenario failed (does not fail the gate): ${stretchFailures.map((r) => r.scenario.key).join(', ')}`)
}
if (requiredFailures.length > 0) {
  console.log(`\nGATE RED: ${requiredFailures.length} required scenario(s) failed`)
  process.exit(1)
}
console.log('\nGATE GREEN: every required scenario produced its typed outcome in a live dsh run' + (stretchFailures.length === 0 ? ' (stretch included)' : ''))
