// P2 spec item 5 (eco #1): the five P1 denial scenarios, ported from the
// subprocess e2e onto the official @deepseek-ai/dsh-agent-loop-testkit as
// the on-every-push deterministic tier. Each test boots the REAL rc.6 agent
// loop, drives a scripted assistant tool call through the genuine pipeline
// (assistant/message -> tool/call -> tools/pre-execute -> monotonic guards
// -> tool/result), and asserts the exact typed code in the session events —
// no credentials, no subprocess, no dsh mock. e2e/run-e2e.mjs remains the
// subprocess smoke tier above this one.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import {
  cleanupWorkspaces,
  denials,
  mountHarness,
  startTurn,
  textResponse,
  toolCallResponse,
  toolResults,
} from './dsh-harness.ts'
import { ALL_DENIAL_CODES } from '../src/vocabulary.ts'

after(() => cleanupWorkspaces())

function prompt(agent: { followup(message: never): void }, text: string): void {
  agent.followup(createUserMessage({
    content: [{ type: 'text', text }],
    source: { kind: 'user' },
  }) as never)
}

/** Assert exactly the expected code appears, and no other AWT code anywhere. */
function assertOnlyDenial(events: readonly { type: string; data: unknown }[], expected?: string): void {
  for (const code of ALL_DENIAL_CODES) {
    const hits = denials(events, code)
    if (code === expected) {
      assert.ok(hits.length >= 1, `expected a ${code} denial in the session events`)
    } else {
      assert.equal(hits.length, 0, `unexpected ${code} denial in the session events`)
    }
  }
}

test('CONTRACT_SCOPE: a chapter write outside the active contract scope is denied in a real loop turn', async () => {
  const { ctx, ws } = await mountHarness(
    [
      toolCallResponse('c1', 'write', {
        file_path: join('chapters', 'ch5.md'),
        content: 'Jones (2021) argues that memory is contested terrain.',
      }),
      textResponse('done'),
    ],
    { workspace: { mayChange: 'chapters/ch3.md' } },
  )
  const agent = startTurn(ctx)
  prompt(agent, 'write chapter five')
  await agent.whenIdle()

  assertOnlyDenial(agent.session.events, 'CONTRACT_SCOPE')
  assert.ok(!existsSync(join(ws, 'chapters', 'ch5.md')), 'denied write must not mutate the workspace')
  await ctx.fiber.dispose()
})

test('NOTES_MISSING: an in-scope chapter write citing a source without conforming notes is denied', async () => {
  const { ctx, ws } = await mountHarness(
    [
      toolCallResponse('c1', 'write', {
        file_path: join('chapters', 'ch3.md'),
        content: 'Jones (2021) argues that memory is contested terrain.',
      }),
      textResponse('done'),
    ],
    { workspace: { mayChange: 'chapters/ch3.md' } },
  )
  const agent = startTurn(ctx)
  prompt(agent, 'write chapter three')
  await agent.whenIdle()

  assertOnlyDenial(agent.session.events, 'NOTES_MISSING')
  assert.ok(!existsSync(join(ws, 'chapters', 'ch3.md')))
  await ctx.fiber.dispose()
})

test('QUOTE_SPAN_MODIFIED: an edit altering text inside a quotation span is denied and the file untouched', async () => {
  const { ctx, ws } = await mountHarness(
    [
      toolCallResponse('c1', 'edit', {
        file_path: join('chapters', 'ch1.md'),
        old_string: 'not a neutral container',
        new_string: 'not a passive container',
      }),
      textResponse('done'),
    ],
    // ch1 must be inside the contract scope so CONTRACT_SCOPE cannot mask
    // the quote denial (decide() evaluates contract scope first).
    { workspace: { mayChange: 'chapters/ch1.md, chapters/ch3.md' } },
  )
  const agent = startTurn(ctx)
  prompt(agent, 'edit chapter one')
  await agent.whenIdle()

  assertOnlyDenial(agent.session.events, 'QUOTE_SPAN_MODIFIED')
  assert.match(readFileSync(join(ws, 'chapters', 'ch1.md'), 'utf8'), /not a neutral container/)
  await ctx.fiber.dispose()
})

