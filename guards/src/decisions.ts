// P1 decision kernel: pure, dependency-injected enforcement decisions for
// the three chapter-write guards (see docs/specs/2026-08-16-p1-guards-headless.md).
// No dsh imports — the dsh adapter (dsh-plugin.ts) and any future harness
// adapter both call into this module.

export type DenialCode = 'NOTES_MISSING' | 'QUOTE_SPAN_MODIFIED' | 'CONTRACT_SCOPE'

export interface Denial {
  code: DenialCode
  message: string
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown>
}

/** Everything the kernel needs from the project, injected for testability. */
export interface RepoView {
  /** Project-root-relative normalisation; returns undefined for paths outside the project. */
  relative(filePath: string): string | undefined
  /** Current content of a project file, or undefined if absent. */
  readFile(rel: string): string | undefined
  /** first-author surname (lowercase) + year for every lint-conforming notes file. */
  conformingSources(): ReadonlyArray<{ surname: string; year: string }>
  /** Active contract scopes (contracts/*.md with an unchecked attempt box), if any. */
  activeContract(): { mayChange: string[]; mustNotChange: string[] } | undefined
}

const CHAPTER_PREFIX = 'chapters/'

function isChapterPath(rel: string): boolean {
  return rel.startsWith(CHAPTER_PREFIX)
}

function insertedText(call: ToolCall): string | undefined {
  if (call.tool === 'write') return typeof call.args.content === 'string' ? call.args.content : undefined
  if (call.tool === 'edit') return typeof call.args.new_string === 'string' ? call.args.new_string : undefined
  return undefined
}

function targetPath(call: ToolCall): string | undefined {
  return typeof call.args.file_path === 'string' ? call.args.file_path : undefined
}

// --- NOTES_MISSING -----------------------------------------------------------
// Conservative author-year extraction: false positives block real writing, so
// only unambiguous forms match; a missed citation fails open per citation.

