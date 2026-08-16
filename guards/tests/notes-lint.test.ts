import { test } from 'node:test'
import assert from 'node:assert/strict'
import { lintNotes, hasErrors } from '../src/notes-lint.ts'

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
  const issues = lintNotes(bad)
  assert.ok(issues.some((i) => i.code === 'status-invalid' && i.severity === 'error'))
})

test('missing Thesis Connections table fails', () => {
  const bad = CONFORMING.replace(
    /## Thesis Connections[\s\S]*?\| Point one \| Ch3 \| S3\.2 \| supports \|/,
    '## Thesis Connections\n\n- Point one relates to Ch3.'
  )
  const issues = lintNotes(bad)
  assert.ok(issues.some((i) => i.code === 'connections-not-table' && i.severity === 'error'))
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
