// dsh adapter for the AWT guard kernel and the P2 session-log projections.
// Compiles against structural interfaces only — no @deepseek-ai/dsh import —
// so upstream developer-preview churn cannot break this package's tests.
// Mounted for real by the live e2e (see e2e/): a profile patch row loads
// guards/dist/dsh-plugin.js with `inject: [tools]` and the kernel decisions
// run on the monotonic `ctx.tools.guard` seam of a real dsh process.
//
// rc.6 seam facts this adapter matches (verified against the installed
// @deepseek-ai/dsh* 0.1.0-rc.6 type declarations):
// - `ToolGuard = (execution: Readonly<ToolExecution>) => string | undefined`
// - `ToolExecution` carries the parsed call as `arguments` (frozen, lossless
//   JSON), NOT `args` — the earlier structural assumption. `callArgs()` reads
//   both so the adapter stays compatible with either field name.
// - `ToolExecution.agent?.session` is the live session whose log is the
//   durable source of truth; the page-budget guard reads the projection
//   snapshot of exactly that session.
// - `ctx.sessionProjections` (@deepseek-ai/dsh-session-projection, mounted
//   by dsh-base) registers `{key, schema, init, apply, view, stateVersion}`
//   units and serves synchronous, consistent `snapshot(session)` cuts. The
//   adapter registers the three P2 projections there; in assemblies without
//   the registry (minimal hosts) the guard falls back to a plugin-local
//   fold, clearly marked non-authoritative below.
// - `tools/result` is an emit event `(execution, result)` observed after the
//   authoritative outcome; it only drives the fallback counter.

import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs'
import { join, relative, resolve, isAbsolute } from 'node:path'
import { lintNotes, hasErrors } from './notes-lint.ts'
import {
  decide,
  decideExport,
  decidePdfRead,
  foldPdfRead,
  shouldAskEscalation,
  type PageBudgetConfig,
  type PageBudgetState,
  type RepoView,
  type ToolCall,
} from './decisions.ts'
import {
  GuardConfigError,
  PAGE_BUDGET_KEY,
  REVISION_ATTEMPTS_KEY,
  REVISION_ESCALATION_THRESHOLD,
  denialReason,
  escalationAskReason,
  type PageBudgetValue,
  type RevisionAttemptsValue,
} from './vocabulary.ts'
import {
  createIntegrationStatusProjection,
  createRevisionAttemptsProjection,
  pageBudgetProjection,
  parseContractSource,
  parseNotesSource,
  type ProjectionDefinitionLike,
} from './projections.ts'

/** One in-pipeline tool call, as this plugin needs to see it (structural). */
export interface GuardedExecution {
  name: string
  /** rc.6 field name for the parsed, frozen call arguments. */
  arguments?: unknown
  /** Legacy structural field name kept for compatibility. */
  args?: unknown
  /** The agent on whose behalf the call runs (rc.6: set by the agent loop). */
  agent?: { session?: unknown }
}

/** Structural slice of rc.6's `ctx.sessionProjections` registry. */
export interface ProjectionRegistryLike {
  register<S, V>(definition: ProjectionDefinitionLike<S, V>): () => void
  snapshot(session: unknown): { asOfSeq: number; values: Record<string, unknown> }
}

/** Structural slice of the dsh Cordis context this plugin needs. */
export interface GuardHostContext {
  tools: {
    /** Monotonic guard seam: return a string to deny, undefined to pass. */
    guard(guard: (execution: GuardedExecution) => string | undefined): () => void
  }
  /**
   * Cordis event subscription (optional in the structural slice).
   * 'tools/result' feeds the registry-less fallback counters; the
   * 'tools/pre-execute' waterfall carries the session-2 escalation ask
   * (return `{ kind: 'ask', reason }` or delegate with `next()`).
   */
  on?: {
    (
      event: 'tools/result',
      listener: (execution: GuardedExecution, result: { isError: boolean }) => void
    ): () => void
    (
      event: 'tools/pre-execute',
      listener: (execution: GuardedExecution, next: () => Promise<unknown>) => Promise<unknown>
    ): () => void
  }
  /** rc.6 projection registry, when the assembly mounts one (dsh-base does). */
  sessionProjections?: ProjectionRegistryLike
  /**
   * Cordis dependency gate (optional in the structural slice). Preferred
   * registration path: the callback runs once `sessionProjections` is
   * available, so load order against dsh-base cannot race.
   */
  inject?(deps: string[], callback: (ctx: GuardHostContext) => void): unknown
}

function callArgs(execution: GuardedExecution): Record<string, unknown> {
  const value = execution.args ?? execution.arguments
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {}
}

