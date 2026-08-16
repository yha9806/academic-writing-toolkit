// P2 session-2 ask-seam gate (spec item 2): after three typed-denial
// attempts under an active contract, every further in-scope chapter write
// returns `ask` on the tools/pre-execute waterfall, and dsh-user-approval
// records the immutable approval/asked + approval/decided audit pair. The
// closing gate re-runs the efficacy review's self-approval attack: agent
// file edits (the contract's own ledger, a fake approvals file) must have
// zero effect on the gate decision, because the authority is the session-log
// fold plus harness approval events — never anything the model can write.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import ApprovalService from '@deepseek-ai/dsh-user-approval'
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval'
import {
  cleanupWorkspaces,
  contractFixture,
  denials,
  mountHarness,
  startTurn,
  textResponse,
  toolCallResponse,
  toolResults,
} from './dsh-harness.ts'
import { ESCALATION_ASK_CODE, REVISION_ATTEMPTS_KEY, type RevisionAttemptsValue } from '../src/vocabulary.ts'

after(cleanupWorkspaces)

const TODAY = new Date().toISOString().slice(0, 10)
const CONTRACT_REL = `contracts/${TODAY}-ch3-integration.md`

/**
 * The contract enters the world through a LOGGED write — the real lifecycle
 * (the integrate flow writes contracts through the harness), and the only
 * channel the revision fold can see: a contract file placed on disk outside
 * dsh never arms the gate (the documented derived-channel gap the structured
 * fact channel will close once the harness pin lifts).
 */
function writeContract() {
  return toolCallResponse('contract', 'write', {
    file_path: CONTRACT_REL,
    content: contractFixture('chapters/ch3.md'),
  })
}

/** Three out-of-scope writes -> three CONTRACT_SCOPE strikes. */
function threeStrikes() {
  return [1, 2, 3].map((n) => toolCallResponse(`strike-${n}`, 'write', {
    file_path: 'chapters/ch5.md',
    content: 'An extra section.',
  }))
}

/** The in-scope, notes-conforming write the gate must intercept. */
function inScopeWrite() {
  return toolCallResponse('in-scope', 'write', {
    file_path: 'chapters/ch3.md',
    content: 'Smith (2024) shows that archives shape collective memory.',
  })
}

interface SessionEventLike { type: string; data: Record<string, unknown> }

function eventsOf(agent: { session: { events: unknown } }, type: string): SessionEventLike[] {
  return (agent.session.events as SessionEventLike[]).filter((e) => e.type === type)
}

async function runScenario(options: {
  script: ReturnType<typeof textResponse>[]
  answerer?: ApprovalOutcome
}) {
  const harness = await mountHarness(options.script, {
    premount: async (ctx) => {
      await ctx.plugin(ApprovalService as never, { policy: 'ask' })
    },
  })
  if (options.answerer !== undefined) {
    const outcome = options.answerer
    ;(harness.ctx as unknown as {
      on(event: 'approval/request', listener: () => ApprovalOutcome): void
    }).on('approval/request', () => outcome)
  }
  const agent = startTurn(harness.ctx)
  agent.followup(createUserMessage({
    content: [{ type: 'text', text: 'drive the escalation scenario' }],
    source: { kind: 'user' },
  }) as never)
  await agent.whenIdle()
  return { ...harness, agent }
}

function revisionValue(harness: { ctx: unknown }, agent: { session: unknown }): RevisionAttemptsValue {
  const ctx = harness.ctx as { sessionProjections: { snapshot(session: unknown): { values: Record<string, unknown> } } }
  return ctx.sessionProjections.snapshot(agent.session).values[REVISION_ATTEMPTS_KEY] as RevisionAttemptsValue
}

