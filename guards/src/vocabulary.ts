// Single owner of the AWT guard vocabulary (P2 spec item 1, eco adoption #3):
// typed denial codes, the denial wire-line format the adapter emits and the
// projections parse back, the custom guard-fact event type with its fact
// shapes, the typed load-error codes for inert-mount rejection, and the wire
// schemas of the three session-log projections. Guard, reducers, and tests
// all import from here so every code and shape exists exactly once — the
// pattern proven by dsh-background-agents' src/vocabulary.ts (parsers return
// undefined for foreign producers; facts are validated before folding).
//
// Wire schemas are hand-rolled rather than zod, deliberately:
// - this package has zero runtime dependencies (P1's self-contained-tools
//   amendment) and the projections must not change that;
// - the rc.6 projection registry only ever calls `schema.parse(value)` at
//   runtime (verified in @deepseek-ai/dsh-session-projection@0.1.0-rc.6
//   lib/index.js: `registration.def.schema.parse(...)` is the sole use), so
//   any object with a throwing `parse` satisfies the seam structurally;
// - the official testkit (@deepseek-ai/dsh-agent-loop-testkit@0.1.0-rc.6)
//   pulls no zod, and upstream itself is split across zod majors (the rc.6
//   registry depends on zod ^4.4.3 while dsh-background-agents ships ^3.24)
//   — a version coupling avoided entirely by owning ~70 lines of validation.

// --- denial codes -------------------------------------------------------------

/** Chapter-write guard denial codes (P1 session 1). */
export const CHAPTER_DENIAL_CODES = ['NOTES_MISSING', 'QUOTE_SPAN_MODIFIED', 'CONTRACT_SCOPE'] as const
export type ChapterDenialCode = (typeof CHAPTER_DENIAL_CODES)[number]

/** read_pdf page-budget denial codes (P1 session 2). */
export const PAGE_DENIAL_CODES = ['PAGE_RANGE_EXCEEDED', 'PAGE_BUDGET_EXCEEDED'] as const
export type PageDenialCode = (typeof PAGE_DENIAL_CODES)[number]

/**
 * Every denial code a mounted AWT guard can emit today. ESCALATION_REQUIRED
 * (parent spec §7, 3-strike row) is deliberately NOT here: it is an `ask`
 * reason on the tools/pre-execute waterfall (see ESCALATION_ASK_CODE below),
 * not a guard denial — a rejected or unavailable ask surfaces as the
 * harness's own tool error, and the revision fold counts it as 'failed',
 * never as a strike.
 */
export const ALL_DENIAL_CODES = [...CHAPTER_DENIAL_CODES, ...PAGE_DENIAL_CODES] as const
export type AnyDenialCode = (typeof ALL_DENIAL_CODES)[number]

// --- escalation ask (P2 session 2) --------------------------------------------

/**
 * The 3-strike escalation returns `{ kind: 'ask' }` on the tools/pre-execute
 * waterfall, so dsh's approval seam produces the immutable audit pair
 * (`approval/asked` + `approval/decided`) — parent spec §8 "approvals are
 * harness events". With no answerer composed (headless, CI) the seam fails
 * closed to a denial; nothing about a grant persists past the one asked call
 * (`allowed-once` only).
 */
export const ESCALATION_ASK_CODE = 'ESCALATION_REQUIRED' as const

/** Ask reason: rule, observed count, limit, contract identity — never content. */
export function escalationAskReason(contract: string, denied: number): string {
  return `${ESCALATION_ASK_CODE}: contract '${contract}' has ${denied} typed-denial attempts (threshold ${REVISION_ESCALATION_THRESHOLD}); author approval is required for further chapter writes under this contract`
}

// --- denial wire format ---------------------------------------------------------

/**
 * The reason string the guard returns on the monotonic `ctx.tools.guard`
 * seam. dsh-tools rc.6 materializes it durably as a `tool/result` event whose
 * text is `Error: <reason>` with `isError: true` — the typed code is
 * greppable verbatim in the session store (P1 close-out discovery 3).
 */
export function denialReason(code: AnyDenialCode, message: string): string {
  return `${code}: ${message}`
}

export interface ParsedDenial {
  readonly code: AnyDenialCode
  readonly detail: string
}

/**
 * Parse a durable tool-result text (or a bare guard reason) back into its
 * typed denial. Returns undefined for anything this package did not produce,
 * so foreign tool failures never fold into AWT projections.
 */
export function parseDenialText(text: string): ParsedDenial | undefined {
  const m = /^(?:Error: )?([A-Z_]+): ([\s\S]*)$/.exec(text)
  if (!m) return undefined
  const code = m[1]
  if (!(ALL_DENIAL_CODES as readonly string[]).includes(code)) return undefined
  return { code: code as AnyDenialCode, detail: m[2] }
}

// --- typed load errors (inert-mount rejection) ---------------------------------

/**
 * Boot-failure codes (P2 spec item 3, eco adoption #4: a guard whose config
 * enables nothing is a load FAILURE, not a quiet pass — dsh-turn-budget's
 * validateConfig pattern). Thrown by `apply()` BEFORE any listener registers.
 */
