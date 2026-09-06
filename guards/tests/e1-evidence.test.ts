import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { openedReference } from '../../e1/evidence.mjs'

const workspace = resolve('fixture-workspace')
const entry = { firstPage: 12, lastPage: 13 }
const call = (path = 'literature/source.pdf') => ({ type: 'tool/call', data: { callId: 'c1', name: 'read_pdf', arguments: JSON.stringify({ file_path: path, first_page: 12, last_page: 13 }) } })
const result = (isError = false) => ({ type: 'tool/result', data: { message: { content: [{ type: 'tool-result', toolCallId: 'c1', isError, content: [{ type: 'text', text: '--- page 12 ---\nActual source text.' }] }] } } })
const log = (...events: object[]) => events.map((event) => JSON.stringify(event)).join('\n')

test('E1 grades text actually returned by a successful read of the manifest source', () => {
  const observed = openedReference([log(call(), result())], workspace, entry)
  assert.equal(observed.sourceOpened, true)
  assert.equal(observed.referenceText, '--- page 12 ---\nActual source text.')
})

test('a failed read, different source, or colliding call ID from another session cannot prove source opening', () => {
  assert.equal(openedReference([log(call(), result(true))], workspace, entry).sourceOpened, false)
  assert.equal(openedReference([log(call('literature/unselected.pdf'), result())], workspace, entry).sourceOpened, false)
  assert.equal(openedReference([log(call()), log(result())], workspace, entry).sourceOpened, false)
  assert.equal(openedReference([], workspace, entry).sourceOpened, false)
  assert.throws(() => openedReference(['malformed log'], workspace, entry))
})
