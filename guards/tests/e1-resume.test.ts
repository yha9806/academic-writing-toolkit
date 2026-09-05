import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { terminalOutcome } from '../../e1/evidence.mjs'
import { classifyRun } from '../../e1/inputs.mjs'
import { readResume } from '../../e1/resume.mjs'

test('a logged model budget exhaustion stays in the measured sample; crashes and ambiguous logs do not', () => {
  const log = JSON.stringify({ type: 'turn/end', data: { reason: { kind: 'max-tokens' } } })
  const outcome = terminalOutcome([log])
  assert.equal(outcome, 'max-tokens')
  assert.equal(terminalOutcome([log, log]), undefined)
  assert.equal(terminalOutcome(['broken']), undefined)
  assert.equal(classifyRun('real', [{ status: 1, outcome }, { status: 0, outcome: 'completed' }], true).evidenceClass, 'E1')
  assert.equal(classifyRun('real', [{ status: 1 }, { status: 0 }], true).evidenceClass, null)
  assert.equal(classifyRun('real', [{ status: 1, outcome, error: { code: 'ETIMEDOUT' } }, { status: 0 }], true).evidenceClass, null)
  const empty = terminalOutcome([JSON.stringify({ type: 'turn/end', data: { reason: { kind: 'error', error: { code: 'EMPTY_RESPONSE' } } } })])
  assert.equal(empty, 'empty-response')
  assert.equal(classifyRun('real', [{ status: 1, outcome: empty }, { status: 0 }], true).evidenceClass, 'E1')
  const unavailable = terminalOutcome([JSON.stringify({ type: 'turn/end', data: { reason: { kind: 'error', error: { code: 'MISSING_CREDENTIAL' } } } })])
  assert.equal(classifyRun('real', [{ status: 1, outcome: unavailable }, { status: 0 }], true).evidenceClass, null)
})

test('continuation binds the original observation to identical sources, graders, model settings and log bytes', () => {
  const root = mkdtempSync(join(tmpdir(), 'awt-e1-resume-'))
  try {
    const run = join(root, 'saved')
    mkdirSync(join(run, 'source/skills/sessions'), { recursive: true })
    const files = ['e1/graders.mjs', 'profiles/awt-headless/awt-read-pdf.plugin.mjs', 'profiles/awt-headless/pdf-pages.mjs', 'guards/dist/notes-lint.js', 'guards/dist/decisions.js']
    const hashes: Record<string, string> = {}
    for (const file of files) {
      mkdirSync(join(root, file, '..'), { recursive: true })
      writeFileSync(join(root, file), file)
      hashes[file] = createHash('sha256').update(file).digest('hex')
    }
    const entries = [{ id: 'source', sha256: 'a'.repeat(64), firstPage: 1, lastPage: 5 }]
    const route = { provider: 'ollama', model: 'fixed', localInfo: { modelDigest: 'b'.repeat(64), contextWindow: 32768 } }
    const prior = { lane: 'real', status: 'incomplete', harness: 'pinned', inputs: entries,
      model: { provider: route.provider, id: route.model, local: route.localInfo }, implementationSha256: hashes,
      results: [{ id: 'source', arm: 'skills', artifacts: 'source/skills', processes: [{ status: 1 }] }] }
    writeFileSync(join(run, 'metrics.json'), JSON.stringify(prior))
    const logFile = join(run, 'source/skills/sessions/one.jsonl')
    writeFileSync(logFile, JSON.stringify({ type: 'turn/end', data: { reason: { kind: 'max-tokens' } } }))
    const resumed = readResume(run, entries, route, 'pinned', root)
    assert.equal(resumed.process.outcome, 'max-tokens')
    assert.equal(resumed.provenance.reusedLogSha256, createHash('sha256').update(readFileSync(logFile)).digest('hex'))
    assert.throws(() => readResume(run, [{ ...entries[0], lastPage: 4 }], route, 'pinned', root), /exact inputs/)
    assert.throws(() => readResume(run, entries, { ...route, model: 'different' }, 'pinned', root), /model/)
    writeFileSync(logFile, JSON.stringify({ type: 'turn/end', data: { reason: { kind: 'error' } } }))
    assert.throws(() => readResume(run, entries, route, 'pinned', root), /durable prefix log/)
  } finally { rmSync(root, { recursive: true, force: true }) }
})
