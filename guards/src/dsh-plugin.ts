// dsh adapter for the P1 decision kernel. Compiles against structural
// interfaces only — no @deepseek-ai/dsh import — so upstream developer-preview
// churn cannot break this package's tests. Mounted for real in P1's closing
// live e2e (see e2e/): a profile patch row loads guards/dist/dsh-plugin.js
// with `inject: [tools]` and the kernel decisions run on the monotonic
// `ctx.tools.guard` seam of a real dsh process.
//
// rc.6 seam facts this adapter matches (verified against the installed
// @deepseek-ai/dsh-tools 0.1.0-rc.6 type declarations):
// - `ToolGuard = (execution: Readonly<ToolExecution>) => string | undefined`
// - `ToolExecution` carries the parsed call as `arguments` (frozen, lossless
//   JSON), NOT `args` — the earlier structural assumption. `callArgs()` reads
//   both so the adapter stays compatible with either field name.
// - `tools/result` is an emit event `(execution, result)` observed after the
//   authoritative outcome; the page-budget fold hooks it when the host
//   exposes `ctx.on` (optional, so a minimal guard host still works).

import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, relative, resolve, isAbsolute } from 'node:path'
import { lintNotes, hasErrors } from './notes-lint.ts'
import {
  decide,
  decidePdfRead,
  foldPdfRead,
  type PageBudgetConfig,
  type PageBudgetState,
  type RepoView,
  type ToolCall,
} from './decisions.ts'

/** One in-pipeline tool call, as this plugin needs to see it (structural). */
export interface GuardedExecution {
  name: string
  /** rc.6 field name for the parsed, frozen call arguments. */
  arguments?: unknown
  /** Legacy structural field name kept for compatibility. */
  args?: unknown
}

/** Structural slice of the dsh Cordis context this plugin needs. */
export interface GuardHostContext {
  tools: {
    /** Monotonic guard seam: return a string to deny, undefined to pass. */
    guard(guard: (execution: GuardedExecution) => string | undefined): () => void
  }
  /**
   * Cordis event subscription (optional in the structural slice). Used only
   * to fold completed `read_pdf` calls into the per-session page counter.
   */
  on?(
    event: 'tools/result',
    listener: (execution: GuardedExecution, result: { isError: boolean }) => void
  ): () => void
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
        const source = text.match(/^\*\*Source\*\*:\s*(.+)$/m)?.[1] ?? ''
        const surname = source.match(/^([A-Za-z'’-]+)\s*,/)?.[1]?.toLowerCase()
        const year = source.match(/\((\d{4})[a-z]?\)/)?.[1] ?? source.match(/\b(\d{4})\b/)?.[1]
        if (surname && year) out.push({ surname, year })
      }
      return out
    },
    activeContract() {
      const dir = join(root, 'contracts')
      if (!existsSync(dir)) return undefined
      for (const name of readdirSync(dir)) {
        if (!name.endsWith('.md')) continue
        const text = readFileSync(join(dir, name), 'utf8')
        if (!/^- \[ \] Attempt/m.test(text)) continue
        const scope = (label: string) =>
          (text.match(new RegExp(`^- ${label}:\\s*(.+)$`, 'm'))?.[1] ?? '')
            .split(',')
            .map((s) => s.trim())
            .filter((s) => s.length > 0 && !s.startsWith('{'))
        return { mayChange: scope('May change'), mustNotChange: scope('Must not change') }
      }
      return undefined
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
 * Cordis plugin entry: registers the three chapter-write guards plus the
 * read_pdf page budgets on the monotonic guard seam. All decisions come from
 * the pure kernel (decisions.ts); this file only adapts the seam.
 */
export function apply(ctx: GuardHostContext, config?: Config): void {
  const repo = fsRepoView(config?.projectRoot ?? process.cwd())
  const budget: PageBudgetConfig = { ...DEFAULT_PAGE_BUDGET, ...config?.pageBudget }
  let pages: PageBudgetState = { pagesRead: 0 }
  ctx.tools.guard((execution) => {
    const call: ToolCall = { tool: execution.name, args: callArgs(execution) }
    const denial = decide(call, repo) ?? decidePdfRead(call, pages, budget)
    return denial ? `${denial.code}: ${denial.message}` : undefined
  })
  // Fold only completed reads into the session counter; a denied or failed
  // call must not consume budget. P2 replaces this plugin state with a
  // session-log fold.
  ctx.on?.('tools/result', (execution, result) => {
    if (result.isError) return
    pages = foldPdfRead(pages, { tool: execution.name, args: callArgs(execution) })
  })
}
