// scripts/audit-citation-fidelity.mjs (P4 item 4): the audit's four findings
// pinned on temp workspaces, plus the honesty test — a citing sentence that
// INVERTS its source in the source's own words, which the tool is REQUIRED
// to pass without a finding, while its output states that limit. The limit
// is a tested claim, not a README sentence.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { notesFixture } from './dsh-harness.ts'

const AUDIT = resolve(import.meta.dirname, '..', '..', 'scripts', 'audit-citation-fidelity.mjs')
const dirs: string[] = []
after(() => { for (const d of dirs.splice(0)) rmSync(d, { recursive: true, force: true }) })

function workspace(chapter: string, notes: string = notesFixture()): string {
  const ws = mkdtempSync(join(tmpdir(), 'awt-fidelity-'))
  dirs.push(ws)
  mkdirSync(join(ws, 'chapters'), { recursive: true })
  mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  writeFileSync(join(ws, 'literature', 'reading_notes', 'smith2024_NOTES.md'), notes)
  writeFileSync(join(ws, 'chapters', 'ch1.md'), chapter)
  return ws
}

function run(ws: string) {
  const res = spawnSync(process.execPath, [AUDIT, '--base-dir', ws, '--json'], { encoding: 'utf8', timeout: 60_000 })
  assert.ok(res.stdout.trim().startsWith('{'), `expected JSON, got: ${res.stdout.slice(0, 200)} ${res.stderr.slice(0, 200)}`)
  return { status: res.status, out: JSON.parse(res.stdout) as { findings: Array<{ kind: string; detail: string; experimental?: boolean }>; limits: Record<string, string>; hard_finding_count: number } }
}

const kinds = (out: { findings: Array<{ kind: string }> }) => out.findings.map((f) => f.kind).sort()

test('a verbatim quote with the right page passes with no finding', () => {
  const { status, out } = run(workspace('Smith (2024) writes that "the archive is not a neutral container of the past" (p.12).\n'))
  assert.deepEqual(kinds(out), [])
  assert.equal(status, 0)
})

test('a quote that is not in the source is a hard finding', () => {
  const { status, out } = run(workspace('Smith (2024) claims that "archives always mirror reality without judgement" (p.12).\n'))
  assert.deepEqual(kinds(out), ['quote-not-in-source'])
  assert.equal(status, 1)
})

test('a verbatim quote cited on the wrong page is a page-mismatch against the notes annotation', () => {
  const { out } = run(workspace('Smith (2024) writes that "the archive is not a neutral container of the past" (p.7).\n'))
  assert.deepEqual(kinds(out), ['page-mismatch'])
  assert.match(out.findings[0].detail, /cited p\.7; the notes place the quote on p\.12/)
})

test('a citation with no notes file is reported, never guessed at', () => {
  const { out } = run(workspace('Jones (2021) argues that memory is contested terrain.\n'))
  assert.deepEqual(kinds(out), ['notes-missing'])
})

test('the first prose sentence after each Markdown heading is audited', () => {
  const { out } = run(workspace(
    '# Chapter introduction\r\n\r\nJones (2021) argues that memory is contested terrain.\r\n\r\n' +
    '  ## Another section\n\nBrown (2020) discusses a different archive.\n',
  ))
  assert.deepEqual(kinds(out), ['notes-missing', 'notes-missing'])
})

test('heading-only citations remain outside the prose audit', () => {
  const { out } = run(workspace('# Jones (2021)\n\nAn uncited introduction.\n'))
  assert.deepEqual(kinds(out), [])
})

test('low-overlap is experimental: flagged, labelled, and never a failure', () => {
  const { status, out } = run(workspace('Smith (2024) demonstrates that retrieval latency dominates throughput budgets in sharded clusters.\n'))
  assert.deepEqual(kinds(out), ['low-overlap'])
  assert.equal(out.findings[0].experimental, true)
  assert.equal(status, 0)
})

test('HONESTY: a sentence inverting its source in the source\'s own words is NOT caught, and the output says so', () => {
  // The notes record the source as arguing that archives are agents of memory
  // that actively shape it. The chapter asserts the opposite using the same
  // vocabulary, without a quote. Every check here is a proxy; none reads.
  const { status, out } = run(workspace(
    'Smith (2024) shows that archives passively store collective memory rather than actively shape it, so archival practice is not a form of authorship.\n',
  ))
  assert.deepEqual(kinds(out), [], 'if this ever reports a finding, the inversion limit changed — update the limit statement AND this test')
  assert.equal(status, 0)
  assert.match(out.limits.semantic_inversion, /NOT detected/)
})
