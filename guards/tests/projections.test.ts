// Harness-neutral fold tests for the three P2 projections. Events are built
// in the exact rc.6 durable shapes (`tool/call` carries the RAW JSON
// arguments string; `tool/result` carries a ToolResultMessage whose single
// block is the tool-result block) so the folds are tested against what the
// session store actually persists, not a convenient invention.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  createIntegrationStatusProjection,
  createRevisionAttemptsProjection,
  foldProjection,
  pageBudgetProjection,
  parseContractSource,
  parseNotesSource,
  relativeToRoot,
  type SessionEventLike,
} from '../src/projections.ts'
import { GUARD_FACT_EVENT } from '../src/vocabulary.ts'

const ROOT = '/ws'
let seq = 0
function event(type: string, data: unknown, ignorable?: true): SessionEventLike {
  return { type, seq: seq++, time: 1_700_000_000_000 + seq, data, ...(ignorable ? { ignorable } : {}) }
}

function toolCall(callId: string, name: string, args: Record<string, unknown>): SessionEventLike {
  return event('tool/call', { turn: 1, step: 1, callId, name, arguments: JSON.stringify(args) })
}

function toolResult(callId: string, opts: { isError?: boolean; text?: string } = {}): SessionEventLike {
  return event('tool/result', {
    turn: 1,
    step: 1,
    message: {
      id: `m-${callId}`,
      role: 'user',
      content: [{
        type: 'tool-result',
        toolCallId: callId,
        content: [{ type: 'text', text: opts.text ?? 'ok' }],
        isError: opts.isError === true,
      }],
      source: { kind: 'tool' },
    },
  })
}

function fact(data: unknown): SessionEventLike {
  return event(GUARD_FACT_EVENT, data, true)
}

const readPdf = (callId: string, first: number, last: number) =>
  toolCall(callId, 'read_pdf', { file_path: `${ROOT}/literature/a.pdf`, first_page: first, last_page: last })

// --- page budget ---------------------------------------------------------------

test('page budget: only completed reads consume pages; a denied read consumes nothing', () => {
  const value = foldProjection(pageBudgetProjection, [
    readPdf('c1', 1, 10),
    toolResult('c1'),
    readPdf('c2', 1, 16),
    toolResult('c2', { isError: true, text: 'Error: PAGE_RANGE_EXCEEDED: requested 16 pages' }),
    readPdf('c3', 1, 5), // still pending — no result yet
  ])
  assert.equal(value.pagesRead, 10)
  assert.deepEqual(value.reads, [{ callId: 'c1', pages: 10 }])
  assert.equal(value.unrecognizedFacts, 0)
})

test('page budget: an uninterested event returns the same state reference (rc.6 drive contract)', () => {
  const state = pageBudgetProjection.init()
  const untouched = pageBudgetProjection.apply(state, event('assistant/chunk', { turn: 1, step: 1, chunk: {} }))
  assert.ok(Object.is(state, untouched))
  const foreignTool = pageBudgetProjection.apply(state, toolCall('x', 'write', { file_path: 'a.md', content: 'x' }))
  assert.ok(Object.is(state, foreignTool))
})

test('page budget: the structured fact channel dedupes against the derived channel by callId, both orders', () => {
  // fact first, then the derived pair: the event channel owns the row.
  const factFirst = foldProjection(pageBudgetProjection, [
    fact({ kind: 'page-read', callId: 'c1', pages: 10 }),
    readPdf('c1', 1, 10),
    toolResult('c1'),
  ])
  assert.equal(factFirst.pagesRead, 10)
  assert.equal(factFirst.reads.length, 1)

  // derived pair first, then the fact replay: still one row, event value wins.
  const derivedFirst = foldProjection(pageBudgetProjection, [
    readPdf('c1', 1, 10),
    toolResult('c1'),
    fact({ kind: 'page-read', callId: 'c1', pages: 10 }),
  ])
  assert.equal(derivedFirst.pagesRead, 10)
  assert.equal(derivedFirst.reads.length, 1)

  // a fact for a call the derived channel never completed counts once.
  const factOnly = foldProjection(pageBudgetProjection, [fact({ kind: 'page-read', callId: 'c9', pages: 7 })])
  assert.equal(factOnly.pagesRead, 7)
})