export function fsRepoView(projectRoot: string): RepoView {
  const root = resolve(projectRoot)
  return {
    relative(filePath: string) {
      const abs = isAbsolute(filePath) ? filePath : join(root, filePath)
      const rel = relative(root, abs)
      if (rel.startsWith('..')) return undefined
      return rel.split('\\').join('/')
    },
    readFile(rel: string) {
      const p = join(root, rel)
      return existsSync(p) ? readFileSync(p, 'utf8') : undefined
    },
    conformingSources() {
      const dir = join(root, 'literature', 'reading_notes')
      if (!existsSync(dir)) return []
      const out: Array<{ surname: string; year: string }> = []
      for (const name of readdirSync(dir)) {
        if (!name.endsWith('_NOTES.md')) continue
        const text = readFileSync(join(dir, name), 'utf8')
        if (hasErrors(lintNotes(text))) continue
        const source = parseNotesSource(text)
        if (source) out.push(source)
      }
      return out
    },
    activeContract() {
      const dir = join(root, 'contracts')
      if (!existsSync(dir)) return undefined
      for (const name of readdirSync(dir)) {
        if (!name.endsWith('.md')) continue
        const parsed = parseContractSource(readFileSync(join(dir, name), 'utf8'))
        if (!parsed.active) continue
        return { path: `contracts/${name}`, mayChange: parsed.mayChange, mustNotChange: parsed.mustNotChange }
      }
      return undefined
    },
    chapterFiles() {
      const out: string[] = []
      const walk = (rel: string) => {
        const dir = join(root, rel)
        if (!existsSync(dir) || !statSync(dir).isDirectory()) return
        for (const name of readdirSync(dir).sort()) {
          const childRel = `${rel}/${name}`
          if (statSync(join(root, childRel)).isDirectory()) walk(childRel)
          else if (name.endsWith('.md')) out.push(childRel)
        }
      }
      walk('chapters')
      return out
    },
    bibText() {
      const preferred = join(root, 'references.bib')
      if (existsSync(preferred)) return readFileSync(preferred, 'utf8')
      const first = readdirSync(root).filter((n) => n.endsWith('.bib')).sort()[0]
      return first === undefined ? undefined : readFileSync(join(root, first), 'utf8')
    },
  }
}

export const name = 'awt-guards'

export const inject = ['tools']

export interface Config {
  /** Thesis workspace root; defaults to the booted process working directory. */
  projectRoot?: string
  /** Page budgets for the profile's read_pdf tool (parent spec: 15/90). */
  pageBudget?: Partial<PageBudgetConfig>
}

const DEFAULT_PAGE_BUDGET: PageBudgetConfig = { perInvocation: 15, perSession: 90 }

/**
 * Inert-mount rejection (P2 spec item 3): a guard whose config enables
 * nothing — or whose workspace lacks the sources the guards consult — is a
 * profile-boot FAILURE with a typed GuardConfigError, never a quiet no-op
 * mount. Exported so tests and `awt verify` (session 2) can run the exact
 * boot check without mounting.
 */
export function validateConfig(config?: Config): { projectRoot: string; budget: PageBudgetConfig } {
  const budget: PageBudgetConfig = { ...DEFAULT_PAGE_BUDGET, ...config?.pageBudget }
  for (const [key, value] of [['perInvocation', budget.perInvocation], ['perSession', budget.perSession]] as const) {
    if (!Number.isSafeInteger(value) || value <= 0) {
      throw new GuardConfigError('PAGE_BUDGET_INERT', `pageBudget.${key} must be a positive safe integer, got ${String(value)}`)
    }
  }
  if (budget.perSession < budget.perInvocation) {
    throw new GuardConfigError(
      'PAGE_BUDGET_INERT',
      `pageBudget.perSession (${budget.perSession}) is below perInvocation (${budget.perInvocation}); no invocation could ever fill the session budget`
    )
  }
  const projectRoot = resolve(config?.projectRoot ?? process.cwd())
  const notesRoot = join(projectRoot, 'literature', 'reading_notes')
  if (!existsSync(notesRoot) || !statSync(notesRoot).isDirectory()) {
    throw new GuardConfigError(
      'NOTES_ROOT_MISSING',
      `notes root ${notesRoot} is not a directory; the notes-before-chapters guard would deny every cited write against an empty index. Create literature/reading_notes/ (awt init scaffolds it) or fix projectRoot`
    )
  }
  const contractsRoot = join(projectRoot, 'contracts')
  if (!existsSync(contractsRoot) || !statSync(contractsRoot).isDirectory()) {
    throw new GuardConfigError(
      'CONTRACTS_SOURCE_UNRESOLVABLE',
      `contracts source ${contractsRoot} is not a directory; the contract-scope guard could never observe an active contract. Create contracts/ (awt init scaffolds it) or fix projectRoot`
    )
  }
  return { projectRoot, budget }
}

/**
 * Cordis plugin entry: validates the mount (throws typed GuardConfigError
 * before any listener registers), registers the three P2 session-log
 * projections on `ctx.sessionProjections`, and installs the chapter-write +
 * page-budget guards on the monotonic guard seam. All decisions come from
 * the pure kernel (decisions.ts); all counters come from the log folds
 * (projections.ts); this file only adapts the seams.
 */
