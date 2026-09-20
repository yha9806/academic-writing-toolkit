// Citation extraction and notes-source parsing shared by the citation-fidelity
// audit. Library only: it makes no pass/fail claim. Extracted unchanged from
// the retired dsh guards (decisions.ts and projections.ts, P1 rules) on
// 2026-09-20; see docs/specs/2026-09-20-retire-dsh-line-design.md.
//
// Conservative author-year extraction: false positives block real writing, so
// only unambiguous forms match; a missed citation fails open per citation.

const PAREN_CITATION = /\(([A-Z][A-Za-z'’-]+)(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’-]+)?,?\s+(\d{4})[a-z]?(?:,\s*p{1,2}\.?\s*[\d,\s–-]+)?\)/g
const NARRATIVE_CITATION = /\b([A-Z][A-Za-z'’-]+)\s+\((\d{4})[a-z]?\)/g

/** @returns {Array<{surname: string, year: string}>} deduplicated, lower-cased surnames */
export function extractCitations(text) {
  const found = new Map()
  for (const re of [PAREN_CITATION, NARRATIVE_CITATION]) {
    for (const m of text.matchAll(re)) {
      const surname = m[1].toLowerCase()
      const year = m[2]
      found.set(`${surname}|${year}`, { surname, year })
    }
  }
  return [...found.values()]
}

/** Parse a notes file's `**Source**:` line into the source key parts. */
export function parseNotesSource(text) {
  const source = text.match(/^\*\*Source\*\*:\s*(.+)$/m)?.[1] ?? ''
  const surname = source.match(/^([A-Za-z'’-]+)\s*,/)?.[1]?.toLowerCase()
  const year = source.match(/\((\d{4})[a-z]?\)/)?.[1] ?? source.match(/\b(\d{4})\b/)?.[1]
  return surname && year ? { surname, year } : undefined
}