export const LOAD_ERROR_CODES = ['PAGE_BUDGET_INERT', 'NOTES_ROOT_MISSING', 'CONTRACTS_SOURCE_UNRESOLVABLE'] as const
export type LoadErrorCode = (typeof LOAD_ERROR_CODES)[number]

/** Typed profile-boot failure; profile boot becomes a truth test of §10.3. */
export class GuardConfigError extends Error {
  readonly code: LoadErrorCode
  constructor(code: LoadErrorCode, detail: string) {
    super(`awt-guards: ${code}: ${detail}`)
    this.name = 'GuardConfigError'
    this.code = code
  }
}

// --- guard-fact events ----------------------------------------------------------

/**
 * The plugin-owned durable fact event type (structured channel of the P2
 * projections), mirroring dsh-background-agents' `background-agents/fact`.
 *
 * rc.6 REALITY (recorded, not worked around silently): no AWT adapter writes
 * this event yet. The published @deepseek-ai/dsh-session@0.1.0-rc.6
 * `Session.append` accepts only `sourceEventSeqs`/`surfaceOp` options — the
 * envelope's `ignorable: true` marker cannot be stamped by a writer — and the
 * rc.6 persistence read path REFUSES to reload a log carrying an unknown
 * event type without that marker (dsh-session-persistence lib:
 * "unknown to this harness and not marked ignorable; refusing to interpret
 * the log"). Appending this event on rc.6 would therefore poison session
 * resume. The projections fold it defensively (provenance 'event', deduped
 * against the derived channel) so the writer can switch on in P2 session 2
 * against a harness whose `append` accepts `{ ignorable: true }` — upstream
 * master has that surface (dsh-background-agents' pinned baseline
 * 8c690c7 uses `session.append(FACT_EVENT, data, { ignorable: true })`).
 */
export const GUARD_FACT_EVENT = 'awt-guards/fact' as const

/** Revision-attempt outcome: the write applied, was denied typed, or failed in the tool body. */
export type RevisionOutcome = 'applied' | 'failed' | AnyDenialCode

/** Notes-integration lifecycle states; 'planned' is only reachable via the structured channel. */
export const INTEGRATION_STATUSES = ['noted', 'planned', 'integrated'] as const
export type IntegrationStatus = (typeof INTEGRATION_STATUSES)[number]

/** One structured guard fact, discriminated on `kind`. */
export type GuardFact =
  | {
    /** One completed read_pdf call's page consumption. */
    readonly kind: 'page-read'
    readonly callId: string
    readonly pages: number
  }
  | {
    /** One chapter-write attempt under an active edit contract. */
    readonly kind: 'revision-attempt'
    /** Project-relative contract file path (e.g. contracts/2026-08-16-ch3.md). */
    readonly contract: string
    /** Project-relative chapter path the attempt targeted. */
    readonly path: string
    readonly outcome: RevisionOutcome
    /** Tool callId when the attempt rode a tool call (dedupe key vs the derived channel). */
    readonly callId?: string
  }
  | {
    /** One notes-integration lifecycle transition for a cited source. */
    readonly kind: 'integration-status'
    /** Source key: lowercase first-author surname + space + year (e.g. "smith 2024"). */
    readonly source: string
    readonly status: IntegrationStatus
    /** Project-relative chapter path, when the transition names one. */
    readonly chapter?: string
  }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isRevisionOutcome(value: unknown): value is RevisionOutcome {
  return value === 'applied' || value === 'failed' || (ALL_DENIAL_CODES as readonly string[]).includes(value as string)
}

/**
 * Runtime-guard one opaque fact payload as this plugin's structured fact.
 * Returns undefined for anything malformed or from a newer vocabulary — the
 * folds then count it in `unrecognizedFacts` (loud in the wire value) instead
 * of silently skipping it, because a silently skipped fact under-counts a
 * budget (the session-log-version note's safety inversion).
 */
export function parseGuardFact(value: unknown): GuardFact | undefined {
  if (!isRecord(value)) return undefined
  switch (value.kind) {
    case 'page-read':
      return typeof value.callId === 'string' && value.callId !== ''
        && typeof value.pages === 'number' && Number.isSafeInteger(value.pages) && value.pages > 0
        ? { kind: 'page-read', callId: value.callId, pages: value.pages }
        : undefined
    case 'revision-attempt':
      return typeof value.contract === 'string' && value.contract !== ''
        && typeof value.path === 'string' && isRevisionOutcome(value.outcome)
        && (value.callId === undefined || typeof value.callId === 'string')
        ? {
          kind: 'revision-attempt',
          contract: value.contract,
          path: value.path,
          outcome: value.outcome,
          ...(typeof value.callId === 'string' ? { callId: value.callId } : {}),
        }
        : undefined
    case 'integration-status':
      return typeof value.source === 'string' && value.source !== ''
        && (INTEGRATION_STATUSES as readonly string[]).includes(value.status as string)
        && (value.chapter === undefined || typeof value.chapter === 'string')
        ? {
          kind: 'integration-status',
          source: value.source,
          status: value.status as IntegrationStatus,
          ...(typeof value.chapter === 'string' ? { chapter: value.chapter } : {}),
        }
        : undefined
    default:
      return undefined
  }
}