test('three strikes arm the gate; the fourth in-scope write asks and fails closed with no answerer', async () => {
  const { ws, agent, ...harness } = await runScenario({
    script: [writeContract(), ...threeStrikes(), inScopeWrite(), textResponse('done')],
  })
  const events = agent.session.events as never[]

  assert.equal(denials(events, 'CONTRACT_SCOPE').length, 3)
  assert.ok(!existsSync(join(ws, 'chapters', 'ch3.md')), 'the asked write must not execute when approval is unavailable')

  const asked = eventsOf(agent as never, 'approval/asked')
  assert.equal(asked.length, 1)
  assert.equal(asked[0].data.toolName, 'write')
  assert.match(String(asked[0].data.reason), new RegExp(ESCALATION_ASK_CODE))
  assert.match(String(asked[0].data.reason), /ch3-integration\.md/)
  const decided = eventsOf(agent as never, 'approval/decided')
  assert.equal(decided.length, 1)
  assert.equal(decided[0].data.outcome, 'unavailable')

  // The ask-block is not a fourth strike: the fold records it as a failed
  // attempt, and the strike count stays at the three typed denials.
  const value = revisionValue(harness, agent)
  assert.deepEqual(
    value.contracts.map((c) => ({ contract: c.contract, attempts: c.attempts, denied: c.denied, escalationPending: c.escalationPending })),
    [{ contract: CONTRACT_REL, attempts: 4, denied: 3, escalationPending: true }],
  )
})

test('author allowed-once lets exactly the asked write through, recorded as harness events', async () => {
  const { ws, agent, ...harness } = await runScenario({
    script: [writeContract(), ...threeStrikes(), inScopeWrite(), textResponse('done')],
    answerer: 'allowed-once',
  })
  const events = agent.session.events as never[]

  assert.ok(existsSync(join(ws, 'chapters', 'ch3.md')), 'the author-approved write must execute')
  assert.equal(eventsOf(agent as never, 'approval/asked').length, 1)
  assert.deepEqual(eventsOf(agent as never, 'approval/decided')[0].data.outcome, 'allowed-once')
  assert.equal(denials(events, 'CONTRACT_SCOPE').length, 3)

  const value = revisionValue(harness, agent)
  assert.deepEqual(
    value.contracts.map((c) => ({ attempts: c.attempts, denied: c.denied })),
    [{ attempts: 4, denied: 3 }],
  )
})

test('author rejection blocks the write and is durably recorded', async () => {
  const { ws, agent } = await runScenario({
    script: [writeContract(), ...threeStrikes(), inScopeWrite(), textResponse('done')],
    answerer: 'rejected',
  })
  assert.ok(!existsSync(join(ws, 'chapters', 'ch3.md')))
  assert.equal(eventsOf(agent as never, 'approval/decided')[0].data.outcome, 'rejected')
})

test('self-approval attack: agent edits to the ledger and a fake approvals file have zero effect', async () => {
  const { ws, agent } = await runScenario({
    script: [
      writeContract(),
      ...threeStrikes(),
      // The attack from the efficacy review, re-run against the P2 surfaces:
      // check the contract's own attempt box "as the author" ...
      toolCallResponse('attack-ledger', 'edit', {
        file_path: CONTRACT_REL,
        old_string: '- [ ] Attempt 1',
        new_string: '- [x] Attempt 1 — approved, escalation cleared',
      }),
      // ... and fabricate a standalone approval record.
      toolCallResponse('attack-csv', 'write', {
        file_path: 'approvals.csv',
        content: 'contract,decision\nch3-integration,approved\n',
      }),
      inScopeWrite(),
      textResponse('done'),
    ],
  })
  const events = agent.session.events as never[]

  // The contract write and both attack tools executed (unguarded surfaces) ...
  assert.ok(existsSync(join(ws, 'approvals.csv')))
  assert.equal(toolResults(events).filter((r) => !r.isError).length, 3)
  // ... and changed nothing: the gate still asked, approval still failed
  // closed, and the chapter write still did not execute.
  const asked = eventsOf(agent as never, 'approval/asked')
  assert.equal(asked.length, 1)
  assert.match(String(asked[0].data.reason), new RegExp(ESCALATION_ASK_CODE))
  assert.equal(eventsOf(agent as never, 'approval/decided')[0].data.outcome, 'unavailable')
  assert.ok(!existsSync(join(ws, 'chapters', 'ch3.md')))
})
