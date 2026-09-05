#!/usr/bin/env node
// Sentence-level citation fidelity audit (P4 item 4).
//
//   node scripts/audit-citation-fidelity.mjs [--base-dir <workspace>] [--json]
//
// The gap this closes: every existing gate asks whether a source was read,
// verified, or cited — none asks whether the CITING SENTENCE matches the
// source. On a real manuscript, five of seven re-read citing sentences were
// wrong about their source and three were inverted. This audit checks what
// can be checked deterministically, per citing sentence under chapters/**:
//
//   quote-not-in-source   a quoted span (>= 4 words) that does not appear
//                         verbatim in the source's reading notes (or in the
//                         source PDF's text when one is present)
//   page-mismatch         the sentence cites a page for a quote and the notes
//                         (or PDF) place that quote on a different page
//   notes-missing         a citation with no lint-parseable notes file — the
//                         same condition the NOTES_MISSING guard enforces
//   low-overlap           EXPERIMENTAL: the sentence shares no content word
//                         with the source's notes. No false-positive rate has
//                         been measured on real notes; treat as a prompt to
//                         re-read, never as a finding.
//
// What it does NOT do, and says so in its own output: detect semantic
// inversion. A sentence that asserts the opposite of its source with the
// source's own vocabulary passes every check here. Catching that still
// requires reading the source; tests/citation-fidelity pin this limit.
//
// Graders are shared with the E1 instrument (e1/graders.mjs) so the audit
// and the instrument measure the same thing; citation extraction and notes
// parsing are the guards' own (guards/dist), so the audit and the
// enforcement agree on what a citation and a notes file are.

import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { join, resolve } from 'node:path'
import { extractQuotedSpans, gradeQuoteFidelity, normalizeForMatch, pagesFromLabeledText } from '../e1/graders.mjs'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..')
const GUARDS_DIST = join(PRODUCT_ROOT, 'guards', 'dist')
const SCHEMA_VERSION = 1

const args = process.argv.slice(2)
const emitJson = args.includes('--json')
const baseArg = args.includes('--base-dir') ? args[args.indexOf('--base-dir') + 1] : '.'
const base = resolve(baseArg)

function die(code, message, remedy) {
  console.error(`${code}: ${message}`)
  if (remedy) console.error(`  remedy: ${remedy}`)
  process.exit(2)
}

if (!existsSync(join(GUARDS_DIST, 'decisions.js'))) {
  die('FIDELITY_GUARDS_UNBUILT', 'guards/dist is missing; this audit reuses the guards\' citation extractor and notes parser', 'npm --prefix guards install && npm --prefix guards run build')
}
const { extractCitations } = await import(join(GUARDS_DIST, 'decisions.js'))
const { parseNotesSource } = await import(join(GUARDS_DIST, 'projections.js'))
const { lintNotes, hasErrors } = await import(join(GUARDS_DIST, 'notes-lint.js'))

// --- corpus ----------------------------------------------------------------------

function chapterFiles(root) {
  const out = []
  const walk = (rel) => {
    const dir = join(root, rel)
    if (!existsSync(dir)) return
    for (const name of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const childRel = `${rel}/${name.name}`
      if (name.isDirectory()) walk(childRel)
      else if (name.name.endsWith('.md')) out.push(childRel)
    }
  }
  walk('chapters')
  return out
}

/** surname|year -> { file, text, parseable, pages: Map<normalizedQuote, page> } */
function notesIndex(root) {
  const dir = join(root, 'literature', 'reading_notes')
  const index = new Map()
  if (!existsSync(dir)) return index
  for (const name of readdirSync(dir).sort()) {
    if (!name.endsWith('_NOTES.md') || name === '_template_NOTES.md') continue
    const text = readFileSync(join(dir, name), 'utf8')
    const source = parseNotesSource(text)
    if (!source) continue
    const pages = new Map()
    for (const span of extractQuotedSpans(text)) {
      if (span.page !== undefined) pages.set(normalizeForMatch(span.quote), span.page)
    }
    index.set(`${source.surname}|${source.year}`, {
      file: `literature/reading_notes/${name}`,
      text,
      parseable: !hasErrors(lintNotes(text)),
      pages,
    })
  }
  return index
}