test('page budget: an unparseable awt-guards/fact is counted loudly, never skipped', () => {
  const value = foldProjection(pageBudgetProjection, [
    fact({ kind: 'page-read-v2', callId: 'c1', pages: 10 }), // newer vocabulary
    fact({ kind: 'page-read', callId: 'c2', pages: 3 }),
  ])
  assert.equal(value.unrecognizedFacts, 1)
  assert.equal(value.pagesRead, 3)
})

test('page budget: view passes its own wire schema', () => {
  const events = [readPdf('c1', 2, 4), toolResult('c1')]
  const state = events.reduce((s, e) => pageBudgetProjection.apply(s, e), pageBudgetProjection.init())
  assert.doesNotThrow(() => pageBudgetProjection.schema.parse(pageBudgetProjection.view(state)))
})

// --- revision attempts -----------------------------------------------------------

const CONTRACT_BODY = `# Edit Contract: ch3
- Spine: Ch3 argues X.
- May change: chapters/ch3.md
- Must not change: chapters/ch2.md

## Attempts
- [ ] Attempt 1: pending
`

const writeContract = (callId: string, body = CONTRACT_BODY, path = `${ROOT}/contracts/c1.md`) =>
  toolCall(callId, 'write', { file_path: path, content: body })

const writeChapter = (callId: string, path = `${ROOT}/chapters/ch3.md`, content = 'New paragraph.') =>
  toolCall(callId, 'write', { file_path: path, content })

test('revision attempts: a contract written through the log activates, and chapter writes fold as attempts with typed outcomes', () => {
  const projection = createRevisionAttemptsProjection(ROOT)
  const value = foldProjection(projection, [
    writeContract('k1'),
    toolResult('k1'),
    writeChapter('k2'),
    toolResult('k2'),
    writeChapter('k3', `${ROOT}/chapters/ch5.md`),
    toolResult('k3', { isError: true, text: 'Error: CONTRACT_SCOPE: "chapters/ch5.md" is outside the scope.' }),
    writeChapter('k4'),
    toolResult('k4', { isError: true, text: 'Error: something the tool body threw' }),
  ])
  assert.equal(value.contracts.length, 1)
  const row = value.contracts[0]
  assert.equal(row.contract, 'contracts/c1.md')
  assert.equal(row.active, true)
  assert.equal(row.attempts, 3)
  assert.equal(row.applied, 1)
  assert.equal(row.denied, 1) // only the typed AWT denial counts as denied
  assert.equal(row.escalationPending, false)
  assert.equal(value.unrecognizedFacts, 0)
})

test('revision attempts: three typed denials flip escalationPending (the session-2 ask-gate input)', () => {
  const projection = createRevisionAttemptsProjection(ROOT)
  const events: SessionEventLike[] = [writeContract('k1'), toolResult('k1')]
  for (let i = 0; i < 3; i++) {
    events.push(writeChapter(`d${i}`, `${ROOT}/chapters/ch3.md`))
    events.push(toolResult(`d${i}`, { isError: true, text: 'Error: QUOTE_SPAN_MODIFIED: edit alters a quotation span' }))
  }
  const value = foldProjection(projection, events)
  assert.equal(value.contracts[0].denied, 3)
  assert.equal(value.contracts[0].escalationPending, true)
})

test('revision attempts: no active contract means chapter writes are not attempts; a failed contract write activates nothing', () => {
  const projection = createRevisionAttemptsProjection(ROOT)
  const value = foldProjection(projection, [
    writeChapter('k0'),
    toolResult('k0'),
    writeContract('k1'),
    toolResult('k1', { isError: true, text: 'Error: disk full' }),
    writeChapter('k2'),
    toolResult('k2'),
  ])
  assert.deepEqual(value.contracts, [])
})

