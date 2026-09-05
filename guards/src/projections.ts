// Session-log projections replacing plugin state (P2 spec item 1, eco
// adoption #3 — dsh-background-agents' ProjectionDefinition discipline).
//
// Each unit matches the rc.6 registration contract EXACTLY as declared by
// @deepseek-ai/dsh-session-projection@0.1.0-rc.6 (lib/types/index.d.ts):
// `{ key, schema, init, apply, view, stateVersion }`, all three functions
// pure and synchronous, state plain JSON, `apply` returning the SAME
// reference for events it is not interested in (an unchanged reference
// produces zero downstream work). The shapes are declared structurally so
// the shipped package keeps zero dsh imports; the adapter (dsh-plugin.ts)
// registers them against the real `ctx.sessionProjections` registry (mounted
// by dsh-base), and the refold test proves every value reconstructs from the
// durable log alone after a simulated crash.
//
// Two channels, provenance-tagged (the background-agents migration recipe):
// - 'derived': facts folded from event types the rc.6 harness already knows
//   (`tool/call` + `tool/result` pairs), so state reconstructs from an rc.6
//   log containing no custom event anywhere. This is the ONLY live channel
//   on rc.6 — see GUARD_FACT_EVENT in vocabulary.ts for why the structured
//   writer cannot exist yet.
// - 'event': structured `awt-guards/fact` records. A row/attempt owned by
//   the event channel stops folding from the derived channel, so a log
//   carrying both channels never double-counts. A fact this build cannot
//   parse increments `unrecognizedFacts` in the wire value instead of being
//   silently skipped (a skipped fact under-counts a budget — the
//   session-log-version note's safety inversion).

import {
  ALL_DENIAL_CODES,
  GUARD_FACT_EVENT,
  INTEGRATION_STATUS_KEY,
  PAGE_BUDGET_KEY,
  REVISION_ATTEMPTS_KEY,
  REVISION_ESCALATION_THRESHOLD,
  integrationStatusSchema,
  pageBudgetSchema,
  parseDenialText,
  parseGuardFact,
  revisionAttemptsSchema,
  type IntegrationStatus,
  type IntegrationStatusValue,
  type PageBudgetValue,
  type RevisionAttemptsValue,
  type RevisionOutcome,
  type WireSchema,
} from './vocabulary.ts'
import { extractCitations, requestedPages } from './decisions.ts'

// --- structural rc.6 shapes -----------------------------------------------------

/** Structural slice of one committed rc.6 session event (dsh-session types.d.ts). */
export interface SessionEventLike {
  readonly type: string
  readonly seq: number
  readonly time: number
  readonly data: unknown
  readonly ignorable?: true
}

/**
 * Structural twin of rc.6 `ProjectionDefinition<K, S>` — same field names,
 * same contracts — with the key widened to string (this package cannot
 * declaration-merge `SessionProjectionMap` without importing dsh types).
 */
export interface ProjectionDefinitionLike<S, V> {
  readonly key: string
  readonly schema: WireSchema<V>
  init(): S
  apply(state: S, event: SessionEventLike): S
  view(state: S): V
  readonly stateVersion: number
}

/** Fold a whole event log through one unit — the test/CLI convenience recipe. */
export function foldProjection<S, V>(definition: ProjectionDefinitionLike<S, V>, events: readonly SessionEventLike[]): V {
  return definition.view(events.reduce((state, event) => definition.apply(state, event), definition.init()))
}

// --- shared fold helpers ----------------------------------------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * Project-root-relative normalisation as pure string logic (the fold must be
 * a function of the log plus fixed registration config only). Handles the
 * absolute paths the model emits in tool arguments and already-relative ones.
 */
