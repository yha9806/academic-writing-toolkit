// Shared fixtures for the testkit tier (P2 spec item 5, eco #1: deterministic
// per-denial-code tests booting the REAL rc.6 agent loop through the official
// @deepseek-ai/dsh-agent-loop-testkit, driven by a scripted LlmAdapter — the
// dsh-turn-budget tests/turn-budget.spec.ts shape). No dsh mock anywhere: the
// tool calls travel assistant/message -> tool/call -> tools/pre-execute ->
// monotonic guards -> tool/result on the published packages.
//
// Shared fixtures live in this plain tests/*.ts helper, never another
// *.test.ts (the headless-agent example's fixture rule).

import { mkdirSync, readFileSync, writeFileSync, existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, isAbsolute, join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { CallId, LlmAdapter } from '@deepseek-ai/dsh-llm'
import type { GenerateOptions, LlmResolvedModelInfo, StreamChunk } from '@deepseek-ai/dsh-llm'
import { SessionId } from '@deepseek-ai/dsh-session'
import { defineContentToolFixture } from '@deepseek-ai/dsh-tools'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
import { mountAgentLoopTestDependencies } from '@deepseek-ai/dsh-agent-loop-testkit'
import SessionProjectionRegistry from '@deepseek-ai/dsh-session-projection'
import * as guards from '../src/dsh-plugin.ts'
import type { Config as GuardsConfig } from '../src/dsh-plugin.ts'

const TODAY = new Date().toISOString().slice(0, 10)

// --- scripted adapter ---------------------------------------------------------------

export function textResponse(text: string): StreamChunk[] {
  return [
    { type: 'block-start', index: 0, blockType: 'text' },
    { type: 'text-delta', index: 0, text },
    { type: 'block-end', index: 0, block: { type: 'text', text } },
    { type: 'usage', usage: { inputTokens: 10, outputTokens: 5 } },
    { type: 'finish', reason: { kind: 'stop' } },
  ]
}

export function toolCallResponse(rawCallId: string, name: string, args: object): StreamChunk[] {
  const callId = CallId(rawCallId)
  const argumentsJson = JSON.stringify(args)
  return [
    { type: 'block-start', index: 0, blockType: 'tool-call' },
    { type: 'tool-call-delta', index: 0, id: callId, name, argumentsDelta: argumentsJson },
    { type: 'block-end', index: 0, block: { type: 'tool-call', id: callId, name, arguments: argumentsJson } },
    { type: 'usage', usage: { inputTokens: 10, outputTokens: 5 } },
    { type: 'finish', reason: { kind: 'tool-calls' } },
  ]
}

/** Deterministic adapter: one script entry per model request, recorded. */
export class ScriptedAdapter extends LlmAdapter {
  readonly requests: GenerateOptions[] = []

  constructor(private readonly script: StreamChunk[][]) {
    super()
  }

  override resolveModel(provider: string, model: string): Promise<LlmResolvedModelInfo> {
    return Promise.resolve({ provider, id: model, name: model })
  }

  async * stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    this.requests.push(options)
    const chunks = this.script.shift()
    if (chunks === undefined) throw new Error('ScriptedAdapter: script exhausted')
    for (const chunk of chunks) yield chunk
  }
}

// --- thesis-workspace fixture (mirrors e2e/run-e2e.mjs buildWorkspace) ----------------

export interface WorkspaceOptions {
  /** `May change:` scope of the active contract; omit to create no contract file. */
  mayChange?: string
}

const workspaces: string[] = []

/** Remove every workspace this module created (call from a test-file after()). */
export async function cleanupWorkspaces(): Promise<void> {
  const { rmSync } = await import('node:fs')
  for (const ws of workspaces.splice(0)) rmSync(ws, { recursive: true, force: true })
}

export function buildWorkspace(options: WorkspaceOptions = {}): string {
  const ws = mkdtempSync(join(tmpdir(), 'awt-testkit-ws-'))
  workspaces.push(ws)
  mkdirSync(join(ws, 'chapters'), { recursive: true })
  mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  mkdirSync(join(ws, 'contracts'), { recursive: true })

  writeFileSync(join(ws, 'chapters', 'ch1.md'), `# Chapter 1: Introduction

As Smith (2024) argues, "the archive is not a neutral container of the past" (Smith, 2024, p. 12).
`)

  writeFileSync(join(ws, 'literature', 'reading_notes', 'smith2024_NOTES.md'), notesFixture())

  if (options.mayChange !== undefined) {
    writeFileSync(join(ws, 'contracts', `${TODAY}-ch3-integration.md`), contractFixture(options.mayChange))
  }
  return ws
}

/** A lint-conforming notes file for exactly smith 2024 (the e2e fixture body). */
export function notesFixture(): string {
  return `# Reading Notes: Smith — The Archive and Memory (2024)

**Source**: Smith, J. (2024) The archive and memory. *Example Press*.
**Date read**: ${TODAY}
**Status**: completed
**Relevance**: Ch3 S3.1 — supports argument about archives
**Evidence status**: full_text

---

## Key Arguments

- Archives actively shape collective memory rather than passively storing it.

## Detailed Notes

### p.10–15: The archive as agent

> "the archive is not a neutral container of the past" (p.12)

Smith frames archival practice as a form of authorship.

## Key Terms

| Term | Translation | Definition in context |
|------|-------------|----------------------|
| archive | — | institutionally curated memory store |

## Thesis Connections

| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|
| archive as agent | Ch3 | S3.1 | supports |

## Questions & Follow-ups

- How does this apply to digital archives?

---
*Last updated: ${TODAY}*
`
}

