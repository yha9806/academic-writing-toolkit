#!/usr/bin/env node
// Deterministic lint for the /note reading-notes data contract.
//
//   node .claude/skills/note/scripts/notes-lint.mjs [--json] <NOTES.md ...>
//
// Library and CLI. Exit 1 when any file has an error-severity issue, 2 when
// given no file (nothing linted is not a pass). The contract (SKILL.md beside
// this) is consumed by /integrate, /map and the citation-fidelity audit; this
// lint is the single source of truth for "does this file conform". It shipped
// inside the retired dsh guards package until 2026-09-20 and moved here
// unchanged (docs/specs/2026-09-20-retire-dsh-line-design.md).

import { readFileSync } from 'node:fs'
import { isAbsolute, resolve as resolvePath } from 'node:path'
import { fileURLToPath } from 'node:url'

export const STATUS_VALUES = ['reading', 'completed', 'integrated']
export const EVIDENCE_VALUES = ['full_text', 'abstract_only', 'metadata_only']
const CONNECTIONS_HEADER = /^\|\s*Note Point\s*\|\s*Chapter\s*\|\s*Section\s*\|\s*Connection Type\s*\|/

function headerValue(lines, field) {
  const prefix = `**${field}**:`
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith(prefix)) {
      return { line: i + 1, value: lines[i].slice(prefix.length).trim() }
    }
  }
  return undefined
}

/** @returns {Array<{line: number, code: string, severity: 'error'|'warning', message: string}>} */
export function lintNotes(content) {
  const issues = []
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
  } else if (!STATUS_VALUES.includes(status.value)) {
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
  } else if (!EVIDENCE_VALUES.includes(evidence.value)) {
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

export function hasErrors(issues) {
  return issues.some((i) => i.severity === 'error')
}

const invokedAsCli = process.argv[1] !== undefined && resolvePath(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsCli) {
  const args = process.argv.slice(2)
  if (args.includes('--help') || args.includes('-h')) {
    console.log('usage: node notes-lint.mjs [--json] <NOTES.md ...>\nexit 0 conforming, 1 error-severity issues, 2 nothing linted')
    process.exit(0)
  }
  const json = args.includes('--json')
  const files = args.filter((a) => a !== '--json')
  if (files.length === 0) {
    console.error('usage: node notes-lint.mjs [--json] <NOTES.md ...>  (nothing linted is not a pass)')
    process.exit(2)
  }
  let failed = false
  const report = {}
  for (const file of files) {
    const target = isAbsolute(file) ? file : resolvePath(process.cwd(), file)
    let source
    try {
      source = readFileSync(target, 'utf8')
    } catch {
      // A stack trace cannot be told apart from a broken install by the
      // person who mistyped a path.
      console.error(`notes-lint: cannot read ${file}`)
      failed = true
      continue
    }
    const issues = lintNotes(source)
    report[file] = issues
    if (hasErrors(issues)) failed = true
    if (!json) {
      for (const i of issues) console.log(`${file}:${i.line} [${i.severity}] ${i.code}: ${i.message}`)
    }
  }
  if (json) console.log(JSON.stringify(report, null, 2))
  process.exit(failed ? 1 : 0)
}