export function apply(ctx: GuardHostContext, config?: Config): void {
  const { projectRoot, budget } = validateConfig(config)
  const repo = fsRepoView(projectRoot)

  // P2: the page-budget counter (and its siblings) are session-log folds,
  // not plugin state. Registration prefers the dependency gate so load order
  // against dsh-base's session-projection row cannot race.
  const revisionAttemptsProjection = createRevisionAttemptsProjection(projectRoot)
  const integrationStatusProjection = createIntegrationStatusProjection(projectRoot)
  let registry: ProjectionRegistryLike | undefined
  const attach = (host: GuardHostContext): void => {
    if (host.sessionProjections === undefined) return
    registry = host.sessionProjections
    registry.register(pageBudgetProjection)
    registry.register(revisionAttemptsProjection)
    registry.register(integrationStatusProjection)
  }
  if (typeof ctx.inject === 'function') ctx.inject(['sessionProjections'], attach)
  else attach(ctx)

  // Registry-less fallback ONLY (minimal hosts without dsh-base): a plugin-
  // local, per-process counter — the P1 shape, kept so a degraded assembly
  // still fails closed rather than not counting at all. Never consulted when
  // the projection snapshot is available.
  let fallbackPages: PageBudgetState = { pagesRead: 0 }
  const pagesReadFor = (execution: GuardedExecution): number => {
    const session = execution.agent?.session
    if (registry !== undefined && session !== undefined) {
      const value = registry.snapshot(session).values[PAGE_BUDGET_KEY]
      if (typeof value === 'object' && value !== null && typeof (value as PageBudgetValue).pagesRead === 'number') {
        return (value as PageBudgetValue).pagesRead
      }
    }
    return fallbackPages.pagesRead
  }

  ctx.tools.guard((execution) => {
    const call: ToolCall = { tool: execution.name, args: callArgs(execution) }
    const denial =
      decide(call, repo) ??
      decidePdfRead(call, { pagesRead: pagesReadFor(execution) }, budget) ??
      decideExport(call, repo)
    return denial ? denialReason(denial.code, denial.message) : undefined
  })

  // Session-2 ask-gate (spec item 2): the 3-strike escalation returns `ask`
  // on the tools/pre-execute waterfall, so dsh-user-approval records the
  // immutable approval/asked + approval/decided pair and fails closed with
  // no answerer. The escalation state comes from the revision-attempts
  // session-log fold — never from files: the contract's own agent-writable
  // ledger is exactly the self-approval attack surface.
  const fallbackDenied = new Map<string, number>()
  const escalationFor = (execution: GuardedExecution): { contract: string; denied: number } | undefined => {
    const session = execution.agent?.session
    if (registry !== undefined && session !== undefined) {
      const value = registry.snapshot(session).values[REVISION_ATTEMPTS_KEY]
      if (typeof value === 'object' && value !== null && Array.isArray((value as RevisionAttemptsValue).contracts)) {
        const row = (value as RevisionAttemptsValue).contracts.find((c) => c.active && c.escalationPending)
        return row === undefined ? undefined : { contract: row.contract, denied: row.denied }
      }
      return undefined
    }
    // Registry-less fallback ONLY (minimal hosts): per-process error counts
    // keyed by the on-disk active contract. Over-counts untyped failures as
    // strikes — the conservative, ask-earlier direction — and is never
    // consulted when the projection snapshot is available.
    const contract = repo.activeContract()
    if (contract?.path === undefined) return undefined
    const denied = fallbackDenied.get(contract.path) ?? 0
    return denied >= REVISION_ESCALATION_THRESHOLD ? { contract: contract.path, denied } : undefined
  }
  ctx.on?.('tools/pre-execute', async (execution, next) => {
    const call: ToolCall = { tool: execution.name, args: callArgs(execution) }
    const escalation = shouldAskEscalation(call, repo, escalationFor(execution))
    if (escalation !== undefined) {
      return { kind: 'ask', reason: escalationAskReason(escalation.contract, escalation.denied) }
    }
    return next()
  })

  ctx.on?.('tools/result', (execution, result) => {
    const call: ToolCall = { tool: execution.name, args: callArgs(execution) }
    if (result.isError) {
      const rel = typeof call.args.file_path === 'string' ? repo.relative(call.args.file_path) : undefined
      if (rel !== undefined && rel.startsWith('chapters/') && (call.tool === 'write' || call.tool === 'edit')) {
        const contract = repo.activeContract()
        if (contract?.path !== undefined) {
          fallbackDenied.set(contract.path, (fallbackDenied.get(contract.path) ?? 0) + 1)
        }
      }
      return
    }
    fallbackPages = foldPdfRead(fallbackPages, call)
  })
}
