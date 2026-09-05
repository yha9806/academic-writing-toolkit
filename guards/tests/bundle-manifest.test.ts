// Bundle-contract test (P3 spec item 2, eco #5): the distribution claim is
// itself a tested claim. Asserts the dsh bundle manifest wiring, the files
// whitelist, the compat pins, and the exact composition row the patch
// ships — so `dsh plugin add` installing this package cannot silently
// drift from what the docs promise.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const PKG_DIR = resolve(import.meta.dirname, '..')
const manifest = JSON.parse(readFileSync(join(PKG_DIR, 'package.json'), 'utf8'))

test('the dsh bundle manifest points at the shipped patch', () => {
  assert.equal(manifest.dsh?.bundle?.patch, './cordis.patch.yml')
  assert.ok(manifest.files.includes('cordis.patch.yml'), 'files whitelist must ship the patch')
  assert.ok(manifest.files.includes('dist'), 'files whitelist must ship the built plugin')
  assert.equal(manifest.main, './dist/dsh-plugin.js')
})

test('compat pins are machine-checkable: engines.dsh plus peer ranges on the attested rc line', () => {
  assert.equal(manifest.engines?.dsh, '>=0.1.0-rc.6')
  assert.equal(manifest.peerDependencies?.['@deepseek-ai/dsh-tools'], '>=0.1.0-rc.6 <0.2.0')
  assert.equal(manifest.peerDependencies?.['@deepseek-ai/dsh-session-projection'], '>=0.1.0-rc.6 <0.2.0')
  assert.equal(manifest.peerDependenciesMeta?.['@deepseek-ai/dsh-session-projection']?.optional, true,
    'the projection registry is optional (registry-less fallback exists); dsh-tools is not')
})

test('the shipped patch inserts exactly the awt-guards row with enforcement-on defaults', () => {
  const patch = readFileSync(join(PKG_DIR, 'cordis.patch.yml'), 'utf8')
  const rows = patch.split('\n').filter((l) => !l.trim().startsWith('#') && l.trim() !== '')
  assert.deepEqual(rows, [
    '- insert:',
    '    - id: awt-guards',
    "      name: '@awt/guards'",
  ], 'the patch must be one insert row, no config overrides (defaults are enforcement-on)')
})

test('COMPAT.json carries a dated, machine-readable baseline matching the pins', () => {
  const compat = JSON.parse(readFileSync(join(PKG_DIR, '..', 'COMPAT.json'), 'utf8'))
  assert.equal(compat.harness, '@deepseek-ai/dsh@0.1.0-rc.6')
  assert.match(compat.upstreamAuditCommit, /^[0-9a-f]{40}$/)
  assert.match(compat.lastVerified, /^\d{4}-\d{2}-\d{2}$/)
  assert.ok(Array.isArray(compat.gates) && compat.gates.length > 0)
})
