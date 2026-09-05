// Unit tests for the E1 machine graders (P3 spec item 3): pure-function
// behavior pinned offline, wired to the same lint and citation extraction
// the enforcement uses.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractQuotedSpans,
  gradeNotesParseability,
  gradePageAccuracy,
  gradeQuoteFidelity,
  gradeUnopenedCitations,
  pagesFromLabeledText,
  // eslint-disable-next-line import/no-relative-packages
} from '../../e1/graders.mjs'
import { lintNotes, hasErrors } from '../src/notes-lint.ts'
import { extractCitations } from '../src/decisions.ts'
import { notesFixture } from './dsh-harness.ts'

const REFERENCE = `--- page 12 ---
Smith argues that the archive is not a neutral container of the past, but an
instrument of curation.

--- page 13 ---
Digital archives accelerate this authorship: selection happens at scale.`

test('extractQuotedSpans finds quotes with and without page references, skipping short idiom', () => {
  const spans = extractQuotedSpans(
    'As Smith says, "the archive is not a neutral container of the past" (p.12). ' +
    'This is "very good" work. Also: “selection happens at scale” (Smith, 2024, p. 13).'
  )
  assert.deepEqual(spans.map((s) => s.page), [12, 13])
  assert.match(spans[0].quote, /neutral container/)
})

test('quote fidelity matches verbatim spans and reports fabricated ones', () => {
  const pages = pagesFromLabeledText(REFERENCE)
  assert.deepEqual([...pages.keys()], [12, 13])
  const good = extractQuotedSpans('"the archive is not a neutral container of the past" (p.12)')
  const bad = extractQuotedSpans('"archives are always neutral containers of history" (p.12)')
  assert.deepEqual(gradeQuoteFidelity(good, REFERENCE), { quotes: 1, matched: 1, misses: [] })
  const graded = gradeQuoteFidelity(bad, REFERENCE)
  assert.equal(graded.matched, 0)
  assert.equal(graded.misses.length, 1)
})

test('page accuracy distinguishes right page, wrong page, and uncited quotes', () => {
  const pages = pagesFromLabeledText(REFERENCE)
  const spans = extractQuotedSpans(
    '"the archive is not a neutral container of the past" (p.12). ' +
    '"selection happens at scale" (p.12). ' +
    '"an instrument of curation" appears too.'
  )
  const graded = gradePageAccuracy(spans, pages)
  assert.equal(graded.cited, 2)
  assert.equal(graded.correct, 1)
  assert.equal(graded.uncited, 1)
  assert.deepEqual(graded.wrong[0].page, 12)
})

test('notes parseability delegates to the shipped lint', () => {
  const good = gradeNotesParseability(notesFixture(), lintNotes, hasErrors)
  assert.deepEqual(good, { present: true, parseable: true, errors: [] })
  const bad = gradeNotesParseability('# not really notes', lintNotes, hasErrors)
  assert.equal(bad.parseable, false)
  assert.ok(bad.errors.length > 0)
  assert.equal(gradeNotesParseability(undefined, lintNotes, hasErrors).present, false)
})

test('unopened-citation count uses the guards citation extractor', () => {
  const draft = 'Smith (2024) shows curation at work; critics disagree (Jones, 2021, p. 3).'
  const graded = gradeUnopenedCitations(draft, [{ surname: 'smith', year: '2024' }], extractCitations)
  assert.equal(graded.citations, 2)
  assert.deepEqual(graded.unopened, ['jones 2021'])
})