// --- projection keys and wire values ---------------------------------------------

export const PAGE_BUDGET_KEY = 'awt/pageBudget' as const
export const REVISION_ATTEMPTS_KEY = 'awt/revisionAttempts' as const
export const INTEGRATION_STATUS_KEY = 'awt/integrationStatus' as const

/** The 3-strike threshold the revision projection reports against (parent spec §7). */
export const REVISION_ESCALATION_THRESHOLD = 3

/** Whole current page-budget value folded from one session log. */
export interface PageBudgetValue {
  /** Pages consumed by COMPLETED reads (a denied or failed read consumes nothing). */
  pagesRead: number
  reads: Array<{ callId: string; pages: number }>
  /** awt-guards/fact records this build could not parse — never silently skipped. */
  unrecognizedFacts: number
}

export interface RevisionContractValue {
  /** Project-relative contract file path. */
  contract: string
  /** Whether the folded contract content still carries an unchecked attempt box. */
  active: boolean
  attempts: number
  applied: number
  /** Attempts whose outcome was a typed AWT denial code. */
  denied: number
  /** denied >= REVISION_ESCALATION_THRESHOLD; the session-2 ask-gate input. */
  escalationPending: boolean
}

/** Whole current per-contract revision-attempt value folded from one session log. */
export interface RevisionAttemptsValue {
  contracts: RevisionContractValue[]
  unrecognizedFacts: number
}

export interface IntegrationSourceValue {
  /** Source key: lowercase surname + space + year. */
  source: string
  status: IntegrationStatus
  /** Project-relative chapter paths this source was integrated into. */
  chapters: string[]
}

/** Whole current notes-integration lifecycle value folded from one session log. */
export interface IntegrationStatusValue {
  sources: IntegrationSourceValue[]
  unrecognizedFacts: number
}

// --- wire schemas ---------------------------------------------------------------

/**
 * Structural stand-in for the registry's `ZodType`: rc.6 only calls
 * `schema.parse(view(state))`, so a throwing parse is the whole contract.
 */
export interface WireSchema<T> {
  parse(value: unknown): T
}

function reject(key: string, why: string): never {
  throw new TypeError(`awt-guards wire value ${key}: ${why}`)
}

function nonNegativeInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function parseCommon(key: string, value: unknown): Record<string, unknown> {
  if (!isRecord(value)) reject(key, 'not an object')
  if (!nonNegativeInt(value.unrecognizedFacts)) reject(key, 'unrecognizedFacts must be a non-negative integer')
  return value
}

export const pageBudgetSchema: WireSchema<PageBudgetValue> = {
  parse(value) {
    const v = parseCommon(PAGE_BUDGET_KEY, value)
    if (!nonNegativeInt(v.pagesRead)) reject(PAGE_BUDGET_KEY, 'pagesRead must be a non-negative integer')
    if (!Array.isArray(v.reads)) reject(PAGE_BUDGET_KEY, 'reads must be an array')
    for (const read of v.reads) {
      if (!isRecord(read) || typeof read.callId !== 'string' || !nonNegativeInt(read.pages)) {
        reject(PAGE_BUDGET_KEY, 'reads entries must be { callId: string, pages: int }')
      }
    }
    return value as PageBudgetValue
  },
}

export const revisionAttemptsSchema: WireSchema<RevisionAttemptsValue> = {
  parse(value) {
    const v = parseCommon(REVISION_ATTEMPTS_KEY, value)
    if (!Array.isArray(v.contracts)) reject(REVISION_ATTEMPTS_KEY, 'contracts must be an array')
    for (const row of v.contracts) {
      if (!isRecord(row) || typeof row.contract !== 'string' || typeof row.active !== 'boolean'
        || !nonNegativeInt(row.attempts) || !nonNegativeInt(row.applied) || !nonNegativeInt(row.denied)
        || typeof row.escalationPending !== 'boolean') {
        reject(REVISION_ATTEMPTS_KEY, 'contract rows must carry contract/active/attempts/applied/denied/escalationPending')
      }
    }
    return value as RevisionAttemptsValue
  },
}

export const integrationStatusSchema: WireSchema<IntegrationStatusValue> = {
  parse(value) {
    const v = parseCommon(INTEGRATION_STATUS_KEY, value)
    if (!Array.isArray(v.sources)) reject(INTEGRATION_STATUS_KEY, 'sources must be an array')
    for (const row of v.sources) {
      if (!isRecord(row) || typeof row.source !== 'string'
        || !(INTEGRATION_STATUSES as readonly string[]).includes(row.status as string)
        || !Array.isArray(row.chapters) || !row.chapters.every((c) => typeof c === 'string')) {
        reject(INTEGRATION_STATUS_KEY, 'source rows must carry source/status/chapters')
      }
    }
    return value as IntegrationStatusValue
  },
}
