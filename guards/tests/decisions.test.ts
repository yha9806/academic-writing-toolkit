import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  decide,
  decideNotesBeforeChapters,
  decideQuoteIntegrity,
  decideContractScope,
  extractCitations,
  type RepoView,
} from '../src/decisions.ts'

function repo(overrides: Partial<RepoView> = {}): RepoView {
  return {
    relative: (p) => (p.startsWith('/') ? undefined : p),
    readFile: () => undefined,
    conformingSources: () => [{ surname: 'smith', year: '2024' }],
    activeContract: () => undefined,
    ...overrides,
  }
}

// --- NOTES_MISSING: red first ------------------------------------------------

test('chapter write citing a source without conforming notes is denied', () => {
  const d = decideNotesBeforeChapters(
    { tool: 'write', args: { file_path: 'chapters/ch3.md', content: 'As Jones (2021) argues, X holds.' } },
    repo()
  )
  assert.equal(d?.code, 'NOTES_MISSING')
  assert.match(d!.message, /jones 2021/)
})

test('chapter write citing a source WITH conforming notes passes', () => {
  const d = decideNotesBeforeChapters(
    { tool: 'write', args: { file_path: 'chapters/ch3.md', content: 'Smith (2024) shows Y. Also (Smith, 2024, p. 4).' } },
    repo()
  )
  assert.equal(d, undefined)
})

test('non-chapter writes and citation-free chapter writes pass', () => {
  const r = repo()
  assert.equal(decideNotesBeforeChapters({ tool: 'write', args: { file_path: 'notes/x.md', content: 'Jones (2021)' } }, r), undefined)
  assert.equal(decideNotesBeforeChapters({ tool: 'write', args: { file_path: 'chapters/ch1.md', content: 'No citations here.' } }, r), undefined)
})

test('citation extractor is conservative: legislation-style parentheticals do not match', () => {
  // (Act 1998)-style false positives plagued the retired citation auditor;
  // a blocking guard must not repeat them: lowercase-context matches are out.
  const found = extractCitations('under the Data Protection Act (1998) and wave 2 (2021) of the study')
  // "Act (1998)" matches the narrative form (capitalised token) — accepted
  // trade-off, documented in the P1 spec; "2 (2021)" must NOT match.
  assert.ok(!found.some((c) => c.surname === '2'))
})

// --- QUOTE_SPAN_MODIFIED: red first -----------------------------------------

const CHAPTER = 'Intro. As Smith puts it: "the workflow is the argument" (Smith, 2024, p. 4). End.'

test('edit that alters text inside a quotation span is denied', () => {
  const d = decideQuoteIntegrity(
    { tool: 'edit', args: { file_path: 'chapters/ch1.md', old_string: 'the workflow is the argument', new_string: 'the workflow is the whole argument' } },
    repo({ readFile: () => CHAPTER })
  )
  assert.equal(d?.code, 'QUOTE_SPAN_MODIFIED')
})

test('edit outside quotation spans passes; deleting the whole span passes', () => {
  const view = repo({ readFile: () => CHAPTER })
  assert.equal(
    decideQuoteIntegrity({ tool: 'edit', args: { file_path: 'chapters/ch1.md', old_string: 'Intro.', new_string: 'Introduction.' } }, view),
    undefined
  )
  assert.equal(
    decideQuoteIntegrity(
      { tool: 'edit', args: { file_path: 'chapters/ch1.md', old_string: 'As Smith puts it: "the workflow is the argument" (Smith, 2024, p. 4). ', new_string: '' } },
      view
    ),
    undefined
  )
})

// --- CONTRACT_SCOPE: red first -----------------------------------------------

const CONTRACT = { mayChange: ['chapters/ch3.md'], mustNotChange: ['chapters/ch4.md'] }

test('write outside the active contract May-change scope is denied', () => {
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch5.md', content: 'x' } },
    repo({ activeContract: () => CONTRACT })
  )
  assert.equal(d?.code, 'CONTRACT_SCOPE')
})

test('write to a Must-not-change path is denied even if also under May-change', () => {
  const d = decideContractScope(
    { tool: 'edit', args: { file_path: 'chapters/ch4.md', old_string: 'a', new_string: 'b' } },
    repo({ activeContract: () => ({ mayChange: ['chapters/'], mustNotChange: ['chapters/ch4.md'] }) })
  )
  assert.equal(d?.code, 'CONTRACT_SCOPE')
})

test('in-scope write passes; no active contract means no scope restriction', () => {
  assert.equal(
    decideContractScope({ tool: 'write', args: { file_path: 'chapters/ch3.md', content: 'x' } }, repo({ activeContract: () => CONTRACT })),
    undefined
  )
  assert.equal(
    decideContractScope({ tool: 'write', args: { file_path: 'chapters/ch9.md', content: 'x' } }, repo()),
    undefined
  )
})

// --- combined ordering --------------------------------------------------------

test('decide() reports contract scope before quote/notes issues', () => {
  const d = decide(
    { tool: 'write', args: { file_path: 'chapters/ch5.md', content: 'Jones (2021)' } },
    repo({ activeContract: () => CONTRACT })
  )
  assert.equal(d?.code, 'CONTRACT_SCOPE')
})
