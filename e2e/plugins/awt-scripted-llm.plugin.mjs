// Scripted LLM adapter for the AWT guards live e2e (P1 closing gate).
//
// Registered on the real `ctx.llm.registerAdapter(['scripted'], adapter)`
// seam of a booted dsh 0.1.0-rc.6 process, so the tool call it emits flows
// through the REAL agent loop: assistant tool-call block -> tools/pre-execute
// waterfall -> monotonic guards -> typed denial (or execution). dsh itself is
// never mocked.
//
// Behavior per dsh run (the e2e drives one scenario per process):
// - auxiliary calls (options.purpose set, e.g. 'session-title') get a plain
//   text response so base-bundle plugins never hang on the scripted route;
// - the first conversation call emits the scripted assistant tool call read
//   from $AWT_E2E_TOOLCALL (JSON: {"tool": <name>, "args": {...}}) and
//   finishes with reason kind 'tool-calls';
// - every later conversation call finishes with plain text ('stop'), so the
//   turn completes and the headless runner exits 0.
//
// Chunk conventions follow the installed @deepseek-ai/dsh-llm StreamChunk
// contract: block-start / deltas / block-end (assembled block), usage before
// the terminal finish, tool arguments as a raw JSON string.
import { LlmAdapter } from '@deepseek-ai/dsh-llm'

export const name = 'awt-scripted-llm'
export const inject = ['llm']

function* textResponse(text) {
  yield { type: 'block-start', index: 0, blockType: 'text' }
  yield { type: 'text-delta', index: 0, text }
  yield { type: 'block-end', index: 0, block: { type: 'text', text } }
  yield { type: 'usage', usage: { inputTokens: 1, outputTokens: 1 } }
  yield { type: 'finish', reason: { kind: 'stop' } }
}

class ScriptedAdapter extends LlmAdapter {
  conversationCalls = 0

  async *stream(options) {
    if (options.purpose !== undefined) {
      yield* textResponse('awt-e2e auxiliary response')
      return
    }
    this.conversationCalls += 1
    if (this.conversationCalls === 1) {
      const raw = process.env.AWT_E2E_TOOLCALL
      if (raw === undefined || raw === '') {
        yield* textResponse('AWT-E2E ERROR: AWT_E2E_TOOLCALL is not set')
        return
      }
      const call = JSON.parse(raw)
      const argumentsJson = JSON.stringify(call.args)
      const id = 'awt-e2e-call-1'
      yield { type: 'block-start', index: 0, blockType: 'tool-call' }
      yield { type: 'tool-call-delta', index: 0, id, name: call.tool, argumentsDelta: argumentsJson }
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id, name: call.tool, arguments: argumentsJson } }
      yield { type: 'usage', usage: { inputTokens: 1, outputTokens: 1 } }
      yield { type: 'finish', reason: { kind: 'tool-calls' } }
      return
    }
    yield* textResponse('AWT-E2E COMPLETE')
  }
}

export function apply(ctx) {
  ctx.llm.registerAdapter(['scripted'], new ScriptedAdapter())
}