export function relativeToRoot(projectRoot: string, filePath: string): string | undefined {
  const normalize = (p: string) => p.split('\\').join('/')
  const root = normalize(projectRoot).replace(/\/+$/, '')
  const p = normalize(filePath)
  const absolute = p.startsWith('/') || /^[A-Za-z]:\//.test(p)
  if (!absolute) return p.replace(/^\.\//, '')
  if (p === root) return ''
  if (p.startsWith(root + '/')) return p.slice(root.length + 1)
  // #34: a session may live in a different workspace than the process was
  // booted in (the web UI picks one per session). Folds only see events, so
  // an absolute path outside the boot root is relativized by structure —
  // from the last workspace marker — which is exact for the three trees the
  // folds read and identical to the root-based result inside the boot root.
  for (const marker of ['/chapters/', '/contracts/', '/literature/reading_notes/']) {
    const at = p.lastIndexOf(marker)
    if (at >= 0) return p.slice(at + 1)
  }
  return undefined
}

interface FoldToolCall {
  callId: string
  name: string
  args: Record<string, unknown>
}

/** Parse one rc.6 `tool/call` event (raw JSON `arguments` string) defensively. */
function toolCallOf(event: SessionEventLike): FoldToolCall | undefined {
  if (event.type !== 'tool/call') return undefined
  const data = event.data
  if (!isRecord(data) || typeof data.callId !== 'string' || typeof data.name !== 'string' || typeof data.arguments !== 'string') return undefined
  try {
    const args: unknown = JSON.parse(data.arguments)
    return isRecord(args) ? { callId: data.callId, name: data.name, args } : undefined
  } catch {
    return undefined
  }
}

interface FoldToolResult {
  callId: string
  isError: boolean
  text: string
}

/** Parse one rc.6 `tool/result` event (`data.message.content[0]` is the ToolResultBlock). */
function toolResultOf(event: SessionEventLike): FoldToolResult | undefined {
  if (event.type !== 'tool/result') return undefined
  const data = event.data
  if (!isRecord(data) || !isRecord(data.message) || !Array.isArray(data.message.content)) return undefined
  const block: unknown = data.message.content[0]
  if (!isRecord(block) || block.type !== 'tool-result' || typeof block.toolCallId !== 'string') return undefined
  const inner = Array.isArray(block.content) ? block.content : []
  const text = inner
    .filter((b): b is { type: 'text'; text: string } => isRecord(b) && b.type === 'text' && typeof b.text === 'string')
    .map((b) => b.text)
    .join('\n')
  return { callId: block.toolCallId, isError: block.isError === true, text }
}

function filePathOf(args: Record<string, unknown>): string | undefined {
  return typeof args.file_path === 'string' ? args.file_path : undefined
}

function insertedTextOf(name: string, args: Record<string, unknown>): string | undefined {
  if (name === 'write') return typeof args.content === 'string' ? args.content : undefined
  if (name === 'edit') return typeof args.new_string === 'string' ? args.new_string : undefined
  return undefined
}

type Channel = 'derived' | 'event'

// --- contract / notes source parsing (single authority, shared with the adapter) ---

export interface ContractSource {
  /** An unchecked `- [ ] Attempt` box marks the contract active (P1 rule). */
  active: boolean
  mayChange: string[]
  mustNotChange: string[]
}

/** Parse one contract file's content (the P1 fsRepoView rules, extracted). */
export function parseContractSource(text: string): ContractSource {
  const scope = (label: string) =>
    (text.match(new RegExp(`^- ${label}:\\s*(.+)$`, 'm'))?.[1] ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !s.startsWith('{'))
  return {
    active: /^- \[ \] Attempt/m.test(text),
    mayChange: scope('May change'),
    mustNotChange: scope('Must not change'),
  }
}

/** Parse a notes file's `**Source**:` line into the source key parts (P1 rules, extracted). */
export function parseNotesSource(text: string): { surname: string; year: string } | undefined {
  const source = text.match(/^\*\*Source\*\*:\s*(.+)$/m)?.[1] ?? ''
  const surname = source.match(/^([A-Za-z'’-]+)\s*,/)?.[1]?.toLowerCase()
  const year = source.match(/\((\d{4})[a-z]?\)/)?.[1] ?? source.match(/\b(\d{4})\b/)?.[1]
  return surname && year ? { surname, year } : undefined
}

// --- page-budget projection --------------------------------------------------------

interface PageRow {
  callId: string
  pages: number
  channel: Channel
}

interface PageBudgetState {
  /** read_pdf calls whose result has not arrived yet: callId -> requested pages. */
  pending: Record<string, number>
  /** Completed reads; only these consume budget. */
  reads: PageRow[]
  unrecognizedFacts: number
}

/**
 * Page-budget counter as a versioned fold of the session log. Replaces the
 * P1 plugin-local counter — and fixes its scope: the fold is per SESSION
 * (the parent-spec budget unit), where the P1 mutable counter was per
 * process. `stateVersion` bumps whenever fold semantics or serialized state
 * fields change, so persisted checkpoint rows from an older unit refold
 * instead of replaying into garbage.
 */
export const pageBudgetProjection: ProjectionDefinitionLike<PageBudgetState, PageBudgetValue> = {
  key: PAGE_BUDGET_KEY,
  schema: pageBudgetSchema,
  stateVersion: 1,
  init: () => ({ pending: {}, reads: [], unrecognizedFacts: 0 }),
  apply(state, event) {
    if (event.type === 'tool/call') {
      const call = toolCallOf(event)
      if (call === undefined || call.name !== 'read_pdf') return state
      const pages = requestedPages({ tool: call.name, args: call.args })
      if (pages === undefined) return state
      return { ...state, pending: { ...state.pending, [call.callId]: pages } }
    }
    if (event.type === 'tool/result') {
      const result = toolResultOf(event)
      if (result === undefined) return state
      const pages = state.pending[result.callId]
      if (pages === undefined) return state
      const pending = { ...state.pending }
      delete pending[result.callId]
      if (result.isError) return { ...state, pending }
      if (state.reads.some((r) => r.callId === result.callId)) return { ...state, pending }
      return { ...state, pending, reads: [...state.reads, { callId: result.callId, pages, channel: 'derived' }] }
    }
    if (event.type === GUARD_FACT_EVENT) {
      const fact = parseGuardFact(event.data)
      if (fact === undefined) return { ...state, unrecognizedFacts: state.unrecognizedFacts + 1 }
      if (fact.kind !== 'page-read') return state
      const existing = state.reads.find((r) => r.callId === fact.callId)
      if (existing?.channel === 'event') return state
      const pending = { ...state.pending }
      delete pending[fact.callId]
      return {
        ...state,
        pending,
        reads: [...state.reads.filter((r) => r.callId !== fact.callId), { callId: fact.callId, pages: fact.pages, channel: 'event' }],
      }
    }
    return state
  },
  view: (state) => ({
    pagesRead: state.reads.reduce((sum, r) => sum + r.pages, 0),
    reads: state.reads.map(({ callId, pages }) => ({ callId, pages })),
    unrecognizedFacts: state.unrecognizedFacts,
  }),
}

// --- per-contract revision-attempt projection ---------------------------------------

interface AttemptRow {
  callId?: string
  path: string
  outcome: RevisionOutcome
  channel: Channel
}

interface ContractRow {
  contract: string
  active: boolean
  mayChange: string[]
  mustNotChange: string[]
  /** Seq of the event that last (re)activated this contract; attribution tiebreaker. */
  activatedSeq: number
  attempts: AttemptRow[]
}

interface RevisionState {
  contracts: ContractRow[]
  /** Contract-file writes awaiting their result: callId -> parsed contract. */
  pendingContracts: Record<string, { contract: string } & ContractSource>
  /** Chapter writes awaiting their result: callId -> attributed contract + target. */
  pendingAttempts: Record<string, { contract: string; path: string }>
  unrecognizedFacts: number
}

function activeContractOf(state: RevisionState): ContractRow | undefined {
  let candidate: ContractRow | undefined
  for (const row of state.contracts) {
    if (!row.active) continue
    if (candidate === undefined || row.activatedSeq > candidate.activatedSeq) candidate = row
  }
  return candidate
}

/**
 * Per-contract revision-attempt counter. The derived channel attributes a
 * chapter write/edit to the contract that was active IN THE LOG at that seq:
 * contract lifecycle is folded from full `write` calls to `contracts/*.md`
 * (their complete content rides the tool/call arguments), and each chapter
 * write while one is active becomes an attempt whose outcome comes from the
 * paired tool/result (applied, typed denial, or failed).
 *
 * What this does not do (derived channel): a contract created or edited
 * OUTSIDE dsh tool calls never enters the log, and an `edit` to a contract
 * file cannot be reconstructed content-wise, so neither changes the folded
 * lifecycle. The structured 'revision-attempt' fact channel closes both gaps
 * in P2 session 2 (the adapter knows the on-disk active contract at decision
 * time).
 */
export function createRevisionAttemptsProjection(projectRoot: string): ProjectionDefinitionLike<RevisionState, RevisionAttemptsValue> {
  return {
    key: REVISION_ATTEMPTS_KEY,
    schema: revisionAttemptsSchema,
    stateVersion: 1,
    init: () => ({ contracts: [], pendingContracts: {}, pendingAttempts: {}, unrecognizedFacts: 0 }),
    apply(state, event) {
      if (event.type === 'tool/call') {
        const call = toolCallOf(event)
        if (call === undefined) return state
        const raw = filePathOf(call.args)
        if (raw === undefined) return state
        const rel = relativeToRoot(projectRoot, raw)
        if (rel === undefined) return state
        if (call.name === 'write' && rel.startsWith('contracts/') && rel.endsWith('.md') && typeof call.args.content === 'string') {
          return {
            ...state,
            pendingContracts: { ...state.pendingContracts, [call.callId]: { contract: rel, ...parseContractSource(call.args.content) } },
          }
        }
        if ((call.name === 'write' || call.name === 'edit') && rel.startsWith('chapters/')) {
          const active = activeContractOf(state)
          if (active === undefined) return state
          return {
            ...state,
            pendingAttempts: { ...state.pendingAttempts, [call.callId]: { contract: active.contract, path: rel } },
          }
        }
        return state
      }
      if (event.type === 'tool/result') {
        const result = toolResultOf(event)
        if (result === undefined) return state
        const pendingContract = state.pendingContracts[result.callId]
        if (pendingContract !== undefined) {
          const pendingContracts = { ...state.pendingContracts }
          delete pendingContracts[result.callId]
          if (result.isError) return { ...state, pendingContracts }
          const existing = state.contracts.find((c) => c.contract === pendingContract.contract)
          const row: ContractRow = {
            contract: pendingContract.contract,
            active: pendingContract.active,
            mayChange: pendingContract.mayChange,
            mustNotChange: pendingContract.mustNotChange,
            activatedSeq: pendingContract.active ? event.seq : existing?.activatedSeq ?? event.seq,
            attempts: existing?.attempts ?? [],
          }
          return {
            ...state,
            pendingContracts,
            contracts: existing === undefined
              ? [...state.contracts, row]
              : state.contracts.map((c) => (c.contract === row.contract ? row : c)),
          }
        }
        const pendingAttempt = state.pendingAttempts[result.callId]
        if (pendingAttempt !== undefined) {
          const pendingAttempts = { ...state.pendingAttempts }
          delete pendingAttempts[result.callId]
          const outcome: RevisionOutcome = result.isError
            ? parseDenialText(result.text)?.code ?? 'failed'
            : 'applied'
          const contracts = state.contracts.map((c) => {
            if (c.contract !== pendingAttempt.contract) return c
            if (c.attempts.some((a) => a.callId === result.callId && a.channel === 'event')) return c
            return {
              ...c,
              attempts: [...c.attempts, { callId: result.callId, path: pendingAttempt.path, outcome, channel: 'derived' as const }],
            }
          })
          return { ...state, pendingAttempts, contracts }
        }
        return state
      }
      if (event.type === GUARD_FACT_EVENT) {
        const fact = parseGuardFact(event.data)
        if (fact === undefined) return { ...state, unrecognizedFacts: state.unrecognizedFacts + 1 }
        if (fact.kind !== 'revision-attempt') return state
        const existing = state.contracts.find((c) => c.contract === fact.contract)
        const row: ContractRow = existing ?? {
          contract: fact.contract,
          active: false,
          mayChange: [],
          mustNotChange: [],
          activatedSeq: event.seq,
          attempts: [],
        }
        const attempt: AttemptRow = {
          ...(fact.callId !== undefined ? { callId: fact.callId } : {}),
          path: fact.path,
          outcome: fact.outcome,
          channel: 'event',
        }
        const collision = fact.callId === undefined ? undefined : row.attempts.find((a) => a.callId === fact.callId)
        if (collision?.channel === 'event') return state
        const attempts = collision === undefined
          ? [...row.attempts, attempt]
          : row.attempts.map((a) => (a.callId === fact.callId ? attempt : a))
        const next: ContractRow = { ...row, attempts }
        return {
          ...state,
          contracts: existing === undefined
            ? [...state.contracts, next]
            : state.contracts.map((c) => (c.contract === next.contract ? next : c)),
        }
      }
      return state
    },
    view: (state) => ({
      contracts: state.contracts
        .map((c) => {
          const denied = c.attempts.filter((a) => (ALL_DENIAL_CODES as readonly string[]).includes(a.outcome)).length
          return {
            contract: c.contract,
            active: c.active,
            attempts: c.attempts.length,
            applied: c.attempts.filter((a) => a.outcome === 'applied').length,
            denied,
            escalationPending: denied >= REVISION_ESCALATION_THRESHOLD,
          }
        })
        .sort((a, b) => (a.contract < b.contract ? -1 : a.contract > b.contract ? 1 : 0)),
      unrecognizedFacts: state.unrecognizedFacts,
    }),
  }
}

// --- notes integration-status projection ---------------------------------------------

const STATUS_RANK: Record<IntegrationStatus, number> = { noted: 0, planned: 1, integrated: 2 }

interface SourceRow {
  source: string
  status: IntegrationStatus
  chapters: string[]
  channel: Channel
}

type PendingIntegration =
  | { kind: 'noted'; source: string }
  | { kind: 'integrated'; sources: string[]; chapter: string }

interface IntegrationState {
  sources: SourceRow[]
  pending: Record<string, PendingIntegration>
  unrecognizedFacts: number
}

function upsertSource(rows: SourceRow[], source: string, mutate: (row: SourceRow) => SourceRow, base: SourceRow): SourceRow[] {
  const existing = rows.find((r) => r.source === source)
  if (existing === undefined) return [...rows, mutate(base)]
  return rows.map((r) => (r.source === source ? mutate(r) : r))
}

/**
 * Notes integration-status lifecycle (noted -> planned -> integrated) per
 * cited source. Derived channel: a successful write of a conforming-shaped
 * notes file marks its source 'noted'; a successful chapter write whose
 * inserted text cites a source marks it 'integrated' for that chapter. The
 * derived channel never downgrades a status; the 'integration-status' fact
 * channel (session 2, author-approved transitions) sets statuses verbatim
 * and owns its rows thereafter. 'planned' is unreachable from the derived
 * channel by design — planning is an approval, not a file write.
 */
export function createIntegrationStatusProjection(projectRoot: string): ProjectionDefinitionLike<IntegrationState, IntegrationStatusValue> {
  return {
    key: INTEGRATION_STATUS_KEY,
    schema: integrationStatusSchema,
    stateVersion: 1,
    init: () => ({ sources: [], pending: {}, unrecognizedFacts: 0 }),
    apply(state, event) {
      if (event.type === 'tool/call') {
        const call = toolCallOf(event)
        if (call === undefined) return state
        const raw = filePathOf(call.args)
        if (raw === undefined) return state
        const rel = relativeToRoot(projectRoot, raw)
        if (rel === undefined) return state
        if (call.name === 'write' && rel.startsWith('literature/reading_notes/') && rel.endsWith('_NOTES.md') && typeof call.args.content === 'string') {
          const parsed = parseNotesSource(call.args.content)
          if (parsed === undefined) return state
          return {
            ...state,
            pending: { ...state.pending, [call.callId]: { kind: 'noted', source: `${parsed.surname} ${parsed.year}` } },
          }
        }
        if ((call.name === 'write' || call.name === 'edit') && rel.startsWith('chapters/')) {
          const text = insertedTextOf(call.name, call.args)
          if (text === undefined) return state
          const cited = extractCitations(text)
          if (cited.length === 0) return state
          return {
            ...state,
            pending: {
              ...state.pending,
              [call.callId]: { kind: 'integrated', sources: cited.map((c) => `${c.surname} ${c.year}`), chapter: rel },
            },
          }
        }
        return state
      }
      if (event.type === 'tool/result') {
        const result = toolResultOf(event)
        if (result === undefined) return state
        const entry = state.pending[result.callId]
        if (entry === undefined) return state
        const pending = { ...state.pending }
        delete pending[result.callId]
        if (result.isError) return { ...state, pending }
        if (entry.kind === 'noted') {
          const sources = upsertSource(
            state.sources,
            entry.source,
            (row) => (row.channel === 'event' || STATUS_RANK[row.status] >= STATUS_RANK.noted ? row : { ...row, status: 'noted' }),
            { source: entry.source, status: 'noted', chapters: [], channel: 'derived' },
          )
          return { ...state, pending, sources }
        }
        let sources = state.sources
        for (const key of entry.sources) {
          sources = upsertSource(
            sources,
            key,
            (row) => {
              if (row.channel === 'event') return row
              const chapters = row.chapters.includes(entry.chapter) ? row.chapters : [...row.chapters, entry.chapter]
              return { ...row, status: 'integrated', chapters }
            },
            { source: key, status: 'integrated', chapters: [entry.chapter], channel: 'derived' },
          )
        }
        return { ...state, pending, sources }
      }
      if (event.type === GUARD_FACT_EVENT) {
        const fact = parseGuardFact(event.data)
        if (fact === undefined) return { ...state, unrecognizedFacts: state.unrecognizedFacts + 1 }
        if (fact.kind !== 'integration-status') return state
        const sources = upsertSource(
          state.sources,
          fact.source,
          (row) => ({
            ...row,
            status: fact.status,
            channel: 'event',
            chapters: fact.chapter !== undefined && !row.chapters.includes(fact.chapter)
              ? [...row.chapters, fact.chapter]
              : row.chapters,
          }),
          { source: fact.source, status: fact.status, chapters: fact.chapter !== undefined ? [fact.chapter] : [], channel: 'event' },
        )
        return { ...state, sources }
      }
      return state
    },
    view: (state) => ({
      sources: state.sources
        .map(({ source, status, chapters }) => ({ source, status, chapters: [...chapters] }))
        .sort((a, b) => (a.source < b.source ? -1 : a.source > b.source ? 1 : 0)),
      unrecognizedFacts: state.unrecognizedFacts,
    }),
  }
}
