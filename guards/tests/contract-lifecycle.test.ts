// Gate A item 5: yesterday's contract must not silently scope today's writes.
//
// A contract is "active" while it still carries an unchecked `- [ ] Attempt`
// line, and the skill's template ships three of them. So a contract is active
// from the moment it is written and stays active until the author ticks every
// box — which nothing told them to do. `activeContract()` then returned the
// FIRST active contract in readdir order, not the newest.
//
// The loop therefore worked on day one and denied on day two: chapter writes
// were scoped against a contract the author was not working under, and the
// denial said "the active edit contract" without naming which one, so there
// was nothing to act on.
//
// Two active contracts is not a state the guard can resolve. Picking one by
// directory order is a silent choice about what the author may edit, which is
// the kind of thing this product refuses rather than guesses.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { decideContractScope, type RepoView } from '../src/decisions.ts'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..', '..')

function repo(overrides: Partial<RepoView> = {}): RepoView {
  return {
    relative: (p) => (p.startsWith('/') ? undefined : p),
    readFile: () => undefined,
    conformingSources: () => [],
    activeContracts: () => [],
    chapterFiles: () => [],
    bibText: () => undefined,
    ...overrides,
  } as RepoView
}

const YESTERDAY = { path: 'contracts/2026-09-06-ch3.md', mayChange: ['chapters/ch3.md'], mustNotChange: [] }
const TODAY = { path: 'contracts/2026-09-07-ch5.md', mayChange: ['chapters/ch5.md'], mustNotChange: [] }

test('two active contracts are a typed refusal, not a silent choice between them', () => {
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch5.md', content: 'x' } },
    repo({ activeContracts: () => [YESTERDAY, TODAY] }),
  )
  assert.equal(d?.code, 'CONTRACT_AMBIGUOUS')
  // The author cannot retire one without being told which two.
  assert.match(d!.message, /2026-09-06-ch3\.md/)
  assert.match(d!.message, /2026-09-07-ch5\.md/)
})

test('the refusal comes before the scope decision, so it cannot be masked by an in-scope path', () => {
  // Writing inside YESTERDAY's scope would have passed silently while TODAY
  // was the contract the author believed they were working under.
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch3.md', content: 'x' } },
    repo({ activeContracts: () => [YESTERDAY, TODAY] }),
  )
  assert.equal(d?.code, 'CONTRACT_AMBIGUOUS')
})

test('one active contract scopes as before, and the denial names it', () => {
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch9.md', content: 'x' } },
    repo({ activeContracts: () => [TODAY] }),
  )
  assert.equal(d?.code, 'CONTRACT_SCOPE')
  assert.match(d!.message, /2026-09-07-ch5\.md/, 'the denial must say which contract decided')
})

test('retiring one leaves the other in charge', () => {
  assert.equal(
    decideContractScope(
      { tool: 'write', args: { file_path: 'chapters/ch5.md', content: 'x' } },
      repo({ activeContracts: () => [TODAY] }),
    ),
    undefined,
  )
})

test('no active contract is still no scope restriction', () => {
  assert.equal(
    decideContractScope(
      { tool: 'write', args: { file_path: 'chapters/anything.md', content: 'x' } },
      repo({ activeContracts: () => [] }),
    ),
    undefined,
  )
})

// Two tests here read `.claude/skills/edit-contract/SKILL.md` -- its shipped
// contract template and its wording about scope lines and ticking an attempt.
// That skill was retired, so they went with it. The contract lifecycle the
// guard enforces is unchanged and still covered by the tests below.
// --- scope lines the guard cannot read ---------------------------------------
// Found by the Gate A §7 acceptance run, not by any unit test: the skill's
// template invites prose in `- May change:` and the parser split on commas and
// matched literally, so a real contract produced
//   mayChange: ["the first prose sentence of chapters/ch1.md only (clarity"]
// which can never match a path. The unit tests all supplied well-formed path
// lists, which is exactly why they could not see it.
//
// Either extreme is wrong here. Treating an unreadable line as "no scope" lets
// a contract the author wrote be silently ignored; treating it as a non-empty
// list denies every chapter write including the one it was meant to allow.
// A scope the guard cannot read is a refusal that says so.

test('a scope line written as prose is refused, not silently matched against', () => {
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch1.md', content: 'x' } },
    repo({ activeContracts: () => [{
      path: 'contracts/prose.md',
      mayChange: ['the first prose sentence of chapters/ch1.md only (clarity'],
      mustNotChange: [],
      unreadableScope: ['May change: the first prose sentence of chapters/ch1.md only (clarity rewrite)'],
    }] }),
  )
  assert.equal(d?.code, 'CONTRACT_UNPARSABLE')
  assert.match(d!.message, /contracts\/prose\.md/)
  assert.match(d!.message, /May change/)
})

test('an unreadable scope does not become a licence to write anywhere', () => {
  // The failure this replaces: the contract named chapters/ch2.md under
  // "Must not change" and ch2 was written minutes later.
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch2.md', content: 'x' } },
    repo({ activeContracts: () => [{
      path: 'contracts/prose.md', mayChange: [], mustNotChange: [],
      unreadableScope: ['Must not change: the rest of chapters/ch1.md, quoted spans, and chapters/ch2.md'],
    }] }),
  )
  assert.equal(d?.code, 'CONTRACT_UNPARSABLE')
})

test('a clean path list is read as before', async () => {
  const { parseContractSource } = await import(
    pathToFileURL(join(PRODUCT_ROOT, 'guards', 'dist', 'projections.js')).href
  )
  const parsed = parseContractSource([
    '## Scope',
    '- May change: chapters/ch1.md, chapters/ch2.md',
    '- Must not change: chapters/ch3.md',
    '',
    '## Attempts',
    '- [ ] Attempt 1: pending',
  ].join('\n'))
  assert.deepEqual(parsed.mayChange, ['chapters/ch1.md', 'chapters/ch2.md'])
  assert.deepEqual(parsed.mustNotChange, ['chapters/ch3.md'])
  assert.deepEqual(parsed.unreadableScope, [])
})

test('the parser reports the prose it could not read rather than dropping it', async () => {
  const { parseContractSource } = await import(
    pathToFileURL(join(PRODUCT_ROOT, 'guards', 'dist', 'projections.js')).href
  )
  const parsed = parseContractSource([
    '## Scope',
    '- May change: the first prose sentence of chapters/ch1.md only (clarity rewrite)',
    '- Must not change: chapters/ch2.md',
  ].join('\n'))
  assert.equal(parsed.unreadableScope.length, 1)
  assert.match(parsed.unreadableScope[0], /May change/)
  // The readable line is still read; one bad line does not poison the other.
  assert.deepEqual(parsed.mustNotChange, ['chapters/ch2.md'])
})

test('the template placeholder is not treated as prose the author wrote', async () => {
  const { parseContractSource } = await import(
    pathToFileURL(join(PRODUCT_ROOT, 'guards', 'dist', 'projections.js')).href
  )
  const parsed = parseContractSource('- May change: {files you may touch}\n- Must not change: {everything else}')
  assert.deepEqual(parsed.unreadableScope, [], 'an unfilled template must not read as a broken contract')
})
