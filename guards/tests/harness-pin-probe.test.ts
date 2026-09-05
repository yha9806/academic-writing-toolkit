// Harness-pin seam probes (P2 session 2 pin decision, 2026-08-16).
//
// DECISION RECORD (full rationale in docs/specs/2026-08-16-p2-projections-approvals.md,
// "Session 2 — harness pin decision"): AWT stays on the published npm
// packages at exact 0.1.0-rc.6. The structured-fact writer stays OFF, gated
// on the first PUBLISHED harness version whose `Session.append` honors the
// `ignorable: true` envelope marker. Upstream has that surface only as three
// commits reachable by SHA and referenced by NO branch (master + 9a20e17a
// "feat(session): expose the ignorable envelope marker on Session.append"
// -> f5be34d7 docs -> 8c690c7 test, authored 2026-08-14; verified via the
// GitHub compare API on 2026-08-16: master...8c690c7 ahead_by 3, and the
// repo's only branch is master). Pinning a build of an unreferenced commit
// or vendoring a from-source monorepo build was rejected; so was the
// model-visible user-message notice channel (governance facts must never
// enter model context — parent spec §7 "content-free").
//
// These probes are seam-probe tripwires: they characterize what the PINNED
// harness actually does, so a future pin bump that changes the behavior
// turns a probe red and forces the deferred work instead of letting it rot
// silently.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { SessionId } from '@deepseek-ai/dsh-session'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
import { mountAgentLoopTestDependencies } from '@deepseek-ai/dsh-agent-loop-testkit'
import JsonlSessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl'
import { GUARD_FACT_EVENT } from '../src/vocabulary.ts'

const roots: string[] = []
after(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }) })

async function mountBare(persistenceRoot?: string): Promise<Context> {
  const ctx = new Context()
  await mountAgentLoopTestDependencies(ctx)
  if (persistenceRoot !== undefined) await ctx.plugin(JsonlSessionPersistence, { root: persistenceRoot })
  await ctx.plugin(AgentLoop, { agents: [] })
  return ctx
}

test('TRIPWIRE: rc.6 Session.append silently drops the ignorable envelope marker', async () => {
  // @deepseek-ai/dsh-session@0.1.0-rc.6 lib/index.js append() destructures
  // exactly { sourceEventSeqs, surfaceOp } from its options — an
  // `ignorable: true` marker is discarded without error. When this probe
  // FAILS, the pinned harness has gained the ignorable-append surface
  // (upstream 9a20e17a): STOP, re-review the pin, enable the structured-fact
  // writer (task: P2s2 item "structured-fact 写入器"), and re-run the refold
  // gate before shipping anything else on the new pin.
  const ctx = await mountBare()
  const agent = ctx.agentLoop.create(SessionId('awt-pin-probe-append'), { provider: 'mock', model: 'mock' })
  const session = agent.session as unknown as {
    append: (type: string, data: unknown, opts?: object) => void
    events: ReadonlyArray<{ type: string; ignorable?: unknown }>
  }

  session.append(GUARD_FACT_EVENT, { kind: 'page-read', callId: 'probe', pages: 1 }, { ignorable: true })

  const envelope = session.events.at(-1)
  assert.equal(envelope?.type, GUARD_FACT_EVENT)
  assert.notEqual(
    envelope?.ignorable,
    true,
    'PIN TRIPWIRE FIRED: the pinned harness now honors { ignorable: true } on Session.append. ' +
    'Enable the structured-fact writer (P2 spec session 2) and re-run the refold gate; ' +
    'see the decision record at the top of this file.',
  )
  await ctx.fiber.dispose()
})

test('CHARACTERIZATION: an unmarked unknown event type poisons session reload on the pinned harness', async () => {
  // The reason the writer stays OFF: rc.6's persistence read path refuses a
  // log carrying an event type it does not know unless the envelope is
  // marked ignorable — and rc.6 gives a writer no way to mark it (probe
  // above). This probe pins the actual failure so the danger stays
  // observable instead of narrative. It is expected to KEEP passing after a
  // pin bump (unknown-and-unmarked must still refuse; that is upstream's
  // deliberate fail-closed default — a silently gutted resume would be the
  // safety failure).
  const persistenceRoot = mkdtempSync(join(tmpdir(), 'awt-pin-probe-store-'))
  roots.push(persistenceRoot)

  const first = await mountBare(persistenceRoot)
  const agent = first.agentLoop.create(SessionId('awt-pin-probe-reload'), { provider: 'mock', model: 'mock' })
  const session = agent.session as unknown as { append: (type: string, data: unknown) => void }
  session.append(GUARD_FACT_EVENT, { kind: 'page-read', callId: 'probe', pages: 1 })
  await first.sessions.flush(agent.session)
  await first.fiber.dispose()

  const second = await mountBare(persistenceRoot)
  await assert.rejects(
    () => second.sessionPersistence.load(SessionId('awt-pin-probe-reload')),
    (error: unknown) => {
      const message = error instanceof Error ? error.message : String(error)
      assert.match(
        message,
        /ignorable|unknown|refusing/i,
        `reload failed, but not with the unknown-event refusal this probe pins (got: ${message})`,
      )
      return true
    },
    'PIN CHARACTERIZATION BROKEN: the pinned harness reloaded a log carrying an unmarked ' +
    'unknown event type. Either the fail-closed default changed upstream (re-review the pin ' +
    'and this decision) or the probe no longer writes what it thinks it writes.',
  )
  await second.fiber.dispose()
})