test('negative control: a conforming citation write passes every guard and reaches the tool body', async () => {
  const { ctx, ws } = await mountHarness(
    [
      toolCallResponse('c1', 'write', {
        file_path: join('chapters', 'ch3.md'),
        content: 'Smith (2024) shows that archives shape collective memory.',
      }),
      textResponse('done'),
    ],
    { workspace: { mayChange: 'chapters/ch3.md' } },
  )
  const agent = startTurn(ctx)
  prompt(agent, 'write chapter three properly')
  await agent.whenIdle()

  assertOnlyDenial(agent.session.events, undefined)
  const results = toolResults(agent.session.events)
  assert.equal(results.length, 1)
  assert.equal(results[0].isError, false)
  assert.match(readFileSync(join(ws, 'chapters', 'ch3.md'), 'utf8'), /Smith \(2024\)/)
  await ctx.fiber.dispose()
})

test('PAGE_RANGE_EXCEEDED: a 16-page read_pdf invocation is denied (limit 15)', async () => {
  const { ctx } = await mountHarness(
    [
      toolCallResponse('c1', 'read_pdf', {
        file_path: join('literature', 'smith2024.pdf'),
        first_page: 1,
        last_page: 16,
      }),
      textResponse('done'),
    ],
    { workspace: { mayChange: 'chapters/ch3.md' } },
  )
  const agent = startTurn(ctx)
  prompt(agent, 'read the whole pdf')
  await agent.whenIdle()

  assertOnlyDenial(agent.session.events, 'PAGE_RANGE_EXCEEDED')
  await ctx.fiber.dispose()
})

test('PAGE_BUDGET_EXCEEDED: the session budget is enforced from the PROJECTION fold of this session log', async () => {
  // Two in-range reads; with perSession 20 the second (15 + 10 > 20) must be
  // denied — and the counted 15 pages exist ONLY as a fold of this session's
  // tool/call + tool/result events, proving the guard reads the projection,
  // not plugin state.
  const { ctx } = await mountHarness(
    [
      toolCallResponse('c1', 'read_pdf', { file_path: join('literature', 'smith2024.pdf'), first_page: 1, last_page: 15 }),
      toolCallResponse('c2', 'read_pdf', { file_path: join('literature', 'smith2024.pdf'), first_page: 16, last_page: 25 }),
      textResponse('done'),
    ],
    {
      workspace: { mayChange: 'chapters/ch3.md' },
      guards: { pageBudget: { perInvocation: 15, perSession: 20 } },
    },
  )
  const agent = startTurn(ctx)
  prompt(agent, 'read a lot')
  await agent.whenIdle()

  assertOnlyDenial(agent.session.events, 'PAGE_BUDGET_EXCEEDED')
  const results = toolResults(agent.session.events)
  assert.equal(results.length, 2)
  assert.equal(results[0].isError, false, 'first read must pass')
  assert.equal(results[1].isError, true, 'second read must be denied')

  // The counted pages exist in the registered projection value itself.
  const snapshot = ctx.sessionProjections.snapshot(agent.session)
  const value = snapshot.values['awt/pageBudget' as never] as { pagesRead: number } | undefined
  assert.equal(value?.pagesRead, 15)
  await ctx.fiber.dispose()
})

test('page budget is per SESSION (projection fold), not per process (the retired P1 plugin counter)', async () => {
  // One plugin instance, two sessions. Session A consumes 15 of a 20-page
  // budget; session B then reads 10 pages and MUST pass, because its own log
  // holds zero completed reads. The P1 plugin-local counter (per process)
  // would have denied it — this pins the rewiring onto the projection.
  const { ctx } = await mountHarness(
    [
      toolCallResponse('c1', 'read_pdf', { file_path: join('literature', 'smith2024.pdf'), first_page: 1, last_page: 15 }),
      textResponse('done'),
      toolCallResponse('c2', 'read_pdf', { file_path: join('literature', 'smith2024.pdf'), first_page: 1, last_page: 10 }),
      textResponse('done'),
    ],
    {
      workspace: { mayChange: 'chapters/ch3.md' },
      guards: { pageBudget: { perInvocation: 15, perSession: 20 } },
    },
  )
  const agentA = startTurn(ctx)
  prompt(agentA, 'read in session A')
  await agentA.whenIdle()
  const agentB = startTurn(ctx)
  prompt(agentB, 'read in session B')
  await agentB.whenIdle()

  const resultsA = toolResults(agentA.session.events)
  const resultsB = toolResults(agentB.session.events)
  assert.equal(resultsA[0]?.isError, false, 'session A read must pass')
  assert.equal(resultsB[0]?.isError, false, 'session B read must pass — its own log is empty')
  assertOnlyDenial(agentB.session.events, undefined)
  await ctx.fiber.dispose()
})
