import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { parseOptions, modelRoute, readManifest, classifyRun } from '../../e1/inputs.mjs'
import { labelPdfPages } from '../../profiles/awt-headless/pdf-pages.mjs'

const root = mkdtempSync(join(tmpdir(), 'awt-e1-inputs-'))
after(() => rmSync(root, { recursive: true, force: true }))
function fixture() {
  return { pdfs: [1, 2, 3].map((n) => {
    const bytes = Buffer.from(`%PDF-1.4\nsynthetic input-validation fixture ${n}`)
    writeFileSync(join(root, `${n}.pdf`), bytes)
    return { id: `author${n}`, path: `${n}.pdf`, sha256: createHash('sha256').update(bytes).digest('hex'), firstPage: 2, lastPage: 3, source: { surname: 'Smith', year: '2024' } }
  }) }
}
function load(value = fixture()) {
  const path = join(root, 'inputs.json')
  writeFileSync(path, '\uFEFF' + JSON.stringify(value))
  return readManifest(path)
}
const code = (expected: string) => (error: any) => error.code === expected

test('E1 input paths resolve beside the manifest and hashes identify three distinct inputs', () => {
  const entries = load()
  assert.equal(entries[0].path, join(root, '1.pdf'))
  assert.equal(new Set(entries.map((entry: any) => entry.sha256)).size, 3)
})

test('E1 rejects empty/duplicate sources, traversal IDs, invalid windows and changed PDF bytes', () => {
  assert.throws(() => load({ pdfs: [] }), code('E1_SOURCE_COUNT'))
  const duplicate = fixture(); duplicate.pdfs[1].id = duplicate.pdfs[0].id
  assert.throws(() => load(duplicate), code('E1_SOURCE_DUPLICATE'))
  const samePdf = fixture(); samePdf.pdfs[1] = { ...samePdf.pdfs[0], id: 'other' }
  assert.throws(() => load(samePdf), code('E1_SOURCE_DUPLICATE'))
  const traversal = fixture(); traversal.pdfs[0].id = '../escape'
  assert.throws(() => load(traversal), code('E1_SOURCE_INVALID'))
  const pages = fixture(); pages.pdfs[0].lastPage = 17
  assert.throws(() => load(pages), code('E1_PAGE_RANGE'))
  const changed = fixture(); writeFileSync(join(root, '1.pdf'), '%PDF-1.4\nchanged')
  assert.throws(() => load(changed), code('E1_PDF_HASH_MISMATCH'))
})

test('E1 explicitly selects the provider; an unrelated key does not make it ready', () => {
  const route = modelRoute('deepseek', undefined, { ANTHROPIC_API_KEY: 'fixture' })
  assert.equal(route.keyPresent, false)
  assert.throws(() => modelRoute('anthropic', undefined, {}), code('E1_MODEL_REQUIRED'))
  assert.equal(modelRoute('anthropic', 'chosen-model', { ANTHROPIC_API_KEY: 'fixture' }).keyPresent, true)
  assert.throws(() => parseOptions(['--manifest']), code('E1_USAGE'))
  assert.throws(() => parseOptions(['--real', '--unknown']), code('E1_USAGE'))
})

test('blank PDF pages preserve the physical page numbers, including a blank final page', () => {
  assert.equal(labelPdfPages('first\f\fthird\f', 7), '--- page 7 ---\nfirst\n\n--- page 8 ---\n\n\n--- page 9 ---\nthird')
  assert.equal(labelPdfPages('first\f\f', 1), '--- page 1 ---\nfirst\n\n--- page 2 ---\n')
})

test('failed sessions cannot produce E1 claims, while successful poor model outcomes remain measurable', () => {
  assert.equal(classifyRun('real', [{ status: 0 }, { status: null, error: { code: 'ETIMEDOUT' } }], true).evidenceClass, null)
  assert.equal(classifyRun('offline', [{ status: 0 }, { status: 0 }], true).evidenceClass, 'E0')
  assert.equal(classifyRun('real', [{ status: 0 }, { status: 0 }], false).evidenceClass, 'E1')
  assert.equal(classifyRun('real', [{ status: 0 }], true).status, 'incomplete')
})