test('revision attempts: a rewrite with every box checked deactivates the contract in the fold', () => {
  const projection = createRevisionAttemptsProjection(ROOT)
  const closed = CONTRACT_BODY.replace('- [ ] Attempt 1', '- [x] Attempt 1')
  const value = foldProjection(projection, [
    writeContract('k1'),
    toolResult('k1'),
    writeContract('k2', closed),
    toolResult('k2'),
    writeChapter('k3'),
    toolResult('k3'),
  ])
  assert.equal(value.contracts[0].active, false)
  assert.equal(value.contracts[0].attempts, 0) // no active contract at attempt time
})

test('revision attempts: the structured fact channel dedupes by callId and owns the attempt', () => {
  const projection = createRevisionAttemptsProjection(ROOT)
  const value = foldProjection(projection, [
    writeContract('k1'),
    toolResult('k1'),
    writeChapter('k2'),
    toolResult('k2'),
    // The session-2 writer restates the same attempt as a structured fact.
    fact({ kind: 'revision-attempt', contract: 'contracts/c1.md', path: 'chapters/ch3.md', outcome: 'applied', callId: 'k2' }),
    fact({ kind: 'revision-attempt', contract: 'contracts/c1.md', path: 'chapters/ch3.md', outcome: 'applied', callId: 'k2' }),
  ])
  assert.equal(value.contracts[0].attempts, 1)
  assert.equal(value.contracts[0].applied, 1)
})

test('revision attempts: a fact for a contract the derived channel never saw opens its row', () => {
  const projection = createRevisionAttemptsProjection(ROOT)
  const value = foldProjection(projection, [
    fact({ kind: 'revision-attempt', contract: 'contracts/manual.md', path: 'chapters/ch1.md', outcome: 'NOTES_MISSING' }),
  ])
  assert.equal(value.contracts.length, 1)
  assert.equal(value.contracts[0].contract, 'contracts/manual.md')
  assert.equal(value.contracts[0].denied, 1)
})

// --- integration status ------------------------------------------------------------

const NOTES_BODY = `# Reading Notes: Smith (2024)

**Source**: Smith, J. (2024) The archive and memory. *Example Press*.
**Status**: completed
`

test('integration status: notes write marks noted, chapter citation write marks integrated, never downgrading', () => {
  const projection = createIntegrationStatusProjection(ROOT)
  const value = foldProjection(projection, [
    toolCall('n1', 'write', { file_path: `${ROOT}/literature/reading_notes/smith2024_NOTES.md`, content: NOTES_BODY }),
    toolResult('n1'),
    writeChapter('w1', `${ROOT}/chapters/ch3.md`, 'Smith (2024) shows that archives shape memory.'),
    toolResult('w1'),
    // a later notes re-write must not downgrade integrated -> noted
    toolCall('n2', 'write', { file_path: `${ROOT}/literature/reading_notes/smith2024_NOTES.md`, content: NOTES_BODY }),
    toolResult('n2'),
  ])
  assert.deepEqual(value.sources, [{ source: 'smith 2024', status: 'integrated', chapters: ['chapters/ch3.md'] }])
})

test('integration status: a failed chapter write changes nothing; an edit with cited new_string integrates', () => {
  const projection = createIntegrationStatusProjection(ROOT)
  const value = foldProjection(projection, [
    writeChapter('w1', `${ROOT}/chapters/ch3.md`, 'Jones (2021) argues X.'),
    toolResult('w1', { isError: true, text: 'Error: NOTES_MISSING: chapter edit cites sources without notes' }),
    toolCall('e1', 'edit', { file_path: `${ROOT}/chapters/ch4.md`, old_string: 'a', new_string: 'As Lee (2020) shows.' }),
    toolResult('e1'),
  ])
  assert.deepEqual(value.sources, [{ source: 'lee 2020', status: 'integrated', chapters: ['chapters/ch4.md'] }])
})

