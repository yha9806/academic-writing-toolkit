// Quote-fidelity graders used by the citation-fidelity audit: pure functions,
// no I/O, no model. Library only, no pass/fail claim of its own. Moved
// unchanged from the retired e1/graders.mjs on 2026-09-20; see
// docs/specs/2026-09-20-retire-dsh-line-design.md.

/** Collapse whitespace and normalize typographic quotes/dashes for matching. */
export function normalizeForMatch(text) {
  return text
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[–—]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Extract quoted spans (>= 4 words — shorter spans are idiom, not quotation)
 * with an adjacent page reference when one exists: "..." (p.12) / (Smith,
 * 2024, p. 12) / (p.12-13).
 */
export function extractQuotedSpans(text) {
  const spans = []
  const re = /["“]([^"“”]{10,}?)["”]/g
  for (const m of text.matchAll(re)) {
    const quote = m[1]
    if (quote.trim().split(/\s+/).length < 4) continue
    const tail = text.slice(m.index + m[0].length, m.index + m[0].length + 60)
    const page = tail.match(/\(\s*(?:[A-Za-z'’-]+,\s*\d{4},\s*)?pp?\.?\s*(\d+)/)
    spans.push({ quote, page: page ? Number(page[1]) : undefined })
  }
  return spans
}

/**
 * Quote fidelity: every quoted span must appear verbatim (whitespace- and
 * typography-normalized) in the reference text.
 */
export function gradeQuoteFidelity(spans, referenceText) {
  const reference = normalizeForMatch(referenceText)
  const misses = spans.filter((s) => !reference.includes(normalizeForMatch(s.quote)))
  return {
    quotes: spans.length,
    matched: spans.length - misses.length,
    misses: misses.map((s) => s.quote.slice(0, 80)),
  }
}

/** Split page-labelled text (`--- page N ---`) back into a per-page map. */
export function pagesFromLabeledText(text) {
  const pages = new Map()
  const re = /--- page (\d+) ---\n([\s\S]*?)(?=\n--- page \d+ ---|$)/g
  for (const m of text.matchAll(re)) pages.set(Number(m[1]), m[2])
  return pages
}
