// P2 spec item 3 (eco #4, dsh-turn-budget's validateConfig pattern): a guard
// whose config enables nothing must FAIL profile boot with a typed load
// error before any listener registers — a silently inert Enforced row is the
// exact failure mode invariant §10.3 forbids. One rejection test per guard
// source, plus proof that a valid workspace mounts and that the throw
// happens before registration.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { GuardConfigError } from '../src/vocabulary.ts'
import { apply, validateConfig, type GuardHostContext } from '../src/dsh-plugin.ts'

const roots: string[] = []
after(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }) })

function workspace(options: { notesRoot?: boolean; contracts?: boolean } = {}): string {
  const ws = mkdtempSync(join(tmpdir(), 'awt-inert-'))
  roots.push(ws)
  mkdirSync(join(ws, 'chapters'), { recursive: true })
  if (options.notesRoot !== false) mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  if (options.contracts !== false) mkdirSync(join(ws, 'contracts'), { recursive: true })
  return ws
}

/** Minimal structural host that counts registrations. */
function host(): { ctx: GuardHostContext; guards: number } {
  const counter = { ctx: undefined as unknown as GuardHostContext, guards: 0 }
  counter.ctx = {
    tools: {
      guard() {
        counter.guards += 1
        return () => undefined
      },
    },
  }
  return counter
}

function assertLoadError(fn: () => void, code: string, messagePattern: RegExp): void {
  assert.throws(fn, (error: unknown) => {
    assert.ok(error instanceof GuardConfigError, `expected GuardConfigError, got ${String(error)}`)
    assert.equal(error.code, code)
    assert.match(error.message, messagePattern)
    return true
  })
}

// --- page-budget guard: inert or invalid limits are load failures ------------------

test('PAGE_BUDGET_INERT: a zero per-invocation limit refuses to mount', () => {
  const h = host()
  assertLoadError(
    () => apply(h.ctx, { projectRoot: workspace(), pageBudget: { perInvocation: 0 } }),
    'PAGE_BUDGET_INERT',
    /perInvocation must be a positive safe integer/
  )
  assert.equal(h.guards, 0, 'no guard may register after a load failure')
})

test('PAGE_BUDGET_INERT: fractional and negative session limits refuse to mount', () => {
  assertLoadError(
    () => validateConfig({ projectRoot: workspace(), pageBudget: { perSession: 1.5 } }),
    'PAGE_BUDGET_INERT',
    /perSession must be a positive safe integer/
  )
  assertLoadError(
    () => validateConfig({ projectRoot: workspace(), pageBudget: { perSession: -90 } }),
    'PAGE_BUDGET_INERT',
    /perSession/
  )
})

test('PAGE_BUDGET_INERT: a session budget below the per-invocation limit is contradictory, not quietly clamped', () => {
  assertLoadError(
    () => validateConfig({ projectRoot: workspace(), pageBudget: { perInvocation: 15, perSession: 10 } }),
    'PAGE_BUDGET_INERT',
    /below perInvocation/
  )
})

// --- notes guard: absent notes root is a load failure ------------------------------

test('NOTES_ROOT_MISSING: a workspace without literature/reading_notes refuses to mount', () => {
  const h = host()
  assertLoadError(
    () => apply(h.ctx, { projectRoot: workspace({ notesRoot: false }) }),
    'NOTES_ROOT_MISSING',
    /literature[/\\]reading_notes/
  )
  assert.equal(h.guards, 0)
})

test('NOTES_ROOT_MISSING: a nonexistent projectRoot surfaces as the missing notes root', () => {
  assertLoadError(
    () => validateConfig({ projectRoot: join(tmpdir(), 'awt-does-not-exist-anywhere') }),
    'NOTES_ROOT_MISSING',
    /not a directory/
  )
})

// --- contract guard: unresolvable contracts source is a load failure ---------------

test('CONTRACTS_SOURCE_UNRESOLVABLE: a workspace without contracts/ refuses to mount', () => {
  const h = host()
  assertLoadError(
    () => apply(h.ctx, { projectRoot: workspace({ contracts: false }) }),
    'CONTRACTS_SOURCE_UNRESOLVABLE',
    /contracts/
  )
  assert.equal(h.guards, 0)
})

// --- positive control ----------------------------------------------------------------

test('a complete workspace with default budgets mounts and registers exactly one guard', () => {
  const h = host()
  apply(h.ctx, { projectRoot: workspace() })
  assert.equal(h.guards, 1)
  const resolved = validateConfig({ projectRoot: workspace() })
  assert.deepEqual(resolved.budget, { perInvocation: 15, perSession: 90 })
})