test('integration status: the fact channel sets statuses verbatim and owns its rows thereafter', () => {
  const projection = createIntegrationStatusProjection(ROOT)
  const value = foldProjection(projection, [
    fact({ kind: 'integration-status', source: 'smith 2024', status: 'planned' }),
    // derived evidence arriving later must not override the event-channel row
    writeChapter('w1', `${ROOT}/chapters/ch3.md`, 'Smith (2024) shows X.'),
    toolResult('w1'),
  ])
  assert.deepEqual(value.sources, [{ source: 'smith 2024', status: 'planned', chapters: [] }])
})

test('integration status: unparseable facts count loudly here too', () => {
  const projection = createIntegrationStatusProjection(ROOT)
  const value = foldProjection(projection, [fact({ kind: 'integration-status', source: 's', status: 'launched' })])
  assert.equal(value.unrecognizedFacts, 1)
  assert.deepEqual(value.sources, [])
})

// --- fold mechanics -----------------------------------------------------------------

test('folds are checkpoint-splittable: folding a prefix then the tail equals folding the whole log', () => {
  const events = [
    writeContract('k1'),
    toolResult('k1'),
    readPdf('c1', 1, 10),
    toolResult('c1'),
    writeChapter('k2', `${ROOT}/chapters/ch3.md`, 'Smith (2024) shows X.'),
    toolResult('k2'),
  ]
  for (const projection of [
    pageBudgetProjection,
    createRevisionAttemptsProjection(ROOT),
    createIntegrationStatusProjection(ROOT),
  ] as const) {
    const whole = foldProjection(projection as never, events) as unknown
    for (let cut = 0; cut <= events.length; cut++) {
      const def = projection as { init(): unknown; apply(s: unknown, e: SessionEventLike): unknown; view(s: unknown): unknown }
      const prefix = events.slice(0, cut).reduce((s, e) => def.apply(s, e), def.init())
      const resumed = events.slice(cut).reduce((s, e) => def.apply(s, e), prefix)
      assert.deepEqual(def.view(resumed), whole)
    }
  }
})

test('relativeToRoot handles absolute, relative, and out-of-root paths', () => {
  assert.equal(relativeToRoot('/ws', '/ws/chapters/ch3.md'), 'chapters/ch3.md')
  assert.equal(relativeToRoot('/ws/', 'chapters/ch3.md'), 'chapters/ch3.md')
  assert.equal(relativeToRoot('/ws', './chapters/ch3.md'), 'chapters/ch3.md')
  assert.equal(relativeToRoot('/ws', '/elsewhere/x.md'), undefined)
})

test('parseContractSource and parseNotesSource are the single parse authority', () => {
  const parsed = parseContractSource(CONTRACT_BODY)
  assert.deepEqual(parsed, { active: true, mayChange: ['chapters/ch3.md'], mustNotChange: ['chapters/ch2.md'] })
  assert.deepEqual(parseNotesSource(NOTES_BODY), { surname: 'smith', year: '2024' })
  assert.equal(parseNotesSource('no source line here'), undefined)
})

// --- #34: folds relativize other-workspace paths by structure ------------------

test('relativeToRoot: inside the boot root by prefix, outside it by workspace marker, unrelated is undefined', () => {
  assert.equal(relativeToRoot('/boot/ws', '/boot/ws/chapters/ch1.md'), 'chapters/ch1.md')
  assert.equal(relativeToRoot('/boot/ws', 'chapters/ch1.md'), 'chapters/ch1.md')
  assert.equal(relativeToRoot('/boot/ws', '/other/thesis/chapters/ch2.md'), 'chapters/ch2.md')
  assert.equal(relativeToRoot('/boot/ws', '/other/thesis/contracts/c.md'), 'contracts/c.md')
  assert.equal(relativeToRoot('/boot/ws', '/other/thesis/literature/reading_notes/x_NOTES.md'), 'literature/reading_notes/x_NOTES.md')
  assert.equal(relativeToRoot('/boot/ws', '/other/thesis/README.md'), undefined)
})