const PAREN_CITATION = /\(([A-Z][A-Za-z'’-]+)(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’-]+)?,?\s+(\d{4})[a-z]?(?:,\s*p{1,2}\.?\s*[\d,\s–-]+)?\)/g
const NARRATIVE_CITATION = /\b([A-Z][A-Za-z'’-]+)\s+\((\d{4})[a-z]?\)/g

export function extractCitations(text: string): Array<{ surname: string; year: string }> {
  const found = new Map<string, { surname: string; year: string }>()
  for (const re of [PAREN_CITATION, NARRATIVE_CITATION]) {
    for (const m of text.matchAll(re)) {
      const surname = m[1].toLowerCase()
      const year = m[2]
      found.set(`${surname}|${year}`, { surname, year })
    }
  }
  return [...found.values()]
}

export function decideNotesBeforeChapters(call: ToolCall, repo: RepoView): Denial | undefined {
  const raw = targetPath(call)
  if (!raw) return undefined
  const rel = repo.relative(raw)
  if (!rel || !isChapterPath(rel)) return undefined
  const text = insertedText(call)
  if (!text) return undefined
  const cited = extractCitations(text)
  if (cited.length === 0) return undefined
  const index = new Set(repo.conformingSources().map((s) => `${s.surname}|${s.year}`))
  const missing = cited.filter((c) => !index.has(`${c.surname}|${c.year}`))
  if (missing.length === 0) return undefined
  const list = missing.map((c) => `${c.surname} ${c.year}`).join(', ')
  return {
    code: 'NOTES_MISSING',
    message: `chapter edit cites sources with no conforming reading notes: ${list}. Create/complete the notes file (and pass the notes lint) before citing.`,
  }
}

// --- QUOTE_SPAN_MODIFIED -----------------------------------------------------

const QUOTE_SPANS = /"([^"\n]{4,500})"|“([^”\n]{4,500})”/g

export function extractQuoteSpans(text: string): string[] {
  const spans: string[] = []
  for (const m of text.matchAll(QUOTE_SPANS)) spans.push(m[1] ?? m[2])
  return spans
}

function applyEdit(previous: string, call: ToolCall): string | undefined {
  if (call.tool === 'write') return typeof call.args.content === 'string' ? call.args.content : undefined
  if (call.tool !== 'edit') return undefined
  const oldStr = call.args.old_string
  const newStr = call.args.new_string
  if (typeof oldStr !== 'string' || typeof newStr !== 'string') return undefined
  if (call.args.replace_all === true) return previous.split(oldStr).join(newStr)
  return previous.replace(oldStr, newStr)
}

export function decideQuoteIntegrity(call: ToolCall, repo: RepoView): Denial | undefined {
  const raw = targetPath(call)
  if (!raw) return undefined
  const rel = repo.relative(raw)
  if (!rel || !isChapterPath(rel)) return undefined
  const previous = repo.readFile(rel)
  if (previous === undefined) return undefined
  const next = applyEdit(previous, call)
  if (next === undefined) return undefined
  // Set comparison: a span that vanished while a new span appeared means
  // quoted text was altered in place (deny). Spans that only vanish are a
  // visible deletion (allow); spans that only appear are new quotes (allow).
  const prevSpans = new Set(extractQuoteSpans(previous))
  const nextSpans = new Set(extractQuoteSpans(next))
  const vanished = [...prevSpans].filter((s) => !nextSpans.has(s))
  const appeared = [...nextSpans].filter((s) => !prevSpans.has(s))
  if (vanished.length > 0 && appeared.length > 0) {
    return {
      code: 'QUOTE_SPAN_MODIFIED',
      message: `edit alters text inside a quotation span ("${vanished[0].slice(0, 60)}…"). Quoted text is immutable; delete the span visibly or leave it byte-identical (adding a new quote and changing an existing one in a single edit is also refused — split the edit).`,
    }
  }
  return undefined
}

// --- CONTRACT_SCOPE ----------------------------------------------------------

function underAny(rel: string, prefixes: string[]): boolean {
  return prefixes.some((p) => {
    const norm = p.replace(/^\.\//, '').replace(/\/+$/, '')
    return norm.length > 0 && (rel === norm || rel.startsWith(norm + '/') || rel.startsWith(norm))
  })
}

export function decideContractScope(call: ToolCall, repo: RepoView): Denial | undefined {
  const raw = targetPath(call)
  if (!raw) return undefined
  const rel = repo.relative(raw)
  if (!rel || !isChapterPath(rel)) return undefined
  if (call.tool !== 'write' && call.tool !== 'edit') return undefined
  const contract = repo.activeContract()
  if (!contract) return undefined
  if (underAny(rel, contract.mustNotChange)) {
    return { code: 'CONTRACT_SCOPE', message: `"${rel}" is listed under "Must not change" in the active edit contract.` }
  }
  if (contract.mayChange.length > 0 && !underAny(rel, contract.mayChange)) {
    return { code: 'CONTRACT_SCOPE', message: `"${rel}" is outside the active edit contract's "May change" scope.` }
  }
  return undefined
}

// --- combined ---------------------------------------------------------------

export function decide(call: ToolCall, repo: RepoView): Denial | undefined {
  return (
    decideContractScope(call, repo) ??
    decideQuoteIntegrity(call, repo) ??
    decideNotesBeforeChapters(call, repo)
  )
}

// --- PAGE BUDGETS (P1 session 2) ---------------------------------------------
// The awt profile's PDF ingestion tool is `read_pdf` (pdftotext-backed;
// args: file_path, first_page, last_page). These decisions enforce the
// per-invocation and per-session budgets; the session counter is plugin
// state in P1 and becomes a session-log fold in P2.

export type PageDenialCode = 'PAGE_RANGE_EXCEEDED' | 'PAGE_BUDGET_EXCEEDED'

export interface PageDenial {
  code: PageDenialCode
  message: string
}

export interface PageBudgetConfig {
  perInvocation: number // parent spec: 15
  perSession: number // parent spec: 90
}

export interface PageBudgetState {
  pagesRead: number
}

export function requestedPages(call: ToolCall): number | undefined {
  if (call.tool !== 'read_pdf') return undefined
  const first = call.args.first_page
  const last = call.args.last_page
  if (typeof first !== 'number' || typeof last !== 'number' || last < first) return undefined
  return last - first + 1
}

export function decidePdfRead(
  call: ToolCall,
  state: PageBudgetState,
  config: PageBudgetConfig
): PageDenial | undefined {
  const pages = requestedPages(call)
  if (pages === undefined) return undefined
  if (pages > config.perInvocation) {
    return {
      code: 'PAGE_RANGE_EXCEEDED',
      message: `requested ${pages} pages; the per-invocation limit is ${config.perInvocation}. Split the range.`,
    }
  }
  if (state.pagesRead + pages > config.perSession) {
    return {
      code: 'PAGE_BUDGET_EXCEEDED',
      message: `session has read ${state.pagesRead} pages; ${pages} more would exceed the ${config.perSession}-page budget. Start a new session.`,
    }
  }
  return undefined
}

/** Fold a completed read into the session counter (call after the tool ran). */
export function foldPdfRead(state: PageBudgetState, call: ToolCall): PageBudgetState {
  const pages = requestedPages(call)
  return pages === undefined ? state : { pagesRead: state.pagesRead + pages }
}
