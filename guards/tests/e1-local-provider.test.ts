import { test } from 'node:test'
import assert from 'node:assert/strict'
import { modelRoute } from '../../e1/inputs.mjs'
import { localModelMetadata, localProviderPatch } from '../../e1/local-provider.mjs'

test('local E1 admits only explicit loopback models and never substitutes cloud credentials', () => {
  const route = modelRoute('ollama', 'experiment:1', { OPENAI_API_KEY: 'unrelated' })
  assert.equal(route.baseURL, 'http://127.0.0.1:11434/v1')
  assert.equal(route.keyEnv, 'AWT_E1_LOCAL_KEY')
  assert.throws(() => modelRoute('ollama', undefined, {}), /explicitly/)
  for (const endpoint of ['https://example.com/v1', 'http://localhost.example.com/v1', 'http://token@localhost:11434/v1', 'http://localhost:11434/v1?key=x']) {
    assert.throws(() => modelRoute('ollama', 'experiment:1', {}, endpoint), /loopback/)
  }
})

test('local E1 requires actual server context and records the installed model digest', () => {
  const route = modelRoute('ollama', 'experiment:1', {})
  const tags = { models: [{ name: 'experiment:1', digest: 'a'.repeat(64) }] }
  const shown = { capabilities: ['tools'], parameters: 'num_ctx 32768\nnum_predict 4096\ntemperature 0.2', details: { quantization_level: 'Q4_K_M' } }
  const info = localModelMetadata(route, { version: 'fixture' }, tags, shown)
  assert.equal(info.contextWindow, 32768)
  assert.equal(info.modelDigest, 'a'.repeat(64))
  assert.throws(() => localModelMetadata(route, {}, tags, { ...shown, parameters: 'num_ctx 4096' }), /server context/)
  assert.throws(() => localModelMetadata(route, {}, tags, { ...shown, remote_host: 'https://example.com' }), /cloud-backed/)
  assert.throws(() => localModelMetadata(route, {}, tags, { ...shown, capabilities: [] }), /tool support/)
  assert.throws(() => localProviderPatch(route), /inspect/)
  const patch = localProviderPatch({ ...route, localInfo: info })
  assert.match(patch, /maxRetries: 0/)
  assert.match(patch, /contextWindow: 32768/)
  assert.doesNotMatch(patch, /OPENAI_API_KEY|DEEPSEEK_API_KEY/)
})