/** Optional stronger reference: the source PDF's text, page-labeled like read_pdf output. */
function pdfText(root, surname, year) {
  const path = join(root, 'literature', `${surname}${year}.pdf`)
  if (!existsSync(path)) return undefined
  const res = spawnSync('pdftotext', ['-layout', path, '-'], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  if (res.status !== 0) return undefined
  const pages = res.stdout.split('\f').filter((p) => p.trim() !== '')
  return pages.map((p, i) => `--- page ${i + 1} ---\n${p.trimEnd()}`).join('\n\n')
}

/**
 * Sentence split that keeps quoted spans intact (never splits inside quotes)
 * and treats a terminator as a boundary only when whitespace and a
 * capital letter or an opening quote follow, or the text ends — so "p.12",
 * "et al.", "3.5" and "e.g." do not cut a citing sentence in half.
 */
function sentences(text) {
  const src = text.replace(/\r/g, '')
  const out = []
  let buf = ''
  let inQuote = false
  for (let i = 0; i < src.length; i++) {
    const ch = src[i]
    buf += ch
    if (ch === '"') inQuote = !inQuote
    else if (ch === '“') inQuote = true
    else if (ch === '”') inQuote = false
    if (!inQuote && /[.!?]/.test(ch)) {
      const rest = src.slice(i + 1)
      const boundary = rest.length === 0 || /^["”)]?\s+(?:[A-Z"“]|$)/.test(rest) || /^["”)]?\s*\n/.test(rest)
      if (boundary) {
        out.push(buf)
        buf = ''
      }
    } else if (ch === '\n' && buf.trim() === '') {
      buf = ''
    }
  }
  if (buf.trim()) out.push(buf)
  return out.map((s) => s.replace(/\s+/g, ' ').trim()).filter((s) => s.length > 0 && !s.startsWith('#'))
}

const STOP = new Set(['about', 'above', 'after', 'again', 'against', 'argue', 'argues', 'argued', 'because', 'before', 'being', 'between', 'could', 'during', 'every', 'found', 'further', 'however', 'might', 'other', 'shows', 'showed', 'since', 'their', 'there', 'these', 'those', 'through', 'under', 'which', 'while', 'where', 'would', 'should', 'study', 'paper', 'work', 'chapter', 'section', 'thesis'])
function contentWords(text) {
  return new Set(text.toLowerCase().match(/[a-z][a-z-]{4,}/g)?.filter((w) => !STOP.has(w)) ?? [])
}

// --- audit -----------------------------------------------------------------------

const notes = notesIndex(base)
const findings = []
let sentencesChecked = 0
let citationsChecked = 0

for (const rel of chapterFiles(base)) {
  const text = readFileSync(join(base, rel), 'utf8')
  for (const sentence of sentences(text)) {
    const cites = extractCitations(sentence)
    if (cites.length === 0) continue
    sentencesChecked += 1
    const spans = extractQuotedSpans(sentence)
    const words = contentWords(sentence)
    for (const c of cites) {
      citationsChecked += 1
      const key = `${c.surname}|${c.year}`
      const source = notes.get(key)
      const loc = `${rel}: ${sentence.slice(0, 90)}${sentence.length > 90 ? '…' : ''}`
      if (!source || !source.parseable) {
        findings.push({ kind: 'notes-missing', source: `${c.surname} ${c.year}`, location: loc,
          detail: source ? `${source.file} does not pass the notes lint` : 'no reading notes file for this source' })
        continue
      }
      const pdf = pdfText(base, c.surname, c.year)
      const reference = pdf ? `${source.text}\n${pdf}` : source.text
      if (spans.length > 0) {
        const graded = gradeQuoteFidelity(spans, reference)
        for (const miss of graded.misses) {
          findings.push({ kind: 'quote-not-in-source', source: `${c.surname} ${c.year}`, location: loc,
            detail: `"${miss}" is not verbatim in ${source.file}${pdf ? ' or the source PDF' : ''}` })
        }
        for (const span of spans) {
          if (span.page === undefined) continue
          const norm = normalizeForMatch(span.quote)
          let actual
          if (pdf) {
            for (const [page, body] of pagesFromLabeledText(pdf)) {
              if (normalizeForMatch(body).includes(norm)) { actual = page; break }
            }
          } else if (source.pages.has(norm)) {
            actual = source.pages.get(norm)
          }
          if (actual !== undefined && actual !== span.page) {
            findings.push({ kind: 'page-mismatch', source: `${c.surname} ${c.year}`, location: loc,
              detail: `cited p.${span.page}; ${pdf ? 'the PDF' : 'the notes'} place the quote on p.${actual}` })
          }
        }
      }
      // The cited surname is in every citing sentence and in every notes file;
      // it says nothing about fidelity, so it is not overlap.
      const candidates = [...words].filter((w) => !cites.some((x) => x.surname === w))
      const overlap = candidates.filter((w) => source.text.toLowerCase().includes(w))
      if (candidates.length >= 3 && overlap.length === 0) {
        findings.push({ kind: 'low-overlap', experimental: true, source: `${c.surname} ${c.year}`, location: loc,
          detail: 'no content word of this sentence appears in the source\'s notes — re-read before trusting either' })
      }
    }
  }
}

const hard = findings.filter((f) => f.kind === 'quote-not-in-source' || f.kind === 'page-mismatch')
const payload = {
  schema_version: SCHEMA_VERSION,
  base: base,
  sentences_checked: sentencesChecked,
  citations_checked: citationsChecked,
  findings,
  hard_finding_count: hard.length,
  limits: {
    semantic_inversion: 'NOT detected: a sentence asserting the opposite of its source in the source\'s own words passes every check here; that still requires reading the source',
    low_overlap: 'experimental — no false-positive rate has been measured on real notes; it never fails the audit',
    matching: 'quotes are matched verbatim after whitespace/typography normalisation; pages come from notes annotations or the source PDF when literature/<surname><year>.pdf exists',
  },
}

if (emitJson) {
  console.log(JSON.stringify(payload, null, 2))
} else {
  console.log(`citation fidelity: ${citationsChecked} citation(s) in ${sentencesChecked} citing sentence(s) under ${base}`)
  for (const kind of ['quote-not-in-source', 'page-mismatch', 'notes-missing', 'low-overlap']) {
    const group = findings.filter((f) => f.kind === kind)
    if (group.length === 0) continue
    console.log(`\n${kind}${kind === 'low-overlap' ? ' (experimental — not a finding)' : ''} (${group.length})`)
    for (const f of group) console.log(`  ${f.source} — ${f.location}\n    ${f.detail}`)
  }
  console.log(`\nNot checked: whether a citing sentence says the OPPOSITE of its source. ${payload.limits.semantic_inversion}.`)
}
process.exit(hard.length > 0 ? 1 : 0)
