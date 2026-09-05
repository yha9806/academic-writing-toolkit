// Script-file-driven LLM adapter for the E1 instrument's OFFLINE lane.
//
// Same seam discipline as the e2e adapter (real ctx.llm.registerAdapter on
// a booted dsh; dsh itself never mocked), but multi-step: $AWT_E1_SCRIPT
// names a JSON file whose entries are consumed one per conversation
// request — {"kind":"tool-call","name":...,"args":{...}} or
// {"kind":"text","text":...}. When the script is exhausted, every further
// conversation call answers plain text so the turn settles.
import { readFileSync } from 'node:fs'
import { LlmAdapter } from '@deepseek-ai/dsh-llm'

export const name = 'awt-e1-scripted-llm'
export const inject = ['llm']

function* textResponse(text) {
  yield { type: 'block-start', index: 0, blockType: 'text' }
  yield { type: 'text-delta', index: 0, text }
  yield { type: 'block-end', index: 0, block: { type: 'text', text } }
  yield { type: 'usage', usage: { inputTokens: 1, outputTokens: 1 } }
  yield { type: 'finish', reason: { kind: 'stop' } }
}

class E1ScriptedAdapter extends LlmAdapter {
  calls = 0
  script

  loadScript() {
    if (this.script === undefined) {
      const path = process.env.AWT_E1_SCRIPT
      this.script = path ? JSON.parse(readFileSync(path, 'utf8')) : []
    }
    return this.script
  }

  async *stream(options) {
    if (options.purpose !== undefined) {
      yield* textResponse('awt-e1 auxiliary response')
      return
    }
    const script = this.loadScript()
    const entry = script[this.calls]
    this.calls += 1
    if (entry === undefined || entry.kind === 'text') {
      yield* textResponse(entry?.text ?? 'AWT-E1 COMPLETE')
      return
    }
    const argumentsJson = JSON.stringify(entry.args)
    const id = `awt-e1-call-${this.calls}`
    yield { type: 'block-start', index: 0, blockType: 'tool-call' }
    yield { type: 'tool-call-delta', index: 0, id, name: entry.name, argumentsDelta: argumentsJson }
    yield { type: 'block-end', index: 0, block: { type: 'tool-call', id, name: entry.name, arguments: argumentsJson } }
    yield { type: 'usage', usage: { inputTokens: 1, outputTokens: 1 } }
    yield { type: 'finish', reason: { kind: 'tool-calls' } }
  }
}

export function apply(ctx) {
  ctx.llm.registerAdapter(['scripted'], new E1ScriptedAdapter())
}
