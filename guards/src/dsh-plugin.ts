// dsh adapter for the P1 decision kernel. Compiles against structural
// interfaces only — no @deepseek-ai/dsh import — so upstream developer-preview
// churn cannot break this package's tests. Mounted for real in P1 session 2
// (awt-headless profile); until the live e2e gate is green these rules are
// documented as not yet enforced in any shipped runtime.

import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, relative, resolve, isAbsolute } from 'node:path'
import { lintNotes, hasErrors } from './notes-lint.ts'
import { decide, type RepoView, type ToolCall } from './decisions.ts'

/** Structural slice of the dsh Cordis context this plugin needs. */
export interface GuardHostContext {
  tools: {
    /** Monotonic guard seam: return a string to deny, undefined to pass. */
    guard(guard: (execution: { name: string; args: unknown }) => string | undefined): () => void
  }
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

export interface Config {
  projectRoot: string
}

/** Cordis plugin entry: registers the three chapter-write guards. */
export function apply(ctx: GuardHostContext, config: Config): void {
  const repo = fsRepoView(config.projectRoot)
  ctx.tools.guard((execution) => {
    const args = (execution.args ?? {}) as Record<string, unknown>
    const call: ToolCall = { tool: execution.name, args }
    const denial = decide(call, repo)
    return denial ? `${denial.code}: ${denial.message}` : undefined
  })
}
