// P2: the vocabulary is the single owner of denial codes, the denial wire
// format, guard-fact shapes, load-error codes, and the projection wire
// schemas. These tests pin the wire formats so guard, reducers, e2e greps,
// and session-2 consumers cannot drift apart silently.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ALL_DENIAL_CODES,
  CHAPTER_DENIAL_CODES,
  GUARD_FACT_EVENT,
  GuardConfigError,
  EXPORT_DENIAL_CODES,
  PAGE_DENIAL_CODES,
  denialReason,
  integrationStatusSchema,
  pageBudgetSchema,
  parseDenialText,
  parseGuardFact,
  revisionAttemptsSchema,
} from '../src/vocabulary.ts'

test('the denial-code catalogue is exactly the six codes — five from P1 plus the P4 export gate', () => {
  assert.deepEqual([...CHAPTER_DENIAL_CODES], ['NOTES_MISSING', 'QUOTE_SPAN_MODIFIED', 'CONTRACT_SCOPE'])
  assert.deepEqual([...PAGE_DENIAL_CODES], ['PAGE_RANGE_EXCEEDED', 'PAGE_BUDGET_EXCEEDED'])
  assert.deepEqual([...EXPORT_DENIAL_CODES], ['EXPORT_SOURCES_UNRESOLVED'])
  assert.equal(ALL_DENIAL_CODES.length, 6)
  // ESCALATION_REQUIRED must NOT be claimed until the session-2 ask seam ships.
  assert.ok(!(ALL_DENIAL_CODES as readonly string[]).includes('ESCALATION_REQUIRED'))
})

test('denialReason round-trips through the durable tool/result form', () => {
  const reason = denialReason('NOTES_MISSING', 'chapter edit cites jones 2021')
  assert.equal(reason, 'NOTES_MISSING: chapter edit cites jones 2021')
  // As the guard returned it.
  assert.deepEqual(parseDenialText(reason), { code: 'NOTES_MISSING', detail: 'chapter edit cites jones 2021' })
  // As rc.6 persists it (`Error: <reason>` in the tool/result text).
  assert.deepEqual(parseDenialText(`Error: ${reason}`), { code: 'NOTES_MISSING', detail: 'chapter edit cites jones 2021' })
})

test('parseDenialText refuses foreign producers', () => {
  assert.equal(parseDenialText('Error: SOMETHING_ELSE: not ours'), undefined)
  assert.equal(parseDenialText('Error: file not found'), undefined)
  assert.equal(parseDenialText('plain tool output'), undefined)
})

test('parseGuardFact accepts each fact kind and normalises optionals', () => {
  assert.deepEqual(parseGuardFact({ kind: 'page-read', callId: 'c1', pages: 12 }), { kind: 'page-read', callId: 'c1', pages: 12 })
  assert.deepEqual(
    parseGuardFact({ kind: 'revision-attempt', contract: 'contracts/c.md', path: 'chapters/ch3.md', outcome: 'CONTRACT_SCOPE', callId: 'c2' }),
    { kind: 'revision-attempt', contract: 'contracts/c.md', path: 'chapters/ch3.md', outcome: 'CONTRACT_SCOPE', callId: 'c2' }
  )
  assert.deepEqual(
    parseGuardFact({ kind: 'integration-status', source: 'smith 2024', status: 'planned' }),
    { kind: 'integration-status', source: 'smith 2024', status: 'planned' }
  )
})

test('parseGuardFact returns undefined for malformed or newer-vocabulary facts', () => {
  assert.equal(parseGuardFact(undefined), undefined)
  assert.equal(parseGuardFact({ kind: 'page-read', callId: '', pages: 3 }), undefined)
  assert.equal(parseGuardFact({ kind: 'page-read', callId: 'c1', pages: -1 }), undefined)
  assert.equal(parseGuardFact({ kind: 'revision-attempt', contract: 'c', path: 'p', outcome: 'exploded' }), undefined)
  assert.equal(parseGuardFact({ kind: 'integration-status', source: 's', status: 'shipped' }), undefined)
  assert.equal(parseGuardFact({ kind: 'from-the-future', anything: 1 }), undefined)
})

test('wire schemas accept their own values and throw on garbage', () => {
  assert.doesNotThrow(() => pageBudgetSchema.parse({ pagesRead: 3, reads: [{ callId: 'c', pages: 3 }], unrecognizedFacts: 0 }))
  assert.throws(() => pageBudgetSchema.parse({ pagesRead: -1, reads: [], unrecognizedFacts: 0 }), TypeError)
  assert.throws(() => pageBudgetSchema.parse({ pagesRead: 1, reads: [{}], unrecognizedFacts: 0 }), TypeError)

  assert.doesNotThrow(() => revisionAttemptsSchema.parse({
    contracts: [{ contract: 'contracts/c.md', active: true, attempts: 1, applied: 0, denied: 1, escalationPending: false }],
    unrecognizedFacts: 0,
  }))
  assert.throws(() => revisionAttemptsSchema.parse({ contracts: [{ contract: 'c' }], unrecognizedFacts: 0 }), TypeError)

  assert.doesNotThrow(() => integrationStatusSchema.parse({
    sources: [{ source: 'smith 2024', status: 'integrated', chapters: ['chapters/ch3.md'] }],
    unrecognizedFacts: 0,
  }))
  assert.throws(() => integrationStatusSchema.parse({ sources: [{ source: 's', status: 'done', chapters: [] }], unrecognizedFacts: 0 }), TypeError)
  assert.throws(() => integrationStatusSchema.parse(null), TypeError)
})

test('GuardConfigError carries its typed code and the awt-guards prefix', () => {
  const error = new GuardConfigError('NOTES_ROOT_MISSING', 'nope')
  assert.equal(error.code, 'NOTES_ROOT_MISSING')
  assert.match(error.message, /^awt-guards: NOTES_ROOT_MISSING: nope$/)
  assert.equal(error.name, 'GuardConfigError')
})

test('the guard-fact event type is namespaced to this plugin', () => {
  assert.equal(GUARD_FACT_EVENT, 'awt-guards/fact')
})
