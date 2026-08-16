// The P2 refold gate, copied from the dsh-background-agents test shape
// (tests/integration.spec.ts "recovers ... after a parent-session reopen"):
// drive a real turn whose tool calls feed all three projections, flush the
// log, dispose the context (simulated crash), remount on the SAME
// persistence root, resume the session, and assert every projection value
// reconstructs from the durable log alone — no plugin state survives the
// crash, so equal values prove the folds are the authority.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import { SessionId } from '@deepseek-ai/dsh-session'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
import { mountAgentLoopTestDependencies } from '@deepseek-ai/dsh-agent-loop-testkit'
import JsonlSessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl'
import SessionProjectionRegistry from '@deepseek-ai/dsh-session-projection'
import * as guards from '../src/dsh-plugin.ts'
import {
  ScriptedAdapter,
  buildWorkspace,
  contractFixture,
  registerWorkspaceTools,
  textResponse,
  toolCallResponse,
} from './dsh-harness.ts'
import {
  INTEGRATION_STATUS_KEY,
  PAGE_BUDGET_KEY,
  REVISION_ATTEMPTS_KEY,
  type IntegrationStatusValue,
  type PageBudgetValue,
  type RevisionAttemptsValue,
} from '../src/vocabulary.ts'

const roots: string[] = []
after(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }) })

async function mount(root: string, ws: string, adapter: ScriptedAdapter): Promise<Context> {
  const ctx = new Context()
  await mountAgentLoopTestDependencies(ctx)
  await ctx.plugin(JsonlSessionPersistence, { root })
  await ctx.plugin(AgentLoop, { agents: [] })
  await ctx.plugin(SessionProjectionRegistry)
  await ctx.plugin(guards as never, { projectRoot: ws })
  registerWorkspaceTools(ctx, ws)
  ctx.llm.registerAdapter(['mock'], adapter)
  return ctx
}

test('refold after crash: flush -> dispose -> remount reconstructs every projection from the durable log alone', async () => {
  // Workspace starts with NO contract file: the contract enters the world
  // through a logged tool call, so the revision fold has a derived-channel
  // lifecycle to reconstruct.
  const ws = buildWorkspace()
  const persistenceRoot = mkdtempSync(join(tmpdir(), 'awt-refold-store-'))
  roots.push(ws, persistenceRoot)

  const adapter = new ScriptedAdapter([
    toolCallResponse('c1', 'write', {
      file_path: join('contracts', 'ch3-integration.md'),
      content: contractFixture('chapters/ch3.md'),
    }),
    toolCallResponse('c2', 'write', {
      file_path: join('chapters', 'ch3.md'),
      content: 'Smith (2024) shows that archives shape collective memory.',
    }),
    toolCallResponse('c3', 'read_pdf', {
      file_path: join('literature', 'smith2024.pdf'),
      first_page: 1,
      last_page: 10,
    }),
    textResponse('done'),
  ])
  const ctx = await mount(persistenceRoot, ws, adapter)
  const agent = ctx.agentLoop.create(SessionId('awt-refold'), { provider: 'mock', model: 'mock' })
  agent.followup(createUserMessage({
    content: [{ type: 'text', text: 'contract, write, read' }],
    source: { kind: 'user' },
  }) as never)
  await agent.whenIdle()

  // Pre-crash truth, straight from the live registry.
  const before = ctx.sessionProjections.snapshot(agent.session)
  const pageBefore = before.values[PAGE_BUDGET_KEY as never] as PageBudgetValue | undefined
  const revisionBefore = before.values[REVISION_ATTEMPTS_KEY as never] as RevisionAttemptsValue | undefined
  const integrationBefore = before.values[INTEGRATION_STATUS_KEY as never] as IntegrationStatusValue | undefined
  assert.equal(pageBefore?.pagesRead, 10)
  assert.deepEqual(revisionBefore?.contracts, [{
    contract: 'contracts/ch3-integration.md',
    active: true,
    attempts: 1,
    applied: 1,
    denied: 0,
    escalationPending: false,
  }])
  assert.deepEqual(integrationBefore?.sources, [{
    source: 'smith 2024',
    status: 'integrated',
    chapters: ['chapters/ch3.md'],
  }])

  // Flush the log before the simulated crash, then dispose everything.
  await ctx.sessions.flush(agent.session)
  await ctx.fiber.dispose()

  // Simulated restart on the same persistence root; fresh plugin instances,
  // fresh registry, zero in-memory state.
  const second = await mount(persistenceRoot, ws, new ScriptedAdapter([]))
  const resumed = (await second.agents.resume({
    resumeSessionId: SessionId('awt-refold'),
    agentOptions: { provider: 'mock', model: 'mock' },
  })).agent

  const afterSnapshot = second.sessionProjections.snapshot(resumed.session)
  assert.deepEqual(afterSnapshot.values[PAGE_BUDGET_KEY as never], pageBefore)
  assert.deepEqual(afterSnapshot.values[REVISION_ATTEMPTS_KEY as never], revisionBefore)
  assert.deepEqual(afterSnapshot.values[INTEGRATION_STATUS_KEY as never], integrationBefore)

  // And the durable log itself carries no custom AWT event: on rc.6 every
  // fact rides harness-known event types only (vocabulary.ts records why),
  // which is exactly what makes this reload possible.
  const reloaded = await second.sessionPersistence.load(SessionId('awt-refold'))
  assert.ok(reloaded.events.length > 0)
  assert.ok(reloaded.events.every((event) => event.type !== 'awt-guards/fact'))
  await second.fiber.dispose()
})
