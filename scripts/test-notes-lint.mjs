// The /note data contract's lint, and the citation extractor and notes-source
// parser the fidelity audit shares with it. These tests ran under the retired
// dsh guards package until 2026-09-20 and moved here with the code
// (docs/specs/2026-09-20-retire-dsh-line-design.md).
import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { lintNotes, hasErrors } from '../.claude/skills/note/scripts/notes-lint.mjs'
import { extractCitations, parseNotesSource } from '../.claude/skills/audit/scripts/citations.mjs'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..')
const LINT = join(PRODUCT_ROOT, '.claude', 'skills', 'note', 'scripts', 'notes-lint.mjs')
const DEMO_NOTES = 'examples/demo-project/literature/reading_notes/smith2024_NOTES.md'

const CONFORMING = `# Reading Notes: Smith -- Methods (2024)

**Source**: Smith, J. (2024) *Methods*. London: Example Press.
**Date read**: 2026-08-16
**Status**: completed
**Evidence status**: full_text
**Relevance**: Ch3 S3.2

---

## Key Arguments

- Point one.

## Detailed Notes

### p.1--2: Introduction

> "quote" (p.1)

## Key Terms

| Term | Translation | Definition in context |
|------|-------------|----------------------|

## Thesis Connections

| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|
| Point one | Ch3 | S3.2 | supports |

## Questions & Follow-ups

- None.

---
*Last updated: 2026-08-16*
`

test('conforming file passes with no errors', () => {
  assert.equal(hasErrors(lintNotes(CONFORMING)), false)
})

// Red-first cases: each proves the lint FAILS on a real contract violation.

test('wrong status vocabulary fails (the shipped demo bug: "complete")', () => {
  const bad = CONFORMING.replace('**Status**: completed', '**Status**: complete')
  assert.ok(lintNotes(bad).some((i) => i.code === 'status-invalid' && i.severity === 'error'))
})

test('missing Thesis Connections table fails', () => {
  const bad = CONFORMING.replace(
    /## Thesis Connections[\s\S]*?\| Point one \| Ch3 \| S3\.2 \| supports \|/,
    '## Thesis Connections\n\n- Point one relates to Ch3.',
  )
  assert.ok(lintNotes(bad).some((i) => i.code === 'connections-not-table' && i.severity === 'error'))
})

test('missing Source line fails', () => {
  const bad = CONFORMING.replace(/\*\*Source\*\*:.*\n/, '')
  assert.ok(lintNotes(bad).some((i) => i.code === 'source-missing' && i.severity === 'error'))
})

test('invalid Evidence status fails; absent Evidence status is only a warning', () => {
  const invalid = CONFORMING.replace('**Evidence status**: full_text', '**Evidence status**: skimmed')
  assert.ok(lintNotes(invalid).some((i) => i.code === 'evidence-status-invalid' && i.severity === 'error'))
  const absent = CONFORMING.replace('**Evidence status**: full_text\n', '')
  const issues = lintNotes(absent)
  assert.equal(hasErrors(issues), false)
  assert.ok(issues.some((i) => i.code === 'evidence-status-missing' && i.severity === 'warning'))
})

test('missing required section fails', () => {
  const bad = CONFORMING.replace('## Key Arguments', '## Arguments')
  assert.ok(lintNotes(bad).some((i) => i.code === 'section-missing'))
})

// --- the CLI, run as the README prints it ---------------------------------

const dirs = []
after(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })

function lintFromRepoRoot(...args) {
  return spawnSync(process.execPath, [LINT, ...args], { cwd: PRODUCT_ROOT, encoding: 'utf8', timeout: 60_000 })
}
const saidBy = (res) => `${res.stdout ?? ''}${res.stderr ?? ''}${res.error ? `\n${res.error.message}` : ''}`

test('the demo command lints a repo-relative path from the repository root', () => {
  const res = lintFromRepoRoot(DEMO_NOTES)
  assert.equal(res.status, 0, `the README's own command failed:\n${saidBy(res)}`)
})

test('a path that does not exist is a message, not a stack trace', () => {
  const res = lintFromRepoRoot('literature/reading_notes/no-such-file_NOTES.md')
  assert.notEqual(res.status, 0)
  const output = saidBy(res)
  assert.doesNotMatch(output, /at readFileSync|at ModuleJob|node:internal/, `raw stack trace:\n${output}`)
  assert.match(output, /no-such-file_NOTES\.md/, 'the message should name the file it could not read')
})

test('an absolute path works, and no file at all is exit 2, not a pass', () => {
  const dir = mkdtempSync(join(tmpdir(), 'awt-lint-cli-'))
  dirs.push(dir)
  const file = join(dir, 'absolute_NOTES.md')
  writeFileSync(file, 'not a notes file')
  const res = lintFromRepoRoot(file)
  assert.notEqual(res.status, 0)
  assert.match(saidBy(res), /absolute_NOTES\.md/)
  assert.doesNotMatch(saidBy(res), /ENOENT/)
  assert.equal(lintFromRepoRoot().status, 2)
})

// --- the extractor and the source parser the fidelity audit relies on -------

test('citation extractor is conservative: legislation-style parentheticals do not match', () => {
  // "Act (1998)" matches the narrative form (capitalised token), an accepted
  // trade-off; "2 (2021)" must NOT match.
  const found = extractCitations('under the Data Protection Act (1998) and wave 2 (2021) of the study')
  assert.ok(!found.some((c) => c.surname === '2'))
  assert.deepEqual(extractCitations('As Smith (2024) and (Jones and Lee, 2021, p. 4) show'),
    [{ surname: 'jones', year: '2021' }, { surname: 'smith', year: '2024' }])
})

test('parseNotesSource reads the Source line and nothing else', () => {
  assert.deepEqual(parseNotesSource(CONFORMING), { surname: 'smith', year: '2024' })
  assert.equal(parseNotesSource('no source line here'), undefined)
})