/** An ACTIVE edit contract (unchecked attempt box) scoping `mayChange`. */
export function contractFixture(mayChange: string): string {
  return `# Edit Contract: integrate smith2024 into chapter 3

- Spine: Ch3 argues archives are agents of memory.
- May change: ${mayChange}
- Must not change: chapters/ch2.md

## Attempts
- [ ] Attempt 1: ${TODAY} — pending
`
}

// --- workspace probe tools -------------------------------------------------------------

/**
 * Register write/edit/read_pdf probe fixtures whose bodies really touch the
 * workspace, so the negative control proves an ALLOWED call reaches the tool
 * body while denied calls provably never mutate anything.
 */
export function registerWorkspaceTools(ctx: Context, ws: string): void {
  const target = (filePath: string) => (isAbsolute(filePath) ? filePath : join(ws, filePath))
  ctx.tools.register(defineContentToolFixture({
    name: 'write',
    description: 'workspace write probe',
    parameters: {
      file_path: { type: 'string', required: true },
      content: { type: 'string', required: true },
    },
    async execute(args) {
      const path = target(args.file_path)
      mkdirSync(dirname(path), { recursive: true })
      writeFileSync(path, args.content)
      return [{ type: 'text', text: `wrote ${args.file_path}` }]
    },
  }))
  ctx.tools.register(defineContentToolFixture({
    name: 'edit',
    description: 'workspace edit probe',
    parameters: {
      file_path: { type: 'string', required: true },
      old_string: { type: 'string', required: true },
      new_string: { type: 'string', required: true },
    },
    async execute(args) {
      const path = target(args.file_path)
      if (!existsSync(path)) return [{ type: 'text', text: 'no such file' }]
      writeFileSync(path, readFileSync(path, 'utf8').replace(args.old_string, args.new_string))
      return [{ type: 'text', text: `edited ${args.file_path}` }]
    },
  }))
  ctx.tools.register(defineContentToolFixture({
    name: 'export_docx',
    description: 'export probe (P4): leaves a marker so an ALLOWED export is provable',
    parameters: {
      scope: { type: 'string', required: true },
      lang_filter: { type: 'string', required: true },
    },
    async execute(args) {
      mkdirSync(join(ws, 'final_output'), { recursive: true })
      writeFileSync(join(ws, 'final_output', 'EXPORTED.txt'), `${args.scope} ${args.lang_filter}`)
      return [{ type: 'text', text: 'exported' }]
    },
  }))
  ctx.tools.register(defineContentToolFixture({
    name: 'read_pdf',
    description: 'pdf read probe (no real pdf needed; the guard decides first)',
    parameters: {
      file_path: { type: 'string', required: true },
      first_page: { type: 'integer', required: true },
      last_page: { type: 'integer', required: true },
    },
    async execute(args) {
      return [{ type: 'text', text: `read pages ${args.first_page}-${args.last_page} of ${args.file_path}` }]
    },
  }))
}

// --- harness ------------------------------------------------------------------------------

export interface Harness {
  ctx: Context
  adapter: ScriptedAdapter
  ws: string
}

export interface HarnessOptions {
  workspace?: WorkspaceOptions
  guards?: Partial<GuardsConfig>
  /** Extra plugins to mount before the guards plugin (e.g. persistence). */
  premount?: (ctx: Context) => Promise<void>
}

let sessionCounter = 0

/** Boot the real agent loop with the AWT guards plugin mounted, per test. */
export async function mountHarness(script: StreamChunk[][], options: HarnessOptions = {}): Promise<Harness> {
  const ws = buildWorkspace(options.workspace)
  const ctx = new Context()
  await mountAgentLoopTestDependencies(ctx)
  await options.premount?.(ctx)
  await ctx.plugin(AgentLoop, { agents: [] })
  await ctx.plugin(SessionProjectionRegistry)
  await ctx.plugin(guards as never, { projectRoot: ws, ...options.guards })
  registerWorkspaceTools(ctx, ws)
  const adapter = new ScriptedAdapter(script)
  ctx.llm.registerAdapter(['mock'], adapter)
  return { ctx, adapter, ws }
}

export function startTurn(ctx: Context, sessionName?: string) {
  const agent = ctx.agentLoop.create(
    SessionId(sessionName ?? `awt-testkit-${++sessionCounter}`),
    { provider: 'mock', model: 'mock' }
  )
  return agent
}

// --- session-event assertions -----------------------------------------------------------

interface EventLike {
  type: string
  data: unknown
}

/** All tool/result events whose model-facing text contains `needle`, with isError. */
export function toolResults(events: readonly EventLike[]): Array<{ isError: boolean; text: string }> {
  const out: Array<{ isError: boolean; text: string }> = []
  for (const event of events) {
    if (event.type !== 'tool/result') continue
    const data = event.data as { message?: { content?: unknown } }
    const content = data.message?.content
    if (!Array.isArray(content)) continue
    const block = content[0] as { type?: string; isError?: boolean; content?: unknown }
    if (block?.type !== 'tool-result' || !Array.isArray(block.content)) continue
    const text = (block.content as Array<{ type?: string; text?: string }>)
      .filter((b) => b.type === 'text' && typeof b.text === 'string')
      .map((b) => b.text as string)
      .join('\n')
    out.push({ isError: block.isError === true, text })
  }
  return out
}

export function denials(events: readonly EventLike[], code: string): Array<{ isError: boolean; text: string }> {
  return toolResults(events).filter((r) => r.isError && r.text.includes(code))
}
