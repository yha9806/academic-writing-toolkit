// Deterministic lint for the /note reading-notes data contract.
// Library + CLI. Exit 1 when any file has an error-severity issue.
//
// The contract (see .claude/skills/note/SKILL.md) is consumed by /integrate,
// /map, and the P1 notes-before-chapters guard; this lint is the single
// source of truth for "does this file conform".

import { readFileSync } from 'node:fs'

export type Severity = 'error' | 'warning'

export interface LintIssue {
  line: number
  code: string
  severity: Severity
  message: string
}

const STATUS_VALUES = ['reading', 'completed', 'integrated'] as const
const EVIDENCE_VALUES = ['full_text', 'abstract_only', 'metadata_only'] as const
const CONNECTIONS_HEADER = /^\|\s*Note Point\s*\|\s*Chapter\s*\|\s*Section\s*\|\s*Connection Type\s*\|/

function headerValue(lines: string[], field: string): { line: number; value: string } | undefined {
  const prefix = `**${field}**:`
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith(prefix)) {
      return { line: i + 1, value: lines[i].slice(prefix.length).trim() }
    }
  }
  return undefined
}

export function lintNotes(content: string): LintIssue[] {
  const issues: LintIssue[] = []
  const lines = content.split('\n')

  const firstText = lines.find((l) => l.trim().length > 0) ?? ''
  if (!firstText.startsWith('# Reading Notes:')) {
    issues.push({ line: 1, code: 'title-missing', severity: 'error', message: 'first line must be "# Reading Notes: {Author} -- {Title} ({Year})"' })
  }

  const source = headerValue(lines, 'Source')
  if (!source || source.value.length === 0) {
    issues.push({ line: source?.line ?? 1, code: 'source-missing', severity: 'error', message: 'missing or empty "**Source**:" line' })
  }

  const status = headerValue(lines, 'Status')
  if (!status) {
    issues.push({ line: 1, code: 'status-missing', severity: 'error', message: 'missing "**Status**:" line' })
  } else if (!(STATUS_VALUES as readonly string[]).includes(status.value)) {
    issues.push({ line: status.line, code: 'status-invalid', severity: 'error', message: `Status must be one of ${STATUS_VALUES.join(' | ')}, saw "${status.value}"` })
  }

  if (!headerValue(lines, 'Date read')) {
    issues.push({ line: 1, code: 'date-missing', severity: 'error', message: 'missing "**Date read**:" line' })
  }
  if (!headerValue(lines, 'Relevance')) {
    issues.push({ line: 1, code: 'relevance-missing', severity: 'error', message: 'missing "**Relevance**:" line' })
  }

  const evidence = headerValue(lines, 'Evidence status')
  if (!evidence) {
    issues.push({ line: 1, code: 'evidence-status-missing', severity: 'warning', message: 'missing "**Evidence status**:" line (full_text | abstract_only | metadata_only)' })
  } else if (!(EVIDENCE_VALUES as readonly string[]).includes(evidence.value)) {
    issues.push({ line: evidence.line, code: 'evidence-status-invalid', severity: 'error', message: `Evidence status must be one of ${EVIDENCE_VALUES.join(' | ')}, saw "${evidence.value}"` })
  }

  for (const section of ['## Key Arguments', '## Detailed Notes', '## Thesis Connections']) {
    if (!lines.some((l) => l.trim() === section)) {
      issues.push({ line: 1, code: 'section-missing', severity: 'error', message: `missing required section "${section}"` })
    }
  }

  const connIndex = lines.findIndex((l) => l.trim() === '## Thesis Connections')
  if (connIndex >= 0) {
    const window = lines.slice(connIndex + 1, connIndex + 6)
    if (!window.some((l) => CONNECTIONS_HEADER.test(l.trim()))) {
      issues.push({ line: connIndex + 1, code: 'connections-not-table', severity: 'error', message: 'Thesis Connections must be a table with header | Note Point | Chapter | Section | Connection Type |' })
    }
  }

  if (!lines.some((l) => l.trim().startsWith('*Last updated:'))) {
    issues.push({ line: lines.length, code: 'last-updated-missing', severity: 'error', message: 'missing "*Last updated: {YYYY-MM-DD}*" footer' })
  }

  return issues
}

export function hasErrors(issues: LintIssue[]): boolean {
  return issues.some((i) => i.severity === 'error')
}

const invokedAsCli = process.argv[1]?.endsWith('notes-lint.ts')
if (invokedAsCli) {
  const args = process.argv.slice(2)
  const json = args.includes('--json')
  const files = args.filter((a) => a !== '--json')
  if (files.length === 0) {
    console.error('usage: lint:notes [--json] <NOTES.md ...>')
    process.exit(2)
  }
  let failed = false
  const report: Record<string, LintIssue[]> = {}
  for (const file of files) {
    const issues = lintNotes(readFileSync(file, 'utf8'))
    report[file] = issues
    if (hasErrors(issues)) failed = true
    if (!json) {
      for (const i of issues) console.log(`${file}:${i.line} [${i.severity}] ${i.code}: ${i.message}`)
    }
  }
  if (json) console.log(JSON.stringify(report, null, 2))
  process.exit(failed ? 1 : 0)
}
