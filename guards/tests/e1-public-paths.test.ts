import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { cpSync, existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { publicContinuation, relativeRunPath } from '../../e1/public-paths.mjs'
import { sanitisePublished } from '../../e1/sanitise-published.mjs'

test('continuation paths are relative on Windows and POSIX, including earlier relative links', () => {
  for (const base of ['F:\\experiment\\runs', '/tmp/experiment/runs']) {
    const sep = base.startsWith('F:') ? '\\' : '/'
    const current = base + sep + 'new'
    const prior = { run: base + sep + 'prior', metricsSha256: 'a'.repeat(64),
      earlierContinuation: { run: '../older', metricsSha256: 'b'.repeat(64) } }
    const original = JSON.stringify(prior)
    const result = publicContinuation(prior, current, prior.run)
    assert.equal(result.run, '../prior')
    assert.equal(result.earlierContinuation.run, '../older')
    assert.equal(result.metricsSha256, prior.metricsSha256)
    assert.equal(result.earlierContinuation.metricsSha256, prior.earlierContinuation.metricsSha256)
    assert.equal(JSON.stringify(prior), original, 'raw provenance stays unchanged')
    assert.equal(relativeRunPath(current, current), '.')
  }
  assert.throws(() => relativeRunPath('C:\\prior', 'F:\\current'), /relative/i)
})

test('repeated resume rebases the whole inherited chain from its containing metrics root', () => {
  const first = publicContinuation({ run: '/runs/old/a', metricsSha256: 'first' }, '/runs/mid/b')
  const second = publicContinuation({ run: '/runs/mid/b', metricsSha256: 'second',
    earlierContinuation: first }, '/runs/latest/c', '/runs/mid/b')
  const third = publicContinuation({ run: '/runs/latest/c', metricsSha256: 'third',
    earlierContinuation: second }, '/runs/final', '/runs/latest/c')
  assert.equal(third.run, '../latest/c')
  assert.equal(third.earlierContinuation.run, '../mid/b')
  assert.equal(third.earlierContinuation.earlierContinuation.run, '../old/a')
})

test('summary identifies legacy session logs by content while retaining usage and raw bytes', () => {
  const root = mkdtempSync(join(tmpdir(), 'awt-e1-public-'))
  try {
    const sessions = join(root, 'paper/skills/sessions/--C-Users-Example-AppData-Local-Temp--')
    mkdirSync(sessions, { recursive: true })
    const log = JSON.stringify({ type: 'assistant/message', time: 1000,
      data: { usage: { inputTokens: 12, outputTokens: 5 } } }) + '\n' +
      JSON.stringify({ type: 'turn/end', time: 2000, data: { reason: { kind: 'completed' } } }) + '\n'
    writeFileSync(join(sessions, 'session.jsonl'), log)
    const hash = createHash('sha256').update(log).digest('hex')
    const metrics = { status: 'completed', evidenceClass: 'E0', model: {}, harness: 'fixture',
      results: [{ id: 'paper', arm: 'skills', artifacts: 'paper/skills', sourceOpened: true,
        taskOutcomes: ['completed'], notes: { present: true, parseable: false, errors: [] },
        quoteFidelity: { quotes: 1, matched: 0 }, pageAccuracy: { cited: 0, correct: 0, uncited: 1 },
        unopenedCitations: { draftPresent: false, citations: 0, unopened: [] } }] }
    writeFileSync(join(root, 'metrics.json'), JSON.stringify(metrics))
    const summary = spawnSync(process.env.PYTHON ?? 'python', ['e1/summarize-run.py', root], {
      cwd: join(import.meta.dirname, '../..'), encoding: 'utf8', timeout: 30_000,
    })
    assert.equal(summary.status, 0, summary.error?.message ?? summary.stderr)
    const analysis = JSON.parse(readFileSync(join(root, 'analysis.json'), 'utf8'))
    assert.equal(analysis.sessions[0].log, `paper/skills/sessions/sha256-${hash}.jsonl`)
    assert.equal(analysis.sessions[0].reportedInputTokens, 12)
    assert.equal(analysis.sessions[0].reportedOutputTokens, 5)
    assert.equal(analysis.arms[0].matchedSpans, 0)
    assert.equal(analysis.sessions[0].sha256, hash)
    assert.equal(readFileSync(join(sessions, 'session.jsonl'), 'utf8'), log)
    assert.doesNotMatch(JSON.stringify(analysis), /C-Users-Example/)
  } finally { rmSync(root, { recursive: true, force: true }) }
})

test('frozen public receipt binds all six files and contains no machine paths', () => {
  const packet = join(import.meta.dirname, '../../e1/published/2026-09-05-local-qwen')
  const receipt = JSON.parse(readFileSync(join(packet, 'verification.json'), 'utf8'))
  assert.equal(Object.keys(receipt.publishedFilesSha256).length, 6)
  for (const [file, expected] of Object.entries(receipt.publishedFilesSha256)) {
    assert.equal(createHash('sha256').update(readFileSync(join(packet, file))).digest('hex'), expected, file)
  }
  for (const file of ['metrics.json', 'analysis.json', 'verification.json']) {
    const value = readFileSync(join(packet, file), 'utf8')
    assert.doesNotMatch(value, /(^|[^\w])[A-Za-z]:[\\/]|--(?:[A-Za-z]-Users-|Users-|home-|private-|tmp-|var-folders-)|\/(?:Users|home|tmp|private|var\/folders)\//)
  }
  assert.equal(receipt.runDirectory, '.')
  assert.equal(receipt.publicSanitisation.pathFieldsRewritten, 19)
  assert.equal(receipt.publicSanitisation.unchangedSessionLogHashes, 12)
  assert.equal(receipt.publicSanitisation.originalContinuationHashesVerified, 3)
})

test('publisher refuses changed frozen bytes before creating output', () => {
  const root = mkdtempSync(join(tmpdir(), 'awt-e1-tamper-'))
  try {
    const packet = join(root, 'packet'), output = join(root, 'output')
    cpSync(join(import.meta.dirname, '../../e1/published/2026-09-05-local-qwen'), packet, { recursive: true })
    writeFileSync(join(packet, 'metrics.json'), '{"tampered":true}')
    assert.throws(() => sanitisePublished(packet, join(root, 'run'), output), /Frozen packet hash mismatch/)
    assert.equal(existsSync(output), false)
  } finally { rmSync(root, { recursive: true, force: true }) }
})
